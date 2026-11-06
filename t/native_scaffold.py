#!/usr/bin/env python3
"""Draft a native case from a C function's signature, or scan every function in a file.

    python3 t/native_scaffold.py SOURCE.c --function NAME --out CASE_DIR -I include/
    python3 t/native_scaffold.py SOURCE.c --scan --out NEW_DIR -I include/ --cbmc CBMC

The file is preprocessed, with project headers expanded and system headers kept as includes, so the case holds all it needs but the C library's own. A draft
checks safety only, since it knows nothing of what the function is for, and it knows nothing of what callers promise: **a candidate from a scan is not a bug until someone has read it.**
Measured in t/PREDICT-2026-11-05-native-scaffold.md.

Prior art: goto-harness in CBMC builds a harness from a signature, without a native replay. arXiv:2312.17677 accepts a drafted harness once it compiles
natively and reaches its end. github.com/janislley/LSVerifier verifies per function with a line parser, read and not lifted.
INVENTED: the mapping from a parameter to an input, the length and pointer-pair heuristics, the doubt on a candidate, and the list of system functions.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_case as cases
import native_check as native
import native_sample as sampler

CHAR_TYPES = {"char", "signed char", "unsigned char"}
BUILTIN_WORDS = {"char", "short", "int", "long", "signed", "unsigned", "float", "double", "_Bool", "__int128"}
QUALIFIERS = re.compile(r"\b(?:const|volatile|restrict|__restrict|__restrict__|__const|register|__extension__|_Nonnull|_Nullable)\b")
ATTRIBUTE = re.compile(r"__attribute__\s*\(\(.*?\)\)|__asm__\s*\(.*?\)|__asm\s*\(.*?\)|__declspec\s*\(.*?\)", re.S)
LENGTH_NAME = re.compile(r"(?:^|_)(?:len|length|size|sz|n|nbytes|bytes|count|cnt|num|cap|capacity|max|limit|bufsize|buflen)(?:$|_)|(?:len|size|count)$", re.I)
# The rest of a length's name once the name of its pointer is taken off: `dst_size` is the size of `dst`, and `buflen` the length of `buf`.
OWNED_LENGTH = re.compile(r"_?(?:len|length|size|sz|n|nbytes|bytes|count|cnt|cap|capacity|max|limit)", re.I)
# The rest of a pointer's name once the name of the pointer before it is taken off: `se` ends `s`, and `buf_end` ends `buf`.
OWNED_END = re.compile(r"_?(?:e|end|endp|lim|limit|stop)", re.I)
END_NAMES = {"end", "endp", "end_ptr", "endptr", "eob", "pe", "limit", "lim", "stop"}
LARGEST_DECLARED_ARRAY = 1024
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# A scan runs each draft natively on arbitrary values, and a function that reaches these is not something to run that way: `kill(-1, 9)`, `close(1)` and `remove("a")` are all arbitrary values.
# This is a list and not a sandbox. Run a scan as a user with nothing to lose, away from the network.
SYSTEM_FUNCTIONS = {"system", "popen", "fork", "vfork", "clone", "daemon", "execl", "execlp", "execle", "execv", "execvp", "execve", "execvpe", "posix_spawn", "posix_spawnp", "kill", "killpg", "raise", "tgkill",
                    "open", "openat", "creat", "fopen", "freopen", "tmpfile", "mkstemp", "unlink", "unlinkat", "remove", "rename", "renameat", "rmdir", "mkdir", "mkdirat", "chmod", "fchmod", "chown", "fchown", "lchown",
                    "truncate", "ftruncate", "link", "linkat", "symlink", "symlinkat", "mknod", "mkfifo", "chdir", "fchdir", "chroot", "mount", "umount",
                    "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4", "send", "sendto", "sendmsg", "recv", "recvfrom", "recvmsg", "shutdown", "setsockopt", "getaddrinfo", "gethostbyname",
                    "read", "write", "pread", "pwrite", "readv", "writev", "close", "dup", "dup2", "dup3", "pipe", "pipe2", "ioctl", "fcntl", "poll", "ppoll", "select", "pselect", "epoll_wait", "epoll_create", "epoll_ctl",
                    "sleep", "usleep", "nanosleep", "pause", "alarm", "setitimer", "setuid", "setgid", "seteuid", "setegid", "setsid", "setpgid", "setrlimit", "prctl", "ptrace", "syscall", "reboot",
                    "mmap", "munmap", "mprotect", "dlopen", "dlsym", "signal", "sigaction", "pthread_create", "thrd_create"}
SYSTEM_CALL = re.compile(r"(?<![\w.>])(" + "|".join(sorted(SYSTEM_FUNCTIONS)) + r")\s*\(")
# What each model defines, so that one is only linked when the code calls it and the file does not define it.
MODEL_FUNCTIONS = {"string": {"strnlen", "strspn", "strcspn", "strpbrk", "strstr", "memchr", "memrchr", "strchrnul", "strsep", "strtok_r", "strtok", "strndup"},
                   "stdlib": {"strtol", "strtoul", "strtoll", "strtoull", "atoi", "atol", "atoll"},
                   "ctype": {"__ctype_b_loc", "__ctype_tolower_loc", "__ctype_toupper_loc"}}


def split_items(text: str) -> list[str]:
    """Top-level items: a declaration ends at its semicolon, and a function definition at its closing brace."""
    items, start, index, braces, parens, first_brace = [], 0, 0, 0, 0, -1
    while index < len(text):
        char, two = text[index], text[index:index + 2]
        if two == "//":
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline
            continue
        if two == "/*":
            close = text.find("*/", index + 2)
            index = len(text) if close < 0 else close + 2
            continue
        if char in "\"'":
            quote, index = char, index + 1
            while index < len(text) and text[index] != quote:
                index += 2 if text[index] == "\\" else 1
            index += 1
            continue
        if char == "#" and braces == 0 and parens == 0 and not text[start:index].strip():
            newline = text.find("\n", index)
            newline = len(text) if newline < 0 else newline
            items.append(text[index:newline])
            index = start = newline + 1
            continue
        if char == "(":
            parens += 1
        elif char == ")":
            parens -= 1
        elif char == "{":
            if braces == 0 and parens == 0 and first_brace < 0:
                first_brace = index
            braces += 1
        elif char == "}":
            braces -= 1
            if braces == 0 and parens == 0 and first_brace >= 0 and is_function_head(text[start:first_brace]):
                items.append(text[start:index + 1].strip())
                start, first_brace = index + 1, -1
        elif char == ";" and braces == 0 and parens == 0:
            items.append(text[start:index + 1].strip())
            start, first_brace = index + 1, -1
        index += 1
    return [item for item in items if item]


def clean_head(head: str) -> str:
    return ATTRIBUTE.sub(" ", head).strip()


def is_function_head(head: str) -> bool:
    cleaned = clean_head(head)
    if not cleaned.endswith(")") or cleaned.startswith("typedef"):
        return False
    depth = 0
    for char in cleaned:
        depth += {"(": 1, ")": -1}.get(char, 0)
        if char == "=" and depth == 0:
            return False
    return True


def split_top(text: str, separator: str = ",") -> list[str]:
    parts, depth, current = [], 0, ""
    for char in text:
        depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(char, 0)
        if char == separator and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    return parts


def function_parts(item: str) -> tuple[str, str, str, str] | None:
    """(return type, name, parameters, body) of a function definition, or None for a shape not understood."""
    brace = item.find("{")
    head = clean_head(item[:brace])
    if brace < 0 or not head.endswith(")"):
        return None
    depth, position = 0, len(head) - 1
    while position >= 0:
        depth += {")": 1, "(": -1}.get(head[position], 0)
        if depth == 0:
            break
        position -= 1
    before = head[:position].rstrip()
    match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", before)
    if position < 0 or not match:
        return None
    return before[:match.start()].strip(), match.group(1), head[position + 1:-1].strip(), item[brace:]


class Types:
    """Which names are scalars, as far as the file's typedefs say."""

    def __init__(self, items: list[str]):
        self.typedefs: dict[str, str] = {}
        for item in items:
            if not item.startswith(("typedef", "__extension__ typedef")) or "(" in clean_head(item).split("{")[0].replace("__attribute__", ""):
                continue
            text = clean_head(item.rstrip(";")).replace("__extension__", " ").replace("typedef", " ", 1)
            text = QUALIFIERS.sub(" ", text)
            text = re.sub(r"\s+", " ", text).strip()
            if "*" in text or "[" in text:
                match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[.*\])?$", text)
                if match:
                    self.typedefs[match.group(1)] = "<pointer or array>"
                continue
            match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", text)
            if match:
                self.typedefs[match.group(1)] = text[:match.start()].strip()

    def resolve(self, name: str) -> str:
        seen = set()
        while name in self.typedefs and name not in seen:
            seen.add(name)
            name = self.typedefs[name]
        return name

    def kind(self, base: str) -> str:
        """`char`, `bool`, `scalar`, `void`, or `aggregate` for anything a draft cannot fill in."""
        resolved = re.sub(r"\s+", " ", self.resolve(re.sub(r"\s+", " ", base).strip())).strip()
        words = set(resolved.split())
        if resolved == "void":
            return "void"
        if resolved in CHAR_TYPES:
            return "char"
        if resolved == "_Bool":
            return "bool"
        if words and words <= BUILTIN_WORDS:
            return "scalar"
        if resolved.startswith("enum"):
            return "scalar"
        return "aggregate"


def is_end_of(first: str, second: str) -> bool:
    """Whether a pointer's name says it ends the pointer before it."""
    return second.lower() in END_NAMES or (second.lower().startswith(first.lower()) and OWNED_END.fullmatch(second[len(first):]) is not None)


def is_length_of(pointer: str, length: str) -> bool:
    return length.lower().startswith(pointer.lower()) and OWNED_LENGTH.fullmatch(length[len(pointer):]) is not None


def plan_lengths(parsed: list[dict], ends: dict[str, str], types: Types) -> dict[str, str]:
    """Which pointer each length belongs to.

    A pointer takes a length from the next integer parameter that reads like one, past any other scalar, and pointers side by side can share it: `memcpy(dst, src, n)`.
    Two exceptions, from reading what the first scan got wrong: a length named after one pointer is that pointer's alone, as in `lv_strlcpy(dst, src, dst_size)`, and beside a
    writable pointer a `const char *` is a string, as in `uv_wtf8_to_utf16(source, target, target_len)`."""
    sized_by: dict[str, str] = {}
    pairs = set(ends) | set(ends.values())
    for index, item in enumerate(parsed):
        if item["stars"] != 1 or item["name"] in pairs or item["declared"] is not None:
            continue
        passed_a_scalar = False
        for later in parsed[index + 1:]:
            if later["stars"] == 0 and later["kind"] == "scalar" and (LENGTH_NAME.search(later["name"]) or types.resolve(later["base"]) in ("long unsigned int", "unsigned long")):
                sized_by[item["name"]] = later["name"]
                break
            if later["stars"] > 0 and passed_a_scalar:
                break
            passed_a_scalar = passed_a_scalar or later["stars"] == 0
    by_name = {item["name"]: item for item in parsed}
    for length in set(sized_by.values()):
        sharing = [pointer for pointer, used in sized_by.items() if used == length]
        owner = next((pointer for pointer in sharing if is_length_of(pointer, length)), None)
        for pointer in sharing:
            item = by_name[pointer]
            if owner is not None and pointer != owner:
                del sized_by[pointer]
            elif owner is None and item["kind"] == "char" and item["pointee_const"] and any(not by_name[other]["pointee_const"] for other in sharing):
                del sized_by[pointer]
    return sized_by


def plan_inputs(parameters: str, types: Types, max_length: int) -> dict:
    """The inputs, the call's arguments and any guess made, or the reason a draft cannot be made."""
    parts = [part.strip() for part in split_top(parameters)]
    if parts in ([""], ["void"]):
        return {"inputs": [{"name": "dawnr_unused", "type": "int"}], "arguments": [], "guesses": [], "assumptions": [], "unused": ["dawnr_unused"]}
    parsed = []
    for position, raw in enumerate(parts):
        text = re.sub(r"\s+", " ", QUALIFIERS.sub(" ", clean_head(raw))).strip()
        if text == "...":
            return {"refused": "takes variable arguments"}
        if "(" in text:
            return {"refused": "takes a function pointer"}
        array = re.search(r"\[([^\]]*)\]$", text)
        declared = int(array.group(1)) if array and array.group(1).strip().isdigit() and int(array.group(1)) > 0 else None
        if array:
            text = text[:array.start()].strip() + " *"
        stars = text.count("*")
        words = text.replace("*", " ").split()
        known = words[-1] in BUILTIN_WORDS or words[-1] in types.typedefs or len(words) == 1
        name = f"arg{position}" if known and (len(words) == 1 or words[-1] in BUILTIN_WORDS) else words[-1]
        base = " ".join(words if name.startswith("arg") and name not in words else words[:-1])
        if not base:
            return {"refused": f"could not read the parameter {raw!r}"}
        pointee_const = bool({"const", "__const"} & set(re.findall(r"\w+", raw.split("*")[0])))
        parsed.append({"name": name, "base": base, "stars": stars, "kind": types.kind(base), "declared": declared, "pointee_const": pointee_const})
    ends = {second["name"]: first["name"] for first, second in zip(parsed, parsed[1:])
            if first["stars"] == second["stars"] == 1 and first["base"] == second["base"] and first["kind"] in ("char", "scalar", "void") and first["declared"] is None
            and second["declared"] is None and is_end_of(first["name"], second["name"])}
    # `a, ae, aee` would read as two pairs that share a pointer, and a pointer cannot be both an end and a start.
    ends = {second: first for second, first in ends.items() if first not in ends}
    sized_by = plan_lengths(parsed, ends, types)
    inputs, arguments, guesses, assumptions, taken = [], [], [], [], set()
    unsized_strings, single_elements = [], []
    first_for_length: dict[str, str] = {}
    lengths_used = set(sized_by.values())
    starts = {first: second for second, first in ends.items()}
    for item in parsed:
        name, base, kind, stars = item["name"], item["base"], item["kind"], item["stars"]
        if stars > 1:
            return {"refused": f"takes a pointer to a pointer ({name})"}
        if stars == 1:
            if kind == "aggregate":
                return {"refused": f"takes a pointer to an aggregate ({name}: {base})"}
            if kind == "bool":
                return {"refused": f"takes a pointer to a bool ({name})"}
            element = "unsigned char" if kind == "void" else base
            if name in ends:
                arguments.append(("end", ends[name], base))
            elif name in starts:
                inputs.append({"name": name, "type": element, "array": {"max": max_length}})
                arguments.append(("cast", name, base))
                guesses.append(f"{starts[name]} is the end of {name}")
            elif item["declared"] is not None:
                if item["declared"] > LARGEST_DECLARED_ARRAY:
                    return {"refused": f"declares an array of {item['declared']} elements ({name})"}
                inputs.append({"name": name, "type": element, "array": {"min": item["declared"], "max": item["declared"]}})
                arguments.append(("cast", name, base))
                guesses.append(f"{name} has the {item['declared']} elements it declares")
            elif name in sized_by:
                inputs.append({"name": name, "type": element, "array": {"max": max_length}})
                arguments.append(("cast", name, base))
                length = sized_by[name]
                if length in first_for_length:
                    assumptions.append(f"    __CPROVER_assume({name}_len == {first_for_length[length]}_len);\n")
                    guesses.append(f"{name} and {first_for_length[length]} have the same length, {length}")
                else:
                    first_for_length[length] = name
                    guesses.append(f"{length} is the length of {name}")
            elif kind == "void":
                return {"refused": f"takes a void pointer with no length ({name})"}
            elif kind == "char":
                inputs.append({"name": name, "type": element, "string": {"max": max_length}})
                arguments.append(("cast", name, base))
                guesses.append(f"{name} is a string")
                if not item["pointee_const"]:
                    unsized_strings.append(name)
            else:
                inputs.append({"name": name, "type": element, "array": {"min": 1, "max": 1}})
                arguments.append(("cast", name, base))
                guesses.append(f"{name} points to one element")
                single_elements.append(name)
        elif kind == "aggregate":
            return {"refused": f"takes an aggregate by value ({name}: {base})"}
        elif kind == "void":
            return {"refused": f"could not read the parameter {name}"}
        elif name in lengths_used:
            owner = next(pointer for pointer, length in sized_by.items() if length == name and first_for_length.get(length, pointer) == pointer)
            arguments.append(("length", owner, base))
        elif kind == "bool":
            inputs.append({"name": name, "type": "unsigned char"})
            arguments.append(("bool", name, base))
        else:
            inputs.append({"name": name, "type": base})
            arguments.append(("plain", name, base))
        taken.add(name)
    rendered = []
    for form, name, base in arguments:
        rendered.append({"plain": name, "bool": f"({name} != 0)", "cast": f"({base} *){name}", "length": f"({base}){name}_len", "end": f"({base} *)({name} + {name}_len)"}[form])
    return {"inputs": inputs or [{"name": "dawnr_unused", "type": "int"}], "arguments": rendered, "guesses": guesses, "assumptions": assumptions,
            "unused": [] if inputs else ["dawnr_unused"], "unsized_strings": unsized_strings, "single_elements": single_elements}


def analyse(text: str, types_from: str | None = None) -> dict:
    """The items of a translation unit, and the functions, globals and types it defines."""
    items = split_items(text)
    types = Types(split_items(types_from) if types_from is not None else items)
    functions, globals_, others = {}, {}, []
    for index, item in enumerate(items):
        if item.startswith("#"):
            others.append(index)
            continue
        brace = item.find("{")
        if item.endswith("}") and brace >= 0 and is_function_head(item[:brace]):
            parts = function_parts(item)
            if parts:
                functions[parts[1]] = index
            continue
        head = clean_head(item.rstrip(";"))
        if not head.startswith(("typedef", "extern", "__extension__ typedef")) and "=" in head:
            match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[[^\]]*\]\s*)*=", head)
            if match:
                globals_[match.group(1)] = index
                continue
        tentative = re.fullmatch(r"(?:static\s+)?[A-Za-z_][\w\s\*]*?\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[[^\]]*\]\s*)*", head)
        if tentative and not head.startswith(("typedef", "extern", "struct", "union", "enum")) and "(" not in head:
            globals_[tentative.group(1)] = index
            continue
        others.append(index)
    return {"items": items, "functions": functions, "globals": globals_, "others": others, "types": types}


def closure(unit: dict, target: str) -> set[int]:
    """The items the target reaches: functions and globals by name, through what those use in turn."""
    items, reached, queue = unit["items"], set(), [unit["functions"][target]]
    named = {**unit["functions"], **unit["globals"]}
    while queue:
        index = queue.pop()
        if index in reached:
            continue
        reached.add(index)
        for word in set(IDENTIFIER.findall(items[index])):
            if word in named and named[word] not in reached:
                queue.append(named[word])
    return reached


def draft(unit: dict, target: str, root: Path, source_name: str, machine: str = "LP64", max_length: int = 4, unwind: int = 6,
          repository: str = "unknown", revision: str = "unpinned", allow_system: bool = False) -> dict:
    """Write a case directory for one function, or return why not. The source of the case is the preprocessed text."""
    items, types = unit["items"], unit["types"]
    parts = function_parts(items[unit["functions"][target]])
    if parts is None:
        return {"function": target, "refused": "the definition's shape was not understood"}
    plan = plan_inputs(parts[2], types, max_length)
    if "refused" in plan:
        return {"function": target, "refused": plan["refused"]}
    if any(not cases.TYPE.match(item["type"]) for item in plan["inputs"]):
        return {"function": target, "refused": "a parameter's type is not a plain name"}
    reached = closure(unit, target)
    others = [index for index in sorted({*unit["others"], *reached}) if index != unit["functions"][target]]
    words = set(IDENTIFIER.findall(" ".join(items[index] for index in reached)))
    defined = set(unit["functions"])
    system = sorted(set(SYSTEM_CALL.findall(" ".join(items[index] for index in reached))) - defined)
    if system and not allow_system:
        return {"function": target, "refused": f"reaches the operating system ({', '.join(system[:4])})"}
    models = [name for name, names in MODEL_FUNCTIONS.items() if names & words and not names & defined]
    prelude = "\n".join(items[index] for index in others) + "\n"
    definition = items[unit["functions"][target]] + "\n"
    source = prelude + definition
    returns_void = types.kind(re.sub(r"\b(?:static|inline|__inline|__inline__|extern|_Noreturn)\b", " ", parts[0])) == "void" and "*" not in parts[0]
    call = f"{target}({', '.join(plan['arguments'])});\n"
    harness = "".join(plan["assumptions"]) + "".join(f"    (void){name};\n" for name in plan["unused"]) + "    " + ("" if returns_void else "(void)") + call + '    __CPROVER_assert(1 == 1, "scaffold.ran");\n'
    root.mkdir(parents=True, exist_ok=False)
    (root / "original.c").write_bytes(source.encode())
    first = prelude.count("\n") + 1
    last = first + definition.count("\n") - 1
    entry = {"file": "original.c", "sha256": native.digest(source), "revision": revision, "definitions": [{"name": target, "line": first, "end_line": last}]}
    case = {"format": cases.FORMAT, "id": f"scaffold-{target}", "repository": repository, "path": source_name, "machine": machine, "sources": {"original": entry},
            "prelude": prelude, "inputs": plan["inputs"], "harness": harness, "assertions": ["scaffold.ran"], "assumptions": len(plan["assumptions"]), "loops": 0, "unwind": unwind,
            "input_domain": f"drafted from the signature: {'; '.join(plan['guesses']) or 'scalars only'}; arrays and strings of at most {max_length} elements",
            "limitations": "a draft from a signature: safety properties only, no caller contract, and every guess above may be wrong", **({"models": models} if models else {})}
    (root / "case.json").write_text(json.dumps(case, indent=1) + "\n", encoding="utf-8")
    return {"function": target, "case": str(root), "guesses": plan["guesses"], "models": models, "unsized_strings": plan.get("unsized_strings", []), "single_elements": plan.get("single_elements", [])}


# Macros that change what a system header declares, so they have to stay before the headers it includes. Everything else is already expanded.
FEATURE_MACROS = {"_GNU_SOURCE", "_DEFAULT_SOURCE", "_BSD_SOURCE", "_SVID_SOURCE", "_POSIX_C_SOURCE", "_POSIX_SOURCE", "_XOPEN_SOURCE", "_XOPEN_SOURCE_EXTENDED",
                  "_ISOC99_SOURCE", "_ISOC11_SOURCE", "_LARGEFILE64_SOURCE", "_FILE_OFFSET_BITS", "__STDC_WANT_LIB_EXT2__"}
MARKER = re.compile(r'^# (\d+) "([^"]*)"((?: \d+)*)\s*$')


def search_directories(compiler: str, machine: str, timeout: float) -> list[str]:
    """Where the compiler looks for <...> headers, longest first, so that a path can be written back as an include."""
    done = subprocess.run([compiler, "-E", "-v", "-x", "c", *(["-m32"] if machine == "ILP32" else []), "-"], input="", capture_output=True, text=True, timeout=timeout, errors="replace")
    listed = re.search(r"#include <\.\.\.> search starts here:\n(.*?)End of search list", done.stderr, re.S)
    return sorted((line.strip() for line in listed.group(1).splitlines()) if listed else [], key=len, reverse=True)


def strip_system_headers(text: str, directories: list[str]) -> str:
    """Project headers stay expanded. A system header goes back to being an include, so that the text can be compiled beside the real ones.

    Uses the line markers of `gcc -E`: flag 1 enters a file, 2 returns from one and 3 marks a system header
    (gcc.gnu.org/onlinedocs/cpp/Preprocessor-Output.html)."""
    out, depth, current, seen = [], 0, "", set()
    for line in text.splitlines():
        marker = MARKER.match(line)
        if marker:
            name, flags = marker.group(2), marker.group(3).split()
            if "1" in flags:
                if depth:
                    depth += 1
                elif "3" in flags:
                    depth = 1
                    relative = next((name[len(directory) + 1:] for directory in directories if name.startswith(directory + "/")), None)
                    include = f"#include <{relative}>" if relative else f'#include "{name}"'
                    if include not in seen:
                        seen.add(include)
                        out.append(include)
            elif "2" in flags and depth:
                depth -= 1
            current = name
            continue
        if depth or current == "<built-in>":
            continue
        if line.startswith(("#define", "#undef")):
            word = line.split()[1].split("(")[0] if len(line.split()) > 1 else ""
            if word in FEATURE_MACROS:
                out.append(line)
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def expand(source: Path, includes: list[str], defines: list[str], compiler: str = "gcc", machine: str = "LP64", timeout: float = 120) -> str:
    flags = ["-E", "-dD", "-std=gnu11", *(["-m32"] if machine == "ILP32" else []), *[f"-I{path}" for path in includes], *[f"-D{item}" for item in defines], str(source)]
    done = subprocess.run([compiler, *flags], capture_output=True, text=True, timeout=timeout, errors="replace")
    if done.returncode != 0:
        raise ValueError(f"the preprocessor failed: {done.stderr[:800]}")
    return done.stdout


def preprocess(source: Path, includes: list[str], defines: list[str], compiler: str = "gcc", machine: str = "LP64", timeout: float = 120) -> str:
    return strip_system_headers(expand(source, includes, defines, compiler, machine, timeout), search_directories(compiler, machine, timeout))


def own_functions(expanded: str) -> set[str]:
    """The functions the file itself defines, by the line markers: inline functions from headers are not the file's to answer for. The first marker names the file."""
    main, current, lines = None, None, []
    for line in expanded.splitlines():
        marker = MARKER.match(line)
        if marker:
            current = marker.group(2)
            main = current if main is None else main
        elif current == main and not line.startswith("#"):
            lines.append(line)
    names = set()
    for item in split_items("\n".join(lines) + "\n"):
        brace = item.find("{")
        if item.endswith("}") and brace >= 0 and is_function_head(item[:brace]):
            parts = function_parts(item)
            if parts:
                names.add(parts[1])
    return names


def load_unit(source: Path, includes: list[str], defines: list[str], compiler: str = "gcc", machine: str = "LP64", timeout: float = 120) -> dict:
    """The items come from the text with system headers as includes, and the types from the whole expansion: size_t is declared in a system header."""
    expanded = expand(source, includes, defines, compiler, machine, timeout)
    return {**analyse(strip_system_headers(expanded, search_directories(compiler, machine, timeout)), expanded), "own": own_functions(expanded)}


ABORT_REPORT = "AddressSanitizer: ABRT"


def sampler_failed(row: dict) -> bool:
    """A sanitizer report from the sampler, other than the abort of the project's own assert."""
    sample = row.get("sample", {})
    return sample.get("status") == "sanitizer_report" and ABORT_REPORT not in (sample.get("report") or "")


def doubt(row: dict, witnesses: list[dict]) -> str | None:
    """Why a failure may only reflect the draft: a size it guessed at, or state it did not set up. The row stays a candidate, and the reader knows what to look at first."""
    failures = [{"report": witness["detail"].get("sanitizer") or "", "memory": witness["status"] == "memory_error", "access": witness["detail"].get("access")}
                for witness in witnesses if witness["status"] in ("memory_error", "undefined_behavior")]
    sample = row.get("sample", {})
    if sampler_failed(row):
        report = sample.get("report") or ""
        failures.append({"report": report, "memory": "AddressSanitizer" in report, "access": sample.get("access")})
    # A draft allocates every pointer it passes, so a null comes from somewhere it did not reach.
    if any("null pointer" in failure["report"] or "address 0x000000000000" in failure["report"] for failure in failures):
        return "a null pointer the draft did not pass, so from state it did not set up"
    failures = [failure for failure in failures if failure["memory"]]
    if not failures:
        return None
    if row.get("single_elements"):
        return f"a guess that {', '.join(row['single_elements'])} points to one element"
    if row.get("unsized_strings") and any(item["access"] == "WRITE" for item in failures):
        return f"a write past {', '.join(row['unsized_strings'])}, a buffer it is given no size for"
    return None


def scan_one(entry: dict, args) -> dict:
    """The gate and the sampler on one draft. A candidate needs a witness confirmed natively, or a sanitizer report from the sampler."""
    root = Path(entry["case"])
    row = dict(entry)
    try:
        receipt = cases.check(root, "original", root.parent / (root.name + "-gate"), args.cbmc, None, args.timeout, args.compiler, args.memory_limit_mb, args.solver)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {**row, "verdict": "input_error", "reason": str(error)[:300], "candidate": False}
    witnesses = receipt.get("native_replay", {}).get("witnesses", [])
    failing = [item.get("description", item["property"])[:110] for item in receipt.get("properties", []) if item["status"] == "FAILURE"]
    row.update(verdict=receipt["verdict"], reason=receipt["reason"][:200], failing=failing[:6], witness_statuses=sorted({witness["status"] for witness in witnesses}))
    row["sanitizer"] = next((witness["detail"]["sanitizer"][:170] for witness in witnesses if witness["detail"].get("sanitizer")), None)
    row["witness"] = next((witness.get("arrays") or {key: value["hex"] for key, value in witness["inputs"].items()} for witness in witnesses if witness["status"] in ("memory_error", "undefined_behavior")), None)
    row["stops"] = sorted(text for text in failing if text.startswith("native.stop."))
    if args.sample:
        result = sampler.sample(root, "original", root.parent / (root.name + "-sample"), args.sample, compiler=args.compiler, timeout=args.timeout)
        row["sample"] = {key: result.get(key) for key in ("status", "reached_the_end", "rejected", "report", "access", "first_inputs")}
    native_failure = bool({"memory_error", "undefined_behavior"} & set(row["witness_statuses"]))
    row["candidate"] = native_failure or sampler_failed(row)
    row["doubt"] = doubt(row, witnesses) if row["candidate"] else None
    # The project's own assert fired: more likely the contract than a defect, so it is counted and not listed.
    row["project_assert"] = "stopped_early" in row["witness_statuses"] or ABORT_REPORT in (row.get("sample", {}).get("report") or "")
    return row


def scan(source: Path, args) -> dict:
    unit = load_unit(source, args.include, args.define, args.compiler, args.machine)
    args.out.mkdir(parents=True, exist_ok=False)
    targets = [name for name in unit["functions"] if name in unit["own"]]
    drafted, refused = [], []
    for name in targets:
        try:
            result = draft(unit, name, args.out / name, source.name, args.machine, args.max_length, args.unwind, args.repository, args.revision)
        except (ValueError, KeyError, IndexError, StopIteration) as error:
            result = {"function": name, "refused": f"could not draft: {type(error).__name__}: {error}"[:200]}
        (refused if "refused" in result else drafted).append(result)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(lambda entry: scan_one(entry, args), drafted))
    verdicts: dict[str, int] = {}
    for row in rows:
        verdicts[row["verdict"]] = verdicts.get(row["verdict"], 0) + 1
    report = {"format": "dawnr-native-scan", "source": str(source.name), "repository": args.repository, "revision": args.revision, "functions": len(targets), "drafted": len(rows),
              "refused": refused, "verdicts": verdicts, "candidates": [row for row in rows if row["candidate"]], "project_asserts": [row["function"] for row in rows if row.get("project_assert")], "rows": rows,
              "reminder": "a candidate is not a bug until someone has read it"}
    (args.out / "scan.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="a C file")
    parser.add_argument("--function", help="draft a case for this function")
    parser.add_argument("--scan", action="store_true", help="draft and check every function the file defines")
    parser.add_argument("--out", type=Path, required=True, help="new directory; existing directories are refused")
    parser.add_argument("-I", dest="include", action="append", default=[], help="an include directory")
    parser.add_argument("-D", dest="define", action="append", default=[], help="a macro definition")
    parser.add_argument("--machine", choices=sorted(cases.MACHINES), default="LP64")
    parser.add_argument("--max-length", type=int, default=4, help="longest array or string drawn")
    parser.add_argument("--unwind", type=int, default=6)
    parser.add_argument("--repository", default="unknown")
    parser.add_argument("--revision", default="unpinned")
    parser.add_argument("--cbmc", default="cbmc")
    parser.add_argument("--compiler", default="gcc")
    parser.add_argument("--solver", choices=cases.SOLVERS, default="cadical")
    parser.add_argument("--timeout", type=float, default=60, help="seconds for each stage of each function")
    parser.add_argument("--memory-limit-mb", type=int, default=2048)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--sample", type=int, default=20000, help="native draws for each function; 0 for none")
    parser.add_argument("--allow-system", action="store_true", help="draft a function that calls the operating system; --scan runs it natively on arbitrary values, so this is refused there")
    args = parser.parse_args(argv)
    if args.allow_system and args.scan:
        parser.error("--allow-system is for drafting one case to read, not for --scan, which runs what it drafts")
    if bool(args.function) == args.scan:
        parser.error("give exactly one of --function and --scan")
    try:
        if args.function:
            unit = load_unit(args.source, args.include, args.define, args.compiler, args.machine)
            if args.function not in unit["functions"]:
                print(json.dumps({"refused": f"{args.function} is not defined in this file"}))
                return 2
            result = draft(unit, args.function, args.out, args.source.name, args.machine, args.max_length, args.unwind, args.repository, args.revision, args.allow_system)
            print(json.dumps(result))
            return 0 if "refused" not in result else 1
        report = scan(args.source, args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"verdict": "input_error", "reason": str(error)[:800]}))
        return 2
    print(json.dumps({key: report[key] for key in ("source", "functions", "drafted", "verdicts")} | {"refused": len(report["refused"]), "candidates": [row["function"] for row in report["candidates"]]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
