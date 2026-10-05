"""Choosing files and moving, copying or removing exactly those (2026-10-05): a marker on the first line, a rule about
the name, the extension, a line inside each file, a set to back up under new names, a nested folder brought up a
level, the names themselves, numbered versions, and a skeleton described in words. Most draw a look-alike that must
stay as it is, and every file of the folder is named in `files` with its end text (a binary one with its bytes, by a
check of its own), so that one moved, changed or removed by mistake fails the task rather than passing it.

The expected end state is computed from the drawn files, as InterCode-Bash takes its expected file-system change
from a gold run (arXiv:2306.14898, section 3.3), and each request names the paths, separators and letter-case rules
the judge checks, as InterCode had to add them to NL2Bash's under-specified requests before those could be judged.

Left out of the group: making files executable or read-only. `selfcheck` puts a solution in place by writing contents
only, so no solution of such a task could be judged done; and `sh` carries a mode back only when it adds an x bit
(dawnr_agent/shell.py, apply), so read-only could not be done by the driver either. Numbered versions, where the
newest by number is not the last by spelling (v10 after v9), take its place. Nor does any family require an emptied
folder to be gone: selfcheck's prune only visits folders that still hold an entry, so a solution cannot remove one,
and flatten_with_prefix asks for the files alone."""
from __future__ import annotations

import datetime
import io
import zipfile

from dawnr_factory import PEOPLE, PLACES, STEMS, THINGS, family, say

VERBS = ("checked", "moved", "fixed", "ordered", "packed", "painted", "measured", "returned", "cleaned", "counted", "labelled", "borrowed")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
MAGIC = {".png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", ".jpg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01", ".gif": b"GIF89a", ".webp": b"RIFF\x40\x00\x00\x00WEBPVP8 ",
         ".mp3": b"ID3\x04\x00\x00\x00\x00\x00\x00", ".ogg": b"OggS\x00\x02\x00\x00", ".wav": b"RIFF\x40\x00\x00\x00WAVEfmt ", ".flac": b"fLaC\x00\x00\x00\x22"}


def _line(rng) -> str:
    return f"{rng.choice(PEOPLE)} {rng.choice(VERBS)} the {rng.choice(THINGS)} in {rng.choice(PLACES)}."


def _text(rng, n: int = 0) -> str:
    return "".join(_line(rng) + "\n" for _ in range(n or rng.randint(1, 3)))


def _title(rng) -> str:
    return f"{rng.choice(STEMS).title()} for {rng.choice(PLACES)}"


def _fresh(rng, used: set, make) -> str:
    """A name from make() that is not taken yet, and is from now on."""
    for _ in range(500):
        name = make()
        if name not in used:
            used.add(name)
            return name
    raise RuntimeError("no fresh name left")


def _and(items) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _zip(parts: dict) -> bytes:
    """A zip with a fixed time in its headers: zipfile stamps the hour it is written otherwise, and a task drawn
    twice from one seed must be the same bytes."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, text in parts.items():
            z.writestr(zipfile.ZipInfo(name, date_time=(2026, 3, 2, 9, 0, 0)), text)
    return out.getvalue()


def _content(rng, ext: str):
    """What a file of this kind holds: text for the text kinds, bytes that begin the way the real format does for the rest."""
    ext = ext.lower()
    if ext in MAGIC:
        return MAGIC[ext] + bytes(rng.randrange(256) for _ in range(rng.randint(48, 160)))
    if ext == ".pdf":
        import dawnr_tasks
        return dawnr_tasks.pdf_bytes(_title(rng), _line(rng))
    if ext == ".docx":
        body = "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in (_title(rng), _line(rng)))
        return _zip({"[Content_Types].xml": "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>",
                     "word/document.xml": f"<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body>{body}</w:body></w:document>"})
    if ext in (".odt", ".xlsx", ".zip"):
        inner = {".odt": "content.xml", ".xlsx": "xl/worksheets/sheet1.xml", ".zip": f"{rng.choice(STEMS)}.txt"}[ext]
        return _zip({**({"mimetype": "application/vnd.oasis.opendocument.text"} if ext == ".odt" else {}), inner: _text(rng)})
    if ext == ".svg":
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{rng.randint(16, 512)}" height="{rng.randint(16, 512)}"><circle r="{rng.randint(2, 9)}"/></svg>\n'
    if ext in (".csv", ".tsv"):
        sep = "," if ext == ".csv" else "\t"
        return f"item{sep}count\n" + "".join(f"{rng.choice(THINGS)}{sep}{rng.randint(1, 60)}\n" for _ in range(rng.randint(2, 4)))
    if ext == ".json":
        return f'{{"{rng.choice(THINGS)}": {rng.randint(1, 60)}, "place": "{rng.choice(PLACES)}"}}\n'
    code = {".py": f"print({rng.choice(THINGS)!r})\n", ".sh": f"#!/bin/sh\necho {rng.choice(THINGS)}\n", ".c": f"int {rng.choice(THINGS)}(void) {{ return {rng.randint(0, 9)}; }}\n",
            ".js": f"console.log('{rng.choice(THINGS)}');\n", ".ini": f"[{rng.choice(STEMS)}]\n{rng.choice(THINGS)} = {rng.randint(1, 60)}\n",
            ".html": f"<h1>{_title(rng)}</h1>\n", ".xml": f'<{rng.choice(THINGS)} count="{rng.randint(1, 60)}"/>\n'}
    return code.get(ext) or f"{_title(rng)}\n" + _text(rng)


def _end_state(start: dict, end: dict, check=None, answer: str = "Done.") -> tuple:
    """The judge's keys and a solution for a folder that must end as `end`: every path of either is named, text is
    compared exactly, and bytes by a check of their own (the judge's `files` reads text)."""
    binary = {rel: data for rel, data in end.items() if isinstance(data, bytes)}
    files = {**{rel: None for rel in start if rel not in end}, **{rel: ([] if isinstance(data, bytes) else data) for rel, data in end.items()}}
    checks = [check] if check else []
    if binary:
        checks.append(lambda work: [f"{rel} is missing or not the file it was" for rel, data in binary.items()
                                    if not (work / rel).is_file() or (work / rel).read_bytes() != data])
    expect = {"files": files, **({"fn": lambda work: [why for c in checks for why in c(work)]} if checks else {})}
    solution = {"answer": answer, "files": {**{rel: None for rel in start if rel not in end}, **{rel: data for rel, data in end.items() if start.get(rel) != data}}}
    return expect, solution


MARKERS = ("DRAFT", "OBSOLETE", "SUPERSEDED", "OUTDATED", "EXPIRED", "WITHDRAWN", "REPLACED")
REASONS = ("replaced by the newer copy", "do not send", "see the May version", "kept only for the record", "wrong figures")


@family
def delete_marked_files(rng):
    """Delete the files whose first line begins with a marker word; the word lower down, inside the line or in a name does not count."""
    marker = rng.choice(MARKERS)
    subs = rng.sample(("old", "shared", "misc", "papers", "inbox"), rng.choice((0, 0, 1, 2)))
    used, files, marked = set(), {}, []
    plain = lambda: f"{rng.choice(STEMS)}-{rng.choice(PLACES).lower()}{rng.choice(('.txt', '.md'))}"
    title = lambda: f"{rng.choice([s for s in STEMS if s != marker.lower()]).title()} for {rng.choice(PLACES)}"   # never "Draft for ..." under DRAFT

    def put(make, text, sub=None):
        rel = _fresh(rng, used, make)
        rel = f"{sub}/{rel}" if sub else f"{rng.choice(subs)}/{rel}" if subs and rng.random() < 0.4 else rel
        files[rel] = text
        return rel
    for i in range(rng.randint(2, 4)):
        first = rng.choice((marker, f"{marker}: {rng.choice(REASONS)}", f"{marker} - {rng.choice(REASONS)}"))
        marked.append(put(plain, first + "\n" + _text(rng), subs[0] if subs and i == 0 else None))
    for trap in rng.sample(("lower", "inside", "named"), rng.randint(2, 3)):
        if trap == "lower":                                     # the marker opens a later line
            put(plain, f"{title()}\n{_line(rng)}\n{marker}: the {rng.choice(THINGS)} list from last year\n")
        elif trap == "inside":                                  # in the first line, but not at its start
            put(plain, f"Current copy (the {marker} one was {rng.choice(('deleted', 'sent back', 'thrown out'))})\n" + _text(rng))
        else:                                                   # in the name only
            put(lambda: f"{marker.lower()}-{rng.choice(STEMS)}{rng.choice(('.txt', '.md'))}", f"{title()}\n" + _text(rng))
    for _ in range(rng.randint(1, 3)):
        put(plain, f"{title()}\n" + _text(rng))
    where = " in this folder and its subfolders" if subs else " here"
    request = say(rng, f"Delete every file{where} whose first line begins with the word {marker}. Keep all the other files as they are.",
                  f"Some of my files{where} are marked {marker} at the start of their first line. Remove those and leave the rest alone: {marker} anywhere else in a file does not count.",
                  f"Go through the files{where} and delete each one whose very first line starts with {marker}. Nothing else should change.",
                  f"Clean up{where}: a file goes if its first line starts with {marker}, and every other file stays exactly as it is.")
    tell = rng.random() < 0.4
    expect, solution = _end_state(files, {rel: text for rel, text in files.items() if rel not in marked}, answer="Deleted " + ", ".join(marked) + ".")
    if tell:
        request += " Then tell me which files you deleted."
        expect["answer"] = [rel.rsplit("/", 1)[-1] for rel in marked]
    return {"kind": "careful", "files": files, "request": request, "expect": expect, "solution": solution}


@family
def delete_by_name_rule(rng):
    """Delete the files whose names follow one rule (a prefix, a trailing ~, a date before a day, a download copy, a patch leftover); near misses stay."""
    rule = rng.choice(("prefix", "tilde", "dated", "copies", "patch"))
    used, files, gone = set(), {}, []
    ext = lambda: rng.choice((".txt", ".md", ".csv", ".log"))

    def add(make, doomed=False, text=None):
        rel = _fresh(rng, used, make if callable(make) else lambda: make)
        files[rel] = text if text is not None else _content(rng, "." + rel.rsplit(".", 1)[-1])
        if doomed:
            gone.append(rel)
        return rel
    if rule == "prefix":
        pre = rng.choice(("tmp-", "temp-", "scratch-", "old-"))
        for _ in range(rng.randint(2, 4)):
            add(lambda: f"{pre}{rng.choice(STEMS)}{ext()}", True)
        add(lambda: f"{rng.choice(STEMS)}-{pre}{rng.choice(THINGS)}{ext()}")            # the prefix in the middle of a name
        if rng.random() < 0.6:
            add(lambda: f"{pre[:-1]}_{rng.choice(STEMS)}{ext()}")                         # the word, another separator
        for _ in range(rng.randint(1, 2)):
            add(lambda: f"{rng.choice(STEMS)}-{rng.choice(PLACES).lower()}{ext()}")
        request = say(rng, f"Delete the files here whose names begin with {pre} (dash included). Leave every other file alone.",
                      f"Remove every file whose name starts with `{pre}`, for example {gone[0]}, and nothing else.",
                      f"Get rid of the {pre}* files in this folder; everything else stays as it is.")
    elif rule == "tilde":
        for _ in range(rng.randint(2, 4)):
            add(add(lambda: f"{rng.choice(STEMS)}{ext()}") + "~", True)                   # the original stays beside it
        for near in rng.sample(("lock", "bak", "middle"), 2):
            if near == "lock":                                                             # an office lock file starts with ~
                add(lambda: f"~${rng.choice(STEMS)}.docx", text=f"{rng.choice(PEOPLE)}\n")
            else:
                add(lambda: f"{rng.choice(STEMS)}{ext()}.bak" if near == "bak" else f"{rng.choice(STEMS)}~{rng.choice(THINGS)}{ext()}")
        request = say(rng, "Delete the editor backup files here, the ones whose names end with a tilde (~). Keep every other file, other kinds of backup included.",
                      f"Remove every file whose name ends in ~ (like {gone[0]}), and nothing else.",
                      "My editor left files ending in ~ in this folder. Delete exactly those.")
    elif rule == "dated":
        kind, kext = rng.choice((("log", ".txt"), ("export", ".csv"), ("snapshot", ".json"), ("scan", ".txt"), ("backup", ".sql")))
        dmy = rng.random() < 0.6
        cut = datetime.date(2026, rng.randint(3, 9), rng.randint(10, 26))
        spell = (lambda d: f"{d.day:02d}-{d.month:02d}-{d.year}") if dmy else (lambda d: f"{d:%Y%m%d}")
        before = {cut - datetime.timedelta(days=k) for k in rng.sample(range(1, 200), rng.randint(2, 3))}
        after = {cut + datetime.timedelta(days=k) for k in rng.sample(range(1, 120), rng.randint(1, 2))} | ({cut} if rng.random() < 0.7 else set())
        if dmy:                                                 # spelled day first, an earlier day can sort after the cut, a later one before it
            before.add(cut.replace(month=cut.month - 1, day=rng.randint(cut.day + 1, 28)))
            after.add(cut.replace(month=cut.month + 1, day=rng.randint(1, cut.day - 1)))
        for d in sorted(before | after):
            add(f"{kind}-{spell(d)}{kext}" if dmy else f"{kind}_{spell(d)}{kext}", d < cut)
        other = rng.choice(("notes", "memo", "receipt"))
        add(f"{other}-{spell(min(before))}.txt" if dmy else f"{other}_{spell(min(before))}.txt")   # old, but not one of them
        on, example = f"{cut.day} {MONTHS[cut.month - 1]} {cut.year}", gone[0]
        spelled = "day-month-year" if dmy else "year, month and day run together (YYYYMMDD)"
        request = say(rng, f"Delete the {kind} files dated before {on}. The date in each name is {spelled}, as in {example}. Keep the rest, including any from that very day.",
                      f"Remove every {kind} file whose date is earlier than {on} (the names carry the date {spelled}: {example}). Files dated {on} or later stay, and so does everything else.",
                      f"I only need the {kind} files from {on} onwards. Delete the older ones (the date is in each name, {spelled}, e.g. {example}) and don't touch anything else.")
    elif rule == "copies":
        for _ in range(rng.randint(1, 3)):
            e, base = ext(), _fresh(rng, used, lambda: f"{rng.choice(STEMS)}-{rng.choice(PLACES).lower()}")
            add(base + e)
            for k in range(1, rng.randint(2, 3)):
                add(f"{base} ({k}){e}", True)
        add(lambda: f"{rng.choice(STEMS)} ({rng.choice(('draft', 'final', 'old', 'copy'))}){ext()}")    # words in brackets
        if rng.random() < 0.5:
            add(lambda: f"{rng.choice(PLACES)} {rng.randint(2019, 2026)}{ext()}")                          # a number, no brackets
        request = say(rng, f"Delete the duplicate downloads: the files whose names end in a number in brackets just before the extension, like '{gone[0]}'. Keep everything else.",
                      "My browser saved some files a second time as 'name (1).ext'. Remove every file whose name has a space and a number in brackets right before the extension, and nothing else.",
                      f"Remove the files named like '{gone[0]}' (a number in brackets before the extension). Other files stay, even ones with words in brackets.")
    else:
        for _ in range(rng.randint(1, 3)):
            source = add(lambda: f"{rng.choice(STEMS)}{rng.choice(('.py', '.c', '.js', '.txt'))}")
            for suffix in rng.sample((".orig", ".rej"), rng.randint(1, 2)):
                add(source + suffix, True, _content(rng, "." + source.rsplit(".", 1)[-1]) if suffix == ".orig" else f"--- a/{source}\n+++ b/{source}\n@@ -1 +1 @@\n-{_line(rng)}\n+{_line(rng)}\n")
        for make in rng.sample((lambda: f"original-{rng.choice(STEMS)}.txt", lambda: f"rejected-{rng.choice(THINGS)}s.md", lambda: f"{rng.choice(STEMS)}.orig.md"), 2):
            add(make)
        request = say(rng, "Applying a patch left .orig and .rej files here. Delete every file whose name ends in .orig or .rej, and nothing else.",
                      f"Remove the patch leftovers, the files with names ending in .orig or .rej (such as {gone[0]}). Keep all other files as they are.",
                      "Clean out the files ending in .orig or .rej; the rest of the folder must stay exactly as it is.")
    expect, solution = _end_state(files, {rel: text for rel, text in files.items() if rel not in gone}, answer="Removed " + ", ".join(gone) + ".")
    if rng.random() < 0.3:
        request += " Tell me which files you removed."
        expect["answer"] = list(gone)
    return {"kind": "careful", "files": files, "request": request, "expect": expect, "solution": solution}


KINDS = (("images", ("images", "pictures", "img"), (".png", ".jpg", ".gif", ".svg", ".webp")),
         ("documents", ("docs", "documents", "papers"), (".pdf", ".docx", ".odt", ".txt", ".md")),
         ("data", ("data", "tables", "sheets"), (".csv", ".json", ".xlsx", ".tsv", ".xml")),
         ("audio", ("audio", "music", "sounds"), (".mp3", ".ogg", ".wav", ".flac")))
OTHER_EXTS = (".py", ".sh", ".log", ".ini", ".html", ".zip")


@family
def sort_by_extension(rng):
    """Move the files of the named extensions into folders by kind, creating them; other extensions, double extensions and what is filed already stay."""
    chosen = [(rng.choice(folders), rng.sample(exts, rng.randint(1, 3))) for _kind, folders, exts in rng.sample(KINDS, rng.randint(2, 3))]
    where = {e: folder for folder, exts in chosen for e in exts}
    spare = [e for _kind, _folders, exts in KINDS for e in exts if e not in where] + list(OTHER_EXTS)
    used, files, end = set(), {}, {}
    name = lambda e: _fresh(rng, used, lambda: (f"IMG_{rng.randint(1000, 9999)}" if e in (".jpg", ".png") and rng.random() < 0.4
                                                 else f"{rng.choice(STEMS + THINGS)}-{rng.choice(PLACES).lower()}") + e)
    for e in where:
        for _ in range(rng.randint(1, 2)):
            rel = name(e)
            files[rel] = end[f"{where[e]}/{rel}"] = _content(rng, e)
    for e in rng.sample(spare, rng.randint(2, 3)):
        rel = name(e)
        files[rel] = end[rel] = _content(rng, e)
    e = rng.choice(sorted(where))
    rel = name(e + rng.choice((".bak", ".old", ".part")))      # a double extension: not that kind of file
    files[rel] = end[rel] = _content(rng, e)
    shout = [e for e in where if e in (".jpg", ".png", ".pdf", ".mp3", ".csv")]
    case = ""
    if shout and rng.random() < 0.4:                            # the same kind with its extension in capitals
        e = rng.choice(shout)
        rel = _fresh(rng, used, lambda: f"{rng.choice(STEMS).upper()}{rng.randint(1, 99)}{e.upper()}")
        files[rel] = end[f"{where[e]}/{rel}"] = _content(rng, e)
        case = f" Go by the extension whatever its letter case: a {e.upper()} file counts as {e}."
    if rng.random() < 0.4:                                      # one folder is there already, with a file in it
        folder, exts = rng.choice(chosen)
        rel = f"{folder}/{name(exts[0])}"
        files[rel] = end[rel] = _content(rng, exts[0])
    mapping = [f"the {_and(exts)} files into {folder}/" for folder, exts in chosen]
    request = say(rng, f"Sort the files in this folder by type: {'; '.join(mapping)}. Create the folders if they are not there, and leave every other file where it is.{case}",
                  f"Move {_and(mapping)}. Make any folder that is missing; files of other types stay where they are.{case}",
                  f"Tidy this folder up by moving files into folders: {_and(f'{folder}/ gets the {_and(exts)} files' for folder, exts in chosen)}. Anything else stays put.{case}")
    expect, solution = _end_state(files, end)
    return {"kind": "command", "files": files, "request": request, "expect": expect, "solution": solution}


FIELDS = {"status": ("open", "done", "waiting", "blocked", "review"), "owner": tuple(p.lower() for p in PEOPLE),
          "team": ("design", "sales", "support", "ops", "research"), "priority": ("high", "low", "normal", "urgent")}


@family
def sort_by_header_line(rng):
    """Move each file into a folder named by the value of a `key:` line inside it; a file without the line stays, a mention lower down does not count."""
    key = rng.choice(sorted(FIELDS))
    values = rng.sample(FIELDS[key], rng.randint(2, 3))
    kind, front = rng.choice(("ticket", "task", "note", "issue")), rng.random() < 0.4
    ext = ".md" if front else rng.choice((".txt", ".md"))
    numbers, files, end = iter(rng.sample(range(100, 1000), 9)), {}, {}

    def text(value, mention=False):
        fields = [f"{other}: {rng.choice(FIELDS[other])}" for other in rng.sample([k for k in sorted(FIELDS) if k != key], 2)] + ([f"{key}: {value}"] if value else [])
        rng.shuffle(fields)
        head = "\n".join([f"title: {_title(rng)}"] + fields)
        body = _text(rng) + (f"Earlier it was {key}: {rng.choice([v for v in FIELDS[key] if v != value])}, until last week.\n" if mention else "")
        return (f"---\n{head}\n---\n\n" if front else f"{head}\n\n") + body
    assign = values + [rng.choice(values) for _ in range(rng.randint(2, 4))]
    rng.shuffle(assign)
    mention = rng.randrange(len(assign)) if rng.random() < 0.6 else -1
    for i, value in enumerate(assign):
        rel = f"{kind}-{next(numbers)}{ext}"
        files[rel] = end[f"{value}/{rel}"] = text(value, i == mention)
    if rng.random() < 0.7:                                      # no such line: it stays
        rel = f"{kind}-{next(numbers)}{ext}"
        files[rel] = end[rel] = text(None)
    if rng.random() < 0.4:                                      # filed already
        rel = f"{values[0]}/{kind}-{next(numbers)}{ext}"
        files[rel] = end[rel] = text(values[0])
    ex = values[0]
    request = say(rng, f"Move each {kind} here into a folder named after the value on its `{key}:` line (one with `{key}: {ex}` goes into {ex}/). Create the folders as needed; a file without a {key}: line stays where it is.",
                  f"Sort the {kind}s into folders by {key}: read the line that starts with '{key}:' in each file and move the file into the folder of that name, creating it if needed. Files with no such line stay put.",
                  f"File the {kind}s away by {key}: every file whose `{key}:` line says {ex} ends up in {ex}/, and the same for each other value. Leave files without that line where they are.")
    expect, solution = _end_state(files, end)
    return {"kind": "command", "files": files, "request": request, "expect": expect, "solution": solution}


CONFIGS = {".conf": lambda rng: f"{rng.choice(THINGS)} {rng.randint(1, 900)}\n", ".ini": lambda rng: f"[{rng.choice(STEMS)}]\n{rng.choice(THINGS)} = {rng.randint(1, 900)}\n",
           ".yaml": lambda rng: f"{rng.choice(THINGS)}: {rng.randint(1, 900)}\nplace: {rng.choice(PLACES)}\n",
           ".toml": lambda rng: f'{rng.choice(THINGS)} = {rng.randint(1, 900)}\nplace = "{rng.choice(PLACES)}"\n', ".cfg": lambda rng: f"[{rng.choice(STEMS)}]\nsize = {rng.randint(1, 900)}\n"}


@family
def backup_with_affix(rng):
    """Copy a chosen set of files into a backup folder, each copy renamed with a suffix or prefix; the originals and everything else stay unchanged."""
    dest = rng.choice(("backup", "backups", "saved", "before-edit", "copies"))
    day = datetime.date(2026, rng.randint(1, 12), rng.randint(1, 28)).isoformat()
    affix = rng.choice(("end", "before_ext", "prefix", "date_prefix", "date_before_ext"))
    tag = {"end": rng.choice((".bak", ".orig", ".old")), "before_ext": rng.choice(("-old", "-copy", "_bak")), "prefix": rng.choice(("old-", "copy-of-", "prev_")),
           "date_prefix": f"{day}-", "date_before_ext": f"-{day}"}[affix]
    how = {"end": f"with {tag} added to the end of its name", "before_ext": f"with {tag} added just before the extension", "prefix": f"with {tag} in front of its name",
           "date_prefix": f"with the date {day} and a dash in front of its name", "date_before_ext": f"with a dash and the date {day} added just before the extension"}[affix]

    def renamed(name):
        stem, ext = name.rsplit(".", 1)
        return name + tag if affix == "end" else f"{stem}{tag}.{ext}" if affix in ("before_ext", "date_before_ext") else tag + name
    pick, used, files = rng.choice(("ext", "list", "folder")), set(), {}
    exts = rng.sample(sorted(CONFIGS), 3)
    simple = lambda e: _fresh(rng, used, lambda: f"{rng.choice(STEMS + THINGS)}{rng.choice(('', '-' + rng.choice(PLACES).lower()))}{e}")
    def fill(rel):                                              # a.conf.example holds what a .conf file does
        e = "." + rel.rsplit("/", 1)[-1].split(".")[1]
        files[rel] = CONFIGS[e](rng) if e in CONFIGS else _content(rng, e)
    if pick == "ext":
        chosen = [simple(exts[0]) for _ in range(rng.randint(2, 4))]
        others = [simple(e) for e in exts[1:]] + ([f"{chosen[0]}.example"] if rng.random() < 0.6 else [])   # .example: not a {exts[0]} file
        selection = f"every {exts[0]} file here"
    elif pick == "list":
        names = [simple(rng.choice(exts + [".txt", ".md", ".csv"])) for _ in range(rng.randint(5, 7))]
        chosen = rng.sample(names, rng.randint(2, 3))
        others = [n for n in names if n not in chosen]
        selection = _and(chosen)
    else:
        folder = rng.choice(("config", "settings", "conf.d"))
        chosen = [f"{folder}/{simple(rng.choice(exts))}" for _ in range(rng.randint(2, 4))]
        others = [simple(rng.choice(exts)) for _ in range(rng.randint(1, 2))]          # the same kinds of file, outside it
        selection = f"every file in {folder}/"
    for rel in chosen + others:
        fill(rel)
    if rng.random() < 0.4:                                      # an older backup is there already, and stays
        files[f"{dest}/{rng.choice(STEMS)}-2025.txt"] = _text(rng)
    copies = {f"{dest}/{renamed(rel.rsplit('/', 1)[-1])}": files[rel] for rel in chosen}
    ex_src, ex_dst = chosen[0], next(iter(copies))
    request = say(rng, f"Back up {selection}: copy each one into {dest}/ {how}, so {ex_src} is copied to {ex_dst}. Create {dest}/ if needed, and leave the originals exactly as they are.",
                  f"Before I edit {selection}, make copies of them in a folder {dest}/, each {how} (for example {ex_dst}). Don't change or move the originals.",
                  f"Copy {selection} into {dest}/, each copy {how}: {ex_src} is copied to {ex_dst}, and so on. The originals stay where they are, unchanged.")
    if pick == "folder":
        request += f" The copies go straight into {dest}/, not into a folder inside it."
    expect, solution = _end_state(files, {**files, **copies})
    return {"kind": "command", "files": files, "request": request, "expect": expect, "solution": solution}


FLATTEN = {"photos": (tuple(p.lower() for p in PLACES), ("beach", "dinner", "harbor", "market", "sunset", "street", "garden", "museum"), ".jpg"),
           "scans": (("2024", "2025", "bank", "school", "house", "car"), ("receipt", "letter", "contract", "form", "statement"), ".pdf"),
           "notes": (("garden", "house", "work", "travel", "books", "health"), ("todo", "ideas", "minutes", "links", "plan"), ".md"),
           "inbox": (tuple(p.lower() for p in PEOPLE), ("reply", "offer", "agenda", "notice", "invite"), ".txt"),
           ".": (("drafts", "final", "shared", "mine", "review"), ("chapter", "outline", "summary", "letter", "list"), ".txt")}


@family
def flatten_with_prefix(rng):
    """Bring every file up out of the subfolders, its folder's name put in front so that nothing clashes; files already at the top stay."""
    top, sep = rng.choice(sorted(FLATTEN)), rng.choice(("-", "_"))
    folders, names, ext = FLATTEN[top]
    base = "" if top == "." else f"{top}/"
    subs, common = rng.sample(folders, rng.randint(2, 3)), rng.choice(names)    # one name in every folder: why the prefix
    files, end = {}, {}
    for sub in subs:
        for n in [common] + rng.sample([n for n in names if n != common], rng.randint(0, 2)):
            files[f"{base}{sub}/{n}{ext}"] = end[f"{base}{sub}{sep}{n}{ext}"] = _content(rng, ext)
    deep = ""
    if rng.random() < 0.3:
        inner, n = rng.choice(("old", "extra", "more", "copies")), rng.choice(names)
        old, new = f"{base}{subs[0]}/{inner}/{n}{ext}", f"{base}{subs[0]}{sep}{inner}{sep}{n}{ext}"
        files[old] = end[new] = _content(rng, ext)
        deep = f" A file two folders down gets both folder names, the outer one first: {old} becomes {new}."
    for n in rng.sample(("index", "readme", "overview", "cover"), rng.randint(1, 2)):   # directly in the folder already: stays
        files[f"{base}{n}{ext}"] = end[f"{base}{n}{ext}"] = _content(rng, ext)
    if top != ".":
        rel = rng.choice(("todo.txt", "plan.md", "list.txt"))
        files[rel] = end[rel] = _text(rng)
    place = "this folder" if top == "." else f"{top}/"
    ex_old, ex_new = f"{base}{subs[0]}/{common}{ext}", f"{base}{subs[0]}{sep}{common}{ext}"
    request = say(rng, f"Flatten {place}: move every file from its subfolders up into {place} itself, putting the subfolder's name and '{sep}' in front of the file name ({ex_old} becomes {ex_new}).",
                  f"I don't want files tucked away in subfolders of {place} any more. Move each one up into {place}, renamed to <subfolder>{sep}<name> so that nothing clashes (for example {ex_old} -> {ex_new}).",
                  f"Bring every file out of the folders inside {place} and into {place} itself, prefixing its name with the name of the folder it came from and '{sep}' ({ex_old} becomes {ex_new}). Files already directly in {place} stay as they are.")
    expect, solution = _end_state(files, end)
    return {"kind": "command", "files": files, "request": request + deep, "expect": expect, "solution": solution}


@family
def normalize_file_names(rng):
    """Rename files to lower case, spaces to underscores, or both, exactly within the scope asked; names already clean, and files outside, stay."""
    mode = rng.choice(("lower", "underscore", "both"))
    scope = rng.choice(("", "", "uploads", "shared", "incoming"))
    clean = {"lower": str.lower, "underscore": lambda s: s.replace(" ", "_"), "both": lambda s: s.lower().replace(" ", "_")}[mode]
    words = STEMS + THINGS + tuple(p.lower() for p in PLACES)

    def draw(dirty):
        ws = [rng.choice((w.lower(), w.title(), w.upper())) if dirty or mode == "underscore" else w for w in rng.sample(words, rng.randint(1, 3))]
        joint = " " if mode != "lower" and dirty else rng.choice(("-", "_", " ") if mode == "lower" and dirty else ("-", "_"))
        name = joint.join(ws).replace(" ", "  ", 1 if mode != "lower" and rng.random() < 0.15 else 0)
        e = rng.choice((".txt", ".md", ".csv", ".pdf", ".jpg", ".json"))
        return name + (rng.choice((e, e.upper())) if mode != "underscore" or dirty else e)
    taken, files, end, changed = set(), {}, {}, []
    for dirty in [True] * rng.randint(3, 5) + [False] * rng.randint(1, 2):
        for _ in range(100):
            name = draw(dirty)
            if (clean(name) != name) == dirty and name not in taken and clean(name) not in taken and (" " in name or mode != "underscore" or not dirty):
                break
        taken |= {name, clean(name)}
        rel = f"{scope}/{name}" if scope else name
        files[rel] = end[f"{scope}/{clean(name)}" if scope else clean(name)] = _content(rng, "." + name.rsplit(".", 1)[-1])
        if dirty:
            changed.append((rel, f"{scope}/{clean(name)}" if scope else clean(name)))
    if scope:                                                   # outside the scope: stays as it is, capitals and spaces too
        for _ in range(rng.randint(1, 2)):
            name = _fresh(rng, taken, lambda: f"{rng.choice(STEMS).title()} {rng.choice(PLACES)}.txt")
            files[name] = end[name] = _text(rng)
    old, new = changed[0]
    within = f"in {scope}/ (only there: files elsewhere stay as they are)" if scope else "in this folder"
    request = {"lower": lambda: say(rng, f"Rename every file {within} so that its whole name is lower case, extension included ('{old}' becomes '{new}'). Change nothing else in the names.",
                                    f"Make all the file names {within} lower-case, the extension too, for example '{old}' -> '{new}'. Names that are already lower-case stay as they are."),
               "underscore": lambda: say(rng, f"Replace every space in the file names {within} with an underscore, one underscore for each space, and keep the letters as they are ('{old}' becomes '{new}').",
                                         f"Some file names {within} have spaces in them. Rename those files, turning each space into _ and changing nothing else (so '{old}' becomes '{new}')."),
               "both": lambda: say(rng, f"Clean up the file names {within}: lower case throughout, extension included, and each space replaced by an underscore ('{old}' -> '{new}'). Files whose names are like that already stay.",
                                   f"Rename the files {within} so their names have no capitals and no spaces: lower-case each name and put _ in place of every space, e.g. '{old}' becomes '{new}'.")}[mode]()
    expect, solution = _end_state(files, end)
    return {"kind": "command", "files": files, "request": request, "expect": expect, "solution": solution}


@family
def keep_latest_versions(rng):
    """Keep only the newest numbered version of each document, newest by number (v10 after v9), deleting or moving the older ones; unnumbered files stay."""
    form = rng.choice(("-v", "_v", "-rev", ".v", " v"))
    move, old = rng.random() < 0.4, rng.choice(("old", "previous", "older-versions", "superseded"))
    stems = rng.sample(STEMS, rng.randint(2, 3))
    files, end, newest = {}, {}, []
    for i, stem in enumerate(stems):
        ext = rng.choice((".md", ".txt"))
        versions = set(rng.sample(range(1, 15), rng.randint(2, 4))) | ({rng.randint(2, 9), rng.randint(10, 14)} if i == 0 else set())
        for v in sorted(versions):
            rel = f"{stem}{form}{v}{ext}"
            files[rel] = f"{stem.title()}, version {v}\n" + _text(rng)
            if v == max(versions):
                end[rel] = files[rel]
                newest.append(rel)
            elif move:
                end[f"{old}/{rel}"] = files[rel]
        if rng.random() < 0.6:
            files[f"{stem}-notes{ext}"] = end[f"{stem}-notes{ext}"] = f"Notes on the {stem}\n" + _text(rng)
    rel = f"{rng.choice([s for s in STEMS if s not in stems])}.txt"
    files[rel] = end[rel] = _text(rng)
    number = {"-v": "the number after -v", "_v": "the number after _v", "-rev": "the number after -rev", ".v": "the number after .v", " v": "the number after the space and v"}[form]
    keep = newest[-1]
    if move:
        request = say(rng, f"Move the older versions of each document into {old}/ (create it), so that only the newest version of each stays here. The version is {number} in the name; files without one stay where they are.",
                      f"Keep only the latest version of every document in this folder and put all its earlier versions into a folder {old}/. The version is {number}; files without a version stay put.",
                      f"For each document, leave the highest-numbered version here and move the others into {old}/. Compare the versions as numbers ({number}), and don't move files that have no version.")
    else:
        request = say(rng, f"For each document here keep only its newest version, the one with the highest version number ({number}), and delete the older versions. Files without a version number stay.",
                      f"I only need the latest version of each document: delete the older ones. The version is {number} in the name, so {keep} is one to keep. Leave files without a version alone.",
                      f"Remove every outdated version: of each document's numbered files only the one with the highest version number ({number}) stays. Files that have no version number stay too.")
    expect, solution = _end_state(files, end, answer="Kept " + ", ".join(newest) + ".")
    return {"kind": "careful", "files": files, "request": request, "expect": expect, "solution": solution}


def _project(rng):
    name = f"{rng.choice(STEMS)}-{rng.choice(('tool', 'kit', 'app', 'cli', 'lib'))}"
    pkg = name.replace("-", "_")
    out = [("README.md", f"# {name}"), (f"src/{pkg}/__init__.py", ""), (f"src/{pkg}/{rng.choice(('main', 'core', 'cli'))}.py", rng.choice(("", f'print("{name}")', "import sys"))),
           (f"tests/test_{pkg}.py", rng.choice(("", f"import {pkg}")))]
    return name, out + rng.sample([(".gitignore", "__pycache__/"), ("requirements.txt", ""), ("docs/index.md", f"# {name}")], rng.randint(0, 2))


def _website(rng):
    place = rng.choice(PLACES)
    out = [("index.html", f"<h1>{place}</h1>"), ("css/style.css", rng.choice(("body { margin: 0; }", "body { font-family: sans-serif; }", ""))),
           ("js/main.js", rng.choice(("", "console.log('ready');"))), ("images/.keep", "")]
    return f"{place.lower()}-{rng.choice(('site', 'web', 'pages'))}", out + ([("about.html", f"<h1>About {place}</h1>")] if rng.random() < 0.6 else [])


def _course(rng):
    subject = rng.choice(("algebra", "botany", "chemistry", "drawing", "economics", "french", "geology", "history", "music", "physics"))
    out = [("syllabus.md", f"# {subject.title()}")]
    for w in range(1, rng.randint(2, 4) + 1):
        out += [(f"week-{w:02d}/notes.md", f"# Week {w}")] + ([(f"week-{w:02d}/exercises.md", "")] if rng.random() < 0.5 else [])
    return f"{subject}-{rng.choice(('course', 'class'))}", out


def _trip(rng):
    place = rng.choice(PLACES)
    out = [("itinerary.md", f"# {place}"), ("budget.csv", rng.choice(("item,amount", "date,item,amount"))), ("packing.txt", ""), ("tickets/.keep", "")]
    return f"trip-{place.lower()}", out + ([("photos/.keep", "")] if rng.random() < 0.5 else [])


def _analysis(rng):
    stem = rng.choice(STEMS)
    return f"{stem}-analysis", [("README.md", f"# {stem.title()} analysis"), ("data/raw/.keep", ""), ("data/clean/.keep", ""),
                                (f"scripts/{rng.choice(('clean', 'load', 'prepare'))}.py", ""), ("reports/summary.md", "# Summary")]


def _book(rng):
    thing = rng.choice(THINGS)
    chapters = rng.sample(("arrival", "storm", "market", "letters", "harbor", "winter", "return", "garden"), rng.randint(2, 4))
    return f"{thing}-{rng.choice(('book', 'story', 'novel'))}", ([("README.md", f"# The {thing.title()}")] + [(f"chapters/{i:02d}-{c}.md", f"# {c.title()}") for i, c in enumerate(chapters, 1)]
                                                                 + [("notes/characters.md", "")])


def _club(rng):
    place, group, month = rng.choice(PLACES), rng.choice(("club", "choir", "team")), rng.randint(1, 12)
    return f"{place.lower()}-{group}", [("README.md", f"# {place} {group}"), ("members.csv", "name,email"), (f"minutes/2026-{month:02d}.md", f"# Minutes, {MONTHS[month - 1]} 2026"),
                                        ("events/calendar.txt", "")]


SKELETONS = (_project, _website, _course, _trip, _analysis, _book, _club)


def _tree(root: str, rels: list) -> str:
    """An indented drawing of the paths, two spaces a level, in the order `tree` prints them."""
    lines, seen = [f"{root}/"], set()
    for rel in sorted(rels):
        parts = rel.split("/")
        for depth in range(1, len(parts)):
            if "/".join(parts[:depth]) not in seen:
                seen.add("/".join(parts[:depth]))
                lines.append("  " * depth + parts[depth - 1] + "/")
        lines.append("  " * len(parts) + parts[-1])
    return "\n".join(lines)


@family
def build_skeleton(rng):
    """Create a folder tree of empty and one-line files from a description (a list, an indented tree, or a layout file), and nothing more."""
    root, entries = rng.choice(SKELETONS)(rng)
    form = rng.choice(("list", "tree", "layout"))
    files = {rng.choice(("todo.txt", "notes.md", "ideas.txt")): _text(rng)}
    if form == "list":
        lines = "\n".join(f"- {root}/{rel}: " + (f"the line `{text}`" if text else "empty") for rel, text in entries)
        request = say(rng, f"Set up a new folder {root} with these files (and the folders they need), and nothing else:\n{lines}",
                      f"Please create this structure, each file holding exactly what is given:\n{lines}",
                      f"Make me a skeleton for {root}. Create the folders as needed and these files:\n{lines}")
    elif form == "tree":
        full = [(rel, text) for rel, text in entries if text]
        holds = ("All the files are empty except " + "; ".join(f"{root}/{rel}, which holds the line `{text}`" for rel, text in full) + ".") if full else "All the files are empty."
        request = say(rng, f"Create this folder tree here:\n{_tree(root, [rel for rel, _ in entries])}\n{holds}",
                      f"Build the following layout in this folder, two spaces of indent for each level:\n{_tree(root, [rel for rel, _ in entries])}\n{holds}")
    else:
        layout = rng.choice(("layout.txt", "skeleton.txt", "structure.txt"))
        files[layout] = "".join(f"{root}/{rel}" + (f" | {text}" if text else "") + "\n" for rel, text in entries)
        request = say(rng, f"Create the files listed in {layout}, with the folders they need. Each line is a path; when it has ' | ', the text after it is the file's single line, otherwise the file is empty. Keep {layout} as it is.",
                      f"{layout} describes a folder skeleton: one path per line, and after ' | ' the one line that file should contain (no ' | ' means an empty file). Please create it all.")
    expect, solution = _end_state(files, {**files, **{f"{root}/{rel}": text for rel, text in entries}})
    return {"kind": "chain", "files": files, "request": request, "expect": expect, "solution": solution}
