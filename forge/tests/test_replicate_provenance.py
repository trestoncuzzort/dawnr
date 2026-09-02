"""A replicate row must name the WHOLE verifier, not just the interpreter.

THE CLASS. Section 71 pinned the interpreter and taught every artifact to record
it, and `ruler_noise measure` refuses to pool replicates whose
`verifier["version"]` differs. That closes ONE of the two ways ground truth can
move under a series. The other is still open: forge.py, screen_tasks.py and the
screened task payloads define what verify() ACCEPTS, and a replicate row said
nothing about them. Loosen a BANNED pattern, shorten CAND_TIMEOUT, re-screen a
task -- every row still records the same interpreter, `measure` still counts the
old replicates as poolable, and 40 replicates that were scored under two
different verifiers become indistinguishable in the file. dataset_gate wrote that
failure mode down for the receipt ("every data hash still matches while the
*meaning* of 'verified' silently changes -- producing a PASSING receipt for a
weaker claim"); the replicate bank had no equivalent.

dataset_gate.verifier_fingerprint() ALREADY computes exactly the right thing --
sha256 of forge.py, of screen_tasks.py, of data/screen_results.jsonl, plus the
interpreter (and, since the receipt was bound to the gate version and the frozen
split, of verify_dataset.py and data/ruler_frozen.json too; this file reads the
set from the gate rather than re-listing it, so that widening arrived here for
free). The defect was that nothing put it on the row. So this file asserts
the row carries it, not that a new hashing scheme is correct.

RED WITNESS (pre-fix bytes, ruler_noise.replicate_row extracted but not yet
merging the fingerprint):
    FAIL test_row_carries_the_full_verifier_fingerprint: replicate row's
    verifier section is missing 4 key(s) that dataset_gate.verifier_fingerprint()
    defines: ['data/screen_results.jsonl', 'forge.py', 'interpreter',
    'screen_tasks.py'].

WHICH SIDE OF THE STRADDLE THE ROW RECORDS, and the second red. The first fix
hashed the files inside replicate_row, i.e. AFTER evaluate() had already scored
the replicate -- so it recorded the state of the DISK at banking time, while the
code that actually produced the verdict was the state LOADED at import (forge and
screen_tasks stay imported for the whole run, and `tasks` are built once before
the loop). Edit forge.py while a 40-replicate run is in flight and every
subsequent row claimed the new hash while still being scored by the old loaded
bytes: a fingerprint that is not merely absent but WRONG, which is worse, because
it is a confident label. Second red witness:
    FAIL test_the_row_stamps_the_snapshot_not_the_disk: row records forge.py
    cd76c09737c60e1e..., the CURRENT disk hash, not the snapshot's
    00000000deadbeef...; a row must name the code that scored it.
So the snapshot is taken ONCE by `measure` before the loop and PASSED IN, and
`verifier_drift` re-reads the disk before each row is banked so a mid-run edit
aborts the run instead of mislabelling rows.

WHAT THIS DOES NOT ASSERT. It does not claim the fingerprint is complete as a
description of "what verified means" -- that scope decision lives in
dataset_gate's VERIFIER_FILES / TASK_SOURCE_FILES / SPLIT_FILES and this file
deliberately reads it from there rather than re-listing it, so widening the
fingerprint widens the test for free. It does not check that anything READS the new fields
to refuse pooling; recording is a precondition for that, not a substitute. And
it says nothing about rows already banked: those stay unfingerprinted, and are
evidence of that fact rather than something this fix can retroactively repair.

THE PIN, and why setting SRLM_VERIFY_PY here is not a mock. forge.py resolves
VERIFY_PY at import, and dataset_gate.verify_py() REFUSES (SystemExit) when
.venv-train is absent and no pin is declared -- deliberately, so an unpinned
machine cannot quietly score against the launcher. On a machine without the
venv, importing ruler_noise at all is therefore impossible until a pin is
declared. This module declares one, through the module's own documented
override, only when there is no venv and the operator has not already chosen:
that is the supported "deliberate pin" path, and it is recorded in the
fingerprint like any other. It is NOT a stub for verify_py/verifier_fingerprint
-- the hashes below are computed by the real gate against the real files on
disk. Consequence, stated rather than hidden: on such a machine the
`interpreter` half of the fingerprint is the launcher, so no assertion here
depends on the interpreter's IDENTITY, only on its PRESENCE.
"""
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_VENV_PY = ROOT / ".venv-train" / "Scripts" / "python.exe"
if not os.environ.get("SRLM_VERIFY_PY") and not _VENV_PY.exists():
    os.environ["SRLM_VERIFY_PY"] = sys.executable   # see THE PIN, above

import dataset_gate  # noqa: E402
import forge  # noqa: E402
import ruler_noise as rn  # noqa: E402


def _evaluate_result() -> dict:
    """One eval.evaluate() return value, in its real shape.

    Only the keys the row builder and the two jsonl readers touch are carried;
    the per-task block is included so the row that gets serialized below is a
    genuine row rather than a stub that could not be written to the file.
    """
    return {
        "ts": "2026-01-01T00:00:00",
        "model": "probe-model",
        "task_set": rn.TASK_SET,
        "n_samples": 5,
        "temp": 0.8,
        "sampler": {"greedy_anchor": False, "temperature": 0.8,
                    "draws_per_task": 5},
        "verifier": forge.verifier_interpreter(),
        "n_tasks": 1,
        "aggregate": {"pass@1": 0.4},
        "gen_errors_total": 0,
        "per_task": [{"tid": "t00", "n": 5, "correct": 2, "greedy": 0,
                      "sampled": [1, 1, 0, 0], "gen_errors": 0}],
    }


SENTINEL = "00000000deadbeef" + "0" * 48      # 64 hex chars, cannot be a real
                                              # hash of anything on disk


def _snapshot() -> dict:
    """What `measure` captures once, before the replicate loop."""
    return dataset_gate.verifier_fingerprint()


def _row(snapshot: dict | None = None) -> dict:
    return rn.replicate_row(_evaluate_result(), 7,
                            _snapshot() if snapshot is None else snapshot)


def test_row_carries_the_full_verifier_fingerprint():
    """THE RED. Every field that defines what 'verified' meant, on the row."""
    row = _row()
    want = dataset_gate.verifier_fingerprint()
    got = row.get("verifier") or {}
    missing = sorted(k for k in want if k not in got)
    assert not missing, (
        f"replicate row's verifier section is missing {len(missing)} key(s) "
        f"that dataset_gate.verifier_fingerprint() defines: {missing}. Two "
        f"replicates scored under different forge.py versions are "
        f"indistinguishable in the bank without them.")
    wrong = {k: (got[k], want[k]) for k in want if got[k] != want[k]}
    assert not wrong, f"row records a fingerprint that is not the live one: {wrong}"


def test_the_forge_hash_is_content_not_a_name():
    """A filename proves nothing; the sha256 of the bytes is the claim.

    Checked against the gate's own hasher on the file on disk, so an
    implementation that recorded a constant, a mtime or a path would fail here.
    """
    row = _row()
    got = (row.get("verifier") or {}).get("forge.py")
    assert got == dataset_gate.sha256_file(ROOT / "forge.py"), (
        f"verifier['forge.py'] is {got!r}, not the sha256 of forge.py's bytes")
    assert len(got) == 64 and all(c in "0123456789abcdef" for c in got), \
        f"not a sha256 hex digest: {got!r}"


def test_the_interpreter_pin_survives_additively():
    """ADDITIVE, not a replacement.

    The section 71 fields are what `measure` and `analyze` already key on. If
    merging the fingerprint renamed or dropped one, the resume count would reset
    and 40 banked replicates would silently become 'foreign'.
    """
    row = _row()
    pin = forge.verifier_interpreter()
    for k, v in pin.items():
        assert row["verifier"].get(k) == v, (
            f"verifier[{k!r}] was {row['verifier'].get(k)!r}, expected the "
            f"section 71 value {v!r}; the merge must not overwrite the pin")


def test_the_two_jsonl_readers_still_work_on_old_and_new_rows():
    """Old rows must stay parseable, new rows must stay poolable.

    These are the exact expressions `cmd_measure` (resume count) and
    `cmd_analyze` (verifier partition) run over every line of the bank. Driven
    here over a legacy pre-pin row, a pin-only row and a fingerprinted row.
    """
    version = forge.verifier_interpreter()["version"]
    legacy = {"model": "probe-model", "task_set": rn.TASK_SET,
              "replicate": 1, "aggregate": {"pass@1": 0.4}}   # no `verifier`
    pin_only = dict(_evaluate_result(), replicate=2)
    fingerprinted = _row()

    # cmd_measure: count mine, ignore foreign, never crash on a legacy row.
    got = [(r.get("verifier") or {}).get("version")
           for r in (legacy, pin_only, fingerprinted)]
    assert got == [None, version, version], (
        f"resume-count expression reads {got!r}; a fingerprinted row must still "
        f"report the pinned version, and a pre-pin row must still parse")

    # cmd_analyze: the partition key.
    vers = {(r.get("verifier") or {}).get("version", "pre-pin/unrecorded")
            for r in (legacy, pin_only, fingerprinted)}
    assert vers == {"pre-pin/unrecorded", version}, (
        f"analyze would partition these into {sorted(vers)}; the fingerprinted "
        f"row must land in the same bucket as the pin-only rows it is pooled "
        f"with")


def test_the_row_stamps_the_snapshot_not_the_disk():
    """THE SECOND RED. The row must name the code that SCORED it.

    Codex review, P1: hashing inside the builder reads the disk AFTER evaluate()
    has already returned, while forge/screen_tasks stay imported and `tasks` were
    built before the loop. A file edited mid-run therefore produces rows claiming
    the NEW hash for verdicts reached by the OLD loaded bytes. A wrong label is
    worse than a missing one.

    STRUCTURAL PROBE, and the honest reason for it: dataset_gate hard-codes its
    paths (`HERE / name`), so there is no parametrized directory to re-point and
    no way to move the hashed bytes without editing forge.py or data/ on disk
    mid-test -- which this file will not do. The probe instead hands the builder
    a snapshot that CANNOT equal any on-disk state and asserts the row carries
    it. That discriminates exactly the reported defect: a builder that recomputes
    the fingerprint itself cannot pass, and one that stamps what it was given
    cannot fail.
    """
    snapshot = dict(_snapshot(), **{"forge.py": SENTINEL})
    got = _row(snapshot)["verifier"]["forge.py"]
    assert got == SENTINEL, (
        f"row records forge.py {got[:16]}..., the CURRENT disk hash, not the "
        f"snapshot's {SENTINEL[:16]}...; a row must name the code that scored it")


def test_drift_names_every_changed_entry():
    """The compare that turns a mid-run edit into an abort.

    Driven with two dicts so it is tested independently of the disk: it must
    report old AND new for each changed entry (the message has to say what
    moved), report nothing when they match, and notice an entry that only one
    side has -- a fingerprint that GAINS a file is a change too.
    """
    base = {"forge.py": "aaa", "screen_tasks.py": "bbb", "interpreter": "3.11.9"}
    same = rn.verifier_drift(base, dict(base))
    assert same == {}, f"identical fingerprints reported drift: {same}"

    moved = rn.verifier_drift(base, dict(base, **{"forge.py": "zzz"}))
    assert moved == {"forge.py": ("aaa", "zzz")}, \
        f"drift on one file reported as {moved}"

    gained = rn.verifier_drift(base, dict(base, **{"data/new.jsonl": "ccc"}))
    assert gained == {"data/new.jsonl": (None, "ccc")}, \
        f"a fingerprint that gained an entry reported as {gained}"

    lost = rn.verifier_drift(dict(base, **{"gone.py": "ddd"}), base)
    assert lost == {"gone.py": ("ddd", None)}, \
        f"a fingerprint that lost an entry reported as {lost}"


def test_drift_defaults_to_the_disk_and_is_quiet_when_nothing_moved():
    """Called with one argument it must read the live files, because that is how
    `measure` uses it: snapshot in hand, disk re-read before each row."""
    live = _snapshot()
    assert rn.verifier_drift(live) == {}, \
        "the live fingerprint disagrees with itself; the compare is not reading disk"
    doctored = dict(live, **{"forge.py": SENTINEL})
    d = rn.verifier_drift(doctored)
    assert list(d) == ["forge.py"] and d["forge.py"][0] == SENTINEL, \
        f"an edited forge.py was not detected against the disk: {d}"


def test_measure_aborts_rather_than_banking_a_mislabelled_row():
    """WIRING, in this repo's existing style (test_verifier_pin.py asserts the
    same way that eval.evaluate records the verifier at all).

    Scope, stated: this reads source text. It witnesses that the snapshot is
    taken before the loop and that the drift check runs before the write, not
    that a live 40-replicate run aborts -- that needs Ollama and a GPU and is not
    something this file can execute.
    """
    src = pathlib.Path(rn.__file__).read_text(encoding="utf-8")
    body = src.split("def cmd_measure")[1]
    snap = body.index("verifier_fingerprint()")
    loop = body.index("for i in range(")
    check = body.index("verifier_drift(")
    write = body.index("OUT.open(\"a\"")
    assert snap < loop, "the snapshot must be captured BEFORE the replicate loop"
    assert loop < check < write, (
        "the drift check must run inside the loop and BEFORE the row is "
        "written, or a mid-run edit is banked under the old label")
    # Read the message as PRINTED, not as typed: adjacent string literals are
    # joined first, so the assertion is about the operator-facing text and not
    # about where the author happened to wrap a line.
    printed = re.sub(r"\s+", " ", re.sub(r'"\s*"', "", body))
    assert "aborting rather than banking" in printed, \
        "a drifted verifier must abort in the same voice as the other abort"


def test_the_row_is_what_gets_written():
    """The row is appended as one JSON line, so it must survive that trip."""
    row = _row()
    assert row["replicate"] == 7, "the replicate number is part of the row"
    back = json.loads(json.dumps(row, ensure_ascii=False))
    assert back["verifier"] == row["verifier"], \
        "the verifier section does not round-trip through JSON"
    assert "\n" not in json.dumps(row, ensure_ascii=False), \
        "a row must serialize to exactly one line"


def test_the_builder_does_not_mutate_the_evaluate_result():
    """`measure` prints from evaluate's result after banking; building the row
    must not be the thing that edits it underneath."""
    res = _evaluate_result()
    before = json.dumps(res, sort_keys=True, ensure_ascii=False)
    rn.replicate_row(res, 3, _snapshot())
    assert json.dumps(res, sort_keys=True, ensure_ascii=False) == before, \
        "replicate_row mutated the result it was handed"


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as e:
                fails.append(name); print(f"FAIL {name}: {e}")
    print(f"\n{len(fails)} failed")
    raise SystemExit(1 if fails else 0)
