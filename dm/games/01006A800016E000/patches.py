# Super Smash Bros. Ultimate (01006A800016E000): the rewriter's patches of this game's own builds. dm/tools/patch_nso.py loads every profile's patches.py and applies those of a module's NSO build ID;
# CUTS, OBS and FRAME_STEP as described there ("Registered patches"). Patches of Nintendo SDK module builds are in dm/tools/sdk_patches.py
CUTS = {
  # Super Smash Bros. Ultimate 13.0.5 (v2031616) main: the engine's memory (the nu:: allocator, set up by a static constructor at main+0x37c9a20) reserves 62 GB of address space with
  # nn::os::AllocateAddressRegion(0xf80000000) and hands it out in 64 KB units: a number line of free ranges, first [0, 0xf7f20) units from the region's start (main+0x37c9b98, given to
  # main+0x37c9c00), and the top 14 MB (region + 0xf7f200000) as the pool of its range nodes, committed 64 KB at a time up to the region's end (the bound checks at main+0x37c9a9c, +0x37c9c50,
  # +0x37ca3cc and +0x37caf68). The Switch's 64 GB alias region holds it; an iPhone's single 6 GB reservation cannot, and the abort at main+0x37c9bd0 followed. Booted on the Mac with a
  # 64 GB alias region, the game commits from the region's start upward (1.73 GB contiguous from it at the title, 75 s in) and the node pool's first 64 KB at the top, so the region is
  # cut to 4 GB (the application pool, 3.2 GB, bounds what it can commit), every constant derived from its size with it: the node pool at 4 GB − 14 MB, the first free range 0xff20 units
  '21450c647b8c5940ed5b68218ea128fd': [
    (0x37c9a5c, 'e11361b2', '2100c0d2', 'AllocateAddressRegion size mov x1,#0xf80000000 → mov x1,#0x100000000 (62 GB → 4 GB)'),
    (0x37c9a6c, 'e97f7cb2', '09fe9fd2', 'node pool top check, low part mov x9,#0xffffffff0 → mov x9,#0xfff0'),
    (0x37c9a70, '0be4afd2', '0be4bfd2', 'node pool start mov x11,#0x7f200000 → mov x11,#0xff200000'),
    (0x37c9a74, '09e4aff2', '09e4bff2', 'node pool top check movk x9,#0x7f20,lsl #16 → movk x9,#0xff20,lsl #16 (0xff20fff0)'),
    (0x37c9a78, 'eb01c0f2', '0b00c0f2', 'node pool start movk x11,#0xf,lsl #32 → movk x11,#0,lsl #32 (0xff200000 = 4 GB − 14 MB)'),
    (0x37c9a9c, 'e91361b2', '2900c0d2', 'node pool bound: region end mov x9,#0xf80000000 → mov x9,#0x100000000'),
    (0x37c9b98, '01e48f52', '01e49f52', 'first free range in 64 KB units mov w1,#0x7f20 → mov w1,#0xff20'),
    (0x37c9b9c, 'e101a072', '0100a072', 'first free range movk w1,#0xf,lsl #16 → movk w1,#0,lsl #16 (0xff20 units = 4 GB − 14 MB)'),
    (0x37c9c50, 'e91361b2', '2900c0d2', 'node pool bound: region end mov x9,#0xf80000000 → mov x9,#0x100000000'),
    (0x37ca3cc, 'e81361b2', '2800c0d2', 'node pool bound: region end mov x8,#0xf80000000 → mov x8,#0x100000000'),
    (0x37caf68, 'e91361b2', '2900c0d2', 'node pool bound: region end mov x9,#0xf80000000 → mov x9,#0x100000000'),
  ],
}

# 13.0.3 (v1900544): the same allocator and all eleven constant sites are
# 0x990 bytes earlier. Checked against main 730c2141...: every original word
# matches, the signature is unique, and the disassembly still reserves 62 GB
# and derives the node pool and free-range bounds from it. SDK/movie builds
# are unchanged, so the SDK's registered memory cuts already apply.
CUTS['730c2141eebf9885e4857e7e50eae441'] = [
    (off - 0x990, original, replacement, reason)
    for off, original, replacement, reason in CUTS['21450c647b8c5940ed5b68218ea128fd']
]


def _render_queue_1303(ctx):
    """Optional render ordering and two-buffer queue, with the original simulation.

    The original-byte assertions and build ID restrict these stubs to 13.0.3.
    state +0x3c is DM_RENDER_LOW_LATENCY; target fps stays 0. With the flag off,
    each stub executes the original instruction. Queue layout checked against
    the dispatch wait/submit and pending-batch promotion in main+0x384f080.
    """
    from nso_asm import ADRP, ADDI, B, BR, BLR, LDRX, STRX, STP, LDP, SUBI, STP_PRE, LDP_POST
    # Promote the pending dispatch before waiting/submitting it, rather than at
    # the end of the flush (which otherwise retains a previous frame's batch).
    site = 0x384f080
    ctx.site(site, 'f85fbca9')  # stp x24,x23,[sp,#-0x40]!
    start = ctx.here()
    ctx.emit(ADRP(16, ctx.here(), ctx.state))
    for word in (
        0xb9403e10,       # ldr w16,[x16,#0x3c]
        0x34000170,       # cbz w16,original
        0x5283a310,       # mov w16,#0x1d18 (pending dispatch flag)
        0x38706811,       # ldrb w17,[x0,x16]
        0x34000111,       # cbz w17,original
        0xb95d2010,       # ldr w16,[x0,#0x1d20] (producer index)
        0x2a3003f0,       # mvn w16,w16
        0x92400210,       # and x16,x16,#1
        STRX(16, 0, 0x1d30 // 8),
        0x5283a510,       # mov w16,#0x1d28 (dispatch ready flag)
        0x52800031,       # mov w17,#1
        0x38306811,       # strb w17,[x0,x16]
        0xa9bc5ff8,       # original prologue
    ): ctx.emit(word)
    ctx.emit(B(ctx.here(), site + 4))
    ctx.put(site, [B(site, start)], 'optional low-latency render queue: flush the pending batch on this frame')

    def cbz(reg, pc, target):
        return 0x34000000 | (((target - pc) // 4 & 0x7ffff) << 5) | reg

    def bc(cond, pc, target):
        return 0x54000000 | (((target - pc) // 4 & 0x7ffff) << 5) | cond

    # Level 2 submits the pending batch immediately before presenting its
    # texture, rather than after presenting. Keep all arguments to the original
    # present/acquire call; the device in x1 is the same object the old flush
    # loads through the singleton at [sp+0x268]. Its +0x88 member's vtable +0x18
    # is the original flush, and +0xec is its original submission flag.
    site = 0x3747798
    ctx.site(site, '2ea00494')  # bl 0x386f850 (present/acquire)
    start = ctx.here()
    words = [ADRP(16, start, ctx.state), 0xb9403e10, 0x71000a1f, 0]
    words.append(SUBI(31, 31, 0x120))
    for reg in range(0, 18, 2): words.append(STP(reg, reg + 1, 31, reg * 8))
    words.append(STRX(30, 31, 144 // 8))
    for reg in range(0, 8, 2):
        words.append(0xad000000 | (((160 + reg * 16) // 16) << 15) | ((reg + 1) << 10) | (31 << 5) | reg)
    words += [LDRX(0, 1, 0x88 // 8), 0x3943b021, LDRX(8, 0), LDRX(8, 8, 3), BLR(8)]
    words += [LDRX(16, 31, 1), 0x3903b21f]  # saved device; strb wzr,[x16,#0xec]
    for reg in range(0, 8, 2):
        words.append(0xad400000 | (((160 + reg * 16) // 16) << 15) | ((reg + 1) << 10) | (31 << 5) | reg)
    for reg in range(0, 18, 2): words.append(LDP(reg, reg + 1, 31, reg * 8))
    words += [LDRX(30, 31, 144 // 8), ADDI(31, 31, 0x120)]
    tail = start + 4 * len(words)
    words.append(B(tail, 0x386f850))
    words[3] = bc(0xb, start + 12, tail)  # b.lt: levels 0/1 keep the original call
    for word in words: ctx.emit(word)
    ctx.put(site, [B(site, start) | 0x80000000], 'optional low-latency level 2: flush before present/acquire')

    # Bypass the old flush and its flag reset only at level 2. The fallback
    # reconstructs the original BLR's LR, returning to the unchanged STRB.
    site = 0x37491e8
    ctx.site(site, '00013fd69fb20339')  # blr x8; strb wzr,[x20,#0xec]
    start = ctx.here()
    for word in (ADRP(16, start, ctx.state), 0xb9403e10, 0x71000a1f, bc(0xb, start + 12, start + 20), B(start + 16, site + 8), ADRP(30, start + 20, site + 4), ADDI(30, 30, (site + 4) & 0xfff), BR(8)):
        ctx.emit(word)
    ctx.put(site, [B(site, start)], 'optional low-latency level 2: omit the old after-present flush')

    # With level 1, render to (acquired + 1) % 2 for the after-present flush.
    # Level 2 flushes before presenting and therefore uses the acquired texture
    # itself. Level 0 retains the triple-buffered (acquired + 2) % 3.
    site = 0x386a76c
    ctx.site(site, '29090011')  # add w9,w9,#2
    start = ctx.here()
    words = [ADRP(16, start, ctx.state), 0xb9403e10, cbz(16, start + 8, start + 32), 0x71000a1f, bc(0xa, start + 16, start + 28), 0x11000529, 0x12000129, B(start + 28, site + 4), 0x11000929, B(start + 36, site + 4)]
    for word in words: ctx.emit(word)
    ctx.put(site, [B(site, start)], 'optional low-latency render queue: select the target for the flush order')

    # Level 3 moves model/fighter recording and dispatch after the scene update.
    # These locations and the vtable relocation are independently checked in
    # this build: the main-loop offsets are -0x3e0 from the community research,
    # worker functions +0x270, globals/vtables +0x1000, and models unchanged.
    def code(items):
        start = ctx.here(); labels = {}; pc = start
        for item in items:
            if isinstance(item, str): labels[item] = pc
            else: pc += 4
        for item in items:
            if isinstance(item, str): continue
            ctx.emit(item(ctx.here(), labels) if callable(item) else item)
        return start

    def jump(label): return lambda pc, labels: B(pc, labels[label])
    def zero(reg, label, nonzero=False, wide=False):
        return lambda pc, labels: cbz(reg, pc, labels[label]) | (0x01000000 if nonzero else 0) | (0x80000000 if wide else 0)
    def cond(n, label): return lambda pc, labels: bc(n, pc, labels[label])
    def call(target): return lambda pc, labels: B(pc, target) | 0x80000000
    def address(reg, target):
        return [lambda pc, labels: ADRP(reg, pc, target), ADDI(reg, reg, target & 0xfff)]
    flag = [lambda pc, labels: ADRP(16, pc, ctx.state), 0xb9403e10, 0x51000e10]  # level - 3, flags preserved

    # Redirect only the model-update vtable slot, not other model functions.
    start = code(flag + [zero(16, 'skip'), lambda pc, labels: B(pc, 0x3ab590), 'skip', 0xd65f03c0])
    ctx.site(0x3a211a0, 'd033f60400000000030400000000000090b53a0000000000')
    ctx.put(0x3a211b0, [start & 0xffffffff, (start >> 32) & 0xffffffff], 'optional low-latency level 3: defer the model-update vtable callback')

    site = 0x374b174
    ctx.site(site, '9bf8f797')
    start = code(flag + [zero(16, 'skip'), lambda pc, labels: B(pc, 0x35493e0), 'skip', 0xd65f03c0])
    ctx.put(site, [B(site, start) | 0x80000000], 'optional low-latency level 3: defer fighter render recording')

    site = 0x374bc74
    ctx.site(site, '20050054')  # b.eq 0x374bd18; preceding cmp is still live
    start = code(flag + [zero(16, 'skip'), cond(0, 'skip'), lambda pc, labels: B(pc, site + 4), 'skip', lambda pc, labels: B(pc, 0x374bd18)])
    ctx.put(site, [B(site, start)], 'optional low-latency level 3: defer dispatch until the scene update finishes')

    # All general/SIMD registers and NZCV survive this inline insertion. A fresh
    # 64-byte worker descriptor follows the save area. The queue walk preserves
    # the original acquire/release lock and deletion/skip semantics.
    site = 0x374c3d4
    ctx.site(site, '68df00b0')  # adrp x8,0x5339000, after all scene-update paths
    seq = [STP_PRE(16, 17, 31, -16)] + flag + [zero(16, 'original', True), LDP_POST(16, 17, 31, 16), SUBI(31, 31, 0x340)]
    for reg in range(0, 30, 2):
        if reg == 18: seq.append(STRX(19, 31, 19))  # x18 belongs to Apple; guest x18 lives in TSD
        else: seq.append(STP(reg, reg + 1, 31, reg * 8))
    seq += [STRX(30, 31, 0xf0 // 8), 0xd53b4210, STRX(16, 31, 0xf8 // 8)]
    for reg in range(0, 32, 2): seq.append(0xad000000 | (((0x100 + reg * 16) // 16) << 15) | ((reg + 1) << 10) | (31 << 5) | reg)
    seq += address(8, 0x5333120) + [LDRX(0, 8), zero(0, 'no_models', wide=True), call(0x3ab590), 'no_models']
    seq += [0x6e201c00, 0xad1803e0, 0xad1903e0, ADDI(0, 31, 0x300)]  # zero worker info
    seq += address(1, 0x374ec70) + [0x2a1f03e2, 0x2a1f03e3, call(0x35493e0), 0xb94313e8, zero(8, 'fighter_done')]
    seq += [0xb94317e8] + address(9, 0x5333f58) + [0xf8687928, 0xb9401100, ADDI(1, 31, 0x310), call(0x354c990), 'fighter_done']
    seq += address(19, 0x5333558) + [0x39408268, 0x7100051f, cond(0, 'dispatch_done'), ADDI(22, 19, 8), 0x5280003a, 'lock']
    seq += [0x085ffec8, 0x08097eda, 0x12000108, 0x7100013f, 0x7a400900, cond(1, 'lock'), LDRX(20, 19), zero(20, 'unlock', wide=True)]
    seq += ['node', 0x3941c288, LDRX(21, 20, 0x48 // 8), 0x7100051f, cond(0, 'advance'), 0x7100091f, cond(1, 'initialize')]
    seq += [STRX(21, 19), LDRX(8, 20), LDRX(8, 8, 1), 0xaa1403e0, BLR(8), 0xaa1503f4, zero(20, 'node', True, wide=True), jump('unlock')]
    seq += ['initialize', 0xb9406a82, 0xb9406e83, ADDI(0, 20, 8)] + address(1, 0x35484b0) + [call(0x35493e0)]
    seq += ['advance', LDRX(8, 19), ADDI(19, 8, 0x48), 0xaa1503f4, zero(20, 'node', True, wide=True), 'unlock', 0x089ffedf, 'dispatch_done']
    seq += [LDRX(16, 31, 0xf8 // 8), 0xd51b4210]
    for reg in range(0, 32, 2): seq.append(0xad400000 | (((0x100 + reg * 16) // 16) << 15) | ((reg + 1) << 10) | (31 << 5) | reg)
    for reg in range(0, 30, 2):
        if reg == 18: seq.append(LDRX(19, 31, 19))
        else: seq.append(LDP(reg, reg + 1, 31, reg * 8))
    seq += [LDRX(30, 31, 0xf0 // 8), ADDI(31, 31, 0x340), lambda pc, labels: ADRP(8, pc, 0x5339000), lambda pc, labels: B(pc, site + 4)]
    seq += ['original', LDP_POST(16, 17, 31, 16), lambda pc, labels: ADRP(8, pc, 0x5339000), lambda pc, labels: B(pc, site + 4)]
    start = code(seq)
    ctx.put(site, [B(site, start)], 'optional low-latency level 3: update models, record fighters, then dispatch after scene update')


FRAME_STEP = {'730c2141eebf9885e4857e7e50eae441': _render_queue_1303}
