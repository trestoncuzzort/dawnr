"""make_corpus.py — build a training corpus out of your own files.

Point it at a folder. It concatenates every matching text file into corpus.txt,
which is what train.py and studio.py learn from. Nothing is downloaded and
nothing leaves your machine.

    python make_corpus.py --src "C:/my/writing"
    python make_corpus.py --src ./notes --ext .md .txt
    python make_corpus.py --src . --ext .py            # train on code

Your corpus IS your vocabulary — the tokenizer is built from exactly the
characters in these files (see data.py).
"""
from __future__ import annotations

import argparse
from pathlib import Path


def _ingest():
    """ingest.py, imported on use. It is the ONE thing allowed to read a file.

    Imported on use rather than at module scope because start_studio.py imports
    `is_trainable_file` from this module at ITS module scope, so a module-level
    `import ingest` would stop the double-click path from LOADING rather than
    from reading. Deferred, importing this module still works and the failure
    lands on the call that actually needed a file read.

    There is deliberately NO fallback: reading a user's file the other way is
    the bug this indirection exists to remove, so a second reader here would
    re-create the drift it is removing. Same choice, for the same reason, as
    home.py's reader().
    """
    import ingest  # noqa: PLC0415
    return ingest


# Kept only as the default for `--ext`, which is now a FILTER you can opt into.
# It is no longer the gate: by default any file whose CONTENT is text gets in.
DEFAULT_EXTS = [".txt", ".md", ".py"]

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".idea", ".vscode"}

# Extensions that are always binary. Checked only to avoid reading large media
# files off disk; the real decision is made on bytes, so an unknown extension is
# never rejected for being unknown.
#
# THIS SET IS THE ONE REAL DUPLICATE LEFT, and it is named rather than hidden.
# ingest.can_train_on makes the decision now, but the contract is
# `can_train_on(path) -> bool` with no channel for a REASON, and this file's
# whole report is a tally of reasons ("3 file(s): binary file type (.png)").
# So ingest owns the verdict and this owns the wording, which costs one shared
# list of extensions. If ingest ever returns a reason, delete this and use it.
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tif", ".tiff",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac", ".ogg",
    ".zip", ".gz", ".tar", ".7z", ".rar", ".bz2", ".xz",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".obj", ".class",
    ".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".npy", ".npz",
    ".pdf", ".docx", ".xlsx", ".pptx", ".sqlite", ".db", ".parquet",
}


# The next two rules no longer decide anything here: ingest.py owns the gate
# (can_train_on) and the read (read_any), which is the point — one
# implementation instead of two that can drift. They survive because
# test_ingest.py imports them from this module by name and that file is not ours
# to edit, so moving them outright would have broken eleven passing tests to no
# purpose. `text_is_readable` below is the exception and is still live: main()
# applies it to the whole decoded file, because "did this decode" and "can a
# character model read this" are different questions and the contract answers
# only the first. A NUL decodes perfectly well as U+0000 and is still not text.
def trim_to_char_boundary(data: bytes) -> bytes:
    """Drop a trailing UTF-8 sequence that a fixed-size read cut in half.

    THE BUG THIS CLOSES. `is_trainable_file` decides a whole-file property from
    the first `probe_bytes`. If that boundary lands inside a multi-byte
    character, the probe is not valid UTF-8 even though the file is, so a
    perfectly good text file was refused as "binary or undecodable". Measured
    against the pre-fix code, 200 synthetic files per script, lengths 9-40 kB:

        CJK (3-byte chars)        refused 100.0%   <- deterministic, not sampling
        Cyrillic (2-byte chars)   refused  45.5%
        EU accented ~10% non-ascii refused 18.0%
        pure ASCII                refused   0.0%

    CJK is 100% because with 3-byte characters the probe boundary is almost
    never a character boundary. Every Japanese, Chinese or Korean log over 8 kB
    was refused, by the same tool whose whole point is training on anything.

    THE CLASS, not the instance: any fixed-size read used to decide a property
    of the whole file has to be cut back to a unit boundary before it is
    decoded. This is that cut, done once, where the probe is taken.
    """
    # At most 4 bytes back: a 4-byte sequence can trail 3 continuation bytes.
    for back in range(1, min(4, len(data)) + 1):
        b = data[-back]
        if b < 0x80:
            # ASCII. At back == 1 the probe ends on a clean boundary; further
            # back it means a continuation byte with no lead, which is genuinely
            # malformed and must stay in so the text rule can refuse it.
            return data
        if b >= 0xC0:
            # 0xC0/0xC1 are overlong forms and 0xF5-0xFF are out of range: none
            # of them can start a character, so they are corruption rather than
            # a cut-off sequence and must stay in to be refused. Trimming them
            # would quietly turn malformed bytes into "text ending early".
            if not 0xC2 <= b <= 0xF4:
                return data
            need = 2 if b < 0xE0 else (3 if b < 0xF0 else 4)
            return data[:-back] if back < need else data
        # 0x80-0xBF: continuation byte, keep walking back to find the lead.
    return data


def text_is_readable(text: str) -> bool:
    """The text rule itself, on decoded characters. One definition.

    Kept separate from `looks_like_text` so the same rule can be applied to a
    byte probe (below) and to a fully decoded file (`main`), without a second
    copy of the thresholds. A probe is a SAMPLE: anything it says is true of the
    first few kB and of nothing else, which is how a NUL past byte 8192 got in.
    """
    if not text:
        return False
    if "\x00" in text:
        return False
    printable = sum(c.isprintable() or c in "\n\r\t" for c in text)
    return printable / len(text) >= 0.90


def looks_like_text(data: bytes) -> bool:
    """Decide from CONTENT whether this is something a character model can read.

    THE POINT OF THIS FUNCTION. Filtering by extension answers "is this one of the
    three file types we thought of?", which is the wrong question for a tool whose
    goal is to train on anything you have. Industrial and commercial data arrives
    as .csv, .jsonl, .log, .tsv, .ndjson, .yaml, .sql, .ini, .srt, or no extension
    at all, and every one of those is plain text a character-level tokenizer reads
    perfectly well. Meanwhile a .bin is not excluded because of its name — it is
    excluded because its bytes are not text.

    Two rules, both cheap:
      1. A NUL byte means binary. Text files do not contain them.
      2. After decoding, the share of characters that are printable, whitespace,
         or common punctuation must be high. This catches the mojibake case that
         `errors="ignore"` would otherwise turn into thousands of junk characters
         in your vocabulary — which is not a cosmetic problem, because the
         tokenizer IS the set of characters in your corpus.
    """
    if not data:
        return False
    if b"\x00" in data:
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return text_is_readable(text)


def is_trainable_file(path: Path, exts: set[str] | None = None,
                      probe_bytes: int = 8192) -> tuple[bool, str]:
    """(accepted, reason). One implementation, imported by every caller.

    start_studio.py used to carry its own `EXTS = {".txt", ".md", ".py"}` set, so
    the double-click path — the one aimed at people who never open a terminal —
    silently ignored every CSV and log file dropped into the folder and then
    reported "no files". A second copy of a rule is a second place for it to be
    wrong, and this repo has paid that bill before.

    WHAT IS STILL DECIDED HERE, and what is not. The three checks above the
    content test are about THIS COMMAND LINE — an ignored directory, the --ext
    filter, a name that says "media" — and ingest knows nothing about any of
    them. The content question is the one that could drift, so it is asked of
    ingest.can_train_on and answered in exactly one place. `probe_bytes` is kept
    in the signature because callers pass it, but ingest owns the probe now, so
    a caller that narrows it is telling this function something it can no longer
    act on; it is accepted and ignored rather than silently reinterpreted.
    """
    if not path.is_file():
        return False, "not a file"
    if any(seg in SKIP_DIRS for seg in path.parts):
        return False, "in an ignored directory"
    if exts is not None and path.suffix.lower() not in exts:
        return False, f"filtered out by --ext ({path.suffix or 'no extension'})"
    # BINARY_EXTS still refuses by name, EXCEPT for the container formats ingest
    # learned to open. .docx and .epub are zip archives, so they sit in
    # BINARY_EXTS and were refused here before can_train_on was ever consulted --
    # which meant the window read a Word document and this path skipped it
    # silently. The name check now defers to the one module that knows what can
    # actually be opened.
    if path.suffix.lower() in BINARY_EXTS and path.suffix.lower() not in _ingest().HANDLED_EXTS:
        return False, f"binary file type ({path.suffix})"
    try:
        # The cheap gate, and it must stay cheap: this answers a LISTING
        # question for a file picker, so it must not read whole media files off
        # disk. ingest.can_train_on is that probe. The reason string is
        # unchanged because the report is a tally of these exact words.
        if not _ingest().can_train_on(path):
            return False, "content is not text (binary or undecodable)"
    except OSError as e:
        return False, f"unreadable ({e.__class__.__name__})"
    return True, "text"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=".", help="folder to read (recursively)")
    ap.add_argument("--ext", nargs="*", default=None,
                    help="OPTIONAL filter, e.g. --ext .csv .log. By default every "
                         "file whose CONTENT is text is included regardless of "
                         "extension, which is what lets this train on anything "
                         "you have rather than the three types we guessed.")
    ap.add_argument("--out", default="corpus.txt")
    ap.add_argument("--min-chars", type=int, default=1,
                    help="skip files shorter than this")
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    if not src.is_dir():
        raise SystemExit(f"not a folder: {src}")
    exts = ({e.lower() if e.startswith(".") else "." + e.lower() for e in args.ext}
            if args.ext else None)

    parts, skipped = [], 0
    rejected: dict[str, int] = {}
    seen: set[str] = set()
    # Never eat your own output. Accepting files by CONTENT rather than extension
    # means `--src .` now reaches corpus.txt, and folding the corpus back into
    # itself doubles every document and quietly doubles the memorisation pressure
    # too. Cheap to prevent, confusing to diagnose.
    out_path = Path(args.out).resolve()
    for p in sorted(src.rglob("*")):
        if p.resolve() == out_path:
            continue
        ok, why = is_trainable_file(p, exts)
        if not ok:
            if p.is_file() and why != "in an ignored directory":
                rejected[why] = rejected.get(why, 0) + 1
            continue
        try:
            # No errors="ignore": a file that does not decode cleanly was already
            # rejected above, so silently mangling one here would only hide it.
            #
            # THAT SENTENCE IS NOW ingest.py's JOB, and it is the argument the
            # whole module exists to enforce: read_any either decodes a file
            # properly and names the encoding that worked, or it refuses and
            # says why — it never returns half-decoded text. This file used to
            # make that guarantee for itself with a strict read, which was
            # right but was only right HERE; train.py was reading the same kind
            # of file with errors="ignore" at the same time. One reader is the
            # fix. The refusal is tallied rather than printed per file because
            # this report is a count per reason, and read_any's sentence names
            # a single file.
            got = _ingest().read_any(p)
        except OSError:
            rejected["unreadable"] = rejected.get("unreadable", 0) + 1
            continue
        if got.text is None:
            # is_trainable_file already accepted the first 8 kB, so a refusal
            # here is by definition about what came after the probe window.
            why = "content is not text past the first 8 kB"
            rejected[why] = rejected.get(why, 0) + 1
            continue
        text = got.text
        # THE PROBE WAS A SAMPLE. is_trainable_file judged the first 8 kB and
        # nothing else; the whole file is in hand here, so the same rule gets
        # applied to all of it. A NUL past byte 8192 used to pass the gate and
        # land in the vocabulary of a character model, which is the mojibake
        # harm the rule exists to prevent, arriving after the probe window.
        if not text_is_readable(text):
            why = "content is not text past the first 8 kB"
            rejected[why] = rejected.get(why, 0) + 1
            continue
        if len(text) < args.min_chars:
            rejected[f"shorter than --min-chars ({args.min_chars})"] = \
                rejected.get(f"shorter than --min-chars ({args.min_chars})", 0) + 1
            continue
        # Exact-duplicate files add nothing but memorisation pressure.
        if text in seen:
            skipped += 1
            continue
        seen.add(text)
        parts.append(f"# file: {p.relative_to(src).as_posix()}\n{text}")

    if not parts:
        detail = "".join(f"\n  {n} file(s): {why}" for why, n in sorted(rejected.items()))
        raise SystemExit(f"no trainable text files under {src}{detail}"
                         if rejected else f"no files at all under {src}")

    out = Path(args.out)
    body = "\n\n".join(parts)
    out.write_text(body, encoding="utf-8")
    vocab = sorted(set(body))
    print(f"wrote {out}: {len(body):,} chars from {len(parts)} files "
          f"({len(vocab)} distinct characters -> that is your vocab size)")
    if skipped:
        print(f"skipped {skipped} exact-duplicate file(s)")
    # Say what was left out and why. A tool that silently ignores most of the
    # folder is indistinguishable from one that is broken.
    for why, n in sorted(rejected.items(), key=lambda kv: -kv[1]):
        print(f"skipped {n} file(s): {why}")

    # THE VOCABULARY IS A CONSEQUENCE OF THE DATA, and on arbitrary input it can
    # get expensive without anyone noticing. Every distinct character becomes a
    # row of the embedding table and a column of the output layer, so a corpus
    # carrying a few thousand rare glyphs makes a materially bigger, slower model
    # that has one or two examples of most of its own vocabulary.
    if len(vocab) > 300:
        rare = [c for c in vocab if body.count(c) < 10]
        print(f"\n[!] {len(vocab)} distinct characters is a large vocabulary for a "
              f"character model.\n    {len(rare)} of them appear fewer than 10 "
              f"times in the whole corpus.\n    Every one costs an embedding row "
              f"and an output column, and the rare ones\n    cannot be learned "
              f"from that few examples. Consider --ext to narrow the input,\n"
              f"    or removing the files that carry unusual symbols.")


if __name__ == "__main__":
    main()
