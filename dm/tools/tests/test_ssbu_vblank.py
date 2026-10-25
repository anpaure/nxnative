"""Execute the retrace-accounting stubs without game files (optional Unicorn)."""
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
spec = importlib.util.spec_from_file_location('ssbu_vblank_profile', TOOLS.parent / 'games/01006A800016E000/patches.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)

class Context:
    def __init__(self): self.words = []; self.puts = {}
    def here(self): return 0x100000 + 4 * len(self.words)
    def emit(self, word): self.words.append(word)
    def site(self, *args): pass
    def put(self, site, words, why): self.puts[site] = words

@unittest.skipUnless(Uc, 'optional unicorn package is required for AArch64 execution')
class VblankTests(unittest.TestCase):
    def run_stubs(self, previous, current):
        ctx = Context(); profile._vblank_count_1303(ctx)
        uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for address, size in [(0x100000, 0x1000), (0x386f000, 0x1000), (0x8000000, 0x4000), (0x9000000, 0x10000)]: uc.mem_map(address, size)
        uc.mem_write(0x100000, b''.join(struct.pack('<I', w) for w in ctx.words))
        for site, words in ctx.puts.items(): uc.mem_write(site, b''.join(struct.pack('<I', w) for w in words))
        regs = [getattr(r, 'UC_ARM64_REG_X' + str(i)) for i in range(31)]
        values = [0x10000 + i * 0x101 for i in range(31)]
        values[19] = 0x8001000; values[21] = 0x8002000; values[23] = 0x8000000; values[25] = current
        for reg, value in zip(regs, values): uc.reg_write(reg, value)
        sp = 0x9008000
        uc.reg_write(r.UC_ARM64_REG_SP, sp); uc.reg_write(r.UC_ARM64_REG_NZCV, 0xa0000000)
        uc.mem_write(sp, b'\xa5' * 0x50)
        uc.mem_write(values[23] + 0x140, struct.pack('<Q', previous))
        uc.mem_write(values[19] + 0x88, struct.pack('<Q', 0x8003000))
        def stop(uc, address, size, data):
            if address in (0x386f8d4, 0x386f9b0): uc.emu_stop()
        uc.hook_add(UC_HOOK_CODE, stop)
        uc.emu_start(0x386f8d0, 0x386f8d4)
        self.assertEqual(uc.reg_read(regs[8]), previous)
        self.assertEqual(struct.unpack('<Q', uc.mem_read(sp + 8, 8))[0], previous)
        for i in range(31):
            if i != 8: self.assertEqual(uc.reg_read(regs[i]), values[i])
        # The unchanged helper has stored its selected current snapshot here.
        uc.mem_write(values[23] + 0x140, struct.pack('<Q', current))
        uc.emu_start(0x386f9ac, 0x386f9b0)
        missing = (current - previous - 1) & ((1 << 64) - 1)
        self.assertEqual(struct.unpack('<Q', uc.mem_read(values[21], 8))[0], missing)
        self.assertEqual(uc.reg_read(regs[0]), 0x8003000)
        for i in range(1, 31):
            if i != 8: self.assertEqual(uc.reg_read(regs[i]), values[i])
        self.assertEqual(uc.reg_read(r.UC_ARM64_REG_NZCV), 0xa0000000)
        self.assertEqual(uc.reg_read(r.UC_ARM64_REG_SP), sp)
        self.assertEqual(bytes(uc.mem_read(sp, 8)), b'\xa5' * 8)
        self.assertEqual(bytes(uc.mem_read(sp + 16, 0x40)), b'\xa5' * 0x40)
        self.assertEqual(struct.unpack('<Q', uc.mem_read(values[23] + 0x140, 8))[0], current)
        return missing

    def test_zero_and_positive_intervals_preserve_registers_flags_and_stack(self):
        for previous, delta in [(100, 0), (100, 1), (100, 2), (100, 9), (0xffffffff, 1), ((1 << 64) - 1, 1)]:
            with self.subTest(previous=previous, delta=delta):
                missing = self.run_stubs(previous, (previous + delta) & ((1 << 64) - 1))
                self.assertEqual(((missing & 0xffffffff) + 1) & 0xffffffff, delta)

    def test_phase_jitter_does_not_manufacture_persistent_catchup(self):
        emitted = {d: self.run_stubs(100, 100 + d) for d in (0, 1, 2)}
        def updates(fixed):
            debt = total = 0
            for delta in [1, 2, 0] * 120:
                missing = emitted[delta] if fixed else max(delta - 1, 0)
                debt += ((missing & 0xffffffff) + 1) & 0xffffffff
                debt = debt - 1 if debt <= 5 else -1
                extra = debt >= 1
                if extra: debt -= 1
                total += 1 + extra
            return total
        self.assertEqual(updates(False), 480)
        self.assertEqual(updates(True), 361)  # one initial real gap; no repeated manufactured ticks

    def test_real_missed_retraces_keep_the_original_count(self):
        for delta in (1, 2, 3, 5, 9):
            with self.subTest(delta=delta): self.assertEqual(self.run_stubs(100, 100 + delta), delta - 1)

if __name__ == '__main__': unittest.main()
