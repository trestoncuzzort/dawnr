# Which inventory is which

`receipts/` holds fourteen `INVENTORY-*.txt` files (thirteen from the build, one from the released image). Each is one run of
`tup/inventory.sh` against the build disk at that moment: one line per file,
`<sha256> <mode> <size> <path>`, symlinks as `-> target`. They were taken as
the build's paper trail, so most of them describe a disk *between* releases.
This file says what each one is, so nobody has to infer it from the
timestamps again (the first outside reader did, on 2026-09-02, and concluded
that Lean was in the release because seven inventories list it; it is not).

The released image is `tup-0.1-arm64.qcow2`, sha256
`5bb06ce14e96097fd7c999e5146850b82d5c347bd5484f5c4d6cb1b032343536`
(release `v0.1-witness`, 2026-08-31). **The inventory that describes that
image is `INVENTORY-RELEASE-0.1.txt`**, taken on 2026-09-02 by mounting the
released qcow2 itself read-only (`-o ro,noload`, ESP mounted) inside a booted
guest and running the same script against the mount; its own sha256 is in
the table. It was made *from the shipped bytes*, not from the build disk, so
it is the one receipt here that cannot be a different disk.

| inventory (UTC, 2026-08-31 unless stated) | files | what the disk was |
|---|---|---|
| `INVENTORY-20260831T111051Z.txt` | 58,143 | base system, after the 105 book pages and before any layer. The "before" of `LAYER-agent-FULL.md`. |
| `INVENTORY-20260831T111449Z.txt` | 62,944 | agent layer, first launch: CA bundle and Node in, Claude Code not yet (the driver stopped and was relaunched). |
| `INVENTORY-20260831T111648Z.txt` | 62,978 | agent layer complete. The "after" of `LAYER-agent-FULL.md` (4,844 added over the base, 1 modified) and of `LAYER-agent-20260831T111843Z.txt` (36 over the relaunch). |
| `INVENTORY-RELEASE-0.1.txt` (2026-09-02) | 62,986 | **the shipped 0.1 image**, inventoried from the qcow2 itself; sha256 of this file `a577ebe8d58989611e1d68e800d353fdb751fa6b76643c98c6c54510bfd85a7b`. Identical in every hash and path to `123219Z` below (0 differing lines), and differs from `111648Z` by exactly eight paths: `/boot/efi/EFI/BOOT/BOOTAA64.EFI` (the ESP was not mounted when `111648Z` ran) and seven `/var/log/*.log` files written by the boot witness. Node and Claude Code present; no Lean, no OCaml, no Rocq, no `/opt/t`. |
| `INVENTORY-20260831T123219Z.txt` | 62,986 | prove layer, launch 1, "before". **Byte-identical in content to the release inventory**: this is the disk the release was cut from, inventoried nine minutes after the cut and before Lean landed. |
| `INVENTORY-20260831T123423Z.txt` | 62,986 | prove layer, launch 2, "before" (a relaunch; no change). |
| `INVENTORY-20260831T123637Z.txt` | 62,986 | prove layer, launch 3, "before" (a relaunch; no change). |
| `INVENTORY-20260831T124058Z.txt` | 80,482 | prove layer in progress: Lean 4.33.1 unpacked to `/opt/lean-4.33.1`. **Not in the release.** |
| `INVENTORY-20260831T124525Z.txt` | 80,482 | prove layer, relaunch after Lean (118 bytes differ: a log). |
| `INVENTORY-20260831T125142Z.txt` | 100,034 | prove layer in progress: OCaml, findlib, dune built. |
| `INVENTORY-20260831T125822Z.txt` | 104,213 | prove layer in progress: zarith, Rocq 9.2.0, and `t` copied to `/opt/t`. |
| `INVENTORY-20260831T130332Z.txt` | 104,213 | prove layer, relaunch (no change). |
| `INVENTORY-20260831T130853Z.txt` | 104,216 | prove layer, relaunch (3 files: logs/state). |
| `INVENTORY-20260831T131350Z.txt` | 105,970 | prove layer, last recorded state (Rocq stdlib in progress). No prove or train layer has shipped in any image yet. |

Rules that follow from the table:

- A claim about what the *released* image contains is checked against
  `INVENTORY-RELEASE-0.1.txt` and nothing else. The other thirteen describe
  the build disk at build time.
- A layer's cost is the diff of its "before" and "after" pair, named in the
  `LAYER-*` receipt; a lone inventory is not a layer.
- The next release names its inventory in this file before it is tagged.
  `release.sh` should write that line; until it does, it is a human's job.
