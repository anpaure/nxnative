"""Execute SSBU's emitted latency stubs against synthetic worker queues.

The optional unicorn package runs the actual AArch64 words. No game files are
needed. This checks register/flag/stack ownership and queue state transitions;
real-game captures and gameplay remain necessary to establish latency/safety.
"""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

try:
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
    import unicorn.arm64_const as r
except ImportError:
    Uc = None

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('ssbu_latency_profile', TOOLS.parent / 'games/01006A800016E000/patches.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class Context:
 state=0x744c000
 def __init__(self):self.words=[];self.puts={}
 def here(self):return 0x100000+4*len(self.words)
 def emit(self,w):self.words.append(w)
 def site(self,*args):pass
 def put(self,site,words,why):self.puts[site]=words
c=Context();p._render_queue_1303(c)
def target(site):
 word=c.puts[site][0];v=word&0x3ffffff
 if v&(1<<25):v-=1<<26
 return site+v*4
post=target(0x374c3d4)
xreg=[getattr(r,'UC_ARM64_REG_X'+str(i)) for i in range(31)] if Uc else []
qreg=[getattr(r,'UC_ARM64_REG_Q'+str(i)) for i in range(32)] if Uc else []

@unittest.skipUnless(Uc, 'optional unicorn package is required for AArch64 execution')
class SsbuLatencyTests(unittest.TestCase):
    def test_post_scene_registers_and_worker_queues(self):
        checks = 0
        for level in range(4):
         for queue in ['mixed','empty','disabled']:
          uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
          for addr,size in [(0x100000,0x1000),(0x744c000,0x1000),(0x5333000,0x1000),(0x8000000,0x10000),(0x9000000,0x10000),(0x3ab000,0x1000),(0x3548000,0x5000),(0x374b000,0x5000)]:uc.mem_map(addr,size)
          uc.mem_write(0x100000,b''.join(struct.pack('<I',w) for w in c.words));uc.mem_write(c.state+0x3c,struct.pack('<I',level))
          uc.reg_write(r.UC_ARM64_REG_CPACR_EL1,3<<20)
          origx=[0x10000+i*0x101 for i in range(31)];origq=[(i+1)*int('01010101010101010101010101010101',16) for i in range(32)]
          for reg,v in zip(xreg,origx):uc.reg_write(reg,v)
          for reg,v in zip(qreg,origq):uc.reg_write(reg,v)
          uc.reg_write(r.UC_ARM64_REG_NZCV,0xa0000000);uc.reg_write(r.UC_ARM64_REG_SP,0x9008000)
          def u64(addr,v):uc.mem_write(addr,struct.pack('<Q',v))
          def u32(addr,v):uc.mem_write(addr,struct.pack('<I',v&0xffffffff))
          u64(0x5333120,0x8000900);u64(0x5333f58+16,0x8000800);u32(0x8000810,0x77)
          nodes=[0x8000100+i*0x100 for i in range(4)]
          u64(0x5333558,nodes[0] if queue=='mixed' else 0)
          if queue=='disabled':uc.mem_write(0x5333578,b'\1')
          for i,n in enumerate(nodes):
           u64(n+0x48,nodes[i+1] if i<3 else 0);uc.mem_write(n+0x70,bytes([0,2,1,0][i:i+1]));u32(n+0x68,10+i);u32(n+0x6c,-3-i);u64(n,0x8000700)
          u64(0x8000708,0x8003000)
          trace=[]
          def return_call():
           pc=uc.reg_read(r.UC_ARM64_REG_LR)
           for i in range(18):uc.reg_write(xreg[i],0xbad000+i)
           for i in list(range(8))+list(range(16,32)):uc.reg_write(qreg[i],0xbad000+i)
           uc.reg_write(r.UC_ARM64_REG_NZCV,0x60000000);uc.reg_write(r.UC_ARM64_REG_PC,pc)
          def hook(uc,addr,size,data):
           if addr==0x374c3d8:uc.emu_stop();return
           if addr==0x3ab590:
            assert uc.reg_read(xreg[0])==0x8000900;trace.append('models');return_call()
           elif addr==0x35493e0:
            args=[uc.reg_read(xreg[i]) for i in range(4)]
            if args[1]==0x374ec70:
             assert args[2:]==[0,0];trace.append('fighter');u32(args[0]+0x10,1);u32(args[0]+0x14,2)
            else:
             assert args[1]==0x35484b0 and args[0] in [nodes[0]+8,nodes[3]+8],args
             idx=nodes.index(args[0]-8);assert args[2:]==[10+idx,(-3-idx)&0xffffffff],args
             trace.append('node'+str(idx))
            return_call()
           elif addr==0x354c990:
            assert uc.reg_read(xreg[0])==0x77;assert uc.reg_read(xreg[1])==0x9008000-0x340+0x310
            trace.append('wait');return_call()
           elif addr==0x8003000:
            assert uc.reg_read(xreg[0])==nodes[1];trace.append('delete');return_call()
          uc.hook_add(UC_HOOK_CODE,hook);uc.emu_start(post,0,count=5000)
          assert uc.reg_read(r.UC_ARM64_REG_PC)==0x374c3d8,hex(uc.reg_read(r.UC_ARM64_REG_PC))
          for i,reg in enumerate(xreg):assert uc.reg_read(reg)==(0x5339000 if i==8 else origx[i]),(level,queue,'x'+str(i),hex(uc.reg_read(reg)))
          for i,reg in enumerate(qreg):assert uc.reg_read(reg)==origq[i],(level,queue,'q'+str(i))
          assert uc.reg_read(r.UC_ARM64_REG_NZCV)==0xa0000000
          assert uc.reg_read(r.UC_ARM64_REG_SP)==0x9008000
          expected=[] if level<3 else ['models','fighter','wait']+(['node0','delete','node3'] if queue=='mixed' else [])
          assert trace==expected,(level,queue,trace,expected)
          assert uc.mem_read(0x5333560,1)==b'\0'
          if level==3 and queue=='mixed':assert struct.unpack('<Q',uc.mem_read(nodes[0]+0x48,8))[0]==nodes[2]
          checks+=1
        self.assertEqual(checks, 12)

if __name__ == '__main__':
    unittest.main()
