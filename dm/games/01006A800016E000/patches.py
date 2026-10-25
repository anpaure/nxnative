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
    """Optional two-buffer render queue, independent of the 60 Hz simulation.

    The original-byte assertions and build ID restrict these stubs to 13.0.3.
    state +0x3c is DM_RENDER_LOW_LATENCY; target fps stays 0. With the flag off,
    each stub executes the original instruction. Queue layout checked against
    the dispatch wait/submit and pending-batch promotion in main+0x384f080.
    """
    from nso_asm import ADRP, B, STRX
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

    # The two active textures rotate 0,1. Render to (acquired + 1) % 2 instead
    # of the triple-buffered delayed target (acquired + 2) % 3.
    site = 0x386a76c
    ctx.site(site, '29090011')  # add w9,w9,#2
    start = ctx.here()
    ctx.emit(ADRP(16, ctx.here(), ctx.state))
    for word in (0xb9403e10, 0x34000090, 0x11000529, 0x12000129):  # flag; cbz original; add w9,#1; and w9,#1
        ctx.emit(word)
    ctx.emit(B(ctx.here(), site + 4))
    ctx.emit(0x11000929)
    ctx.emit(B(ctx.here(), site + 4))
    ctx.put(site, [B(site, start)], 'optional low-latency render queue: match the two active window textures')


FRAME_STEP = {'730c2141eebf9885e4857e7e50eae441': _render_queue_1303}
