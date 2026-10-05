"""Changing text inside one or several files exactly: a phrase replaced everywhere but in one place, a first or last
line added where it is missing, a version raised in each file's own spelling of it, lines sorted or made unique,
tabs, final newlines and line endings made regular, a numbered list renumbered, corrections applied from a table, a
config value changed and a key added, and a line put next to a marker in several files.

Every expected file is computed from what the family drew and compared whole, and the files a careless edit would
also touch are named with their text, so touching them fails the task. The traps are the ones the tools of the trade
guard against: bump-my-version scopes its search to the version's own context because the same digits turn up
elsewhere (its docs/reference/search-and-replace-config.md), and markdownlint's MD029 numbers each list from 1 on its
own. The judge compares text with its final newlines stripped and line endings read as LF, so the families about
those compare bytes (`_exact`)."""
from __future__ import annotations

import datetime
import json
import re

from dawnr_factory import PEOPLE, PLACES, STEMS, THINGS, family, say

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
CODENAMES = ("Bluefin", "Driftwood", "Kestrel", "Marigold", "Nimbus", "Pebble", "Quartz", "Saffron", "Tamarack", "Wicket", "Larkspur",
             "Juniper", "Halcyon", "Foxglove", "Cobalt", "Basalt", "Thistle", "Osprey", "Fennel", "Garnet")
PKGS = ("tidyparse", "quicklog", "pathkit", "minicache", "textgrid", "plainconf", "shelfscan", "datebook", "tinyqueue", "wordtally",
        "colorpick", "unitconv")
DEPS = ("corelib", "yamlite", "colorterm", "netretry", "dateparts", "smalljson", "termsize", "pathutil")


def _and(names) -> str:
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _sentence(rng) -> str:
    """A plain line about made-up things, for the parts of a file a task does not touch."""
    thing, other, person, place, day = rng.choice(THINGS), rng.choice(THINGS), rng.choice(PEOPLE), rng.choice(PLACES), rng.choice(WEEKDAYS)
    return rng.choice((f"The new {thing} arrives on {day}.", f"{person} will look at the {thing} in {place}.", f"Keep the {thing} next to the {other}.",
                       f"The {place} office closes early on {day}.", f"Please return the {thing} by the end of the week.", f"{person} has the key to the {thing} cupboard.",
                       f"Order a second {thing} before {day}.", f"The {thing} in {place} needs a new plug."))


def _change(rng) -> str:
    """One line of a changelog."""
    return rng.choice((f"Fixed reading {rng.choice(THINGS)} files with empty lines.", f"Added a --{rng.choice(STEMS)} option.", "Faster start-up.",
                       f"Clearer error when the {rng.choice(THINGS)} list is missing.", f"Sorted the {rng.choice(STEMS)} output by name."))


def _doc(ext: str, title: str, lines: list) -> str:
    """A short document of one kind: a title, then one line each."""
    if ext == ".md":
        return f"# {title}\n\n" + "".join(line + "\n" for line in lines)
    if ext == ".rst":
        return title + "\n" + "=" * len(title) + "\n\n" + "".join(line + "\n" for line in lines)
    if ext == ".html":
        return f"<h1>{title}</h1>\n" + "".join(f"<p>{line}</p>\n" for line in lines)
    return f"{title}\n\n" + "".join(line + "\n" for line in lines)


def _exact(want: dict):
    """A check byte for byte, for what the judge's text comparison cannot see: final newlines and line endings."""
    def check(work) -> list:
        return [f"{rel} is not, byte for byte, what was asked for" for rel, text in want.items()
                if not (work / rel).is_file() or (work / rel).read_bytes() != text.encode("utf-8")]
    return check


# ------------------------------------------------------------------ a phrase replaced, with one exception --

def _phrase(rng):
    """(old, new, why it changed, a maker of lines that carry the old phrase)."""
    kind = rng.choice(("name", "address", "room", "share"))
    if kind == "name":
        old, new = rng.sample(CODENAMES, 2)
        why, ways = "The project has a new name.", ("{x} keeps the {thing} list in one place.", "To start {x}, run the setup script once.",
                                                    "{x} was first tried in {place}.", "Ask {person} if {x} stops answering.", "The {x} notes are updated every {day}.")
    elif kind == "address":
        old, new = (f"{a}@example.org" for a in rng.sample(("help", "desk", "support", "orders", "office", "team", "info", "bookings"), 2))
        why, ways = "Our contact address has changed.", ("Questions go to {x}.", "Write to {x} to book the {thing}.", "Send receipts to {x} before {day}.",
                                                         "For a key to the {thing} cupboard, write to {x}.")
    elif kind == "room":
        old, new = (f"Room {p}" for p in rng.sample(PLACES, 2))
        why, ways = "The meeting room was renamed.", ("We meet in {x} on {day}s.", "The {thing} is kept in {x}.", "{x} has the projector.",
                                                      "Ask {person} for the key to {x}.")
    else:
        old, new = (f"/srv/{a}" for a in rng.sample(("shared", "media", "exports", "team", "public", "records"), 2))
        why, ways = "The shared folder moved.", ("Backups are copied to {x} every night.", "The {thing} photos live in {x}.", "Put finished drafts in {x}.",
                                                 "{person} tidies {x} on {day}s.")
    return old, new, why, lambda: rng.choice(ways).format(x=old, thing=rng.choice(THINGS), place=rng.choice(PLACES), person=rng.choice(PEOPLE), day=rng.choice(WEEKDAYS))


@family
def edit_replace_except(rng):
    """Replace a phrase in every file of one kind, subfolders included, except one named file or one subfolder; other kinds stay."""
    old, new, why, carry = _phrase(rng)
    ext = rng.choice((".md", ".txt", ".rst", ".html"))
    stems = rng.sample(STEMS, 6)
    sub, skip = rng.choice(("docs", "guides", "team", "howto")), rng.choice(("archive", "old", "attic", "2025"))

    def text(title, carried):
        lines = [carry() for _ in range(carried)] + [_sentence(rng) for _ in range(rng.randint(1, 3))]
        rng.shuffle(lines)
        return _doc(ext, title, lines)
    files = {f"{stems[0]}{ext}": text(stems[0].capitalize(), 2), f"{stems[1]}{ext}": text(stems[1].capitalize(), 1),
             f"{sub}/{stems[2]}{ext}": text(stems[2].capitalize(), rng.randint(1, 2))}
    if rng.random() < 0.5:
        files[f"{sub}/{stems[3]}{ext}"] = text(stems[3].capitalize(), 0)       # a file of the kind with nothing to replace
    if rng.random() < 0.5:
        excluded = [rng.choice(("CHANGELOG", "HISTORY")) + ext]
        where = f"{excluded[0]}, which records how things were"
    else:
        excluded = [f"{skip}/{s}{ext}" for s in stems[4:4 + rng.randint(1, 2)]]
        where = f"the files under {skip}/"
    for rel in excluded:
        files[rel] = text(rel.split("/")[-1][:-len(ext)].capitalize(), rng.randint(1, 2))
    other_ext = rng.choice([e for e in (".txt", ".md", ".cfg", ".json") if e != ext])
    other = rng.choice(("contacts", "about", "meta", "info")) + other_ext
    files[other] = {".cfg": f"[site]\nlabel = {old}\n", ".json": json.dumps({"label": old}) + "\n"}.get(other_ext) or _doc(other_ext, "About", [carry()])
    want = {rel: (t if rel in excluded or not rel.endswith(ext) else t.replace(old, new)) for rel, t in files.items()}
    request = say(rng, f"{why} Replace `{old}` with `{new}` in every {ext} file in this folder and its subfolders, except {where}. Files of other kinds stay as they are.",
                  f"Change every `{old}` to `{new}` in all the {ext} files here, subfolders included, but not in {where}. Leave the files that are not {ext} alone.",
                  f"{why} In the {ext} files under this folder (subfolders too), put `{new}` wherever `{old}` appears. Skip {where}, and do not touch any file that is not {ext}.")
    return {"kind": "careful", "files": files, "request": request, "expect": {"files": want},
            "solution": {"answer": f"Replaced {old} with {new}.", "files": {rel: t for rel, t in want.items() if t != files[rel]}}}


# ------------------------------------------------------------------ a first or last line where it is missing --

CSV_KINDS = (("date,item,amount", lambda rng: f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d},{rng.choice(THINGS)},{rng.randint(1, 400)}.{rng.randint(0, 99):02d}"),
             ("id,name,qty", lambda rng: f"{rng.randint(100, 999)},{rng.choice(THINGS)},{rng.randint(1, 40)}"),
             ("day,place,temp", lambda rng: f"{rng.choice(WEEKDAYS)[:3].lower()},{rng.choice(PLACES)},{rng.randint(5, 35)}.{rng.randint(0, 9)}"),
             ("code,shelf,count", lambda rng: f"{rng.choice('ABCDEFGH')}{rng.randint(1, 99)},{rng.choice(('top', 'middle', 'bottom'))},{rng.randint(0, 60)}"))
SCRIPT_LINES = ('echo "Backing up {s}"', "mkdir -p backup/{s}", "cp {s}.txt backup/{s}/", "tar -czf {s}.tar.gz {s}", "date >> {s}.log", "rm -f {s}.tmp",
                "ls -l {s} > {s}-files.txt", "gzip -k {s}.csv")
SHEBANGS = ("#!/bin/sh", "#!/usr/bin/env bash", "#!/bin/bash", "#!/usr/bin/env sh")


@family
def edit_add_header(rng):
    """Add a given first line (or last line) to every file of one kind that lacks it; files that have it, and other kinds, stay."""
    variant = rng.choice(("csv", "shebang", "doctype", "footer"))
    n = rng.randint(3, 5)
    stems = rng.sample(STEMS, n)
    has = set(rng.sample(range(n), rng.randint(1, n - 2)))     # at least one has it already, at least two lack it
    files, want = {}, {}
    if variant == "csv":
        line, row = rng.choice(CSV_KINDS)
        for i, s in enumerate(stems):
            body = "".join(row(rng) + "\n" for _ in range(rng.randint(2, 5)))
            want[f"{s}.csv"] = f"{line}\n{body}"
            files[f"{s}.csv"] = want[f"{s}.csv"] if i in has else body
        files["README.txt"] = f"Exports from the {rng.choice(THINGS)} tracker, one file a month.\n"
        request = say(rng, f"Some of the .csv files here have lost their header row. Add `{line}` as the first line of each .csv file that does not already start with it; the ones that do stay as they are.",
                      f"Every .csv file in this folder should begin with the header line `{line}`. Put it at the top of the ones that lack it, and leave the rest untouched.",
                      f"Make sure each .csv here starts with `{line}`: insert that line at the top where it is missing. Do not change anything else.")
    elif variant == "shebang":
        line = rng.choice(SHEBANGS[:3])
        for i, s in enumerate(stems):
            body = "".join(step.format(s=s) + "\n" for step in rng.sample(SCRIPT_LINES, rng.randint(2, 4)))
            files[f"{s}.sh"] = f"{rng.choice(SHEBANGS)}\n{body}" if i in has else body    # any #! line counts, the same one or another
            want[f"{s}.sh"] = files[f"{s}.sh"] if i in has else f"{line}\n{body}"
        files["README.md"] = f"# Scripts\n\nSmall scripts for the {rng.choice(THINGS)} backups. Run them from this folder.\n"
        request = say(rng, f"Add `{line}` as the first line of every .sh script here that has no `#!` line. Scripts that already start with a `#!` line, whichever it is, stay as they are.",
                      f"Some of the .sh files in this folder have no shebang. Give each of those `{line}` as its first line; leave the scripts that already have a `#!` line, and every other file, alone.")
    elif variant == "doctype":
        line = "<!DOCTYPE html>"
        for i, s in enumerate(stems):
            body = f"<html>\n<head>\n<title>{s.capitalize()}</title>\n</head>\n<body>\n<h1>{s.capitalize()}</h1>\n<p>{_sentence(rng)}</p>\n</body>\n</html>\n"
            want[f"{s}.html"] = f"{line}\n{body}"
            files[f"{s}.html"] = want[f"{s}.html"] if i in has else body
        files["style.css"] = "body { font-family: sans-serif; margin: 2em; }\n"
        request = say(rng, f"Put `{line}` as the very first line of each .html page here that does not start with it. Pages that already have it stay as they are, and so does every other file.",
                      f"A few of the .html files are missing the `{line}` line at the top. Add it to those, and change nothing else.")
    else:
        ext = rng.choice((".md", ".txt"))
        line = rng.choice(("Questions? Write to help@example.org.", f"Kind regards, {rng.choice(PEOPLE)}") if ext == ".txt" else
                          ("Questions? Write to help@example.org.", f"Kept up to date by the {rng.choice(PLACES)} team.", "Please do not forward this outside the team."))
        for i, s in enumerate(stems):
            body = _doc(ext, s.capitalize(), [_sentence(rng) for _ in range(rng.randint(2, 4))])
            want[f"{s}{ext}"] = f"{body}\n{line}\n"
            files[f"{s}{ext}"] = want[f"{s}{ext}"] if i in has else body
        other = ".txt" if ext == ".md" else ".md"
        files[f"todo{other}"] = _doc(other, "Todo", [_sentence(rng) for _ in range(2)])
        request = say(rng, f"Every {ext} file here should close with the line `{line}`, after one empty line. Add the empty line and that line at the end of each {ext} file that does not end that way yet; leave the others, and every file that is not {ext}, as they are.",
                      f"Give each {ext} file in this folder the closing line `{line}`, with one empty line before it, at the very end. Files that already end that way stay as they are; other kinds of files are not touched.")
    return {"kind": "multi", "files": files, "request": request, "expect": {"files": {**files, **want}},
            "solution": {"answer": "Added where it was missing.", "files": {rel: t for rel, t in want.items() if t != files[rel]}}}


# ------------------------------------------------------------------ a version raised where it is stated --

@family
def edit_bump_version(rng):
    """Raise a package's version in each file that states it, in that file's own syntax, and nowhere else: not a dependency with the same digits, not the changelog."""
    pkg, dep = rng.choice(PKGS), rng.choice(DEPS)
    major, minor, patch = rng.randint(0, 3), rng.randint(0, 12), rng.randint(1, 15)
    old, prev = f"{major}.{minor}.{patch}", f"{major}.{minor}.{patch - 1}"
    kind = rng.choice(("patch", "minor", "major", "to"))
    new = {"patch": f"{major}.{minor}.{patch + 1}", "minor": f"{major}.{minor + 1}.0", "major": f"{major + 1}.0.0", "to": f"{major}.{minor + rng.randint(1, 3)}.0"}[kind]
    pin = old if rng.random() < 0.6 else f"{rng.randint(0, 4)}.{rng.randint(0, 20)}.{rng.randint(0, 9)}"    # the dependency, often with the same digits
    desc = rng.choice(("Small helpers for {} files", "Read and tidy {} lists", "A tiny tool to sort {} records", "Keep track of {} loans")).format(rng.choice(THINGS))
    js = rng.random() < 0.25
    if js:
        meta = ("package.json", lambda v: json.dumps({"name": pkg, "version": v, "description": desc, "dependencies": {dep: "^" + pin}}, indent=2) + "\n")
        source = ("src/version.js", lambda v: f'export const VERSION = "{v}";\n')
    else:
        meta = rng.choice((("setup.cfg", lambda v: f"[metadata]\nname = {pkg}\nversion = {v}\ndescription = {desc}\n\n[options]\npython_requires = >=3.10\ninstall_requires =\n    {dep}>={pin}\n"),
                           ("pyproject.toml", lambda v: f'[project]\nname = "{pkg}"\nversion = "{v}"\ndescription = "{desc}"\nrequires-python = ">=3.10"\ndependencies = ["{dep}>={pin}"]\n')))
        source = rng.choice(((f"src/{pkg}/__init__.py", lambda v: f'"""{desc}."""\n\n__version__ = "{v}"\n'), (f"{pkg}/version.py", lambda v: f'VERSION = "{v}"\n')))
    install = f"npm install {pkg}@" if js else f"pip install {pkg}=="
    readme = ("README.md", lambda v: f"# {pkg}\n\n{desc}.\n\nLatest release: {v}\n\nInstall it with `{install}{v}`.\n")
    places = [meta, source] + ([readme] if rng.random() < 0.6 else [])
    rng.shuffle(places)
    files = {path: write(old) for path, write in places}
    want = {path: write(new) for path, write in places}
    files.setdefault("README.md", f"# {pkg}\n\n{desc}.\n")
    files["CHANGELOG.md"] = (f"# Changelog\n\n## {old} - 2026-{rng.randint(5, 9):02d}-{rng.randint(1, 28):02d}\n\n- {_change(rng)}\n\n"
                             f"## {prev} - 2026-{rng.randint(1, 4):02d}-{rng.randint(1, 28):02d}\n\n- {_change(rng)}\n")
    names = _and([path for path, _write in places])
    rule = {"patch": "raise its patch number by one", "minor": "raise its minor number by one and set the patch number to 0",
            "major": "raise its major number by one and set the minor and patch numbers to 0"}.get(kind)
    if kind == "to":
        request = say(rng, f"Bump {pkg} from {old} to {new}. Its version is written in {names}; change it everywhere it appears there as {pkg}'s version. The {dep} requirement and CHANGELOG.md stay as they are.",
                      f"Set the version of {pkg} to {new} in {names} (it is {old} now). Only {pkg}'s own version changes: leave the version of {dep} and the changelog alone.")
    else:
        request = say(rng, f"Time for a {kind} release of {pkg}: {rule} in {names}, wherever {old} appears there as {pkg}'s version. Leave the {dep} requirement and CHANGELOG.md as they are, and tell me the new version.",
                      f"{pkg} is at {old}. Make it the next {kind} version ({rule}) in {names}; the version of {dep} and the changelog do not change. Which version is it now?")
    expect = {"files": {**files, **want}}
    if kind != "to":
        expect["answer"] = [new]
    return {"kind": "multi", "files": files, "request": request, "expect": expect, "solution": {"answer": f"{pkg} is now at {new}.", "files": want}}


# ------------------------------------------------------------------ lines sorted, or made unique --

@family
def edit_sort_lines(rng):
    """Order a file's lines by the rule asked (a number, a column, a day/month/year date, one section only) or drop repeated lines keeping first occurrences; a file like it stays."""
    variant = rng.choice(("number", "column", "date", "section", "unique"))
    if variant == "number":
        def draw():
            k = rng.randint(6, 9)
            nums = [rng.randint(2, 9), rng.randint(10, 99)] + rng.sample(range(100, 400), k - 2)     # numbers of one, two and three digits
            rng.shuffle(nums)
            return [f"{p} {n}" for p, n in zip(rng.sample(PEOPLE, k), nums)]
        stem, high = rng.choice(("scores", "points", "tally", "results", "votes", "laps")), rng.random() < 0.5
        name, keep = f"{stem}.txt", f"{stem}-{rng.choice(('2025', 'old', 'march', 'last-week', 'backup'))}.txt"
        lines, other = draw(), draw()
        want = sorted(lines, key=lambda line: int(line.split()[1]), reverse=high)
        while lines == want:
            rng.shuffle(lines)
        first, last = ("highest", "lowest") if high else ("lowest", "highest")
        request = say(rng, f"Sort the lines of {name} by the number at the end of each line, {first} first. Leave {keep} as it is.",
                      f"Reorder {name} so that the lines go from the {first} number to the {last}; each line stays as it is otherwise, and {keep} is not touched.",
                      f"In {name}, put the lines in numeric order of their numbers, {first} first (so 9 comes {'after' if high else 'before'} 10). Do not change {keep}.")
        files, want_text = {name: "\n".join(lines) + "\n", keep: "\n".join(other) + "\n"}, "\n".join(want) + "\n"
    elif variant == "column":
        def draw():
            k = rng.randint(5, 8)
            qty = [rng.randint(1, 9), rng.randint(10, 99)] + rng.sample(range(100, 300), k - 2)
            rng.shuffle(qty)
            return [{"item": i, "qty": q, "shelf": f"{rng.choice('ABCD')}{rng.randint(1, 12)}"} for i, q in zip(rng.sample(THINGS, k), qty)]
        stem = rng.choice(("inventory", "stock", "parts", "supplies", "store"))
        name, keep = f"{stem}.csv", f"{stem}-{rng.choice(('old', 'backup', 'last-month', '2025'))}.csv"
        by = rng.choice(("qty", "qty", "item"))
        cols = ("shelf", "item", "qty") if by == "item" else rng.choice((("item", "qty", "shelf"), ("shelf", "item", "qty")))     # never the first column: a plain sort is not the answer
        rows, other = draw(), draw()
        up = by == "item" or rng.random() < 0.5
        order = "in alphabetical order" if by == "item" else "smallest first" if up else "largest first"
        want = sorted(rows, key=lambda r: r[by], reverse=not up)
        while rows == want:
            rng.shuffle(rows)
        table = lambda rs: ",".join(cols) + "\n" + "".join(",".join(str(r[c]) for c in cols) + "\n" for r in rs)
        request = say(rng, f"Sort the rows of {name} by the {by} column, {order}. The header line stays at the top, and {keep} stays as it is.",
                      f"Reorder the data rows of {name} by {by}, {order}, keeping the header as the first line. Do not change {keep}.")
        files, want_text = {name: table(rows), keep: table(other)}, table(want)
    elif variant == "date":
        def draw():
            rows = []
            for d in rng.sample(range(640), rng.randint(5, 8)):
                day = datetime.date(2025, 1, 1) + datetime.timedelta(days=d)
                what = rng.choice((f"{rng.choice(PEOPLE)} fixed the {rng.choice(THINGS)}", f"trip to {rng.choice(PLACES)}", f"new {rng.choice(THINGS)} delivered",
                                   f"{rng.choice(PEOPLE)} came to visit", f"meeting in {rng.choice(PLACES)}"))
                rows.append((day, f"{day.day:02d}/{day.month:02d}/{day.year} {what}"))
            return rows
        stem, oldest = rng.choice(("diary", "events", "bookings", "journal", "jobs")), rng.random() < 0.6
        name, keep = f"{stem}.txt", f"{stem}-{rng.choice(('copy', 'old', 'backup', '2024'))}.txt"
        rows, other = draw(), draw()
        want = [line for _day, line in sorted(rows, reverse=not oldest)]
        lines = [line for _day, line in rows]
        while lines == want:
            rng.shuffle(lines)
        request = say(rng, f"Put the lines of {name} in date order, {'oldest' if oldest else 'newest'} first. The dates are written day/month/year; the lines themselves do not change, and {keep} stays as it is.",
                      f"Sort {name} by date, {'earliest' if oldest else 'latest'} first (the dates are DD/MM/YYYY). Leave {keep} alone.")
        files, want_text = {name: "\n".join(lines) + "\n", keep: "".join(line + "\n" for _day, line in other)}, "\n".join(want) + "\n"
    elif variant == "section":
        heads = rng.sample(("To buy", "To pack", "To fix", "To borrow", "To return", "To visit"), 2)
        pool = rng.sample(THINGS, len(THINGS))

        def items(head):
            got = rng.sample(PLACES, rng.randint(4, 6)) if head == "To visit" else [pool.pop() for _ in range(rng.randint(4, 6))]
            while got == sorted(got):
                rng.shuffle(got)
            return got
        a, b = items(heads[0]), items(heads[1])
        title = rng.choice(("Weekend", "This week", f"Trip to {rng.choice(PLACES)}", "Before the move"))
        doc = lambda x, y: f"# {title}\n\n## {heads[0]}\n\n" + "".join(f"- {i}\n" for i in x) + f"\n## {heads[1]}\n\n" + "".join(f"- {i}\n" for i in y)
        t = rng.randint(0, 1)
        name, keep = rng.choice(("lists.md", "packing.md", "plans.md", "errands.md")), rng.choice(("ideas.md", "wishlist.md", "someday.md"))
        request = say(rng, f"In {name}, sort the items of the list under '{heads[t]}' alphabetically. The other list and the rest of the file stay as they are.",
                      f"Put the list under the heading '{heads[t]}' in {name} in alphabetical order; leave the other list, and {keep}, as they are.")
        idea = [pool.pop() for _ in range(3)]
        files = {name: doc(a, b), keep: f"# {keep[:-3].capitalize()}\n\n" + "".join(f"- a new {i}\n" for i in idea)}
        want_text = doc(sorted(a), b) if t == 0 else doc(a, sorted(b))
    else:
        stem, source = rng.choice((("guests", PEOPLE), ("invited", PEOPLE), ("shopping", THINGS), ("packing", THINGS), ("visited", PLACES), ("cities", PLACES),
                                  ("tags", STEMS), ("topics", STEMS)))
        name, keep = f"{stem}.txt", f"{stem}-{rng.choice(('2025', 'old', 'backup', 'draft'))}.txt"

        def draw():
            while True:
                base = rng.sample(source, rng.randint(5, 8))
                seq = list(base)
                for _ in range(rng.randint(2, 4)):
                    x = rng.choice(base)
                    seq.insert(rng.randint(seq.index(x) + 1, len(seq)), x)
                adjacent = [x for j, x in enumerate(seq) if j == 0 or seq[j - 1] != x]
                if base != sorted(base) and adjacent != base:          # neither `sort -u` nor `uniq` gives the answer
                    return base, seq
        want, seq = draw()
        _base, other = draw()
        request = say(rng, f"{name} has some lines more than once. Remove the repeats so that each line appears once, where it first appears; do not sort, and leave {keep} as it is.",
                      f"Drop the duplicate lines from {name}: keep the first occurrence of each line, delete the later ones, and keep the order. {keep} stays as it is.",
                      f"Make the lines of {name} unique, keeping each line's first appearance and the existing order; {keep} is not to be changed.")
        files, want_text = {name: "\n".join(seq) + "\n", keep: "\n".join(other) + "\n"}, "\n".join(want) + "\n"
    return {"kind": "change", "files": files, "request": request, "expect": {"files": {**files, name: want_text}},
            "solution": {"answer": f"{name} is in order.", "files": {name: want_text}}}


# ------------------------------------------------------------------ whitespace made regular in one kind of file --

PY_BODIES = ("def count_{s}(items):\n\ttotal = 0\n\tfor item in items:\n\t\tif item:\n\t\t\ttotal += 1\n\treturn total\n",
             "def read_{s}(path):\n\twith open(path) as handle:\n\t\treturn handle.read().splitlines()\n",
             "class {S}:\n\tdef __init__(self, size):\n\t\tself.size = size\n\n\tdef doubled(self):\n\t\treturn self.size * 2\n",
             "def greet_{s}(name):\n\tif name:\n\t\treturn 'hello ' + name\n\treturn 'hello'\n",
             "def total_{s}(prices):\n\tresult = 0\n\tfor price in prices:\n\t\tresult += price\n\treturn round(result, 2)\n",
             "def first_{s}(rows):\n\tfor row in rows:\n\t\tif row.strip():\n\t\t\treturn row\n\treturn None\n")


@family
def edit_whitespace(rng):
    """Make whitespace regular in the files of one kind only: tab indentation to four spaces, exactly one final newline, or CRLF endings to LF; other files keep theirs byte for byte."""
    variant = rng.choice(("tabs", "final", "crlf"))
    stems = rng.sample(STEMS, 6)
    if variant == "tabs":
        python = lambda s: "\n\n".join(b.format(s=s, S=s.capitalize()) for b in rng.sample(PY_BODIES, rng.randint(1, 2)))
        sub, tsv = rng.choice(("lib", "tools", "scripts")), f"{stems[4]}.tsv"
        tabbed = [f"{stems[0]}.py", f"{sub}/{stems[1]}.py"] + ([f"{stems[2]}.py"] if rng.random() < 0.5 else [])
        files = {rel: python(rel.split("/")[-1][:-3]) for rel in tabbed}
        files[f"{stems[3]}.py"] = python(stems[3]).replace("\t", "    ")              # already four spaces
        files["Makefile"] = f"all:\n\tpython3 {tabbed[0]}\n\nclean:\n\trm -f *.pyc\n"
        files[tsv] = "name\tqty\n" + "".join(f"{t}\t{rng.randint(1, 30)}\n" for t in rng.sample(THINGS, 3))
        want = {rel: (t.replace("\t", "    ") if rel.endswith(".py") else t) for rel, t in files.items()}
        request = say(rng, f"Change the indentation of the .py files here and in subfolders from tabs to spaces: each tab becomes four spaces. The Makefile and {tsv} need their tabs, so leave them, and every other file, as they are.",
                      "Our Python style is four spaces, not tabs. Replace every tab in the .py files (subfolders included) with four spaces; files that are not .py keep their tabs.",
                      "Some .py files in this folder tree are indented with tabs. Convert them to four spaces per tab, and do not touch any file that is not .py.")
        expect = {"files": want}
    elif variant == "final":
        sub = rng.choice(("notes", "docs", "letters"))
        targets = [f"{stems[0]}.txt", f"{stems[1]}.md", f"{sub}/{stems[2]}.txt"] + ([f"{sub}/{stems[3]}.md"] if rng.random() < 0.5 else [])
        endings = ["", rng.choice(("\n\n", "\n\n\n"))] + [rng.choice(("", "\n", "\n\n")) for _ in targets[2:]]
        rng.shuffle(endings)
        bare = {rel: _doc(rel[-4:] if rel.endswith(".txt") else ".md", rel.split("/")[-1].split(".")[0].capitalize(), [_sentence(rng) for _ in range(rng.randint(1, 3))]).rstrip("\n")
                for rel in targets}
        files = {rel: bare[rel] + end for rel, end in zip(targets, endings)}
        files["data.csv"] = "name,qty\n" + "\n".join(f"{t},{rng.randint(1, 30)}" for t in rng.sample(THINGS, 3))       # no final newline, and it stays so
        files["config.json"] = json.dumps({"name": stems[4], "items": rng.randint(2, 9)})
        want = {**files, **{rel: bare[rel] + "\n" for rel in targets}}
        request = say(rng, "Make every .txt and .md file in this folder and its subfolders end with exactly one newline: add one where the last line has none, and remove the extra empty lines at the end where there are some. Other files stay as they are, byte for byte.",
                      "Some text files here end without a newline and some end with several. Fix the .txt and .md files (subfolders too) so that each ends with a single newline character; leave data.csv and config.json untouched.")
        expect = {"files": want, "fn": _exact(want)}
    else:
        targets = [f"{s}.txt" for s in stems[:rng.randint(2, 4)]]
        lines = {rel: [_sentence(rng) for _ in range(rng.randint(2, 4))] for rel in targets}
        unix = targets[-1] if rng.random() < 0.4 else None                    # one may have LF already
        files = {rel: "".join(line + ("\n" if rel == unix else "\r\n") for line in lines[rel]) for rel in targets}
        for s in stems[4:4 + rng.randint(1, 2)]:
            files[f"{s}.bat"] = f"@echo off\r\necho Copying {s}\r\nxcopy {s} backup /E /I\r\n"
        want = {**files, **{rel: "".join(line + "\n" for line in lines[rel]) for rel in targets}}
        request = say(rng, "The .txt files here came from a Windows machine and end their lines with CR LF. Convert them to Unix line endings (LF only). The .bat files keep their CR LF endings, and nothing else changes.",
                      "Change the line endings of every .txt file in this folder from Windows (CRLF) to Unix (LF). Leave the .bat files, and everything else, as they are.")
        expect = {"files": {rel: t.replace("\r\n", "\n") for rel, t in want.items()}, "fn": _exact(want)}     # the judge reads text with CR LF as LF
    return {"kind": "multi", "files": files, "request": request, "expect": expect,
            "solution": {"answer": "Done.", "files": {rel: t for rel, t in want.items() if t != files[rel]}}}


# ------------------------------------------------------------------ a numbered list renumbered --

STEPS = ("Unpack the {thing} and check it for damage.", "Write the serial number of the {thing} in the log.", "Ask {person} for the key to the {place} room.",
         "Plug in the {thing} and wait for the green light.", "Wipe the {thing} with a dry cloth.", "Put the {thing} back on its shelf.",
         "Send a short note to {person} when you are done.", "Switch off the {thing} at the wall.", "Count the spare parts of the {thing}.",
         "Lock the cupboard in the {place} room.", "Take a photo of the label on the {thing}.", "Check that the {thing} is on the list.",
         "Book the {place} room for {day}.", "Fill in the form for the {thing}.", "Tell {person} which {thing} you used.", "Close the windows in the {place} room.")


def _steps(rng, n: int, avoid=()) -> list:
    out = []
    for template in rng.sample(STEPS, len(STEPS)):
        text = template.format(thing=rng.choice(THINGS), person=rng.choice(PEOPLE), place=rng.choice(PLACES), day=rng.choice(WEEKDAYS))
        if text not in out and text not in avoid:
            out.append(text)
        if len(out) == n:
            break
    return out


@family
def edit_renumber_list(rng):
    """Renumber a markdown list after a step was added or taken out (or add or remove one and renumber); the other list counts from 1 on its own, and a file beside it stays."""
    variant = rng.choice(("inserted", "removed", "insert", "remove"))
    delim = rng.choice((".", ".", ")"))
    name = rng.choice(("setup.md", "checklist.md", "howto.md", "steps.md", "closing.md"))
    head_a, head_b = rng.sample(("Steps", "Before you start", "On the day", "Afterwards", "Checks", "Packing up"), 2)
    title = rng.choice((f"Setting up the {rng.choice(THINGS)}", f"Moving to the {rng.choice(PLACES)} office", "Closing up for the night", f"Lending out the {rng.choice(THINGS)}"))
    intro, middle = _sentence(rng), _sentence(rng)
    n = rng.randint(4, 7)
    a = _steps(rng, n + 1)
    b = _steps(rng, rng.randint(3, 5), avoid=a)
    # the numbers a list shows after a step went in at p (its own number given, the later ones not moved on: p+1 twice)
    # or out at p (the later ones not moved back: p+1 is missing)
    inserted = lambda m, p: list(range(1, p + 2)) + list(range(p + 1, m))
    removed = lambda m, p: list(range(1, p + 1)) + list(range(p + 2, m + 2))
    t, k = "", 0
    if variant == "inserted":
        start_a, numbers, want_a = a, inserted(n + 1, rng.randint(1, n - 1)), a
    elif variant == "removed":
        start_a, numbers, want_a = a[:n], removed(n, rng.randint(1, n - 1)), a[:n]
    elif variant == "insert":
        t, k = a[n], rng.randint(2, n)
        start_a, numbers, want_a = a[:n], list(range(1, n + 1)), a[:k - 1] + [t] + a[k - 1:n]
    else:
        t = a[rng.randint(0, n - 2)]
        start_a, numbers, want_a = a[:n], list(range(1, n + 1)), [x for x in a[:n] if x != t]
    both = variant in ("inserted", "removed") and rng.random() < 0.4
    numbers_b = (inserted(len(b), rng.randint(1, len(b) - 2)) if variant == "inserted" else removed(len(b), rng.randint(1, len(b) - 1))) if both else list(range(1, len(b) + 1))
    kept = [x for x in want_a if x in start_a]
    notes = {rng.choice(kept): f"(the {rng.choice(THINGS)} is in the {rng.choice(PLACES)} cupboard)"} if rng.random() < 0.4 else {}

    def listing(items, numbers):                  # an item's second line, if it has one, is indented under its text
        return "".join(f"{number}{delim} {item}\n" + (f"   {notes[item]}\n" if item in notes else "") for item, number in zip(items, numbers))

    def doc(list_a, list_b):
        return f"# {title}\n\n{intro}\n\n## {head_a}\n\n{list_a}\n{middle}\n\n## {head_b}\n\n{list_b}"
    start = doc(listing(start_a, numbers), listing(b, numbers_b))
    want = doc(listing(want_a, range(1, len(want_a) + 1)), listing(b, range(1, len(b) + 1)))
    files = {name: start, "notes.md": "# Notes\n\n" + "".join(f"1. {_sentence(rng)}\n" for _ in range(3))}
    rest = f" The list under '{head_b}' has the same problem: renumber it too, counting from 1 again." if both else ""
    if variant == "inserted":
        request = say(rng, f"I added a step to the list under '{head_a}' in {name}, and now two steps have the same number. Renumber that list 1, 2, 3, ... in its current order, without changing any text.{rest}",
                      f"The numbers of the list under '{head_a}' in {name} are off since a step was inserted. Fix the numbering so it runs 1, 2, 3, ... from the top; the steps stay in their order.{rest}")
    elif variant == "removed":
        request = say(rng, f"I deleted a step from the list under '{head_a}' in {name}, so the numbers skip one. Renumber that list so it runs 1, 2, 3, ... with no gap, without changing any text.{rest}",
                      f"After a step was taken out, the list under '{head_a}' in {name} jumps a number. Renumber it 1, 2, 3, ... in its current order.{rest}")
    elif variant == "insert":
        request = say(rng, f"In {name}, add the step `{t}` to the list under '{head_a}' so that it becomes step {k}, and renumber the steps after it. Leave the rest of the file as it is.",
                      f"Insert `{t}` as step {k} of the list under '{head_a}' in {name}; the steps that were {k} and later each get a number one higher. Nothing else changes.")
    else:
        request = say(rng, f"Take the step `{t}` out of the list under '{head_a}' in {name} and renumber the steps after it so there is no gap. Change nothing else.",
                      f"Remove `{t}` from the list under '{head_a}' in {name}, and renumber the remaining steps 1, 2, 3, ... in order.")
    return {"kind": "change", "files": files, "request": request, "expect": {"files": {**files, name: want}},
            "solution": {"answer": "Renumbered.", "files": {name: want}}}


# ------------------------------------------------------------------ corrections from a table, whole words only --

TYPOS = {"to": "ot", "is": "si", "of": "fo", "it": "ti", "in": "ni", "do": "od", "we": "ew", "be": "eb", "the": "teh", "and": "adn",
         "that": "taht", "with": "wiht", "you": "yuo", "their": "thier", "what": "waht", "have": "ahve", "can": "cna", "not": "ont"}
# a slot for each word a typo stands in for; the fixed words hold the short typos inside them (n-ot-e, vi-si-t, fo-od,
# ti-me, ni-ght, go-od, n-ew, w-eb), which a replacement that is not by whole words breaks
WRITTEN = ("By the end {of} {the} month {we} {have} {to} {be} ready {with} {the} new web page.",
           "Lunch {is} nice when {the} food {is} good {and} hot.",
           "Please note {that} {you} {can} visit {the} office until nine {in} {the} evening.",
           "Today {we} {do} {not} know {what} time {the} other team {can} come.",
           "Over {the} last few weeks {we} followed a simple plan {with} four steps.",
           "All {their} notes {and} {the} title page {have} {to} {be} printed {in} time.",
           "Ask {the} team {what} {you} should {do} {with} {the} tiny spare parts.",
           "Bring {the} notebook {and} {the} lamp {to} {the} rebuild meeting at nine.",
           "Our web shop {is} closed for four days, so {we} {can} {not} send {the} orders.",
           "Most {of} {the} music {that} {we} play comes from {the} other room.",
           "Last night {it} was {not} easy {to} find {the} note {with} {the} code.",
           "Since spring {we} {have} kept {the} spare keys {in} a tin box.",
           "Every visitor {can} sign {the} book {in} {the} front hall.")
SLOT = re.compile(r"\{(\w+)\}")


def _typed(rng, chosen: list, table: list) -> str:
    """The sentences with some of the table's words mistyped, each of them at least once."""
    slots = [m.group(1) for line in chosen for m in SLOT.finditer(line)]
    typo = [w in table and rng.random() < 0.6 for w in slots]
    for w in table:
        if w in slots and not any(t for t, s in zip(typo, slots) if s == w):
            typo[slots.index(w)] = True
    filled = iter(TYPOS[w] if t else w for w, t in zip(slots, typo))
    lines = [SLOT.sub(lambda m: next(filled), line) for line in chosen]
    cut = rng.randint(1, len(lines) - 1)
    return " ".join(lines[:cut]) + "\n\n" + " ".join(lines[cut:]) + "\n"


@family
def edit_corrections(rng):
    """Apply a table of corrections (wrong word, right word) to a text by whole words only, so a wrong word inside a longer word stays; the table and other files stay."""
    while True:
        chosen = rng.sample(WRITTEN, rng.randint(4, 6))
        slots = sorted({m.group(1) for line in chosen for m in SLOT.finditer(line)})
        fixed = set(re.findall(r"[A-Za-z]+", SLOT.sub(" ", " ".join(chosen))))
        inside = [w for w in slots if any(TYPOS[w] in x and x != TYPOS[w] for x in fixed)]     # its typo also sits inside a word here
        if inside:
            break
    table = rng.sample(inside, min(len(inside), rng.randint(1, 3)))
    rest = [w for w in slots if w not in table]
    table += rng.sample(rest, min(len(rest), rng.randint(1, 2)))
    wrong = {TYPOS[w]: w for w in table}
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(wrong, key=len, reverse=True)) + r")\b")
    rows = sorted(wrong.items(), key=lambda kv: rng.random())
    table_name, table_text = rng.choice((("fixes.csv", "wrong,right\n" + "".join(f"{a},{b}\n" for a, b in rows)),
                                        ("typos.txt", "".join(f"{a} -> {b}\n" for a, b in rows)),
                                        ("corrections.tsv", "wrong\tright\n" + "".join(f"{a}\t{b}\n" for a, b in rows))))
    def more():                                   # three more sentences, at least one with a slot for a word of the table
        while True:
            lines = rng.sample(WRITTEN, 3)
            if any(w in table for line in lines for w in SLOT.findall(line)):
                return lines
    targets = rng.sample(("letter.txt", "newsletter.md", "notice.txt", "draft.txt", "announcement.md"), rng.choice((1, 1, 2)))
    files = {table_name: table_text}
    for rel in targets:
        body = _typed(rng, chosen if rel == targets[0] else more(), table)
        to, by = rng.sample(PEOPLE, 2)
        files[rel] = f"# {rel[:-3].capitalize()}\n\n{body}" if rel.endswith(".md") else f"Dear {to},\n\n{body}\nBest wishes,\n{by}\n"
    files["old-notes.txt"] = _typed(rng, more(), table)                         # has the same kind of mistakes, and is not to be corrected
    want = {**files, **{rel: pattern.sub(lambda m: wrong[m.group(1)], files[rel]) for rel in targets}}
    word, part = rng.choice(sorted({(x, y) for x in re.findall(r"[A-Za-z]+", files[targets[0]]) for y in wrong if y in x and x != y}))
    example = f" (so `{word}` stays as it is even though it contains `{part}`)"
    names = _and(targets)
    request = say(rng, f"{table_name} lists spelling mistakes and their corrections. Fix those mistakes in {names}: replace each wrong word with its correction, but only where it stands as a whole word{example}. Change nothing else.",
                  f"Apply the corrections in {table_name} to {names}. Only whole words count, spelled exactly as in the table{example}; the rest of the text stays the same, and so do the other files.",
                  f"Correct {names} with the table in {table_name} (each row: a wrong word, then the right one), whole words only{example}. Do not edit any other file.")
    return {"kind": "change", "files": files, "request": request, "expect": {"files": want},
            "solution": {"answer": "Corrected.", "files": {rel: want[rel] for rel in targets}}}


# ------------------------------------------------------------------ one config value changed, one key added --

@family
def edit_config_value(rng):
    """Change one value in a config file (ini, env, json or yaml) where the same or a longer key also appears, and add a missing key where asked; every other line stays."""
    variant = rng.choice(("ini", "env", "json", "yaml"))
    app = rng.choice(PKGS)
    expect = {}
    if variant == "ini":
        name = rng.choice(("app.ini", "service.ini", "server.ini", "tool.ini"))
        sections = {"server": [["host", "localhost"], ["port", str(rng.randint(8000, 8999))], ["workers", str(rng.randint(2, 8))]],
                    "database": [["host", "localhost"], ["port", str(rng.randint(5400, 5499))], ["name", rng.choice(STEMS)], ["timeout", str(rng.randint(5, 30))]],
                    "logging": [["level", "info"], ["file", f"{app}.log"]]}
        section, key = rng.choice((("server", "port"), ("database", "port"), ("database", "port"), ("database", "timeout"), ("server", "workers"), ("logging", "level")))
        current = dict(sections[section])[key]
        value = rng.choice(("debug", "warning", "error")) if key == "level" else str(int(current) + rng.randint(1, 900 if key == "port" else 20))
        add = rng.choice({"server": (("keepalive", "60"), ("max_body", "10m"), ("threads", "4")), "database": (("pool_size", "10"), ("retries", "3"), ("sslmode", "require")),
                          "logging": (("rotate", "daily"), ("max_size", "5MB"), ("format", "plain"))}[section])

        def render(secs):
            out = [f"; {app} settings"]
            for sec, pairs in secs.items():
                out.append(f"[{sec}]")
                for k, v in pairs:
                    out += (["; keep the timeout short on the laptop"] if (sec, k) == ("database", "timeout") else []) + [f"{k} = {v}"]
                out.append("")
            return "\n".join(out[:-1]) + "\n"
        changed = {sec: [[k, value if (sec, k) == (section, key) else v] for k, v in pairs] + ([list(add)] if sec == section else []) for sec, pairs in sections.items()}
        files, want = {name: render(sections)}, render(changed)
        request = say(rng, f"In {name}, set the {key} of the [{section}] section to {value}, and add the line `{add[0]} = {add[1]}` at the end of that section. Keep the comments and every other line exactly as they are.",
                      f"Change [{section}] {key} to {value} in {name} and give [{section}] a new last line, `{add[0]} = {add[1]}`. Nothing else in the file changes; the other sections keep their own values.")
    elif variant == "env":
        name, p = rng.choice(("app.env", "service.env", "local.env", "deploy.env")), rng.randint(3000, 8999)
        groups = [("LOG_LEVEL", "info", ("LOG_LEVEL_FILE", "warn"), ("debug", "warning", "error")),
                  ("PORT", str(p), ("PORT_ADMIN", str(p + 1)), tuple(str(p + d) for d in (2, 10, 100, 444))),
                  ("CACHE_SIZE", rng.choice(("64", "128")), ("CACHE_SIZE_MAX", "512"), ("256", "384")),
                  ("TIMEOUT", "30", ("TIMEOUT_CONNECT", "5"), ("45", "60", "90"))]
        used = rng.sample(groups, 3)
        key, current, _decoy, values = rng.choice(used)
        value, aside = rng.sample(values, 2)
        lines = [f"# {app} settings", f"# {key}={aside} for local runs", f"APP_NAME={app}"]
        for k, v, (dk, dv), _values in used:
            lines += [f"{k}={v}", f"{dk}={dv}"][::rng.choice((1, -1))]
        lines.append(f"DATA_DIR=/srv/{rng.choice(STEMS)}")
        add = rng.choice(("RETRIES=3", "MAX_UPLOAD_MB=20", "TZ=UTC", "FEATURE_EXPORT=on"))
        files = {name: "\n".join(lines) + "\n"}
        want = "\n".join(f"{key}={value}" if line == f"{key}={current}" else line for line in lines) + f"\n{add}\n"
        request = say(rng, f"In {name}, set {key} to {value} and add `{add}` as the last line. Every other line, comments included, stays exactly as it is.",
                      f"Change the value of {key} in {name} to {value} (only {key} itself, not the keys whose names start the same way, and not the comment), then append the line `{add}`. Leave everything else alone.")
    elif variant == "json":
        name = rng.choice(("config.json", "app.json", "service.json"))
        data = {"server": {"host": "localhost", "port": rng.randint(8000, 8999), "workers": rng.randint(2, 8)},
                "database": {"host": "localhost", "port": rng.randint(5400, 5499), "name": rng.choice(STEMS)}, "logging": {"level": "info", "file": f"{app}.log"}}
        section, key = rng.choice((("server", "port"), ("database", "port"), ("database", "port"), ("server", "workers"), ("logging", "level"), ("database", "name")))
        current = data[section][key]
        value = {"port": lambda: current + rng.randint(1, 500), "workers": lambda: current + rng.randint(1, 6), "level": lambda: rng.choice(("debug", "warning", "error")),
                 "name": lambda: rng.choice([x for x in STEMS if x != current])}[key]()
        add = rng.choice({"server": (("timeout", 30), ("keepalive", True)), "database": (("pool_size", 10), ("ssl", True), ("retries", 3)),
                          "logging": (("rotate", "daily"), ("color", False))}[section])
        changed = json.loads(json.dumps(data))
        changed[section][key] = value
        changed[section][add[0]] = add[1]
        files, want = {name: json.dumps(data, indent=2) + "\n"}, None
        expect["json"] = {name: changed}
        also = f" The {'database' if section == 'server' else 'server'} port stays as it is." if key == "port" else ""
        request = say(rng, f"In {name}, change the {key} of the {section} object to `{json.dumps(value)}` and add the key `{add[0]}` with the value `{json.dumps(add[1])}` to that same object.{also} Nothing else changes.",
                      f"Set {section}.{key} to `{json.dumps(value)}` in {name}, and give the {section} object a new key `{add[0]}` whose value is `{json.dumps(add[1])}`. Everything else in the file keeps its value.")
    else:
        name = rng.choice(("config.yaml", "app.yml", "service.yaml"))
        sections = {"http": [["host", "localhost"], ["port", str(rng.randint(8000, 8999))], ["retries", str(rng.randint(1, 4))]],
                    "database": [["host", "localhost"], ["port", str(rng.randint(5400, 5499))], ["retries", str(rng.randint(5, 9))]], "logging": [["level", "info"]]}
        section, key = rng.choice(("http", "database")), rng.choice(("port", "retries"))
        value = str(int(dict(sections[section])[key]) + rng.randint(1, 300 if key == "port" else 5))
        add = rng.choice((("timeout", "30"), ("keepalive", "true"), ("pool", "4"), ("verify", "false")))
        render = lambda secs: f"# {app}\n" + "".join(f"{sec}:\n" + "".join(f"  {k}: {v}\n" for k, v in pairs) for sec, pairs in secs.items())
        changed = {sec: [pair for k, v in pairs for pair in ([[k, value], list(add)] if (sec, k) == (section, key) else [[k, v]])] for sec, pairs in sections.items()}
        files, want = {name: render(sections)}, render(changed)
        other = "database" if section == "http" else "http"
        request = say(rng, f"In {name}, under `{section}:` set `{key}` to {value}, and add `{add[0]}: {add[1]}` on a new line right after it, indented the same way. Leave every other line as it is.",
                      f"Change {section}.{key} to {value} in {name}, and put the line `  {add[0]}: {add[1]}` directly below it. Nothing else changes; {other} keeps its own {key}.")
    if want is not None:
        expect["files"] = {name: want}
    solution = want if want is not None else json.dumps(expect["json"][name], indent=2) + "\n"
    return {"kind": "change", "files": files, "request": request, "expect": expect, "solution": {"answer": "Updated.", "files": {name: solution}}}


# ------------------------------------------------------------------ a line put next to a marker in several files --

@family
def edit_insert_line(rng):
    """Put a given line right after (or right before) the line that matches a marker, in each file that has the marker and lacks the line; the rest stay."""
    variant = rng.choice(("import", "changelog", "stylesheet", "restart"))
    files, want = {}, {}
    if variant == "import":
        mod = rng.choice(("logging", "sys", "json", "time", "shutil"))
        stems = rng.sample(STEMS, rng.randint(4, 5))
        kinds = ["os", "os", rng.choice(("os.path", "from"))] + [rng.choice(("os", "os.path", "from", "none")) for _ in stems[3:]]
        rng.shuffle(kinds)
        for s, kind in zip(stems, kinds):
            marker = {"os": "import os", "os.path": "import os.path", "from": "from os import path", "none": "import re"}[kind]
            imports = rng.sample(("import csv", "from pathlib import Path"), rng.randint(0, 2))
            imports.insert(rng.randint(0, len(imports)), marker)
            body = {"os": f"def {s}_files(folder):\n    return sorted(os.listdir(folder))\n", "os.path": f"def {s}_name(p):\n    return os.path.basename(p)\n",
                    "from": f"def {s}_name(p):\n    return path.basename(p)\n", "none": f"def {s}_words(text):\n    return re.findall('[a-z]+', text)\n"}[kind]
            files[f"{s}.py"] = f'"""{s.capitalize()} helpers."""\n' + "\n".join(imports) + "\n\n\n" + body
            want[f"{s}.py"] = files[f"{s}.py"].replace("\nimport os\n", f"\nimport os\nimport {mod}\n") if kind == "os" else files[f"{s}.py"]
        files["README.md"] = "# Tools\n\nEvery script that walks folders starts with\n\n```\nimport os\n```\n"     # the line, but not in a .py file
        request = say(rng, f"In every .py file here that has the line `import os`, add the line `import {mod}` right after it. Files without that exact line (`import os.path` or `from os import path` do not count) stay as they are.",
                      f"Each .py file in this folder that contains exactly the line `import os` should get `import {mod}` on the next line. Change no other line and no other file.")
    elif variant == "changelog":
        entry = rng.choice(("Dropped support for Python 3.9.", f"Moved the {rng.choice(THINGS)} settings to a config file.", "Updated the licence text.",
                            f"Renamed the --{rng.choice(STEMS)} option."))
        pkgs = rng.sample(PKGS, rng.randint(3, 4))
        has = set(rng.sample(range(len(pkgs)), rng.randint(2, len(pkgs) - 1)))
        for i, p in enumerate(pkgs):
            released = f"## {rng.randint(0, 2)}.{rng.randint(0, 9)}.{rng.randint(0, 9)}\n" + "".join(f"- {_change(rng)}\n" for _ in range(rng.randint(1, 2)))
            unreleased = "## Unreleased\n" + "".join(f"- {_change(rng)}\n" for _ in range(rng.randint(1, 2))) + "\n" if i in has else ""
            files[f"packages/{p}/CHANGELOG.md"] = f"# Changelog\n\n{unreleased}{released}"
            want[f"packages/{p}/CHANGELOG.md"] = files[f"packages/{p}/CHANGELOG.md"].replace("## Unreleased\n", f"## Unreleased\n- {entry}\n")
        files["CHANGELOG.md"] = f"# Changelog\n\n## Unreleased\n- {_change(rng)}\n"                                # the top-level one is not a package's
        request = say(rng, f"In each CHANGELOG.md under packages/ that has a `## Unreleased` section, add the line `- {entry}` directly below the `## Unreleased` line. Changelogs without that section, and the CHANGELOG.md at the top level, stay as they are.",
                      f"Note this change in the package changelogs (packages/*/CHANGELOG.md): put `- {entry}` as the first line under `## Unreleased`, in every one that has that heading. Leave the others, and the top-level CHANGELOG.md, alone.")
    elif variant == "stylesheet":
        css = rng.choice(("style.css", "site.css", "theme.css", "print.css"))
        link = f'<link rel="stylesheet" href="{css}">'
        stems = rng.sample(STEMS, rng.randint(3, 5))
        has = set(rng.sample(range(len(stems)), rng.randint(1, len(stems) - 2)))
        for i, s in enumerate(stems):
            head = f"<title>{s.capitalize()}</title>\n" + ('<meta charset="utf-8">\n' if rng.random() < 0.5 else "")
            page = lambda h: f"<!DOCTYPE html>\n<html>\n<head>\n{h}</head>\n<body>\n<h1>{s.capitalize()}</h1>\n<p>{_sentence(rng)}</p>\n</body>\n</html>\n"
            files[f"{s}.html"] = page(head + (link + "\n" if i in has else ""))
            want[f"{s}.html"] = files[f"{s}.html"].replace("</head>\n", f"{link}\n</head>\n") if i not in has else files[f"{s}.html"]
        files[css] = "body { font-family: sans-serif; }\n"
        request = say(rng, f"Every .html page here should load {css}. In each page that does not have it yet, insert the line `{link}` directly above the `</head>` line; pages that have it stay as they are.",
                      f"Add `{link}` on its own line just before `</head>` in each .html file that lacks it. Do not change anything else.")
    else:
        value = rng.choice(("on-failure", "always"))
        jobs = rng.sample(("backup", "indexer", "notifier", "sync", "cleanup", "mirror", "report", "thumbnailer"), rng.randint(3, 4))
        has = set(rng.sample(range(len(jobs)), rng.randint(1, len(jobs) - 2)))
        for i, s in enumerate(jobs):
            existing = f"Restart={rng.choice(('always', 'on-failure', 'no'))}\n" if i in has else ""
            files[f"units/{s}.service"] = f"[Unit]\nDescription={s.capitalize()} job\n\n[Service]\nExecStart=/usr/local/bin/{s}\n{existing}\n[Install]\nWantedBy=default.target\n"
            want[f"units/{s}.service"] = files[f"units/{s}.service"].replace("[Service]\n", f"[Service]\nRestart={value}\n") if i not in has else files[f"units/{s}.service"]
        files["units/README.md"] = "User units for the nightly jobs.\n"
        request = say(rng, f"In each .service file under units/ that has no `Restart=` line, add `Restart={value}` on the line right after `[Service]`. Units that already have a `Restart=` line stay as they are.",
                      f"Make the services in units/ restart: put `Restart={value}` directly below the `[Service]` line of every .service file that does not set Restart= yet. Leave the rest alone.")
    return {"kind": "multi", "files": files, "request": request, "expect": {"files": {**files, **want}},
            "solution": {"answer": "Inserted.", "files": {rel: t for rel, t in want.items() if t != files[rel]}}}
