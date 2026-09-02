# tup

**A Linux distribution built from source with a receipt on every step.**

tup is Linux From Scratch (arm64, r12.4) built by a driver instead of by hand,
so that what would otherwise be a weekend of typing becomes an artifact anyone
can audit: every command is the book's own bytes, every source tarball is
hashed before it is used, every page records its duration, exit status, and
the hash of its own log, and every deviation from the book is a separate,
diffable file rather than an edit nobody can see.

**tup 0.1 is a WITNESSED system, not a verified one.** Nothing here proves the
kernel or libc correct; it proves what was built, from which bytes, in what
order, with what outcome. That distinction is load-bearing in this repository
and it is not softened anywhere in these files. Verification lives next door
in [`../t/`](../t/); provenance lives here.

## Why it is in this repo

The repository root asks how much of a measured result is real. Its answer
depends on a verifier, which depends on an interpreter, which depends on a
libc, which depends on a compiler — and the receipts stop at the interpreter.
tup is that descent continued: the same discipline applied to the ground the
verdicts stand on. The paper's own findings (a verifier whose answer changed
with its Python version; digests that differed by platform) are what make
"control the substrate" a research position rather than a hobby.

## Layout

| Path | What it is |
|---|---|
| `extract_book.py` | Fetches an LFS book (`--arch arm64`, the default, or `--arch x86_64`) and writes one script per page, in TOC order, containing that page's `<pre class="userinput">` blocks verbatim. Package pages are resolved against the wget-list's actual filenames; an unresolved package page is a loud WARNING, never a silent skip. |
| `driver.sh` | Runs a chapter: extract tarball, enter, execute the page, delete the tree, append a receipt. Resumes from `driver.state`, stops loudly on the first failure. Reads its ORDER list on fd 3 with pages' stdin on `/dev/null`, because a page that reads stdin would otherwise eat the build list. |
| `overrides/` | The only sanctioned deviation mechanism. One file per page it replaces, each stating in its own header what it changes and why. Keyed by page NAME within a chapter (`ch08/glibc.sh`), never by page number, because the two books number chapter 8 differently; arch-bound pages (kernel, bootloader, fstab) live under `overrides/arm64/` and `overrides/x86_64/`. `check_overrides.py` proves every override hooks a real page in every book it applies to. |
| `chain7.sh`, `chain8.sh`, `chain-home.sh` | The chroot legs, each waiting on the previous chapter's completion marker. |
| `boot_witness.sh` | Boots the finished disk under QEMU with **nothing but firmware and the disk** (EDK2 for arm64, SeaBIOS for x86_64; no `-kernel`, no `-initrd`, no `-append`) and records the console transcript. A login prompt is the acceptance test. |
| `bundle_receipts.py` | Collects `receipts.jsonl`, the source manifest, and the test-policy record into one auditable file under `receipts/`. |
| `book/`, `book-x86_64/` | Generated, one per book (arm64 r12.4 fork; official x86 12.4). Never hand-edited; regenerate with `extract_book.py`. Each carries a `BOOK-SOURCE` naming the book and the fetch date. |
| `buildvm/` | The x86_64 leg's scaffolding on a Linux host with no sudo and no Lima: `vm.sh` (a QEMU build VM from the Ubuntu cloud image, hashed), `prepare-host.sh` (the book's chapters 2 to 4, scripted, every deviation named), `chain56.sh`, `build-all.sh`, and `build-x86_64.sh`, which runs the leg end to end and is resumable. |
| `X86-FEASIBILITY.md` | The x86_64 probe (2026-08-31), the BIOS-versus-EFI ruling, and what the leg measured. |

## The overrides, and why each exists

The book assumes a human at a terminal. Every place it does, tup has a file
saying so:

- **`exec /usr/bin/bash --login`** (createfiles, bash) — a human re-enters the
  shell; under the driver it would silently discard the rest of the page.
- **`passwd root`** — prompts. tup sets an initial password of `tup`; **change
  it at first boot.** The override exists so nobody can pretend the password
  was chosen well.
- **`make menuconfig`** — a curses UI. Replaced by `defconfig` plus the
  virtio/ext4/vfat options a QEMU guest boots from, forced in so no initramfs
  is needed.
- **Prose pages with code in them** — 8.2 Package Management is an advisory
  essay whose bare `./configure` fails instantly; 9.4 is device-naming
  diagnostics; 9.5 and 9.7 are placeholder examples (`<Your Domain Name>`).
  Each is replaced by either a no-op with a reason, or tup's real config.
- **8.86 Stripping** — optional and soname-fragile. Skipped by policy; tup
  keeps its debug symbols, because a system that can be debugged is worth more
  here than a smaller one.

## Test policy

Ruling, 2026-08-31: run the suites that are load-bearing — **glibc** (the book
calls it essential), **GCC**, **binutils** — and record every other suite as
skipped *by name* in the receipt. A skipped suite that nobody can enumerate is
indistinguishable from a suite that passed, which is the failure mode this
whole repository is about.

## Running it

The build happens inside a Lima VM (Ubuntu as disposable scaffolding — the LFS
two-pass toolchain exists precisely to sever the result from its host):

```bash
python3 tup/extract_book.py 5 6 7 8 9 10 11   # regenerate book/
# driver.sh runs per chapter inside the VM; chain*.sh sequence the legs
python3 tup/bundle_receipts.py                # collect the evidence
bash tup/boot_witness.sh                      # boot it alone, record the verdict
```

The x86_64 leg runs on a Linux host from QEMU alone (no Lima, no sudo):

```bash
python3 tup/extract_book.py --arch x86_64 5 6 7 8 9 10 11   # regenerate book-x86_64/
python3 tup/check_overrides.py && python3 tup/check_placeholders.py
bash tup/buildvm/build-x86_64.sh              # VM, chapters 2-11, receipts, witness, release
```

## Known findings from building it

Two silent-drop classes were found and closed during the first build, both
recorded here because this project treats its own instruments as suspect:

1. **A case-sensitive page name.** The TOC scanner matched lowercase only, so
   `chapter07/Python.html` vanished without a word; the temporary Python was
   never built and the damage surfaced three chapters later as glibc's
   configure reporting a missing program. Found by counting pages against the
   book's own index (12 where the book lists 13), not by luck.
2. **stdin theft.** The driver read its build list on stdin, so a page that
   reads stdin consumed the remaining list, which bash then executed as
   commands. Both are fixed at the class level, not the instance.
