#!/usr/bin/env python3
"""sync_forge.py — publish the FORGE to its own public repository.

WHY A SECOND PUBLISHER. The forge already shipped, but as `dpo/` inside the
product repo: a subdirectory of a different project, with no front door of its
own. That is backwards from what the forge is for. Research-shaped work needs an
exact repository to cite, and the two projects have different audiences and make
different claims.

WHAT IT DOES NOT DUPLICATE. The whitelist and the forbidden-term pattern are
IMPORTED from sync_public, never copied. Two lists of "what may leave this
machine" would agree only with each other, and the day they diverge is the day
one of them is wrong without telling anyone.

THE RULES ARE THE SAME ONES, deliberately:
  1. WHITELIST ONLY. There is no "sync everything" mode and no glob over the
     repo root. A file not named here does not get published, ever.
  2. SCAN, THEN ABORT. Any forbidden term aborts the publish. It does NOT strip
     the line and continue -- a sanitiser would let a real leak through by
     quietly editing it into something that looks fine.
  3. The working repo's own record (the channel, the run logs, the handoff
     package) is not in the whitelist and never will be.

    python sync_forge.py --check      # scan and diff only, write nothing
    python sync_forge.py -m "message"
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import sync_public as SP

HERE = Path(__file__).resolve().parent
REMOTE = "https://github.com/jonhhjackson-a11y/srlm-forge"
CLONE = HERE.parent / "_srlm_forge_publish"   # sibling, never inside the repo

# The forge's own front page, and its licence. Everything else is the whitelist
# sync_public already maintains, published at the ROOT here instead of under
# dpo/ -- same files, no longer a subdirectory of someone else's project.
EXTRA = {
    "publish/forge_README.md": "README.md",
    # The forge's OWN licence file, kept in step with the repository root
    # LICENSE (research use only, 2026-09-15).
    "publish/forge_LICENSE": "LICENSE",
}


def files_to_publish() -> dict[str, str]:
    mapping = dict(SP.DPO_PUBLISH)
    mapping.pop("publish/dpo_README.md", None)   # replaced by the forge README
    mapping.update(EXTRA)
    return mapping


def scan(mapping: dict[str, str]) -> list[str]:
    """Forbidden-term scan. Returns problems; empty means clean.

    Streams every file line-by-line rather than reading it whole, so this
    scans data/dpo_pairs.jsonl (~2.3MB) at the same coverage as any other
    file. A prior version skipped the content scan entirely for any .jsonl/
    .json file over 2MB -- a forbidden term planted past that size limit would
    never be seen, and the file it would have hit (dpo_pairs.jsonl) is exactly
    the kind of file this scan exists to check.
    """
    problems: list[str] = []
    for src in mapping:
        p = HERE / src
        if not p.exists():
            problems.append(f"{src}: MISSING")
            continue
        try:
            with p.open(encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    for m in SP.DPO_PATTERN.finditer(line):
                        if SP._permitted_copyright_line(line, m.group(0)):
                            continue
                        problems.append(f"{src}:{i}: forbidden {m.group(0)!r}")
        except OSError as e:
            problems.append(f"{src}: unreadable ({e})")
            continue
    return problems


def run(cmd: list[str], cwd: Path) -> str:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", default="")
    ap.add_argument("--check", action="store_true",
                    help="scan and diff only; write and push nothing")
    args = ap.parse_args()

    mapping = files_to_publish()
    print(f"scanning {len(mapping)} forge files for internal references...")
    problems = scan(mapping)
    if problems:
        print("\nREFUSING TO PUBLISH:")
        for p in problems[:40]:
            print("  " + p)
        return 1
    print("  clean.")

    if not CLONE.exists():
        print(f"cloning {REMOTE} -> {CLONE}")
        run(["git", "clone", REMOTE, str(CLONE)], HERE.parent)
    else:
        run(["git", "fetch", "origin"], CLONE)

    # A repository that has never been pushed to has no `main` to rebase onto,
    # and asking for one fails with "couldn't find remote ref main". Ask first.
    # Where main DOES exist the rebase is not optional: the repo owner may edit
    # on GitHub, and this must build on their commit rather than overwrite it.
    if run(["git", "ls-remote", "--heads", "origin", "main"], CLONE).strip():
        run(["git", "pull", "--rebase", "origin", "main"], CLONE)
    else:
        print("  remote has no main yet; this is the first publish.")

    for src, rel in mapping.items():
        dest = CLONE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / src, dest)

    status = run(["git", "status", "--porcelain"], CLONE)
    if not status.strip():
        print("nothing to publish; the public repo already matches.")
        return 0
    print("\nchanges to publish:")
    print(status.rstrip())

    if args.check:
        print("\n--check: nothing written, nothing pushed.")
        return 0

    run(["git", "add", "-A"], CLONE)
    msg = args.message or "publish the forge"
    run(["git", "commit", "-m", msg], CLONE)
    run(["git", "push", "origin", "HEAD:main"], CLONE)
    head = run(["git", "log", "--oneline", "-1"], CLONE).strip()
    print(f"\ncommitted: {msg}")
    print(f"pushed to {REMOTE}\n  {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
