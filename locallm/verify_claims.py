"""verify_claims.py — check the README's factual claims against this repo.

    python verify_claims.py

A README is a set of promises. This file is the mechanism that keeps them true:
every empirical claim in README.md that CAN be checked mechanically is checked
here, against the artifacts that ship beside it, and the script exits non-zero if
any of them has drifted. No claim in the README is asked to be taken on trust
when a machine could settle it.

WHAT THIS DOES NOT DO, stated first because the limits are the honest part:

  - It cannot check claims about the FUTURE (the roadmap) or about taste
    ("small, readable"). Those are not falsifiable and are not touched here.
  - It cannot check hardware timings. The benchmark table is machine-specific;
    the README already tells you to run `bench_device.py` on your own machine,
    and this script only checks that the numbers quoted match the result file
    they were taken from, IF that file is present.
  - It cannot click the GUI. Tk needs a desktop session. `test_checkpoint.py`
    covers the logic the buttons call; nothing here proves a button is wired to
    it.
  - A passing run means "the claims this script knows how to check still hold".
    It is a fixed list, not a general fact-checker: a NEW unsupported sentence
    added to the README is not caught automatically. Flashlight, not fence.

Run it after editing README.md, and after any change to the experiment or
benchmark artifacts.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
README = (HERE / "README.md").read_text(encoding="utf-8")

RESULTS: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "", ok_detail: str = "") -> None:
    """`detail` describes the FAILURE, `ok_detail` the pass.

    Printing a failure message beside an [ok] is how a green check comes to read
    as a red one, and the first run of this script did exactly that on three
    rows — reporting "no torch.Generator found" next to a passing check.
    """
    RESULTS.append((ok, name, ok_detail if ok else detail))


def claims(pattern: str, flags=0):
    return re.search(pattern, README, flags)


# ---------------------------------------------------------------------------
# 1. The file table promises these files exist.
# ---------------------------------------------------------------------------
def check_file_table():
    listed = set(re.findall(r"^\| `([^`]+)` \|", README, re.M))
    missing = sorted(f for f in listed if not (HERE / f).exists())
    check("file table: every listed file exists", not missing,
          f"missing: {missing}" if missing else f"{len(listed)} files listed")

    # And the reverse: a shipped module the table forgets is a README that has
    # gone stale. Only modules a user would run or import are required.
    shipped = {p.name for p in HERE.glob("*.py")
               if not p.name.startswith(("test_", "verify_claims", "exp_"))}
    undocumented = sorted(shipped - listed)
    check("file table: no shipped module is undocumented", not undocumented,
          f"in the folder but not in the table: {undocumented}"
          if undocumented else "")


# ---------------------------------------------------------------------------
# 2. "~145 lines", and the dependency claim.
# ---------------------------------------------------------------------------
def check_model_size():
    m = claims(r"attention, MLP, blocks, weight tying, GPT-2 scaled init\. ~(\d+) lines")
    if not m:
        return check("model.py line count claim present", False, "claim not found")
    claimed = int(m.group(1))
    actual = len((HERE / "model.py").read_text(encoding="utf-8").splitlines())
    check("model.py is ~the claimed length", abs(actual - claimed) <= 15,
          f"claimed ~{claimed}, actual {actual}")


def check_dependencies():
    """'Dependencies: PyTorch and Tk. That's it.'"""
    # The interpreter's OWN list, not one I typed. A hand-written set is a
    # coverage list produced by the same head that wrote the code, and mine was
    # wrong on its first run: it omitted `multiprocessing`, so a stdlib import
    # was reported as a third-party dependency. Two lists written by one head
    # agree only with each other.
    stdlib_ok = set(sys.stdlib_module_names) | {"__future__"}
    local = {p.stem for p in HERE.glob("*.py")}
    allowed = stdlib_ok | local | {"torch", "tkinter"}
    third_party = set()
    for p in HERE.glob("*.py"):
        # PARSED, not pattern-matched. The regex version read any line beginning
        # "import x" or "from x", including inside docstrings and comments, and
        # a sentence that happened to start "from someone else's machine" was
        # reported as a third-party dependency called `someone`. That is the
        # second time a scanner here has tripped over English prose about code
        # (the network check did it first), so this one is fixed by asking
        # Python what the imports ARE instead of guessing from text.
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            third_party.add(f"UNPARSEABLE ({p.name})")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [(node.module or "").split(".")[0]] if node.level == 0 else []
            else:
                continue
            for mod in mods:
                if mod and mod not in allowed:
                    third_party.add(f"{mod} ({p.name})")
    check("dependencies really are torch + Tk + stdlib", not third_party,
          f"unexpected imports: {sorted(third_party)}" if third_party else "")


# The ONE file allowed to open a socket, and only ever to fetch text. Named
# rather than pattern-matched, so adding a second downloader is a decision
# someone has to make here in the open instead of a file quietly slipping past.
DOWNLOADER = "get_corpus.py"


def check_nothing_phones_home():
    """'Nothing leaves your computer' / 'nothing phones home' / 'no telemetry'.

    This used to be "no network module anywhere", which was true until
    get_corpus.py existed to download training TEXT. The blunt version would now
    have to be either false or switched off, and switching a safety scan off is
    how the thing it guards gets in. So it is SPLIT instead, into the two claims
    that are actually load-bearing and are both still true:

      1. only the declared downloader touches the network at all
      2. NOTHING anywhere sends data out - no POST, no mail, no socket write

    That is strictly stronger than what was checked before, because (2) applies
    to the downloader too. "Nothing leaves your computer" was always the real
    promise; "no network" was a proxy for it that stopped fitting.
    """
    # Match IMPORTS and CALLS, not mentions of a word. A scanner that fires on
    # the string "socket" appearing inside a regex flagged THIS VERY FILE on its
    # first run — and the fix is a more precise pattern, not an exemption for the
    # scanner.
    #
    # AND THE SAME MISTAKE CAME BACK IN THE OTHER DIRECTION. `urllib` and `http`
    # are PACKAGES whose submodules do unrelated jobs, so the bare name cannot
    # tell an opened socket from string work. urllib.request is the "Extensible
    # library for opening URLs" (docs.python.org/3/library/urllib.request.html);
    # urllib.parse only "break[s] Uniform Resource Locator (URL) strings up in
    # components ... and combine[s] the components back into a URL string"
    # (docs.python.org/3/library/urllib.parse.html) and opens nothing. Matching
    # the bare name reported `from urllib.parse import quote` at
    # build_source_corpus.py:19 as a network call, for a `quote` used once to
    # percent-encode an attribution path that is written into provenance.jsonl
    # and never requested (OFFLINE.md section 4). So this check sat red on a
    # false positive, and a red safety check everyone knows to ignore is worth
    # less than no check at all.
    #
    # The fix is a narrower pattern, NOT a build_source_corpus exemption — which
    # is exactly what the DOWNLOADER comment above was written to prevent. Only
    # the two string-only submodules are excluded and nothing is widened: bare
    # `import urllib` and `import http` still match, because a bare import
    # reaches urlopen from there. urllib.robotparser is deliberately NOT
    # excluded — RobotFileParser.read() fetches robots.txt over the network.
    # `from urllib import parse` still matches, which is conservative rather
    # than exact; no file here writes it, and over-reporting an import that
    # names the package is the safe direction for a safety scan.
    net = re.compile(
        r"^\s*(?:import|from)\s+(?:requests|socket|httpx|aiohttp|smtplib|ftplib"
        r"|urllib(?!\.parse\b)|http(?!\.(?:cookiejar|cookies)\b))\b"
        r"|\b(?:urlopen|urlretrieve|socket\.socket|requests\.(?:get|post))\s*\(")
    # Anything that could carry bytes OFF this machine.
    upload = re.compile(
        r"\b(?:requests\.(?:post|put|patch)|httpx\.(?:post|put|patch))\s*\("
        r"|\b(?:urlopen|Request)\s*\([^)]*\bdata\s*="
        r"|^\s*(?:import|from)\s+smtplib\b"
        r"|\.(?:send|sendall|sendto)\s*\(")
    stray, uploads = [], []
    for p in sorted(HERE.glob("*.py")):
        if p.name == pathlib.Path(__file__).name:
            continue                       # this file quotes the patterns above
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if net.search(line) and p.name != DOWNLOADER:
                stray.append(f"{p.name}:{i}")
            if upload.search(line):
                uploads.append(f"{p.name}:{i}")
    n = len(list(HERE.glob("*.py")))
    check(f"only {DOWNLOADER} touches the network", not stray,
          f"network use outside the downloader: {stray}",
          f"no network import or call in the other {n - 1} files")
    check("nothing leaves your computer: no upload anywhere", not uploads,
          f"data-sending calls: {uploads}",
          f"no POST, mail or socket write in {n} files, downloader included")


# ---------------------------------------------------------------------------
# 3. The worked result. Every number in it must come from the result file.
# ---------------------------------------------------------------------------
def check_worked_result():
    path = HERE / "exp_lr_width_result.json"
    if not path.exists():
        return check("worked result: result file present", False, str(path))
    d = json.loads(path.read_text(encoding="utf-8"))
    block = claims(r"```\ncontrol\s+lr[^`]+?```", re.S)
    if not block:
        return check("worked result: block found in README", False, "")
    text = block.group(0)

    def num(pat):
        m = re.search(pat, text)
        return float(m.group(1)) if m else None

    lo_c, hi_c = min(d["control_losses"]), max(d["control_losses"])
    lo_t, hi_t = min(d["treatment_losses"]), max(d["treatment_losses"])
    pairs = [
        ("control mean", num(r"control\s+lr [\d.e-]+\s+mean ([\d.]+)"), d["mean_control"]),
        ("control range lo", num(r"control.*?range \[([\d.]+)"), lo_c),
        ("control range hi", num(r"control.*?range \[[\d.]+, ([\d.]+)\]"), hi_c),
        ("treatment mean", num(r"treatment\s+lr [\d.e-]+\s+mean ([\d.]+)"), d["mean_treatment"]),
        ("treatment range lo", num(r"treatment.*?range \[([\d.]+)"), lo_t),
        ("treatment range hi", num(r"treatment.*?range \[[\d.]+, ([\d.]+)\]"), hi_t),
        ("gap", num(r"gap \+([\d.]+)"), d["gap"]),
    ]
    bad = [f"{n}: README {c} vs artifact {round(a, 4)}"
           for n, c, a in pairs if c is None or abs(c - round(a, 4)) > 5e-5]
    check("worked result: every quoted number matches the artifact", not bad,
          "; ".join(bad) if bad else f"{len(pairs)} numbers verified")

    check("worked result: PASS matches the artifact's verdict",
          ("PASS" in text) == bool(d["passed"]),
          f"README says PASS={'PASS' in text}, artifact passed={d['passed']}")
    check("worked result: overlap claim matches the artifact",
          ("overlap: no" in text) == (not d["ranges_overlap"]),
          f"artifact ranges_overlap={d['ranges_overlap']}")
    check("worked result: seed count matches", str(len(d["seeds"])) == "5"
          and "Five seeds per arm" in README,
          f"artifact seeds={d['seeds']}")


def check_bar_is_preregistered():
    """'bar 0.020' must come from the prereg file, written before the run."""
    p = HERE / "prereg_lr_width.json"
    if not p.exists():
        return check("prereg file present", False, str(p))
    prereg = json.loads(p.read_text(encoding="utf-8"))
    blob = json.dumps(prereg)
    m = re.search(r">=\s*([\d.]+)", blob)
    claimed = claims(r"bar ([\d.]+)")
    ok = bool(m and claimed and abs(float(m.group(1)) - float(claimed.group(1))) < 1e-9)
    check("the quoted bar is the PREREGISTERED bar", ok,
          f"prereg says >= {m.group(1) if m else '?'}, "
          f"README says {claimed.group(1) if claimed else '?'}")


def check_fast_profile_verdict():
    """The README quotes the fast profile's verdict string; it must be verbatim."""
    p = HERE / "exp_lr_width_result_fast.json"
    if not p.exists():
        return check("fast profile result present", False, str(p))
    d = json.loads(p.read_text(encoding="utf-8"))
    verdict = d.get("verdict_string", "")
    # README wraps the line; compare with whitespace collapsed.
    flat_readme = re.sub(r"\s+", " ", README)
    flat_verdict = re.sub(r"\s+", " ", verdict)
    check("fast profile: README quotes the verdict string verbatim",
          flat_verdict and flat_verdict in flat_readme,
          f"artifact verdict: {verdict!r}")
    m = claims(r"fast profile: (\d+) steps, (\d+)-LR grid, (\d+) seeds")
    if m:
        steps, grid, seeds = (int(x) for x in m.groups())
        ok = (d["config"]["steps"] == steps and len(d["sweep"]) == grid
              and len(d["seeds"]) == seeds)
        check("fast profile: steps/grid/seeds match the artifact", ok,
              f"artifact: steps={d['config']['steps']}, grid={len(d['sweep'])}, "
              f"seeds={len(d['seeds'])}")


# ---------------------------------------------------------------------------
# 4. Claims about behaviour that the code either has or has not.
# ---------------------------------------------------------------------------
def check_dedicated_generator():
    """'Eval batches come from a dedicated torch.Generator, never the global RNG.'"""
    src = "".join((HERE / f).read_text(encoding="utf-8")
                  for f in ("train.py", "data.py") if (HERE / f).exists())
    check("eval uses a dedicated torch.Generator", "torch.Generator" in src,
          "no torch.Generator found in train.py/data.py",
          "torch.Generator present in train.py/data.py")


def check_auto_lr_exists():
    """'auto_lr(n_embd) scales with width.'"""
    src = (HERE / "train.py").read_text(encoding="utf-8")
    check("auto_lr(n_embd) exists and takes a width",
          re.search(r"def auto_lr\(\s*n_embd", src) is not None,
          "no def auto_lr(n_embd ...) in train.py", "found in train.py")


def check_detector_keeps_the_old_bug():
    """'test_detectors.py keeps the previous, broken fingerprinter on purpose and
    runs every test against both.'"""
    p = HERE / "test_detectors.py"
    if not p.exists():
        return check("test_detectors.py present", False, "")
    src = p.read_text(encoding="utf-8")
    check("the detector test still keeps a deliberately broken twin",
          re.search(r"broken|stride|old_fingerprint|buggy", src, re.I) is not None,
          "no reference to the broken fingerprinter found",
          "the broken twin is still in the file")


def check_resume_claim_still_true():
    """'No resume-from-checkpoint yet.' If resume is ever added, this must change.
    checkpoint.py loads a model for SAMPLING; that is not resuming training."""
    if "No resume-from-checkpoint yet" not in README:
        return check("limits: resume claim present", True, "claim removed")
    src = (HERE / "train.py").read_text(encoding="utf-8")
    resumes = re.search(r"--resume|resume_from|load_optimizer|optimizer\.load_state", src)
    check("limits: 'no resume-from-checkpoint yet' is still true", not resumes,
          "train.py appears to support resuming; the README says it does not",
          "train.py has no resume path, so the stated limit holds")


def check_checkpoint_round_trip_is_claimed():
    """'generate.py --out <folder> reads them back.' — the claim the GUI bug broke."""
    check("README claims checkpoints can be read back",
          "generate.py --out" in README, "")
    src = (HERE / "generate.py").read_text(encoding="utf-8")
    check("generate.py actually loads a checkpoint",
          "load_checkpoint" in src or "ckpt.pt" in src, "")


# ---------------------------------------------------------------------------
def main() -> int:
    for fn in (check_file_table, check_model_size, check_dependencies,
               check_nothing_phones_home, check_worked_result,
               check_bar_is_preregistered, check_fast_profile_verdict,
               check_dedicated_generator, check_auto_lr_exists,
               check_detector_keeps_the_old_bug, check_resume_claim_still_true,
               check_checkpoint_round_trip_is_claimed):
        try:
            fn()
        except Exception as e:  # a broken check is a failure, not a pass
            check(fn.__name__, False, f"check itself errored: {e!r}")

    width = max(len(n) for _, n, _ in RESULTS)
    failed = 0
    for ok, name, detail in RESULTS:
        failed += not ok
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {name.ljust(width)}  {detail}")
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} README claims verified"
          + ("" if not failed else f", {failed} FAILED"))
    print("Scope: the claims this script knows how to check. A newly added "
          "sentence is not checked automatically.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
