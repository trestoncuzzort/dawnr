"""skills.py: packaged instructions (and optional scripts) the model loads only when a task needs them.

The folder format is the Agent Skills specification (agentskills.io/specification,
read 2026-09-26): a directory holding SKILL.md, whose YAML front matter has
`name` (1-64 lowercase letters, digits and single hyphens, not starting or
ending with one, equal to the folder's name) and `description` (1-1024
characters, what the skill does and when to use it), then Markdown
instructions; optional scripts/, references/, assets/. Loading is the
specification's progressive disclosure: the name and description of every
skill are in the index from the start, the body arrives when the model calls
`skill`, and other files only when asked for by path.

Not taken, on purpose: `allowed-tools` is read and recorded but grants
nothing, and Claude Code's front-matter hooks and `!command` context
injection are not supported, because each would let a file change what the
harness permits or runs. Permissions come only from the operator's policy.

The front matter is parsed by a small reader of the YAML subset skills use
(`key: value`, quoted scalars, `>`/`|` blocks, one level of `metadata:`
mapping), so the harness needs no YAML library; anything outside the subset
is refused by line, never guessed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .tools import CallContext, Tool, ToolResult, one_line

NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME, MAX_DESCRIPTION = 64, 1024
MAX_FILE_BYTES = 256 * 1024
MAX_LISTED_FILES = 50
MAX_INDEX_DESCRIPTION = 240


class SkillError(ValueError):
    pass


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    body: str
    meta: dict = field(default_factory=dict)

    def index_line(self) -> str:
        return f"{self.name}: {one_line(self.description, MAX_INDEX_DESCRIPTION)}"

    def files(self) -> list[str]:
        out = []
        for p in sorted(self.path.rglob("*")):
            if p.is_file() and p.name != "SKILL.md" and "__pycache__" not in p.parts:
                out.append(p.relative_to(self.path).as_posix())
        return out


def _scalar(raw: str, where: str):
    raw = raw.strip()
    if raw.startswith('"'):
        try:
            return json.loads(raw)
        except ValueError:
            raise SkillError(f"{where}: unreadable double-quoted value") from None
    if raw.startswith("'"):
        if len(raw) < 2 or not raw.endswith("'"):
            raise SkillError(f"{where}: unclosed single-quoted value")
        return raw[1:-1].replace("''", "'")
    if " #" in raw:
        raw = raw.split(" #", 1)[0].rstrip()
    return raw


def parse_front_matter(text: str) -> tuple[dict, str]:
    """(front matter as a dict, the Markdown body) of a SKILL.md."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillError("SKILL.md must start with a --- line")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise SkillError("SKILL.md front matter has no closing --- line") from None
    meta: dict = {}
    i = 1
    while i < end:
        line = lines[i]
        where = f"front matter line {i + 1}"
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0] in " \t":
            raise SkillError(f"{where}: unexpected indentation")
        key, sep, rest = line.partition(":")
        key = key.strip()
        if not sep or not re.match(r"^[A-Za-z0-9_-]+$", key):
            raise SkillError(f"{where}: expected `key: value`")
        rest = rest.strip()
        block = []
        j = i + 1
        while j < end and (not lines[j].strip() or lines[j][0] in " \t"):
            block.append(lines[j])
            j += 1
        while block and not block[-1].strip():
            block.pop()
        if rest in (">", "|", ">-", "|-"):
            texts = [b.strip() for b in block]
            meta[key] = (" ".join(t for t in texts if t) if rest.startswith(">") else "\n".join(texts)).strip()
        elif rest == "":
            mapping = {}
            for k, b in enumerate(block):
                if not b.strip():
                    continue
                sub, sep2, val = b.strip().partition(":")
                if not sep2:
                    raise SkillError(f"front matter line {i + 2 + k}: expected `key: value` under {key}")
                mapping[sub.strip()] = _scalar(val, f"front matter line {i + 2 + k}")
            meta[key] = mapping
        else:
            if block:
                raise SkillError(f"{where}: a multi-line value needs `>` or `|`")
            meta[key] = _scalar(rest, where)
        i = j
    return meta, "\n".join(lines[end + 1:]).strip("\n") + "\n"


def load_skill(folder: str | Path) -> Skill:
    folder = Path(folder)
    md = folder / "SKILL.md"
    if not md.is_file():
        raise SkillError(f"{folder.name}: no SKILL.md")
    meta, body = parse_front_matter(md.read_text(encoding="utf-8"))
    name, description = meta.get("name"), meta.get("description")
    if not isinstance(name, str) or not name:
        raise SkillError(f"{folder.name}: front matter needs a name")
    if len(name) > MAX_NAME or not NAME.match(name):
        raise SkillError(f"{folder.name}: name {name!r} is not 1-64 lowercase letters, digits and single hyphens")
    if name != folder.name:
        raise SkillError(f"{folder.name}: name {name!r} does not match its folder")
    if not isinstance(description, str) or not description.strip():
        raise SkillError(f"{name}: front matter needs a description")
    if len(description) > MAX_DESCRIPTION:
        raise SkillError(f"{name}: description is over {MAX_DESCRIPTION} characters")
    return Skill(name, description.strip(), folder.resolve(), body, meta)


def discover(dirs) -> tuple[dict[str, Skill], list[str]]:
    """Skills in the given directories, in order: ({name: skill}, problems). The first of a name wins."""
    skills: dict[str, Skill] = {}
    problems: list[str] = []
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            problems.append(f"{d}: not a directory")
            continue
        for folder in sorted(p for p in d.iterdir() if p.is_dir()):
            if not (folder / "SKILL.md").exists():
                continue
            try:
                skill = load_skill(folder)
            except (SkillError, OSError, UnicodeDecodeError) as e:
                problems.append(f"{folder}: {e}")
                continue
            if skill.name in skills:
                problems.append(f"{folder}: skill {skill.name} already loaded from {skills[skill.name].path}")
                continue
            skills[skill.name] = skill
    return skills, problems


def _inside(skill: Skill, rel: str) -> Path:
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or rel.startswith(("/", "\\")):
        raise SkillError(f"file {rel!r}: give a path relative to the skill's folder")
    target = (skill.path / rel).resolve()
    try:
        target.relative_to(skill.path)
    except ValueError:
        raise SkillError(f"file {rel!r} is outside the skill's folder") from None
    return target


def skill_tool(skills: dict[str, Skill]) -> Tool:
    """`skill {"name"}` loads a skill's instructions; `skill {"name", "file"}` reads one of its files."""

    def run(args: dict, ctx: CallContext) -> ToolResult:
        skill = skills.get(args["name"])
        if skill is None:
            return ToolResult(f"no skill named {args['name']!r}; skills: {', '.join(sorted(skills)) or 'none'}",
                              is_error=True)
        if "file" not in args:
            files = skill.files()
            listing = ", ".join(files[:MAX_LISTED_FILES]) + (" ..." if len(files) > MAX_LISTED_FILES else "")
            return ToolResult(f"skill {skill.name}\n\n{skill.body.rstrip()}\n\nfiles: {listing or 'none'}")
        try:
            target = _inside(skill, args["file"])
        except SkillError as e:
            return ToolResult(str(e), is_error=True)
        if not target.is_file():
            return ToolResult(f"{skill.name} has no file {args['file']}", is_error=True)
        raw = target.read_bytes()[:MAX_FILE_BYTES + 1]
        if b"\x00" in raw:
            return ToolResult(f"{args['file']} is not text; not returned", is_error=True)
        text = raw[:MAX_FILE_BYTES].decode("utf-8", errors="replace")
        if len(raw) > MAX_FILE_BYTES:
            text += f"\n[truncated at {MAX_FILE_BYTES} bytes]"
        return ToolResult(text)

    names = sorted(skills)
    schema = {"type": "object",
              "properties": {"name": {"type": "string", **({"enum": names} if names else {})},
                             "file": {"type": "string", "maxLength": 512}},
              "required": ["name"], "additionalProperties": False}
    return Tool("skill", "Load a skill's instructions, or one file from its folder.", schema, run,
                permission="allow", trust="trusted", origin="skills")


def script_tool(skills: dict[str, Skill], timeout: float = 60.0, max_chars: int = 20000) -> Tool:
    """`skill_script {"name", "script", "args"}` runs scripts/<script> (Python) from a skill's folder."""

    def run(args: dict, ctx: CallContext) -> ToolResult:
        skill = skills.get(args["name"])
        if skill is None:
            return ToolResult(f"no skill named {args['name']!r}", is_error=True)
        script = args["script"]
        try:
            target = _inside(skill, script if "/" in script or "\\" in script else f"scripts/{script}")
        except SkillError as e:
            return ToolResult(str(e), is_error=True)
        if target.suffix != ".py" or not target.is_file():
            return ToolResult(f"{skill.name} has no Python script {script} (only .py scripts run, the same on "
                              "every system)", is_error=True)
        try:
            p = subprocess.run([sys.executable, str(target), *args.get("args", [])], cwd=str(skill.path),
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return ToolResult(f"{script} timed out after {timeout:g}s", is_error=True)
        text = f"exit {p.returncode}\n{p.stdout}" + (f"\nstderr:\n{p.stderr[-2000:]}" if p.stderr.strip() else "")
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n[truncated at {max_chars} characters]"
        return ToolResult(text, is_error=p.returncode != 0, trust="untrusted")

    schema = {"type": "object",
              "properties": {"name": {"type": "string"}, "script": {"type": "string", "maxLength": 256},
                             "args": {"type": "array", "items": {"type": "string", "maxLength": 1000},
                                      "maxItems": 16}},
              "required": ["name", "script"], "additionalProperties": False}
    return Tool("skill_script", "Run a Python script shipped in a skill's scripts folder.", schema, run,
                permission="ask", trust="untrusted", consequential=True, origin="skills")
