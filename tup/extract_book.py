#!/usr/bin/env python3
"""extract_book.py: turn an LFS book into ordered, driver-runnable scripts.

Maintained extraction is OFFLINE, explicit and separate from the old books:

    python3 tup/extract_book.py --arch x86_64 --version 13.1 --init systemd \
      --profile lfs-13.1-systemd \
      --snapshot tup/extraction/13.1-systemd/LFS-BOOK-13.1.tar.xz \
      --snapshot-metadata tup/extraction/13.1-systemd/snapshot.json \
      --audit-profile tup/extraction/13.1-systemd/audit-profile.json

The reviewed inventory preserves every command block; unresolved execution
choices require named overrides. An observed archive SHA256 is not publisher
authentication. Use --check for byte-for-byte regeneration validation.

Historical online extraction (does not select the maintained profile):

    python3 tup/extract_book.py 5 6 7 8 9 10                # arm64 book -> tup/book/
    python3 tup/extract_book.py --arch x86_64 5 6 7 8 9 10  # x86 12.4 book -> tup/book-x86_64/

For every page in each chapter (in TOC order) this writes
<bookdir>/chNN/MM-<page>.sh containing that page's <pre class="userinput">
blocks, verbatim and in order, with a header naming the page title and URL.
The driver, not this file, decides execution context (lfs user / chroot).

Two books, one extractor. The arm64 edition (xry111's r12.4 fork) and the
official x86 12.4 book share TOC shape and page classes but NOT page
numbering: x86 chapter 8 has 85 pages where arm64 has 87, so the same page
name sits at a different MM- prefix in each. That is why overrides are
matched by page NAME and chapter, never by number (see driver.sh). Each
book directory carries a BOOK-SOURCE file naming the arch, the base URL and
the fetch date, so a receipt can say which book's bytes were run.

WHAT IS AND IS NOT AUTOMATED, stated plainly:
  - Command blocks are the book's own bytes. Nothing is paraphrased.
  - Package pages (title like "5.5. GCC-15.2.0 - Pass 1") get tarball
    extract/cd/cleanup WRAPPING from the driver, matching the book's standing
    instruction ("for each package: extract, enter, build, delete") which the
    book states once in prose rather than per-page.
  - Blocks that invoke test suites (make check / make -k check / make test)
    are wrapped in a tup_tests guard. Policy ruling 2026-08-31: glibc, gcc,
    binutils suites run; everything else is receipted as SKIPPED, never
    silently dropped.
  - A file in tup/overrides/<page>.sh REPLACES the extracted page entirely.
    That is the only sanctioned way to handle the book's interactive moments
    (root passwd, make menuconfig, GRUB); an override is a visible, diffable
    decision; an inline edit to book/ would be a silent one. book/ is
    regenerated at will and never hand-edited.
"""
from __future__ import annotations

import html
import hashlib
from html.parser import HTMLParser
import json
import os
import re
import shlex
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

BOOKS = {
    "arm64": "https://www.linuxfromscratch.org/~xry111/lfs/view/arm64/",
    "x86_64": "https://www.linuxfromscratch.org/lfs/view/12.4/",
}
HERE = Path(__file__).resolve().parent
BOOKDIRS = {"arm64": HERE / "book", "x86_64": HERE / "book-x86_64"}
# Set in main() from --arch; module-level so the helpers below stay simple.
BASE = BOOKS["arm64"]
BOOK = BOOKDIRS["arm64"]

# Test invocations are not spelled one way. The book writes `make check`,
# `make -k check`, `make -j1 test`, `make NON_ROOT_USERNAME=tester check-root`,
# and `su tester -c "... make -j1 test"`. A pattern that only knew the first
# two let vim's suite run unguarded despite vim not being in TUP_TESTS, and it
# failed the build 210 seconds in with its output redirected to a file, so the
# log showed no error at all. Match `make` followed by anything up to the next
# command separator, then check or test.
TEST_RE = re.compile(
    r"\b(?:make|ninja|meson)\b[^;&|\n]*?\b(?:check|test)(?:[-_]\w+)*\b"
    r"|\b(?:bash|sh)\s+(?:\./)?tests/run\.sh\b"
    r"|(?:^|[;&|\n]\s*)ctest\b")
# The package is found ANYWHERE in the title ("Linux-6.17.3 API Headers",
# "Libelf from Elfutils-0.193", "GCC-15.2.0 - Pass 2" are all real), names may
# contain hyphens and colons, and the classification is settled by resolving
# against the wget-list's ACTUAL filenames; an unresolved package page gets a
# loud WARNING, never a silent demotion to action-page (the linux-headers
# failure that taught this cost a chain restart).
TITLE_PKG_RE = re.compile(r"([A-Za-z][A-Za-z0-9_+:.-]*?)-(\d[\w.-]*\w)")
NAME_FIXUPS = {"xml::parser": "xml-parser", "flit-core": "flit_core",
               "d-bus": "dbus", "sqlite": "sqlite-autoconf"}


def load_tarballs() -> list[str]:
    txt = fetch(BASE + "wget-list-sysv")
    return [u.rsplit("/", 1)[-1] for u in txt.split() if "/" in u]


def resolve_pkg(title: str, tarballs: list[str]) -> str:
    for m in TITLE_PKG_RE.finditer(title):
        name = NAME_FIXUPS.get(m.group(1).lower(), m.group(1).lower())
        for stem in (f"{name}-{m.group(2)}".lower(),
                     f"{name}{m.group(2)}".lower()):   # tcl8.6.17, expect5.45.4
            for t in tarballs:
                tl = t.lower()
                if tl.startswith((stem + ".tar", stem + ".tgz", stem + "-src")):
                    return t
    return ""


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


class BookHTML(HTMLParser):
    """Read rendered DocBook command blocks and actual TOCs, not navigation.

    The pinned book is strict UTF-8. Entities become the displayed command
    text; no shell rewrite, diagnostic suppression, or choice is made here.
    """
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.in_title = False
        self.toc_depth = 0
        self.toc_links = []
        self.pre_class = None
        self.pre_parts = []
        self.replaceable = False
        self.prose = []
        self.blocks = []
        self.feed(text)
        self.close()
        if self.pre_class is not None or self.toc_depth:
            raise ValueError("unclosed book command block or table of contents")
        self.title = re.sub(r"\s+", " ", "".join(self.title_parts)).strip()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())
        if tag == "title":
            self.in_title = True
        if tag == "div" and (self.toc_depth or "toc" in classes):
            self.toc_depth += 1
        if tag == "a" and self.toc_depth and "href" in attrs:
            self.toc_links.append(attrs["href"])
        if tag == "pre":
            if self.pre_class is not None:
                raise ValueError("nested book command block")
            if classes & {"userinput", "root"}:
                self.pre_class = "root" if "root" in classes else "userinput"
            elif classes == {"screen"}:
                self.pre_class = "screen"
            else:
                raise ValueError("unreviewed pre class in book")
            self.pre_parts = []
            self.replaceable = False
        if self.pre_class and "replaceable" in classes:
            self.replaceable = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "div" and self.toc_depth:
            self.toc_depth -= 1
        if tag == "pre":
            if self.pre_class is None:
                raise ValueError("unmatched book command block")
            command = "".join(self.pre_parts).strip("\n")
            if self.pre_class != "screen":
                if not command.strip():
                    raise ValueError("empty book command block")
                if re.search(r"^# TUP_(?:BLOCK_|BOOK_COMMANDS_|REQUIRES_OVERRIDE)", command, re.M):
                    raise ValueError("reserved TUP marker inside book command")
                self.blocks.append({"index": len(self.blocks) + 1,
                                    "text": command, "sha256": digest_bytes(command.encode()),
                                    "source_class": self.pre_class,
                                    "replaceable": self.replaceable,
                                    "context": re.sub(r"\s+", " ", "".join(self.prose)).strip()})
                self.prose = []
            self.pre_class = None

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self.pre_class is not None:
            self.pre_parts.append(data)
        else:
            self.prose.append(data)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def toc_pages(chapter: int, read=None) -> list[str]:
    """Require ordered agreement between master and chapter TOCs; fail closed."""
    read = read or (lambda name: fetch(BASE + name))
    directory = f"chapter{chapter:02d}"

    def page_links(text, master):
        links = []
        bare_seen = set()
        for href in BookHTML(text).toc_links:
            target, _, fragment = href.partition("#")
            if master:
                if not target.startswith(directory + "/"):
                    continue
                target = target.removeprefix(directory + "/")
            if target == directory + ".html":
                continue
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*\.html", target):
                raise ValueError(f"unsafe/unrecognized chapter TOC link: {href}")
            if not fragment:
                if target in bare_seen:
                    raise ValueError(f"duplicate chapter TOC link: {href}")
                bare_seen.add(target)
            if target not in links:
                links.append(target)
        return links

    master = page_links(read("index.html"), True)
    local = page_links(read(f"{directory}/{directory}.html"), False)
    if not master or master != local:
        raise ValueError(f"chapter {chapter} page order/count disagrees: master={master}, chapter={local}")
    return [directory + "/" + name for name in master]


def extract(page_html: str) -> tuple[str, list[str]]:
    t = re.search(r"<title>\s*(.*?)\s*</title>", page_html, re.S)
    title = html.unescape(re.sub(r"\s+", " ", t.group(1))) if t else "?"
    title = title.replace(" ", " ")
    # `userinput` is not the only class the book uses for COMMANDS. ch09's
    # etcshells page is a single <pre class="root"> block, so extracting only
    # userinput produced a 140-byte page with no commands at all and /etc/shells
    # would never have been written. `screen` is deliberately excluded; that
    # class is sample OUTPUT, and running it would be nonsense.
    blocks = [html.unescape(re.sub(r"<[^>]+>", "", b)).strip()
              for b in re.findall(r'<pre class="(?:userinput|root)">(.*?)</pre>',
                                  page_html, re.S)]
    return title, blocks


# Book pages carry DIAGNOSTIC greps, "grep '^FAIL:' $(find -name '*.log')",
# "grep 'Timed out' ...", the toolchain sanity greps in chapters 5 and 6.
# They exist for a human to READ. grep exits 1 when it matches nothing, so
# under `set -e` the good outcome (no failures, no timeouts) aborts the build
# Measured three separate times tonight, on glibc, on binutils, and on the
# chapter-5 sanity checks. They are advisory output, not assertions, so the
# driver prints them and does not gate on them. If a check should GATE, it
# needs an explicit assertion; the book does not provide one, and neither
# does this transformation pretend to.
# `awk` joins `grep` here for the same reason plus one more: gmp's page
# summarises its test log with awk AFTER the test block, so SKIPPING the
# tests leaves the summariser reading a file that was never created
# (measured: "awk: fatal: cannot open file `gmp-check-log`"). A summary of
# output that does not exist is advisory by definition.
DIAG_RE = re.compile(r"^(grep|awk)\b(?!.*\|\|)")


def guard_diagnostics(block: str) -> str:
    out = []
    for line in block.splitlines():
        if DIAG_RE.match(line) and not line.rstrip().endswith("\\"):
            out.append(line + "   || true   # advisory: see extract_book.py")
        else:
            out.append(line)
    return "\n".join(out)


def guard_tests(block: str, pkg: str) -> str:
    if not TEST_RE.search(block):
        return block
    return (f'if tup_tests_enabled "{pkg}"; then\n{block}\n'
            f'else tup_receipt_skip_tests "{pkg}"; fi')


MAINTAINED = {"arch": "x86_64", "version": "13.1", "init": "systemd",
              "profile": "lfs-13.1-systemd"}
MAINTAINED_BASE = "https://www.linuxfromscratch.org/lfs/view/13.1-systemd/"
SNAPSHOT_URL = "https://www.linuxfromscratch.org/lfs/downloads/13.1-systemd/LFS-BOOK-13.1.tar.xz"
BLOCK_KINDS = {"command", "test", "build-test", "test-setup", "test-cleanup", "diagnostic", "example", "optional", "interactive", "platform"}


class OfflineBook:
    """Hash the original archive, then read regular members without extraction."""
    def __init__(self, path: Path, metadata: dict):
        raw = path.read_bytes()
        if digest_bytes(raw) != metadata.get("sha256") or len(raw) != metadata.get("size_bytes"):
            raise ValueError("book snapshot digest/size mismatch")
        if metadata.get("url") != SNAPSHOT_URL or metadata.get("resolved_url") != SNAPSHOT_URL:
            raise ValueError("unsupported book snapshot URL")
        # Merely supplying a string 'verified' must never upgrade a downloaded
        # checksum observation to authenticated publisher evidence.
        if metadata.get("authentication") != "observed-integrity":
            raise ValueError("unsupported book authentication assertion")
        self.files = {}
        names = set()
        total = 0
        import io
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
            for member in archive:
                name = member.name.rstrip("/") if member.isdir() else member.name
                parts = PurePosixPath(name).parts
                if (not parts or parts[0] != "13.1" or ".." in parts
                        or str(PurePosixPath(name)) != name or "\\" in name
                        or name in names or not (member.isdir() or member.isfile())):
                    raise ValueError(f"unsafe/duplicate snapshot member: {name}")
                names.add(name)
                if len(names) > 10000 or member.size > 4 * 1024 * 1024:
                    raise ValueError("book snapshot member limit exceeded")
                if member.isfile():
                    total += member.size
                    if total > 50 * 1024 * 1024:
                        raise ValueError("book snapshot size limit exceeded")
                    self.files[name.removeprefix("13.1/")] = archive.extractfile(member).read()

    def read(self, name: str) -> str:
        try:
            return self.files[name].decode("utf-8", errors="strict")
        except KeyError as error:
            raise ValueError(f"snapshot member missing: {name}") from error


def parse_downloads(text: str) -> list[str]:
    from urllib.parse import urlsplit
    names = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        url = urlsplit(line)
        name = PurePosixPath(url.path).name
        if (url.scheme not in {"http", "https", "ftp"} or not url.netloc
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", name)):
            raise ValueError(f"invalid source-list entry: {line}")
        if name in names:
            raise ValueError(f"ambiguous duplicate source filename: {name}")
        names.append(name)
    if not names:
        raise ValueError("empty source download list")
    return names


def render_offline(snapshot: Path, metadata_path: Path, audit_path: Path,
                   identity: dict) -> dict[str, bytes]:
    """Validate the complete pinned extraction before publishing any files.

    The audit is a versioned review input, not an inferred build policy. It
    binds exact page order, HTML bytes, displayed command bytes and each
    block's role. A changed page needs another explicit audit. The original
    archive remains available for the prose/alternatives and copyright terms.
    """
    if identity != MAINTAINED:
        raise ValueError("unsupported version/init/architecture/extraction profile")
    metadata_raw = metadata_path.read_bytes()
    audit_raw = audit_path.read_bytes()
    metadata = json.loads(metadata_raw)
    audit = json.loads(audit_raw)
    if audit.get("schema") != "tup.book-audit.v1" or audit.get("identity") != identity:
        raise ValueError("audit profile identity/schema mismatch")
    if audit.get("snapshot_sha256") != metadata.get("sha256"):
        raise ValueError("audit profile is bound to a different book snapshot")
    book = OfflineBook(snapshot, metadata)
    if "Version 13.1-systemd" not in book.read("index.html"):
        raise ValueError("book version/init banner mismatch")
    download_raw = book.files.get("wget-list-systemd")
    if download_raw is None:
        raise ValueError("systemd source list missing; refusing SysV fallback")
    tarballs = parse_downloads(download_raw.decode("utf-8", errors="strict"))
    chapters = {f"ch{ch:02d}": toc_pages(ch, book.read) for ch in range(5, 12)}
    if chapters != audit.get("chapters"):
        raise ValueError("audited chapter names/order differ from book")
    all_pages = [page for pages in chapters.values() for page in pages]
    if set(all_pages) != set(audit.get("pages", {})):
        raise ValueError("audit page coverage differs from book")
    source_values = {**identity, "base": MAINTAINED_BASE,
                     "snapshot_url": SNAPSHOT_URL, "snapshot_sha256": metadata["sha256"],
                     "snapshot_metadata_sha256": digest_bytes(metadata_raw),
                     "audit_profile_sha256": digest_bytes(audit_raw),
                     "authentication": "observed-integrity",
                     "wget_list": "wget-list-systemd",
                     "wget_list_sha256": digest_bytes(download_raw),
                     "extractor_sha256": digest_bytes(Path(__file__).read_bytes())}
    source_raw = "".join(f"{key}={value}\n" for key, value in source_values.items()).encode()
    files = {"BOOK-SOURCE": source_raw, ".gitattributes": b"* -text\n"}
    manifest = {"schema": "tup.book-extraction.v1", "identity": identity,
                "book_source_sha256": digest_bytes(source_raw),
                "snapshot": metadata, "audit_profile_sha256": digest_bytes(audit_raw),
                "source_list": "wget-list-systemd", "source_count": len(tarballs),
                "chapters": {}, "pages": {}}
    for chapter, pages in chapters.items():
        order = []
        for number, source in enumerate(pages, 1):
            raw = book.files[source]
            parsed = BookHTML(raw.decode("utf-8", errors="strict"))
            review = audit["pages"][source]
            if not parsed.title or digest_bytes(raw) != review.get("html_sha256"):
                raise ValueError(f"page HTML/title differs from audit: {source}")
            if len(parsed.blocks) != len(review.get("blocks", [])):
                raise ValueError(f"command block count differs from audit: {source}")
            reasons = review.get("requires_override")
            if (not isinstance(reasons, list) or any(not isinstance(x, str) or not x for x in reasons)
                    or not isinstance(review.get("review"), str) or not review["review"]):
                raise ValueError(f"missing explicit page review: {source}")
            tarball = resolve_pkg(parsed.title, tarballs)
            if not tarball and TITLE_PKG_RE.search(parsed.title):
                raise ValueError(f"unresolved package archive: {source}: {parsed.title}")
            name = PurePosixPath(source).stem
            script = f"{number:02d}-{name}.sh"
            order.append(script)
            page_key = f"{chapter}/{script}"
            lines = ["#!/bin/bash", f"# {parsed.title}", f"# {MAINTAINED_BASE}{source}",
                     f"# TUP_TARBALL={tarball}" if tarball else "# TUP_ACTION_PAGE"]
            if reasons:
                lines += ["# TUP_REQUIRES_OVERRIDE=" + ",".join(reasons),
                          "printf '%s\\n' " + shlex.quote(f"{page_key}: named override required: {', '.join(reasons)}") + " >&2",
                          "exit 97"]
                # Unselected examples may not even be syntactically valid
                # shell (e.g. <paper_size>). Keep their exact commands as
                # unreachable quoted data; native helpers select marked blocks.
                delimiter = "TUP_UNSELECTED_" + digest_bytes(raw)
                if any(delimiter in block["text"].splitlines() for block in parsed.blocks):
                    raise ValueError("reserved book-data delimiter collision")
                lines.append(": <<'" + delimiter + "'")
            lines += ["# TUP_BOOK_COMMANDS_BEGIN"]
            blocks = []
            for block, checked in zip(parsed.blocks, review["blocks"]):
                kind = checked.get("kind")
                if block["sha256"] != checked.get("sha256") or kind not in BLOCK_KINDS:
                    raise ValueError(f"command block identity/role differs from audit: {source}/{block['index']}")
                if (block["replaceable"] or kind in {"example", "optional", "interactive", "platform", "diagnostic", "test-setup", "test-cleanup"}) and not reasons:
                    raise ValueError(f"unresolved command requires named override: {source}/{block['index']}")
                if TEST_RE.search(block["text"]) and kind not in {"test", "build-test", "example", "optional", "platform"}:
                    raise ValueError(f"suite command not classified as test: {source}/{block['index']}")
                # Markers enclose EXACT displayed command text. Test wrappers
                # live outside them so named overrides can select raw blocks.
                marker = f"{block['index']:03d}"
                rendered = f"# TUP_BLOCK_BEGIN={marker}\n{block['text']}\n# TUP_BLOCK_END={marker}"
                if kind == "test":
                    rendered = (f'if tup_tests_enabled "{name}"; then\n{rendered}\n'
                                f'else tup_receipt_skip_tests "{page_key}:block-{marker}"; fi')
                lines += ["", rendered]
                blocks.append({key: value for key, value in block.items() if key != "text"} | {"kind": kind, "review": checked.get("review", "")})
            if reasons:
                lines += [delimiter]
            script_raw = ("\n".join(lines) + "\n").encode("utf-8")
            files[page_key] = script_raw
            manifest["pages"][page_key] = {"source_page": source, "title": parsed.title,
                "source_html_sha256": digest_bytes(raw), "script_sha256": digest_bytes(script_raw),
                "tarball": tarball or None, "requires_override": reasons,
                "review": review["review"], "blocks": blocks}
        files[f"{chapter}/ORDER"] = ("\n".join(order) + "\n").encode()
        manifest["chapters"][chapter] = order
    files["EXTRACTION.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return files


def publish_extraction(files: dict[str, bytes], destination: Path, check=False):
    destination = destination.resolve()
    for historical in (HERE / "book", HERE / "book-x86_64"):
        if destination == historical or historical in destination.parents or destination in historical.parents:
            raise ValueError("historical generated books cannot be replaced")
    if destination.exists():
        if not destination.is_dir() or any(p.is_symlink() for p in destination.rglob("*")):
            raise ValueError("existing extraction contains non-directory root or symlinks")
        existing = {p.relative_to(destination).as_posix(): p.read_bytes()
                    for p in destination.rglob("*") if p.is_file()}
        if existing != files:
            raise ValueError("existing extraction differs; choose a fresh output directory")
        return
    if check:
        raise ValueError("extraction output missing")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tup-extract-book-", dir=destination.parent) as staging:
        stage = Path(staging)
        for name, raw in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        # Same-parent rename publishes only a fully validated generated tree.
        os.rename(stage, destination)


def offline_main(argv) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Extract the audited x86_64 LFS 13.1-systemd snapshot offline")
    for key in MAINTAINED:
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--snapshot-metadata", type=Path, required=True)
    parser.add_argument("--audit-profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "book-x86_64-13.1-systemd")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        files = render_offline(args.snapshot, args.snapshot_metadata, args.audit_profile,
                               {key: getattr(args, key) for key in MAINTAINED})
        publish_extraction(files, args.output, args.check)
    except (OSError, ValueError, tarfile.TarError) as error:
        print(f"extraction refused: {error}", file=sys.stderr)
        return 1
    print(f"audited offline extraction: {sum(name.endswith('.sh') for name in files)} pages; observed snapshot pin, no publisher-authentication claim")
    return 0


def legacy_main() -> int:
    global BASE, BOOK
    import argparse
    from datetime import datetime, timezone
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", choices=sorted(BOOKS), default="arm64",
                    help="which book to extract (default arm64)")
    ap.add_argument("chapters", nargs="*", type=int)
    args = ap.parse_args()
    BASE, BOOK = BOOKS[args.arch], BOOKDIRS[args.arch]
    chapters = args.chapters or [5, 6, 7, 8, 9, 10]
    tarballs = load_tarballs()
    BOOK.mkdir(parents=True, exist_ok=True)
    (BOOK / "BOOK-SOURCE").write_text(
        f"arch={args.arch}\nbase={BASE}\n"
        f"fetched={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n",
        encoding="utf-8")
    for ch in chapters:
        outdir = BOOK / f"ch{ch:02d}"
        outdir.mkdir(parents=True, exist_ok=True)
        pages = toc_pages(ch)
        manifest = []
        for i, p in enumerate(pages, 1):
            title, blocks = extract(fetch(BASE + p))
            name = Path(p).stem
            tarball = resolve_pkg(title, tarballs)
            if not tarball and TITLE_PKG_RE.search(title):
                print(f"  WARNING ch{ch:02d}/{name}: title names a package "
                      f"but no wget-list tarball resolves: {title!r}")
            body = "\n\n".join(guard_diagnostics(guard_tests(b, name)) for b in blocks)
            script = (f"# {title}\n# {BASE}{p}\n"
                      + (f"# TUP_TARBALL={tarball}\n" if tarball
                         else "# TUP_ACTION_PAGE\n")
                      + "\n" + body + "\n")
            (outdir / f"{i:02d}-{name}.sh").write_text(script, encoding="utf-8")
            manifest.append(f"{i:02d}-{name}.sh")
            print(f"  ch{ch:02d}/{i:02d}-{name}.sh  "
                  f"[{tarball or 'action'}] {len(blocks)} blocks")
        (outdir / "ORDER").write_text("\n".join(manifest) + "\n", encoding="utf-8")

        # COUNT AGAINST THE BOOK'S OWN CHAPTER INDEX. Every page-dropping bug
        # in this extractor has been invisible in its output and obvious in
        # its arithmetic; this is the check that makes the arithmetic
        # automatic instead of something someone remembers to do.
        try:
            cidx = fetch(f"{BASE}chapter{ch:02d}/chapter{ch:02d}.html")
            listed = {m.group(1) for m in re.finditer(
                r'href=\s*"([a-zA-Z0-9+._-]+\.html)"', cidx)
                if not m.group(1).startswith("chapter")}
            got = {p.rsplit("/", 1)[-1] for p in pages}
            lost = sorted(listed - got)
            if lost:
                print(f"  !! ch{ch:02d}: {len(lost)} page(s) in the book's own "
                      f"index are MISSING from this extraction: {', '.join(lost)}")
                return 1
            print(f"  ch{ch:02d}: {len(got)} pages, matches the book's index")
        except Exception as e:                            # noqa: BLE001
            print(f"  ch{ch:02d}: could not verify against the chapter index ({e})")
    return 0


def main() -> int:
    if any(arg.startswith(("--version", "--init", "--profile", "--snapshot", "--audit-profile", "--output", "--check")) for arg in sys.argv[1:]):
        return offline_main(sys.argv[1:])
    return legacy_main()


if __name__ == "__main__":
    raise SystemExit(main())
