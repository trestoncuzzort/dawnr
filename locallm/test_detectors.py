"""test_detectors.py — tests for the leakage detector.

    python test_detectors.py

No framework, no dependencies, no config. Run it and read the output.

Why this file exists, stated plainly because it is the point: the detector in
leakage.py shipped twice with a correctness bug that no test would have caught,
because there were no tests. Both bugs were found by a reviewer reading the
code, which is luck, not a system. This is the system.

Two rules the bugs themselves taught, and both are load-bearing here:

  ASSERT ON THE DECISION, NOT A SUB-METRIC. The first bug lived in one metric
  while a neighbouring metric still looked fine, and the report printed both. A
  human read the healthy number. So these tests assert on the VERDICT the tool
  actually returns, which is what a user acts on.

  DO NOT PICK TEST INPUTS BY HAND. The first bug was a fixed stride of 10, and
  every "obvious" test offset a person reaches for (0, 100, 500, 1000) is a
  multiple of 10, so a hand-written suite passes on the broken code. When an
  implementation parameter could align with a test input, the input must be
  adversarial or random. Every offset test below mixes round numbers with
  random.Random-drawn ones, and the random ones are what actually bite.

The old, broken fixed-stride sampler is KEPT here on purpose as a regression
oracle, and every test runs against both implementations so you can see which
tests actually discriminate.

BE PRECISE ABOUT WHAT THIS SUITE GUARANTEES, because the first version of this
docstring overstated it and a later one went stale on its own arithmetic. Read
off the two columns this file prints, not counted from memory:

    phase invariance                        old sampler 4/16 offsets   FAILS
    documented length guarantee             old sampler 16/20 runs     FAILS
    line arm has a denominator              old sampler 2 lines        FAILS
                                              -> SUSPECT via CONTENT overlap
    no false positive at scale                                         passes
    clean split reads CLEAN                                            passes
    short copies are caught                                            passes
    the floor does not swallow a full copy                             passes
    the record names the deciding signal                               passes

Five of the eight pass against the known-broken sampler. That is not a defect in
them and it does not make them toothless: their regression target is the old
VERDICT RULE, or the old ROW, rather than the old fingerprinter, and each names
what it fails against.

  short copies are caught                 fails against leakage.py at 4b0b4f7,
                                          whose verdict read content overlap
                                          alone.
  the floor does not swallow a full copy   fails against leakage.py at 5d0c184,
                                          whose line floor gated the whole arm
                                          instead of its borderline band.
  the record names the deciding signal     fails against the row the writers
                                          built by hand before
                                          leakage.Report.record() existed:
                                          verdict plus the CONTENT fraction,
                                          which on its fixture is the arm that
                                          did not decide.

Both fixtures are the ones those changes were measured on, and they live in this
file rather than in a commit message because a fixture quoted in prose is not
run by anything.

NOT COVERED, measured rather than assumed: renamed or rewritten copies. The
detector scores 0% recall on identifier-renamed Python. No test here checks for
that, because the detector is not built to find it and a test would only assert
a known failure.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import leakage
from leakage import Report, shingles as current_shingles


def broken_fixed_stride_shingles(text: str, k: int = 50, stride: int = 10) -> set:
    """The original sampler, preserved as a permanent regression oracle.

    DO NOT USE THIS. It is here so the tests can prove they are capable of
    failing. It samples every `stride`-th window starting from position 0, so
    two copies of a passage are only ever compared when both happen to start on
    the same phase.
    """
    if len(text) < k:
        return {text} if text.strip() else set()
    return {text[i:i + k] for i in range(0, len(text) - k + 1, stride)}


def _verdict(train: str, val: str, shingle_fn) -> str:
    """Build a Report the way scan() does, but with a swappable fingerprinter,
    then ask for the VERDICT. Tests assert on this, never on a raw fraction."""
    train_sh, val_sh = shingle_fn(train), shingle_fn(val)
    rep = Report(
        train_chars=len(train), val_chars=len(val),
        val_docs=0, val_docs_in_train=0, doc_aligned=False,
        val_lines=len([l for l in val.splitlines() if l.strip()]),
        val_lines_in_train=0,
        val_shingles=len(val_sh),
        val_shingles_in_train=len(val_sh & train_sh))
    return rep.verdict


def _scan_like(train: str, val: str, shingle_fn, doc_aligned: bool) -> Report:
    """scan(), with a swappable fingerprinter and all three signals real.

    _verdict above zeroes the document and line counts on purpose: its tests are
    about the fingerprinter, and a stray line collision in generated filler
    would move a verdict those tests read as the fingerprinter's answer. This
    one keeps all three, because the fixture below is about what the verdict
    does with the two signals content overlap cannot see.
    """
    train_docs = set(leakage.documents(train))
    val_docs = leakage.documents(val)
    train_lines = set(train.splitlines())
    val_lines = [l for l in val.splitlines() if l.strip()]
    train_sh, val_sh = shingle_fn(train), shingle_fn(val)
    return Report(
        train_chars=len(train), val_chars=len(val),
        val_docs=len(val_docs),
        val_docs_in_train=sum(1 for d in val_docs if d in train_docs),
        doc_aligned=doc_aligned,
        val_lines=len(val_lines),
        val_lines_in_train=sum(1 for l in val_lines if l in train_lines),
        val_shingles=len(val_sh),
        val_shingles_in_train=len(val_sh & train_sh))


def short_document_fixture(seed: int = 4242, n_copied: int = 40) -> tuple[str, str]:
    """A holdout made ENTIRELY of verbatim copies of SHORT training documents.

    Every copied document is 30-35 characters, which is below SHINGLE = 50, so
    the content arm cannot fingerprint the duplication at any offset: it is not
    a matter of the copies being hard to find, they are shorter than the unit
    the arm measures in. The copies are re-ordered on the holdout side and the
    training side interleaves unrelated multi-line filler, so no 50-character
    window is shared across the two either — the content arm reads 0.0% because
    there is nothing there for it to see, while 100% of the holdout is
    byte-identical to training.
    """
    rng = random.Random(seed)
    words = ["alpha", "beta", "gamma", "delta", "value", "index", "buffer",
             "result", "window", "offset", "table", "kernel", "row", "seed"]

    def line(lo: int, hi: int) -> str:
        s = ""
        while len(s) < lo:
            s += (" " if s else "") + rng.choice(words)
        return s[:hi]

    copied = [line(30, 35) for _ in range(n_copied)]
    filler = ["\n".join(line(60, 90) for _ in range(4)) for _ in range(n_copied)]
    train_docs = []
    for c, f in zip(copied, filler):
        train_docs += [f, c]
    rng.shuffle(train_docs)
    val_docs = list(copied)
    rng.shuffle(val_docs)
    return "\n\n".join(train_docs), "\n\n".join(val_docs)


def _filler(n: int, seed: int) -> str:
    rng = random.Random(seed)
    words = ["alpha", "beta", "gamma", "delta", "value", "return", "index",
             "buffer", "result", "compute", "window", "offset"]
    out = []
    while sum(len(w) + 1 for w in out) < n:
        out.append(rng.choice(words))
        if rng.random() < 0.12:
            out.append("\n")
    return " ".join(out)[:n]


# ---------------------------------------------------------------- the tests

def test_phase_invariance(shingle_fn) -> tuple[bool, str]:
    """A verbatim copy must be found no matter what byte offset it sits at.

    Offsets deliberately mix round numbers with random ones. Round numbers
    alone pass on the broken sampler, which is exactly the trap this guards.
    """
    rng = random.Random(0)
    offsets = [0, 100, 500, 1000] + [rng.randrange(1, 997) for _ in range(12)]
    victim = _filler(3000, seed=7)
    missed = []
    for off in offsets:
        train = _filler(4000, seed=8) + ("x" * off) + victim + _filler(4000, seed=9)
        if _verdict(train, victim, shingle_fn) != "CONTAMINATED":
            missed.append(off)
    ok = not missed
    round_only = [o for o in missed if o % 10 == 0]
    detail = (f"{len(offsets) - len(missed)}/{len(offsets)} offsets detected"
              + ("" if ok else f"; missed {sorted(missed)[:8]}"
                               f" (of which {len(round_only)} were round numbers)"))
    return ok, detail


def test_no_false_positive_at_scale(shingle_fn) -> tuple[bool, str]:
    """Two independently generated corpora share no text, so any overlap is the
    fingerprinter colliding with itself. Must stay clean as size grows."""
    worst, worst_size = -1.0, 0
    for size in (200_000, 800_000):
        rng_a, rng_b = random.Random(101), random.Random(202)
        a = "".join(rng_a.choice("abcdefghijklmnopqrstuvwxyz \n") for _ in range(size))
        b = "".join(rng_b.choice("abcdefghijklmnopqrstuvwxyz \n") for _ in range(size))
        sa, sb = shingle_fn(a), shingle_fn(b)
        frac = len(sa & sb) / max(len(sb), 1)
        if frac > worst:
            worst, worst_size = frac, size
    ok = worst < 0.001
    return ok, f"worst false overlap {worst:.4%} at {worst_size // 1000}KB"


def test_clean_split_reads_clean(shingle_fn) -> tuple[bool, str]:
    """The complement of the phase test: unrelated text must NOT read as
    contaminated. A detector that always says CONTAMINATED would pass the
    phase test alone."""
    train, val = _filler(20000, seed=11), _filler(4000, seed=12)
    v = _verdict(train, val, shingle_fn)
    return v == "CLEAN", f"unrelated text reads {v}"


def test_guarantee_length(shingle_fn) -> tuple[bool, str]:
    """The documented guarantee is that a shared run of >= WINDOW + SHINGLE - 1
    characters is caught. Assert the documented number, not a hopeful one."""
    need = leakage.WINDOW + leakage.SHINGLE - 1
    rng = random.Random(3)
    hits = 0
    trials = 20
    for _ in range(trials):
        run = _filler(need, seed=rng.randrange(10**6))
        train = _filler(6000, seed=rng.randrange(10**6)) + run + _filler(6000, seed=rng.randrange(10**6))
        if shingle_fn(run) & shingle_fn(train):
            hits += 1
    ok = hits == trials
    return ok, f"{hits}/{trials} runs of the documented {need} chars were found"


def test_short_copies_are_caught(shingle_fn) -> tuple[bool, str]:
    """A holdout of verbatim copies too SHORT to fingerprint must not read CLEAN.

    The regression oracle here is not the old sampler, it is the old VERDICT:
    against leakage.py at 4b0b4f7, which decided on content overlap alone while
    printing all three signals, this fixture returns CLEAN with trustworthy
    True. Measured on that commit: documents 40/40, lines 40/40, content 0/95.

    The assertion deliberately includes `content is below its own SUSPECT bar`.
    Without it the test would pass on a detector that reached CONTAMINATED
    through the content arm, which is the one arm that structurally cannot see
    this fixture; with it, the test can only pass because the document and line
    arms are read too.
    """
    train, val = short_document_fixture()
    rep = _scan_like(train, val, shingle_fn, doc_aligned=True)
    ok = (rep.verdict == "CONTAMINATED" and not rep.trustworthy
          and rep.doc_frac == 1.0 and rep.line_frac == 1.0
          and rep.shingle_frac < leakage.SUSPECT)
    return ok, (f"documents {rep.val_docs_in_train}/{rep.val_docs} "
                f"({rep.doc_frac:.1%}), lines {rep.val_lines_in_train}/"
                f"{rep.val_lines} ({rep.line_frac:.1%}), content "
                f"{rep.shingle_frac:.1%} -> {rep.verdict}")


BOILERPLATE = "# Copyright (c) 2026 the locallm authors. MIT licence."


def test_line_arm_has_a_denominator(shingle_fn) -> tuple[bool, str]:
    """The line arm must not decide on a holdout too small to have a fraction.

    Both halves are asserted, because a floor is only correct if it silences
    the arm WITHOUT disarming it:

      tiny   a 2-line holdout whose only shared line is a licence header reads
             50.0%, which is the SUSPECT bar exactly. On leakage.py before the
             floor this returned SUSPECT and trustworthy False on a holdout
             that is entirely unseen text plus one boilerplate line.
      large  a 24-line holdout, half of it copied line for line, must still
             read SUSPECT. A floor that also quieted this one would be a
             deletion of the arm, not a fix.

    The large half is built so the LINE arm is the only one that can answer:
    every line is under SHINGLE = 50 characters and no two of them are adjacent
    on both sides of the split, so content overlap is structurally 0.0%, and
    doc_aligned is False so the document arm does not answer for it either.
    """
    train = "\n\n".join(f"{BOILERPLATE}\ndef f{i}(x): return x + {i}"
                        for i in range(3))
    val = BOILERPLATE + "\ndef unseen_and_entirely_original(q): return q ** 7"
    tiny = _scan_like(train, val, shingle_fn, doc_aligned=True)

    shared = [f"def shared{i}(x): return x * {i}" for i in range(12)]
    fresh = [f"def fresh{i}(y): return y - {i}" for i in range(12)]
    filler = [_filler(120, seed=500 + i) for i in range(12)]
    big_train = "\n\n".join(x for pair in zip(filler, shared) for x in pair)
    big_val = "\n\n".join(x for pair in zip(shared, fresh) for x in pair)
    big = _scan_like(big_train, big_val, shingle_fn, doc_aligned=False)

    ok = (tiny.verdict == "CLEAN" and not tiny.lines_readable
          and big.lines_readable and big.verdict == "SUSPECT")
    # The detail is read off report() rather than off lines_readable, so that a
    # detector without the floor at all fails with a legible line instead of an
    # AttributeError. The `and` above short-circuits before it reaches the
    # attribute for the same reason.
    row = next(l.strip() for l in tiny.report().splitlines()
               if l.strip().startswith("lines"))
    return ok, (f"{tiny.val_lines}-line holdout: {row} -> {tiny.verdict}; "
                f"{big.val_lines}-line holdout: {big.line_frac:.1%} of lines "
                f"shared -> {big.verdict}")


def test_the_floor_does_not_swallow_a_full_copy(shingle_fn) -> tuple[bool, str]:
    """A holdout entirely copied from training must not read CLEAN for being SMALL.

    The companion to the test above, and the case that one silenced. The floor
    was added because at small n one recurring line moves line_frac too far for
    the SUSPECT band to mean anything. It was implemented as a gate on the whole
    arm, so it also silenced the top of the range: measured on leakage.py at
    commit 5d0c184, a 19-line holdout whose every line is a verbatim training
    line in a different order read

        lines 19 / 19 (100.0%), content 0.0%, documents n/a -> CLEAN, trustworthy

    and the same fixture at 20 lines read CONTAMINATED. One line of denominator
    was the whole difference between "your holdout is your training set" and
    "no signal above its bar".

    Three sizes are asserted together, because each one alone permits a wrong
    fix:

      19 lines, all copied   must be caught. This is the case that read CLEAN.
       2 lines, all copied   must NOT be caught by the line arm: two shared
                             lines is the boilerplate shape the floor exists
                             for, and a fix that just deleted the floor would
                             catch this too.
      19 lines, 9 copied     must NOT be caught. 47.4% is inside the borderline
                             band the floor still owns, so a fix that lowered
                             the floor rather than reading the top of the range
                             fails here.

    Like the large half above, the fixture is built where only the LINE arm can
    answer: every line is under SHINGLE = 50 characters, training interleaves
    unrelated filler between the copied lines so no 50-character window is
    shared, and doc_aligned is False.
    """
    def fixture(n_lines: int, n_copied: int):
        shared = [f"def shared{i}(x): return x * {i}" for i in range(n_copied)]
        fresh = [f"def fresh{i}(y): return y - {i}" for i in range(n_lines - n_copied)]
        fill = [_filler(120, seed=900 + i) for i in range(n_copied)]
        train = "\n\n".join(x for pair in zip(fill, shared) for x in pair)
        val = shared + fresh
        random.Random(17).shuffle(val)
        return _scan_like(train, "\n\n".join(val), shingle_fn, doc_aligned=False)

    full19 = fixture(19, 19)
    full2 = fixture(2, 2)
    half19 = fixture(19, 9)

    ok = (full19.verdict == "CONTAMINATED" and not full19.trustworthy
          and full19.line_frac == 1.0
          and full19.shingle_frac < leakage.SUSPECT
          and full2.verdict == "CLEAN"
          and half19.verdict == "CLEAN")
    return ok, (f"19 lines all copied: {full19.line_frac:.1%} -> {full19.verdict} "
                f"(content {full19.shingle_frac:.1%}); "
                f"2 lines all copied: {full2.line_frac:.1%} -> {full2.verdict}; "
                f"19 lines 9 copied: {half19.line_frac:.1%} -> {half19.verdict}")


def test_the_record_names_the_deciding_signal(shingle_fn) -> tuple[bool, str]:
    """The row a writer persists must carry the signal that DECIDED the verdict.

    The regression oracle here is the old ROW, not the old sampler. Before
    Report.record() existed, train.py:104 and studio.py:522 each built
    {"verdict": rep.verdict, "content_frac": rep.shingle_frac} by hand, and on
    this fixture -- a holdout every document of which is a verbatim copy of a
    training document -- runlog printed

        CONTAMINATED  content 0.00%

    a verdict beside the one arm that structurally cannot see what caused it.
    The fallback below IS that row, so a detector without record() fails here
    with a legible line instead of an AttributeError.

    ASSERTED MECHANICALLY, not by naming the arms: whatever the row says
    decided the verdict must appear in the row with a number. A row that says
    CONTAMINATED and carries no fraction for the arm that said so is the
    failure, whichever arm it turns out to be, and an arm added to
    Report._signals() later inherits the assertion.
    """
    train, val = short_document_fixture()
    rep = _scan_like(train, val, shingle_fn, doc_aligned=True)
    rec = getattr(rep, "record", lambda: {"verdict": rep.verdict,
                                          "content_frac": rep.shingle_frac})()
    deciding = rec.get("deciding", [])
    missing = [n for n in deciding
               if not isinstance(rec.get(f"{n}_frac"), (int, float))]
    ok = (rec["verdict"] == "CONTAMINATED" and bool(deciding) and not missing
          and rec.get("reason") == rep.reason
          and rec["content_frac"] < leakage.SUSPECT)
    return ok, (f"row {sorted(rec)}; deciding {deciding or 'NOT RECORDED'}; "
                f"content {rec['content_frac']:.1%}"
                + (f"; no fraction for {missing}" if missing else ""))


TESTS = [
    ("phase invariance", test_phase_invariance),
    ("no false positive at scale", test_no_false_positive_at_scale),
    ("clean split reads CLEAN", test_clean_split_reads_clean),
    ("documented length guarantee", test_guarantee_length),
    ("short copies are caught", test_short_copies_are_caught),
    ("line arm has a denominator", test_line_arm_has_a_denominator),
    ("the floor does not swallow a full copy",
     test_the_floor_does_not_swallow_a_full_copy),
    ("the record names the deciding signal",
     test_the_record_names_the_deciding_signal),
]


def main() -> None:
    print("Running each test against the CURRENT detector (must pass) and against")
    print("the OLD fixed-stride sampler (must FAIL, or the test proves nothing).\n")

    failures = 0
    toothless = 0
    for name, fn in TESTS:
        cur_ok, cur_detail = fn(current_shingles)
        old_ok, old_detail = fn(broken_fixed_stride_shingles)

        status = "PASS" if cur_ok else "FAIL"
        print(f"  [{status}] {name}")
        print(f"         current: {cur_detail}")
        print(f"         old     : {old_detail}")
        if not cur_ok:
            failures += 1
        # A test the old broken sampler also passes cannot have caught the bug.
        # That is worth reporting, but only the phase test is expected to
        # discriminate; the others guard different properties.
        if name == "phase invariance" and old_ok:
            print("         !! this test PASSES on the known-broken sampler and is "
                  "therefore worthless")
            toothless += 1
        print()

    print("=" * 64)
    if failures:
        print(f"{failures} of {len(TESTS)} tests FAILED against the current detector")
    elif toothless:
        print("all tests passed, but a regression test did not fail on known-bad code")
    else:
        print(f"all {len(TESTS)} tests pass, and the phase test still fails on the "
              f"old sampler")
    print("=" * 64)
    sys.exit(1 if (failures or toothless) else 0)


if __name__ == "__main__":
    main()
