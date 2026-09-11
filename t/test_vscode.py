#!/usr/bin/env python3
"""test_vscode.py: ROADMAP 15.3's VS Code extension, checked the way this
box can check it -- there is no display here, so nothing here launches VS
Code itself (see t/editors/WALKTHROUGH.md for the parts that need a
person on Linux or Windows to run it). What IS checked, standard library
only:

- t/editors/vscode/package.json parses as JSON and declares the "t"
  language (contributes.languages), the grammar (contributes.grammars),
  and the three settings t.pythonPath, t.serverPath, t.kernels
  (contributes.configuration.properties).
- t/editors/vscode/syntaxes/t.tmLanguage.json parses as JSON and its
  patterns collectively mention every t/surface.py KEYWORDS entry and
  every STR_METHODS entry -- the grammar's coverage of the two the ROADMAP
  15.3 item names ("a TextMate grammar for the notation").
- t/editors/vscode/extension.js parses as JavaScript: `node --check`.
- if the .vsix was built (t/editors/vscode/*.vsix, git-ignored, built by
  `npx @vscode/vsce package`), it exists and is a zip archive containing
  extension/package.json.

Run: python3 t/test_vscode.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VSCODE_DIR = HERE / "editors" / "vscode"
PACKAGE_JSON = VSCODE_DIR / "package.json"
GRAMMAR_JSON = VSCODE_DIR / "syntaxes" / "t.tmLanguage.json"
EXTENSION_JS = VSCODE_DIR / "extension.js"


def test_package_json_declares_language():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    contributes = data["contributes"]

    languages = contributes["languages"]
    assert any(lang.get("id") == "t" for lang in languages), languages
    t_lang = next(lang for lang in languages if lang["id"] == "t")
    assert ".t" in t_lang["extensions"], t_lang

    grammars = contributes["grammars"]
    assert any(g.get("language") == "t" for g in grammars), grammars
    grammar_path = next(g["path"] for g in grammars if g["language"] == "t")
    resolved = (VSCODE_DIR / grammar_path).resolve()
    assert resolved == GRAMMAR_JSON.resolve(), (resolved, GRAMMAR_JSON)
    assert resolved.exists(), resolved

    props = contributes["configuration"]["properties"]
    for setting in ("t.pythonPath", "t.serverPath", "t.kernels"):
        assert setting in props, (setting, sorted(props))
    assert props["t.pythonPath"]["default"] == "python3", props["t.pythonPath"]
    assert isinstance(props["t.kernels"]["default"], list), props["t.kernels"]

    commands = contributes["commands"]
    assert any(c.get("command") == "t.verify" for c in commands), commands

    print("test_package_json_declares_language: language 't', grammar "
         f"{grammar_path}, settings t.pythonPath/t.serverPath/t.kernels, "
         "command t.verify -- all present")


def _grammar_pattern_text(grammar):
    """Every literal string appearing in a "match"/"begin"/"end" field
    anywhere in the grammar, concatenated -- enough to search for whole
    keywords with a word-boundary regex without parsing TextMate regex
    syntax."""
    chunks = []

    def walk(node):
        if isinstance(node, dict):
            for key in ("match", "begin", "end"):
                if key in node and isinstance(node[key], str):
                    chunks.append(node[key])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(grammar)
    return "\n".join(chunks)


def test_grammar_covers_keywords_and_string_methods():
    sys.path.insert(0, str(HERE))
    import surface

    grammar = json.loads(GRAMMAR_JSON.read_text(encoding="utf-8"))
    assert grammar["scopeName"] == "source.t", grammar.get("scopeName")
    text = _grammar_pattern_text(grammar)

    missing_kw = sorted(
        kw for kw in surface.KEYWORDS
        if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(kw) + r"(?![A-Za-z0-9_])", text)
    )
    assert not missing_kw, f"grammar mentions no pattern for KEYWORDS: {missing_kw}"

    missing_methods = sorted(
        m for m in surface.STR_METHODS
        if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(m) + r"(?![A-Za-z0-9_])", text)
    )
    assert not missing_methods, (
        f"grammar mentions no pattern for STR_METHODS: {missing_methods}")

    print("test_grammar_covers_keywords_and_string_methods: "
         f"{len(surface.KEYWORDS)} KEYWORDS and {len(surface.STR_METHODS)} "
         "STR_METHODS entries all named in the grammar's patterns")


def test_extension_js_is_valid_javascript():
    node = shutil.which("node")
    if node is None:
        print("test_extension_js_is_valid_javascript: SKIPPED, no node on PATH "
             "(node is required for this check; see RUN-ON-LINUX.md/"
             "RUN-ON-WINDOWS.md for the user-local Node 22 setup)")
        return
    result = subprocess.run(
        [node, "--check", str(EXTENSION_JS)],
        capture_output=True, text=True)
    assert result.returncode == 0, (
        f"node --check {EXTENSION_JS} failed:\n{result.stdout}\n{result.stderr}")
    print(f"test_extension_js_is_valid_javascript: node --check {EXTENSION_JS.name} OK")


def test_vsix_if_built():
    vsix_files = sorted(VSCODE_DIR.glob("*.vsix"))
    if not vsix_files:
        print("test_vsix_if_built: SKIPPED, no .vsix under "
             f"{VSCODE_DIR} (run `npm install && npx @vscode/vsce package` "
             "there first; the .vsix is git-ignored, see "
             "t/editors/vscode/.gitignore)")
        return
    vsix = vsix_files[0]
    assert vsix.stat().st_size > 0, vsix
    with zipfile.ZipFile(vsix) as z:
        names = z.namelist()
        assert "extension/package.json" in names, (vsix, names[:20])
    print(f"test_vsix_if_built: {vsix.name} ({vsix.stat().st_size} bytes) is "
         "a zip containing extension/package.json")


def main():
    test_package_json_declares_language()
    test_grammar_covers_keywords_and_string_methods()
    test_extension_js_is_valid_javascript()
    test_vsix_if_built()
    print("OK")


if __name__ == "__main__":
    main()
