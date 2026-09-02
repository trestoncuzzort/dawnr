#!/usr/bin/env python3
"""bundle_receipts.py — turn the build's scattered evidence into one record.

    python3 tup/bundle_receipts.py            # pull from the Lima build VM (arm64 leg)
    python3 tup/bundle_receipts.py --local /path/to/log   # from a copied log dir
                                              # (the x86_64 leg: buildvm/build-x86_64.sh
                                              #  copies /mnt/lfs/sources/log plus the
                                              #  SHA256-MANIFEST-*.txt beside it)

Collects, from the machine that did the work:
  * receipts.jsonl   — one line per page: package, seconds, exit, log sha256
  * SHA256-MANIFEST  — every source tarball as downloaded
  * driver.state     — the pages that actually completed
  * the test-policy record — which suites ran, WITH THEIR RESULTS, and which
    were skipped, BY NAME

and writes tup/receipts/BUILD-<date>.md: a single file a reader can check the
build against without trusting this script. Every number here is derived from
those files, and the files' own hashes are printed so the derivation can be
re-run.

WHAT THIS IS NOT: a proof the system is correct. It is a record of what was
built, from which bytes, in what order, with what outcome — provenance, not
verification. tup 0.1 is a WITNESSED system, not a verified one, and the
distinction is the whole point of keeping it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "receipts"
VM = "lfs-host"
REMOTE_LOG = "/mnt/lfs/sources/log"
REMOTE_SRC = "/mnt/lfs/sources"


def vm_read(path: str) -> str:
    p = subprocess.run(["limactl", "shell", VM, "--", "cat", path],
                       capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# The test receipts come in more than one shape, because the suites do: the
# glibc page records pass/fail/check_exit, binutils records expected_passes,
# fail_lines and unresolved, gcc records unexpected_failures and the name of a
# file listing them. Render whichever keys a record carries instead of assuming
# one schema — and print unknown keys too, because a suite result nobody prints
# is a suite result nobody reads.
TEST_FIELDS = (
    ("pass", "pass"),
    ("fail", "fail"),
    ("expected_passes", "expected passes"),
    ("fail_lines", "FAIL: lines"),
    ("unexpected_failures", "unexpected failures"),
    ("unresolved", "unresolved"),
    ("unexpected", "unexpected"),
)
EXIT_FIELDS = ("check_exit", "make_exit")
TEST_KNOWN = ({"page", "ts", "tests_run", "criterion", "fail_list"}
              | {k for k, _ in TEST_FIELDS} | set(EXIT_FIELDS))


def test_result(r: dict) -> str:
    bits = []
    for k, label in TEST_FIELDS:
        if k in r:
            v = r[k]
            if isinstance(v, str):
                v = v.strip() or "none named"
            bits.append(f"{label} {v}")
    bits += [f"{k} {r[k]}" for k in r if k not in TEST_KNOWN]
    return ", ".join(bits) if bits else "no counts recorded"


def test_exit(r: dict) -> str:
    bits = [f"{k.split('_')[0]} exit {r[k]}" for k in EXIT_FIELDS if k in r]
    return ", ".join(bits) if bits else "—"


def human(sec: float) -> str:
    if sec < 90:
        return f"{sec:.0f}s"
    if sec < 5400:
        return f"{sec/60:.1f} min"
    return f"{sec/3600:.2f} h"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="read the log dir from a local path instead")
    args = ap.parse_args()

    def read(name: str, base: str = REMOTE_LOG) -> str:
        if args.local:
            p = Path(args.local) / name
            return p.read_text(encoding="utf-8") if p.exists() else ""
        return vm_read(f"{base}/{name}")

    receipts_raw = read("receipts.jsonl")
    state_raw = read("driver.state")
    manifest_raw = ""
    if not args.local:
        ls = subprocess.run(["limactl", "shell", VM, "--", "sh", "-c",
                             f"cat {REMOTE_SRC}/SHA256-MANIFEST-*.txt"],
                            capture_output=True, text=True)
        manifest_raw = ls.stdout
    else:
        # the manifest lives beside the log dir on the build disk; the x86_64
        # orchestrator copies it into the log dir it hands over
        for d in (Path(args.local), Path(args.local).parent):
            found = sorted(d.glob("SHA256-MANIFEST-*.txt"))
            if found:
                manifest_raw = "".join(f.read_text(encoding="utf-8") for f in found)
                break
    prov_note = read("PROVENANCE-NOTE-bootscripts.txt")

    if not receipts_raw.strip():
        print("no receipts found — is the build VM running?")
        return 1

    rows = [json.loads(l) for l in receipts_raw.splitlines() if l.strip()]
    # THREE different kinds of line carry a "page" key, and they name different
    # things: a build receipt names "ch08/05-glibc.sh", a test result names
    # "ch08/05-glibc", a skip record names the bare suite "zlib". Only the
    # first is a page of the build. Counting all three as pages inflated the
    # retry figure from 39 to 43 on the 2026-08-31 ledger — four "retries" that
    # were a test result and three skip records wearing a build page's name.
    build_rows = [r for r in rows if "page" in r and "exit" in r]
    tests_run = [r for r in rows if r.get("tests_run")]
    # A page that failed and was retried leaves MULTIPLE receipts, and counting
    # them all reported "158 pages" where the state file held fewer. The last
    # receipt per page is the page's outcome; earlier ones are its history.
    # Both are reported, separately, and the count is reconciled against
    # driver.state so the two sources of truth cannot drift silently.
    last_by_page: dict = {}
    for r in build_rows:
        last_by_page[r["page"]] = r
    built = [r for r in last_by_page.values() if r.get("exit") == 0]
    failed = [r for r in last_by_page.values() if r.get("exit") not in (0, None)]
    retries = len(build_rows) - len(last_by_page)
    skipped_tests = sorted({r["page"] for r in rows if r.get("tests_skipped")})
    total = sum(r.get("seconds", 0) for r in rows)   # history: every attempt costs time
    by_ch = Counter(r["page"].split("/")[0] for r in built)
    state_pages = {l.strip() for l in state_raw.splitlines() if "/" in l}
    receipt_pages = {r["page"] for r in built}
    only_state = sorted(state_pages - receipt_pages)
    only_receipts = sorted(receipt_pages - state_pages)
    slowest = sorted(built, key=lambda r: -r.get("seconds", 0))[:10]
    tarballs = [l for l in manifest_raw.splitlines() if l.strip()]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(exist_ok=True)
    dest = OUT / f"BUILD-{stamp}.md"
    L: list[str] = []
    w = L.append
    w(f"# tup build receipt — {stamp}")
    w("")
    w("Provenance, not verification: this records what was built, from which")
    w("bytes, in what order, with what outcome. tup 0.1 is a WITNESSED system,")
    w("not a verified one.")
    w("")
    w("## Totals")
    w("")
    w(f"- distinct pages built: **{len(built)}** ({retries} retried attempts recorded besides)")
    w(f"- reconciliation vs driver.state: {len(state_pages)} state lines, "
      f"{len(receipt_pages)} receipted pages"
      + ("" if not only_state and not only_receipts else
         f" — **MISMATCH**: only-in-state {only_state[:5]}, only-in-receipts {only_receipts[:5]}"))
    w("")
    w(f"- pages completed: **{len(built)}**"
      + (f" (plus {len(failed)} failed page(s), listed below)" if failed else ""))
    w(f"- machine time in builds: **{human(total)}**")
    w(f"- source tarballs hashed: **{len(tarballs)}**")
    w(f"- chapters: " + ", ".join(f"{c} ({n})" for c, n in sorted(by_ch.items())))
    w("")
    w("## Test policy, as executed")
    w("")
    w("Ruling 2026-08-31: run the suites that are mathematically load-bearing")
    w("(glibc — the book calls it essential — plus GCC and binutils); record")
    w("every other suite as skipped BY NAME rather than dropping it silently.")
    w("")
    # The section is titled "as executed" and used to print only the suites
    # that did NOT execute. The three the ruling names as load-bearing ran,
    # and their results — glibc's one failure, binutils' one unresolved test,
    # gcc's 51 unexpected failures — appeared nowhere in the receipt.
    if tests_run:
        pages = {r.get("page") for r in tests_run}
        w(f"Suites that RAN ({len(tests_run)} records across {len(pages)} pages).")
        w("These are the suites' own numbers, recorded as the build saw them;")
        w("this script judges none of them.")
        w("")
        w("| page | what the run reported | exit |")
        w("|---|---|---|")
        for r in tests_run:
            w(f"| `{r.get('page','?')}` | {test_result(r)} | {test_exit(r)} |")
        w("")
        seen = set()
        for r in tests_run:
            pg = r.get("page", "?")
            if r.get("criterion") and (pg, r["criterion"]) not in seen:
                seen.add((pg, r["criterion"]))
                w(f"- `{pg}` pass criterion: {r['criterion']}")
            if r.get("fail_list"):
                w(f"- `{pg}` named failures are listed in `{r['fail_list']}`")
        w("")
    else:
        w("No test-result records present in this run's receipts.")
        w("")
    if skipped_tests:
        w(f"Suites skipped by policy ({len(skipped_tests)}):")
        w("")
        for p in skipped_tests:
            w(f"- `{p}`")
    else:
        w("No skip records present in this run's receipts.")
    w("")
    if failed:
        w("## Failed pages")
        w("")
        for r in failed:
            w(f"- `{r['page']}` exit {r['exit']} after {human(r.get('seconds',0))}"
              f" — log sha256 `{r.get('log_sha256','?')[:16]}…`")
        w("")
    w("## Ten slowest pages")
    w("")
    w("| page | package | time |")
    w("|---|---|---|")
    for r in slowest:
        w(f"| `{r['page']}` | {r.get('package') or '—'} | {human(r.get('seconds',0))} |")
    w("")
    if prov_note.strip():
        w("## Provenance exceptions")
        w("")
        w("```")
        w(prov_note.strip())
        w("```")
        w("")
    w("## Evidence hashes")
    w("")
    w("Every number above derives from these files; hash them on the build")
    w("machine to confirm this report was generated from them.")
    w("")
    w(f"- `receipts.jsonl` sha256 `{sha256_text(receipts_raw)}`"
      f" ({len(rows)} lines)")
    w(f"- `driver.state` sha256 `{sha256_text(state_raw)}`"
      f" ({len(state_raw.splitlines())} lines)")
    w(f"- `SHA256-MANIFEST` sha256 `{sha256_text(manifest_raw)}`"
      f" ({len(tarballs)} entries)")
    w("")
    w("## Source manifest (first 20 of the tarballs this system was built from)")
    w("")
    w("```")
    for line in tarballs[:20]:
        w(line)
    if len(tarballs) > 20:
        w(f"... {len(tarballs)-20} more")
    w("```")

    dest.write_text("\n".join(L) + "\n", encoding="utf-8")
    (OUT / f"receipts-{stamp}.jsonl").write_text(receipts_raw, encoding="utf-8")
    (OUT / f"SHA256-MANIFEST-{stamp}.txt").write_text(manifest_raw, encoding="utf-8")
    print(f"wrote {dest.relative_to(HERE.parent)}")
    print(f"  {len(built)} pages, {human(total)} of builds, {len(tarballs)} tarballs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
