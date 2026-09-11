#!/usr/bin/env python3
"""t/tasks_io.py: the one place that reads a task file, .t or .json.

ROADMAP 14.1: t/tasks/ holds .t files; the JSON is derived and never edited.
`surface.parse`/`surface.print_task` are the notation's own round trip
(surface.py's --check is the measurement of it); this module is only the
small amount of path and extension handling that every reader of a tasks
directory duplicated before it existed: pick the file (.t preferred, .json
for a directory that has never been converted, such as a spec-experiment
run's own out/.../tasks/, which stays JSON on purpose), read it, and name it
by its stem.

Nothing here changes what a task IS -- a JSON-shaped dict, exactly as
surface.parse and json.load both produce. A caller that already has a dict
does not need this module at all.
"""
from __future__ import annotations

import json
from pathlib import Path

import surface

KNOWN_VERSIONS = (0, 1)


def task_name(path) -> str:
    """The task's name: a task file's stem, .t or .json alike."""
    return Path(path).stem


def load_task(path) -> dict:
    """Read one task file. A .t file is parsed with surface.parse; anything
    else (.json, or no suffix) is read as the JSON the notation is derived
    from. Older callers that only ever pass a .json path keep working
    unchanged."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".t":
        task = surface.parse(text)
    else:
        task = json.loads(text)
    assert task.get("t") in KNOWN_VERSIONS, (
        f"{path.name}: not a t task I know (t={task.get('t')!r}, "
        f"known: {KNOWN_VERSIONS})")
    return task


def load_dir(directory) -> list[Path]:
    """The sorted list of task file paths in `directory`: .t files if the
    directory has any (the committed corpus, post-14.1), else .json files
    (an unconverted corpus, such as a spec-experiment run's generated
    tasks/ or a lifted-task sweep). task_name(path) gives each one's name."""
    d = Path(directory)
    paths = sorted(d.glob("*.t"))
    if paths:
        return paths
    return sorted(d.glob("*.json"))


def find(directory, name: str) -> Path:
    """The path for task `name` inside `directory`: `<name>.t` if it exists,
    else `<name>.json`. For callers that build a path from a name they
    already have (fewshot examples, named regression fixtures) rather than
    globbing a whole directory."""
    d = Path(directory)
    t_path = d / f"{name}.t"
    if t_path.exists():
        return t_path
    return d / f"{name}.json"
