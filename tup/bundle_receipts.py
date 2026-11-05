#!/usr/bin/env python3
"""bundle_receipts.py: turn the build's scattered evidence into one record.

    python3 tup/bundle_receipts.py            # pull from the Lima build VM (arm64 leg)
    python3 tup/bundle_receipts.py --local /path/to/log   # from a copied log dir
                                              # (the x86_64 leg: buildvm/build-x86_64.sh
                                              #  copies /mnt/lfs/sources/log plus the
                                              #  SHA256-MANIFEST-*.txt beside it)

Collects, from the machine that did the work:
  * receipts.jsonl   : one line per page: package, seconds, exit, log sha256
  * SHA256-MANIFEST  : every source tarball as downloaded
  * driver.state     : the pages that actually completed
  * the test-policy record: which suites ran, WITH THEIR RESULTS, and which
    were skipped, BY NAME

and writes tup/receipts/BUILD-<date>.md: a single file a reader can check the
build against without trusting this script. Every number here is derived from
those files, and the files' own hashes are printed so the derivation can be
re-run.

Receipts, driver.state and at least one nonempty source manifest are required.
The state may be empty for a failed first page. Hashes and archived copies use
the collected bytes; UTF-8 decoding is only for interpreting the evidence.

WHAT THIS IS NOT: a proof the system is correct. It is a record of what was
built, from which bytes, in what order and with what outcome: provenance, not
verification. tup 0.1 is a WITNESSED system, not a verified one, and the
distinction is the whole point of keeping it.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
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


class EvidenceError(ValueError):
    """Required evidence is missing, unreadable or cannot be interpreted."""


def vm_bytes(command: list[str], description: str) -> bytes:
    # subprocess text mode translates CRLF before the caller can hash it.
    p = subprocess.run(["limactl", "shell", VM, "--", *command], capture_output=True)
    if p.returncode != 0:
        raise EvidenceError(f"cannot collect {description}: remote exit {p.returncode}")
    return p.stdout


def vm_read(path: str, *, optional: bool = False) -> bytes | None:
    if not optional:
        return vm_bytes(["cat", "--", path], path)
    # A successful, framed response distinguishes an absent optional note from
    # a failed read/transport. Do not turn arbitrary command failures into absence.
    raw = vm_bytes(["sh", "-c",
                    'if [ -e "$1" ] || [ -L "$1" ]; then '
                    'printf 1; cat -- "$1"; else printf 0; fi',
                    "tup-read", path], path)
    if raw == b"0":
        return None
    if raw.startswith(b"1"):
        return raw[1:]
    raise EvidenceError(f"invalid optional-file response for {path}")


def local_read(path: Path, *, optional: bool = False) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        if optional and not path.is_symlink():
            return None
        raise EvidenceError(f"missing evidence: {path.name}") from None
    except OSError as exc:
        raise EvidenceError(f"cannot read {path.name}: {exc}") from exc


def evidence_text(raw: bytes, name: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeError as exc:
        raise EvidenceError(f"{name}: invalid UTF-8 evidence") from exc


def read_manifests(local: str | None) -> list[tuple[str, bytes]]:
    """Collect each manifest once; order is UTF-8 basename bytes on every host."""
    if local:
        # A copied log directory may contain its manifests; otherwise they live
        # beside it on the build disk. Never mix these two source directories.
        for directory in (Path(local), Path(local).parent):
            found = [p for p in directory.iterdir()
                     if fnmatch.fnmatchcase(p.name, "SHA256-MANIFEST-*.txt")]
            if found:
                return [(p.name, local_read(p)) for p in
                        sorted(found, key=lambda p: p.name.encode("utf-8"))]
    else:
        listing = vm_bytes(["sh", "-c",
                            'cd "$1" || exit; '
                            'for path in SHA256-MANIFEST-*.txt; do '
                            '[ -e "$path" ] || [ -L "$path" ] || continue; '
                            'printf "%s\\0" "$path"; done',
                            "tup-manifests", REMOTE_SRC], "manifest list")
        if listing:
            if not listing.endswith(b"\0"):
                raise EvidenceError("invalid remote manifest list")
            names = [evidence_text(name, "manifest filename")
                     for name in listing[:-1].split(b"\0")]
            if (len(set(names)) != len(names) or
                    any("/" in name or not fnmatch.fnmatchcase(name, "SHA256-MANIFEST-*.txt")
                        for name in names)):
                raise EvidenceError("invalid remote manifest filename")
            return [(name, vm_read(f"{REMOTE_SRC}/{name}"))
                    for name in sorted(names, key=lambda name: name.encode("utf-8"))]
    raise EvidenceError("no source manifests found (SHA256-MANIFEST-*.txt)")


def parse_receipts(raw: bytes) -> list[dict]:
    rows = []
    # JSONL is separated by LF, not by every Unicode line-separator character.
    for number, line in enumerate(evidence_text(raw, "receipts.jsonl").split("\n"), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise EvidenceError(f"receipts.jsonl:{number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise EvidenceError(f"receipts.jsonl:{number}: expected a JSON object")
        rows.append(row)
    if not rows:
        raise EvidenceError("receipts.jsonl: no receipt records found")
    return rows


def manifest_entries(parts: list[tuple[str, bytes]]) -> list[str]:
    entries = []
    for name, raw in parts:
        lines = [line.removesuffix("\r") for line in evidence_text(raw, name).split("\n")
                 if line.strip()]
        if not lines:
            raise EvidenceError(f"{name}: empty source manifest")
        # GNU sha256sum's untagged format, including its escaped-filename prefix.
        # Validate the record shape; no tarball bytes are available to verify.
        for number, line in enumerate(lines, 1):
            if not re.fullmatch(r"\\?[0-9a-fA-F]{64} [ *].+", line):
                raise EvidenceError(f"{name}:{number}: invalid SHA-256 manifest entry")
        entries.extend(lines)
    return entries


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


# Everything rendered below came out of the build's own files: a page name out
# of ORDER, a package name out of a page's "# TUP_TARBALL=" line, glibc's
# "unexpected" field out of test names scraped from check.out. None of it was
# written to be Markdown, and Markdown reads some of it as structure. A GFM
# table row is split on its pipes BEFORE anything inline is parsed -- so a pipe
# in a value opens a new cell even inside a code span -- and a newline ends the
# row, leaving what followed to be read as the document's own text. Measured: a
# package name of "evil|cell\nnext" cut its row to two cells and left
# "next | 13.3 min |" standing on its own; a test criterion holding
# "| forged | criterion | row |" printed exactly that, as a table. So values
# are escaped where they meet the Markdown.
def md_cell(v) -> str:
    """One table cell from an arbitrary value: pipes escaped, control
    characters made visible instead of left to act."""
    s = "" if v is None else str(v)
    out = []
    for ch in s:
        if ch == "|":
            out.append("\\|")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\x{ord(ch):02x}")
        else:
            out.append(ch)
    return "".join(out)


def md_code(v) -> str:
    """The same value in a code span it cannot close. CommonMark ends a span at
    the next run of exactly as many backticks as opened it, so open with one
    more than the longest run inside, and pad if it starts or ends with one."""
    s = md_cell(v)
    n = max((len(m) for m in re.findall(r"`+", s)), default=0)
    fence = "`" * (n + 1)
    pad = " " if s.startswith("`") or s.endswith("`") else ""
    return f"{fence}{pad}{s}{pad}{fence}"


def md_fence(text: str) -> str:
    """A fence for a block that the block's own text cannot close: three
    backticks at least, and longer than any fence line inside it."""
    n = max((len(m) for m in re.findall(r"^\s*(`{3,})", text, re.M)), default=0)
    return "`" * max(3, n + 1)


# The test receipts come in more than one shape, because the suites do: the
# glibc page records pass/fail/check_exit, binutils records expected_passes,
# fail_lines and unresolved, gcc records unexpected_failures and the name of a
# file listing them. Render whichever keys a record carries instead of assuming
# one schema, and print unknown keys too, because a suite result nobody prints
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

    def read(name: str, *, optional: bool = False) -> bytes | None:
        if args.local:
            return local_read(Path(args.local) / name, optional=optional)
        return vm_read(f"{REMOTE_LOG}/{name}", optional=optional)

    try:
        receipts_raw = read("receipts.jsonl")
        state_raw = read("driver.state")
        manifest_parts = read_manifests(args.local)
        manifest_raw = b"".join(raw for _, raw in manifest_parts)
        prov_raw = read("PROVENANCE-NOTE-bootscripts.txt", optional=True)
        rows = parse_receipts(receipts_raw)
        state_text = evidence_text(state_raw, "driver.state")
        tarballs = manifest_entries(manifest_parts)
        prov_note = (evidence_text(prov_raw, "PROVENANCE-NOTE-bootscripts.txt")
                     if prov_raw is not None else "")
    except (EvidenceError, OSError, UnicodeError) as exc:
        print(f"cannot bundle evidence: {exc}", file=sys.stderr)
        return 1
    # THREE different kinds of line carry a "page" key, and they name different
    # things: a build receipt names "ch08/05-glibc.sh", a test result names
    # "ch08/05-glibc", a skip record names the bare suite "zlib". Only the
    # first is a page of the build. Counting all three as pages inflated the
    # retry figure from 39 to 43 on the 2026-08-31 ledger, four "retries" that
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
    state_pages = {l.strip() for l in state_text.splitlines() if "/" in l}
    receipt_pages = {r["page"] for r in built}
    only_state = sorted(state_pages - receipt_pages)
    only_receipts = sorted(receipt_pages - state_pages)
    slowest = sorted(built, key=lambda r: -r.get("seconds", 0))[:10]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
         f", **MISMATCH**: only-in-state {only_state[:5]}, only-in-receipts {only_receipts[:5]}"))
    w("")
    w(f"- pages completed: **{len(built)}**"
      + (f" (plus {len(failed)} failed page(s), listed below)" if failed else ""))
    w(f"- machine time in builds: **{human(total)}**")
    w(f"- source manifest entries: **{len(tarballs)}**")
    w(f"- chapters: " + ", ".join(f"{md_cell(c)} ({n})" for c, n in sorted(by_ch.items())))
    w("")
    w("## Test policy, as executed")
    w("")
    w("Ruling 2026-08-31: run the suites that are mathematically load-bearing")
    w("(glibc, which the book calls essential, plus GCC and binutils); record")
    w("every other suite as skipped BY NAME rather than dropping it silently.")
    w("")
    # The section is titled "as executed" and used to print only the suites
    # that did NOT execute. The three the ruling names as load-bearing ran,
    # and their results, glibc's one failure, binutils' one unresolved test
    # and gcc's 51 unexpected failures, appeared nowhere in the receipt.
    if tests_run:
        pages = {r.get("page") for r in tests_run}
        w(f"Suites that RAN ({len(tests_run)} records across {len(pages)} pages).")
        w("These are the suites' own numbers, recorded as the build saw them;")
        w("this script judges none of them.")
        w("")
        w("| page | what the run reported | exit |")
        w("|---|---|---|")
        for r in tests_run:
            w(f"| {md_code(r.get('page','?'))} | {md_cell(test_result(r))}"
              f" | {md_cell(test_exit(r))} |")
        w("")
        seen = set()
        for r in tests_run:
            pg = r.get("page", "?")
            if r.get("criterion") and (pg, r["criterion"]) not in seen:
                seen.add((pg, r["criterion"]))
                w(f"- {md_code(pg)} pass criterion: {md_cell(r['criterion'])}")
            if r.get("fail_list"):
                w(f"- {md_code(pg)} named failures are listed in"
                  f" {md_code(r['fail_list'])}")
        w("")
    else:
        w("No test-result records present in this run's receipts.")
        w("")
    if skipped_tests:
        w(f"Suites skipped by policy ({len(skipped_tests)}):")
        w("")
        for p in skipped_tests:
            w(f"- {md_code(p)}")
    else:
        w("No skip records present in this run's receipts.")
    w("")
    if failed:
        w("## Failed pages")
        w("")
        for r in failed:
            w(f"- {md_code(r['page'])} exit {md_cell(r['exit'])}"
              f" after {human(r.get('seconds',0))}"
              f", log sha256 {md_code(str(r.get('log_sha256','?'))[:16] + '…')}")
        w("")
    w("## Ten slowest pages")
    w("")
    w("| page | package | time |")
    w("|---|---|---|")
    for r in slowest:
        w(f"| {md_code(r['page'])} | {md_cell(r.get('package') or '—')}"
          f" | {human(r.get('seconds',0))} |")
    w("")
    if prov_note.strip():
        w("## Provenance exceptions")
        w("")
        fence = md_fence(prov_note)
        w(fence)
        w(prov_note.strip())
        w(fence)
        w("")
    w("## Evidence hashes")
    w("")
    w("These hashes identify the original bytes collected, before UTF-8 parsing.")
    w("Hash the preserved copies or the unchanged source files to compare them.")
    w("This does not authenticate the source or verify the tarballs named within.")
    w("")
    w(f"- `receipts.jsonl` sha256 `{sha256_bytes(receipts_raw)}`"
      f" ({len(rows)} lines)")
    w(f"- `driver.state` sha256 `{sha256_bytes(state_raw)}`"
      f" ({len(state_text.splitlines())} lines; copy `driver-state-{stamp}.txt`)")
    w(f"- `SHA256-MANIFEST` sha256 `{sha256_bytes(manifest_raw)}`"
      f" ({len(tarballs)} entries; {len(manifest_raw)} bytes)")
    if prov_raw is not None:
        w(f"- `PROVENANCE-NOTE-bootscripts.txt` sha256 `{sha256_bytes(prov_raw)}`"
          f" (copy `provenance-note-{stamp}.txt`)")
    w("")
    w("The manifest aggregate is the exact concatenation of the files below in")
    w("UTF-8 basename byte order, with no inserted separators. Its hash")
    w("does not bind filenames or file boundaries; the component hashes and byte")
    w("counts identify those separately. Entries are parsed per component, even")
    w("when a component has no final newline. A previously combined input is")
    w("identified as supplied; this report cannot recover its original components.")
    w("")
    for number, (name, raw) in enumerate(manifest_parts, 1):
        w(f"{number}. {md_code(name)} sha256 `{sha256_bytes(raw)}`"
          f" ({len(raw)} bytes; copy `manifest-components-{stamp}/{number}.txt`)")
    w("")
    w("## Source manifest (first 20 recorded entries)")
    w("")
    fence = md_fence("\n".join(tarballs[:20]))
    w(fence)
    for line in tarballs[:20]:
        w(line)
    if len(tarballs) > 20:
        w(f"... {len(tarballs)-20} more")
    w(fence)

    # Preserve evidence as bytes on every host; text writes can translate LF.
    # Finish the copies before emitting the report that refers to them.
    try:
        OUT.mkdir(exist_ok=True)
        (OUT / f"receipts-{stamp}.jsonl").write_bytes(receipts_raw)
        (OUT / f"driver-state-{stamp}.txt").write_bytes(state_raw)
        (OUT / f"SHA256-MANIFEST-{stamp}.txt").write_bytes(manifest_raw)
        components = OUT / f"manifest-components-{stamp}"
        components.mkdir(exist_ok=True)
        for number, (_, raw) in enumerate(manifest_parts, 1):
            (components / f"{number}.txt").write_bytes(raw)
        if prov_raw is not None:
            (OUT / f"provenance-note-{stamp}.txt").write_bytes(prov_raw)
        dest.write_text("\n".join(L) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"cannot write evidence bundle: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {dest.relative_to(HERE.parent)}")
    print(f"  {len(built)} pages, {human(total)} of builds, {len(tarballs)} manifest entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
