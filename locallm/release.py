#!/usr/bin/env python3
"""release.py — assemble the download: one zip a stranger unzips and runs.

    python3 locallm/release.py                  writes dist/locallm-0.2.0.zip
    python3 locallm/release.py --no-model       without the bundled checkpoint
    python3 locallm/release.py --out somewhere  writes somewhere/locallm-0.2.0.zip

WHY NOT THE REPOSITORY. The working tree is 3.8 GB, .git another 234 MB, and
fourteen files live in Git LFS, so a stranger who clones gets none of what they
wanted and most of what they did not. What they want is locallm/ plus a model
that already talks back, which is about 41 MB of zip.

WHY THE FILE LIST IS COMPUTED AND NOT TYPED. A hand-written list of modules is
wrong the first time somebody adds an import, and it is wrong silently: the zip
builds, the stranger unzips, and home.py dies on `import look` at the one moment
there is nobody to ask. So the list is the transitive import closure of the
programs a person actually starts, walked with ast, and a module in that closure
that is not on disk is a refusal rather than a missing member. The same walk is
what keeps the research record out: the closure of the eleven entry points is
fifteen modules, and none of them matches the study-script patterns below
(measured 2026-09-21; it was fourteen until ingest.py was split out of
make_corpus.py that morning, which is the point of counting it rather than
typing it).

DETERMINISM. Two builds of the same tree must give byte-identical zips, because
that is what makes the sha256 in MANIFEST.txt worth printing. Three things leak
the build environment into an archive — modification times, entry order from the
filesystem, and permissions from the caller's umask (reproducible-builds.org/
docs/archives/). zipfile stamps time.localtime() on any member written with a
plain string name and only honours a fixed stamp through an explicit ZipInfo
date_time (docs.python.org/3/library/zipfile.html), so every member here goes
through _member(): fixed 1980-01-01, name-sorted order, a fixed mode table, and
create_system pinned so the archive does not change with the platform. The
reproducible-builds advice is to touch the tree's mtimes to SOURCE_DATE_EPOCH
first; that was rejected because this file does not own the tree it reads and
other people are editing those files — normalising at write time touches nothing.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import re
import sys
import zipfile
from pathlib import Path
from typing import NamedTuple

VERSION = "0.2.0"

# Every path in the zip lives under this one folder, so unzipping in a downloads
# folder cannot scatter fourteen loose .py files across it.
TOP = f"locallm-{VERSION}"

HERE = Path(__file__).resolve().parent

# The model the scoreboard credits with 209 of 232 well-formed answers: the 10.9M
# round-4 arm, ckpt.pt 43,526,601 bytes and tokenizer.json 411 bytes as measured
# 2026-09-21. Kept relative to the repository root — an absolute path would name
# somebody's home directory, and this repository is public.
MODEL = Path("t") / "runs" / "2026-09-17" / "home-4080" / "models" / "model-r4"

# home.py's own INCLUDED constant. ready_made() looks for ckpt.pt and
# tokenizer.json inside HERE/"included-model", where HERE is home.py's folder, so
# the folder is a sibling of home.py in the zip and not a level down.
INCLUDED = "included-model"

# Everything locallm imports and does not ship. torch is 800 MB of wheel
# (github.com/pytorch/pytorch/issues/94262) and install.py fetches it on the
# machine that wants it; tokenizers is optional inside data.py; tkinterdnd2 is the
# optional drag-and-drop in home.py. The list is short on purpose: any other name
# that is neither the standard library nor a file beside home.py is a module
# somebody forgot, and the closure refuses instead of building a zip that dies on
# import. sys.stdlib_module_names is the standard library's own answer to "is this
# one of mine" (docs.python.org/3/library/sys.html#sys.stdlib_module_names) and
# needs Python 3.10; this is a build tool, not the shipped program, so that is a
# cheaper dependency here than a hand-kept list of module names.
EXTERNAL = frozenset({"torch", "tokenizers", "tkinterdnd2"})
STDLIB = frozenset(sys.stdlib_module_names)

# The programs a person starts. look.py is imported by home.py rather than run,
# and is named anyway so the closure cannot quietly lose the only module that
# draws anything.
ENTRY_POINTS = ("home.py", "look.py", "studio.py", "model.py", "data.py",
                "train.py", "checkpoint.py", "generate.py", "plain_generate.py",
                "make_corpus.py", "get_corpus.py")

# The research record: prereg arms, audits, probes, benchmarks and every test.
# They are how the numbers in the README were earned, and they are not a program
# a stranger runs. If the closure ever reaches one, that is a real finding about
# an import — the build stops and says which module, instead of shipping it.
RESEARCH = tuple(re.compile(p) for p in (
    r"run_.*_study\.py$", r"summarize_.*\.py$", r"probe_.*\.py$",
    r"audit_.*\.py$", r"bench_.*\.py$", r"measure_.*\.py$", r"latent_.*\.py$",
    r"research_model\.py$", r"train_factorial\.py$", r"train_distributed\.py$",
    r"score_execution\.py$", r"sample_.*\.py$", r"completion_batch\.py$",
    r"continue_from_checkpoint\.py$", r"next_latent\.py$", r"test_.*\.py$",
))

# A launcher that is not executable is a launcher a stranger cannot start on
# macOS or Linux. Everything else is data.
EXECUTABLE = 0o755
READABLE = 0o644

# The files a stranger reads or double-clicks, and the mode each needs. The three
# launcher names are not a guess: START-HERE.md's "Start it" table tells the
# reader to run ./start-linux.sh, start-macos.command or start-windows.bat, so
# these are the files that document has promised and a missing one is a front door
# that lies. A .sh or .command with mode 644 is a launcher that cannot be started
# on Linux or macOS, which is why the mode is in the table and not assumed.
#
# Listed by name rather than found by pattern so the three Windows launchers that
# predate this release — INSTALL.bat, "Train My AI.bat", "Check My Computer.bat" —
# stay out. They assume Python already on PATH and a connection to
# download.pytorch.org, and they drive install.py, which is not in the closure.
FRONT_DOOR = (
    ("START-HERE.md", READABLE),
    ("start-linux.sh", EXECUTABLE),
    ("start-macos.command", EXECUTABLE),
    ("start-windows.bat", EXECUTABLE),
)
LAUNCHERS = ("start-linux.sh", "start-macos.command", "start-windows.bat")

# Taken from the repository root, not from locallm/. locallm/LICENSE is seven
# lines saying the terms are "in the repository root (../LICENSE)", and there is
# no ../LICENSE in a zip — so the release shipped a pointer to nothing while
# START-HERE.md told the reader to read the terms before building anything on
# this. The licence asks for both of these by name: "Every copy or derivative you
# distribute must carry this license and the copyright notice above" (LICENSE
# 3(a)) and "The copyright notice, this license and the provenance files ... must
# not be removed from a copy or a derivative" (4(c)). NOTICE also carries the
# only contact for a commercial licence, which a research-use download needs.
#
# SHA256SUMS and its signature are the third provenance file and stay out: every
# path in them is a repository path, so `sha256sum -c` over them inside this zip
# fails on every line and would teach a stranger to distrust a sound download.
# MANIFEST.txt is this archive's own provenance instead.
ROOT_DOOR = (
    ("LICENSE", READABLE),
    ("NOTICE", READABLE),
)

# cmd.exe finds a label by seeking through the file, and with LF-only line
# endings a `goto :label` past a block boundary fails with "The system cannot
# find the batch label specified"
# (stackoverflow.com/questions/232651 — the accepted answer's two conditions are
# LF endings and a label across a block boundary, which is exactly this
# launcher's three error paths). The usual fix is `*.bat text eol=crlf` in
# .gitattributes, but locallm/.gitattributes is `* text=auto eol=lf`, so a clone
# hands the packer an LF file again. Normalising here instead means the zip is
# right whatever the checkout did, and it costs no determinism: the rule is
# applied to bytes, so two builds of one file give one member.
CRLF_MEMBERS = (".bat",)

# A DOS timestamp cannot hold anything earlier than this, and it is zipfile's own
# documented default for a ZipInfo nobody stamped.
FIXED_DATE = (1980, 1, 1, 0, 0, 0)

# create_system 3 is Unix. ZipInfo picks it from the building machine otherwise,
# which would make the same tree produce two different zips on two platforms.
UNIX = 3

# Explicit rather than None: zlib's default level is a library choice, and the
# compressed bytes are part of what the manifest hash promises.
LEVEL = 6


class ReleaseError(Exception):
    """Something needed is missing. Printed as a sentence, not a traceback."""


class Built(NamedTuple):
    path: Path
    size: int
    sha256: str
    members: list[str]
    notes: list[str]


def _imports(path: Path) -> set[str]:
    """Top-level module names this file imports, wherever the import sits.

    ast.walk and not a regex, and not the import machinery either: home.py
    imports studio.py inside a function on purpose, because studio.py is
    `import torch` at module scope and the window has to open on a machine that
    has never installed torch. A walk sees that one; importing home.py to ask
    would need tkinter, which is a separate package on Debian and Ubuntu.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def closure(src: Path = HERE, roots: tuple[str, ...] = ENTRY_POINTS) -> list[str]:
    """Every module the released programs import, transitively, sorted by name.

    An import is ours unless the standard library or EXTERNAL claims it, so a
    sibling that has been renamed or deleted is a refusal and not a silent pass
    for a third-party package — deciding by "is there a file of that name" would
    make a missing module look exactly like a missing dependency.
    """
    src = Path(src)
    asked = {name: "the release list" for name in roots}
    kept: set[str] = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in kept:
            continue
        path = src / name
        if not path.is_file():
            raise ReleaseError(
                f"{name} belongs in the release ({asked[name]} imports it) and "
                f"there is no such file in {src}")
        kept.add(name)
        for found in sorted(_imports(path)):
            if found in STDLIB or found in EXTERNAL:
                continue
            child = f"{found}.py"
            if not (src / child).is_file():
                raise ReleaseError(
                    f"{name} imports {found}, which is not in the standard "
                    f"library, is not one of the dependencies locallm expects to "
                    f"find installed ({', '.join(sorted(EXTERNAL))}), and is not "
                    f"a file beside it — either {child} is missing from {src} or "
                    f"it is a new dependency this build has never heard of")
            if child not in kept:
                asked.setdefault(child, name)
                pending.append(child)
    return sorted(kept)


def research(names: list[str]) -> list[str]:
    """Which of these are the study record rather than the program."""
    return [n for n in names if any(p.match(n) for p in RESEARCH)]


def _member(arc: str, mode: int) -> zipfile.ZipInfo:
    """A member header with nothing in it that varies between two builds."""
    info = zipfile.ZipInfo(f"{TOP}/{arc}", date_time=FIXED_DATE)
    info.create_system = UNIX
    info.external_attr = mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _launcher_notes(launchers: list[tuple[str, bytes]],
                    shipped: set[str]) -> list[str]:
    """Modules a launcher names that the zip does not contain.

    Not a refusal: a launcher may mention a file in prose. It is worth saying
    anyway, because the one failure this cannot survive is a double-click that
    runs `python3 install.py` against a zip with no install.py in it.

    The boundaries are load-bearing. Without them the pattern matched "docs.py"
    inside every launcher's citation of docs.python.org/3/library/tkinter.html,
    so all three launchers reported a module that does not exist on every single
    build — three false alarms a reader learns to scroll past, which is worse
    than saying nothing. \b will not do it: the character to exclude is the dot,
    and \b treats a dot as a boundary. A fixed-width [\\w.] class on each side is
    what re's own reference allows in a lookbehind
    (docs.python.org/3/library/re.html).
    """
    notes = []
    for name, blob in launchers:
        text = blob.decode("utf-8", errors="replace")
        for module in sorted(set(re.findall(
                r"(?<![\w.])([A-Za-z_][A-Za-z0-9_]*\.py)(?![\w.])", text))):
            if module not in shipped:
                notes.append(f"{name} names {module}, which the zip does not ship")
    return notes


def manifest(entries: list[tuple[str, bytes, int]], model: str) -> str:
    """Every shipped path with its size and sha256, and what produced them.

    A download cannot show its work, so this is how it proves it arrived whole:
    the hashes are of the bytes in the zip, the paths are the member names
    exactly, and the checkpoint is named rather than implied. Paths last on each
    line because a launcher name is allowed to contain spaces and a hash is not.
    """
    lines = [
        f"locallm {VERSION}",
        "",
        f"bundled model: {model}",
        f"built deterministically: every member stamped "
        f"{FIXED_DATE[0]:04d}-{FIXED_DATE[1]:02d}-{FIXED_DATE[2]:02d}, entries "
        f"sorted by name, so two builds of one tree are byte-identical",
        "",
        f"{'sha256':<64}  {'bytes':>11}  path",
    ]
    total = 0
    for arc, blob, _mode in entries:
        total += len(blob)
        lines.append(f"{hashlib.sha256(blob).hexdigest()}  {len(blob):>11}  "
                     f"{TOP}/{arc}")
    lines += ["",
              f"total: {len(entries)} files, {total:,} bytes before compression",
              "MANIFEST.txt is the only member not listed above: it cannot "
              "contain its own hash.",
              ""]
    return "\n".join(lines)


def build(out: str | Path | None = None, *, src: str | Path = HERE,
          model_dir: str | Path | None = None, include_model: bool = True,
          roots: tuple[str, ...] = ENTRY_POINTS) -> Built:
    """Write the zip and return what was in it. Raises ReleaseError, readably."""
    src = Path(src).resolve()
    root = src.parent
    out_dir = Path(out) if out is not None else root / "dist"
    model_path = Path(model_dir) if model_dir is not None else root / MODEL
    notes: list[str] = []

    modules = closure(src, roots)
    strays = research(modules)
    if strays:
        raise ReleaseError(
            "the import closure reaches the research record — "
            f"{', '.join(strays)} — which the release must not carry; fix the "
            "import rather than the file list")

    entries: list[tuple[str, bytes, int]] = [
        (name, (src / name).read_bytes(), READABLE) for name in modules]

    launchers = []
    for base, table in ((src, FRONT_DOOR), (root, ROOT_DOOR)):
        for name, mode in table:
            path = base / name
            if not path.is_file():
                notes.append(f"{name} is not in {base.name}/ — the zip goes out "
                             f"without a file a stranger is told to use")
                continue
            blob = path.read_bytes()
            if name.endswith(CRLF_MEMBERS):
                # Every ending CRLF and none doubled, whatever the checkout did.
                blob = blob.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            entries.append((name, blob, mode))
            if name in LAUNCHERS:
                launchers.append(name)

    if include_model:
        weights = b""
        for name in ("ckpt.pt", "tokenizer.json"):
            path = model_path / name
            if not path.is_file():
                raise ReleaseError(
                    f"the bundled model needs {name} and there is no such file "
                    f"at {path} — pass --model-dir to name another checkpoint "
                    f"folder, or --no-model to ship without one")
            blob = path.read_bytes()
            if name == "ckpt.pt":
                weights = blob
            entries.append((f"{INCLUDED}/{name}", blob, READABLE))
        try:
            where = model_path.relative_to(root).as_posix()
        except ValueError:      # a folder outside the tree: name it, not its path
            where = model_path.name
        model = (f"{where} — ckpt.pt {len(weights):,} bytes, "
                 f"sha256 {hashlib.sha256(weights).hexdigest()}")
    else:
        model = "none — built with --no-model, so train one or point step 4 at a "\
                "checkpoint of your own"

    notes += _launcher_notes([(n, b) for n, b, _ in entries if n in launchers],
                             {a for a, _, _ in entries})

    # Sorted before the manifest is written as well as after, so the list a
    # reader checks by eye is in the same order as the archive they checked it
    # against.
    entries.sort(key=lambda e: e[0])
    entries.append(("MANIFEST.txt", manifest(entries, model).encode("utf-8"),
                    READABLE))
    entries.sort(key=lambda e: e[0])

    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{TOP}.zip"
    # Built under a dot-name and renamed: a reader who unzips the half-written
    # file gets nothing at all, which is better than a zip missing the model.
    # Path.replace is os.replace, atomic within one filesystem
    # (docs.python.org/3/library/os.html#os.replace).
    part = out_dir / f".{TOP}.zip.part"
    try:
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED,
                             compresslevel=LEVEL) as zf:
            for arc, blob, mode in entries:
                zf.writestr(_member(arc, mode), blob)
        part.replace(final)
    finally:
        part.unlink(missing_ok=True)

    blob = final.read_bytes()
    return Built(final, len(blob), hashlib.sha256(blob).hexdigest(),
                 [f"{TOP}/{arc}" for arc, _, _ in entries], notes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Assemble the locallm release: one zip, one folder inside "
                    "it, a manifest that proves it arrived whole.")
    ap.add_argument("--out", default=None,
                    help="folder to write the zip into (default: dist/ next to "
                         "the locallm folder)")
    ap.add_argument("--no-model", action="store_true",
                    help="leave out the bundled checkpoint (43.5 MB of the zip)")
    ap.add_argument("--model-dir", default=None,
                    help="bundle this checkpoint folder instead of the "
                         "recorded one; needs ckpt.pt and tokenizer.json")
    args = ap.parse_args(argv)

    try:
        built = build(args.out, include_model=not args.no_model,
                      model_dir=args.model_dir)
    except ReleaseError as e:
        print(f"release: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        # --out pointed at a file, or a full disk. Same sentence, same exit code:
        # a build that cannot write is not different news from one that cannot read.
        print(f"release: {e}", file=sys.stderr)
        return 2

    for note in built.notes:
        print(f"release: {note}", file=sys.stderr)
    print(built.path)
    print(f"{len(built.members)} files, {built.size:,} bytes")
    print(f"sha256 {built.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
