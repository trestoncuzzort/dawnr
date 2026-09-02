"""tests/test_dataset_gate_holes.py — six ways the data gate said PASS.

verify_dataset.py is the mechanism behind "every training pair was executed and
checked". These are the inputs on which it said so without having checked.

  1. SIGNATURE COLLISION. signature() concatenated prompt + chosen + rejected +
     tid with no delimiter and hashed the result. Concatenation is not
     injective: {"prompt": "ab", "chosen": "c"} and {"prompt": "a",
     "chosen": "bc"} build the same string, so two DIFFERENT pairs got the same
     identity. load_pairs() keeps the first and lets every later file inherit
     its verdict, so the second pair was never executed and still counted as
     verified. The fix hashes a canonical JSON object of the four named fields,
     where the field boundaries survive.
  2. A MALFORMED LINE WAS SKIPPED IN SILENCE. `except json.JSONDecodeError:
     continue`. A truncated write, a half-flushed append, a hand-edit -- the
     row vanished from the count, and the gate reported PASS over the rows it
     could still parse. A file the gate cannot read is not a file the gate has
     cleared.
  3. NO PARTITION CHECK. Nothing asserted that a training pair belongs to the
     training side of the frozen split. A pair labelled with one of the 31
     frozen RULER task ids -- the eval set -- would have been executed,
     verified, and passed, because "chosen passes and rejected fails" is true
     of a contaminating pair too. The gate's own subject matter is which pairs
     may be trained on, so this one it has to answer.
  4. A FILE WITH NOTHING IN IT PASSED AFFIRMATIVELY. Every count the gate
     reports is a count OVER the rows it parsed, so a file truncated to zero
     length -- or left holding only blank lines -- came out zero on all of
     them and the report said "PASS: 0/0 pairs valid" with exit 0. The receipt
     entry, {"pairs": 0, "violations": 0}, is the exact shape
     require_verified() grants permission on, so training then started on it.
     A present pair file with no parseable row is now a violation of its own.
  5. A RECEIPT OUTLIVED THE GATE THAT ISSUED IT. Every fix above changed what
     verify_dataset.py checks, and nothing recorded WHICH version of that file
     wrote a receipt: the fingerprint covered forge.py, the task source and the
     interpreter, never the gate's own bytes. So a receipt written by the OLD
     gate -- the one that skipped malformed lines, certified an empty file and
     never looked at the partition -- is byte-indistinguishable from one written
     after, require_verified() honours it, and all four fixes are invisible at
     consumption time. The same silence covered the frozen split: the partition
     check reads data/ruler_frozen.json at verification time, so with the split
     unrecorded a receipt stays valid across a re-freeze that moves a training
     task into the eval set, and training on eval data becomes possible under a
     receipt that is still, on its own terms, correct.
  6. THE RECEIPT WAS FINGERPRINTED AFTER THE VERDICT, NOT BEFORE. Fix 5
     put the gate's own bytes and the frozen split into the fingerprint so
     a receipt says WHICH questions it answered -- but the fingerprint was
     taken at the END of the run, while the split is read at the START
     (load_partition, before any pair is executed) and the pair files
     before that, with minutes of subprocesses in between. Edit
     data/ruler_frozen.json inside that window and the receipt records the
     NEW hash beside a verdict computed against the OLD split: it says '0
     violations' while naming the very bytes under which the pair it
     cleared is an eval-set contamination. Append to a pair file and it
     names a sha256 covering a pair that was never executed. Every input is
     now hashed BEFORE the checks, re-hashed before the write, and any
     difference aborts without writing anything -- a receipt whose bytes
     did not produce its verdict is the one failure a receipt exists to
     prevent.

Each test keeps the broken twin beside it (test_stats_core.py idiom) and
asserts the twin STILL misbehaves, so a test that stops discriminating is
itself a failure rather than a silent pass.

THE PIN. Importing verify_dataset pulls in dataset_gate, which SystemExits when
neither .venv-train nor SRLM_VERIFY_PY resolves. Declared here through the
module's own documented override, and only when the operator has not already
chosen -- the same path tests/test_replicate_provenance.py takes, for the same
reason. Nothing here executes a candidate, so the interpreter's identity does
not enter any assertion.

NOTHING HERE TOUCHES data/. Tests 1-4 drive load_pairs() or
partition_violations() against fixtures in a temp directory, or read the
committed pairs without verifying them. The class-5 tests write receipts,
but only into temp directories: each assembles one from the same two helpers
main() writes with (dataset_gate.build_file_entries and
verifier_fingerprint) and re-points dataset_gate.HERE at a byte-copy of the
fingerprinted files, so "the verifier changed" and "the split moved" can be
staged without editing anything in the repo. The class-6 tests DO call
main() -- the window they are about exists only inside it -- with
dataset_gate.HERE and verify_dataset.DATA both pointed at that same
byte-copy, so every file it reads and the receipt it writes are under the
temp root. They also replace check(), which is where a real run spends its
minutes in subprocesses; the elapsed window is what is under test, not what
check() computes. data/dataset_verification.json is never written and data/
is read only to copy it. Receipt regeneration is the maintainer's explicit
decision (docs/UBUNTU-BOOTSTRAP.md, step 6).

Run: python tests/test_dataset_gate_holes.py
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_VENV_PY = ROOT / ".venv-train" / "Scripts" / "python.exe"
if not os.environ.get("SRLM_VERIFY_PY") and not _VENV_PY.exists():
    os.environ["SRLM_VERIFY_PY"] = sys.executable   # see THE PIN, above

import dataset_gate                                               # noqa: E402
import forge                                                      # noqa: E402
import verify_dataset as V                                        # noqa: E402

# The two pairs the audit executed. Same rejected, same tid; the prompt/chosen
# split is the only difference, and concatenation erases exactly that.
PAIR_A = {"prompt": "ab", "chosen": "c", "rejected": "r", "meta": {"tid": "t"}}
PAIR_B = {"prompt": "a", "chosen": "bc", "rejected": "r", "meta": {"tid": "t"}}


def _signature_concat_sha1(d):
    """The bug, verbatim: four fields glued together with no separator."""
    tid = (d.get("meta") or {}).get("tid") or ""
    return hashlib.sha1(
        (d.get("prompt", "") + d.get("chosen", "") +
         d.get("rejected", "") + tid).encode("utf-8")).hexdigest()


def _fixture(*lines: str) -> pathlib.Path:
    """A DATA directory holding one dpo_pairs.jsonl of exactly these lines."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="test_gate_holes_"))
    (d / "dpo_pairs.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


def _fixture_bytes(body: str) -> pathlib.Path:
    """A DATA directory whose dpo_pairs.jsonl is EXACTLY these bytes. _fixture()
    always terminates the file with a newline, and a zero-length file is one of
    the two shapes under test here."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="test_gate_holes_"))
    (d / "dpo_pairs.jsonl").write_text(body, encoding="utf-8", newline="")
    return d


def _load_from(data_dir):
    saved = V.DATA
    try:
        V.DATA = data_dir
        return V.load_pairs()
    finally:
        V.DATA = saved


# --- 1. signature ---------------------------------------------------------
def test_signature_separates_the_documented_collision_pair():
    assert V.signature(PAIR_A) != V.signature(PAIR_B), (
        "two different pairs share one identity; the second is never executed "
        "and inherits the first one's verdict")
    # The twin must still collide, or this test has stopped testing anything.
    assert _signature_concat_sha1(PAIR_A) == _signature_concat_sha1(PAIR_B), \
        "twin lost its bug; the test is dead"


def test_signature_still_depends_on_all_four_fields():
    base = dict(PAIR_A)
    for field, value in (("prompt", "zz"), ("chosen", "zz"), ("rejected", "zz")):
        assert V.signature(dict(base, **{field: value})) != V.signature(base), \
            f"{field} does not enter the signature"
    assert V.signature(dict(base, meta={"tid": "other"})) != V.signature(base), \
        "tid does not enter the signature"


def test_signature_is_stable_across_key_order_and_extra_keys():
    """Only the four named fields may decide identity: a pair carrying extra
    metadata is the same pair, and dict order is not content."""
    reordered = {"meta": {"tid": "t"}, "rejected": "r", "chosen": "c",
                 "prompt": "ab", "score": 0.5, "round": 3}
    assert V.signature(reordered) == V.signature(PAIR_A)


# --- 2. malformed lines ---------------------------------------------------
def test_a_malformed_line_is_reported_with_file_and_line():
    good = json.dumps(PAIR_A)
    data = _fixture(good, "{not json at all", json.dumps(PAIR_B))
    out = _load_from(data)
    assert len(out) == 3, (
        "load_pairs() still returns only (unique, rows_by_file); a malformed "
        "line has nowhere to be reported")
    unique, rows_by_file, malformed = out
    assert len(malformed) == 1, f"malformed lines not surfaced: {malformed}"
    m = malformed[0]
    assert m["file"] == "dpo_pairs.jsonl", m
    assert m["line"] == 2, f"wrong line number reported: {m}"
    assert not m["ok"] and "json" in m["why"].lower(), m
    # `why` is the stable class (so the type histogram groups); the file and
    # line are carried in `detail` as well as in the fields above.
    assert m["detail"].startswith("dpo_pairs.jsonl:2:"), m
    # the parseable rows are still loaded -- the gate reports, it does not bail
    assert len(unique) == 2, unique
    assert len(rows_by_file["dpo_pairs.jsonl"]) == 2, rows_by_file


def test_a_trailing_blank_line_is_not_a_violation():
    """A file that ends with a newline is not malformed, and calling it that
    would make the gate cry wolf on every well-formed file."""
    data = _fixture(json.dumps(PAIR_A), "", "")
    _, _, malformed = _load_from(data)
    assert malformed == [], malformed


def test_the_committed_pair_files_have_no_malformed_lines():
    """States what the retained bytes actually are, so the fix is known to be
    a new fence rather than a change of verdict on the current data."""
    _, _, malformed = V.load_pairs()
    assert malformed == [], malformed


# --- 3. the frozen split --------------------------------------------------
def test_a_frozen_ruler_tid_in_training_data_is_fatal():
    ruler, _pool = V.load_partition()
    assert len(ruler) == 31, f"the frozen ruler is not 31 tasks: {len(ruler)}"
    contaminating = dict(PAIR_A, meta={"tid": sorted(ruler)[0]})
    bad = V.partition_violations([dict(contaminating, _src="forge", _row=0,
                                       _file="dpo_pairs.jsonl")])
    assert len(bad) == 1, bad
    assert bad[0]["why"] == "ruler_task_in_training_data", bad
    assert not bad[0]["ok"]


def test_a_tid_outside_the_training_pool_is_fatal():
    stray = dict(PAIR_A, meta={"tid": "ace_oss_definitely_not_screened"})
    bad = V.partition_violations([dict(stray, _src="forge", _row=7,
                                       _file="dpo_pairs.jsonl")])
    assert len(bad) == 1, bad
    assert bad[0]["why"] == "tid_outside_training_pool", bad
    assert bad[0]["row"] == 7, bad


def test_a_seed_task_is_allowed_outside_the_pool():
    """SEED_TASKS predate the frozen split and are neither ruler nor pool.
    They are hand-written and were never eval material; refusing them would
    reject the pairs the project started from."""
    seed = sorted(t.tid for t in forge.SEED_TASKS)[0]
    ok = dict(PAIR_A, meta={"tid": seed}, _src="forge", _row=0,
              _file="dpo_pairs.jsonl")
    assert V.partition_violations([ok]) == []


def test_the_ruler_and_the_training_pool_do_not_overlap():
    """The precondition the check rests on. If these two sets ever intersect,
    'in the pool' and 'in the ruler' stop being a decision."""
    ruler, pool = V.load_partition()
    assert not (ruler & pool), sorted(ruler & pool)


def test_the_committed_pairs_are_all_on_the_training_side():
    """The retained data passes the new check -- so it is a fence against the
    next generation run, not a re-verdict on this one."""
    unique, _, _ = V.load_pairs()
    bad = V.partition_violations(list(unique.values()))
    assert bad == [], bad[:5]


# --- 4. a file with nothing verifiable in it ------------------------------
def test_an_empty_pair_file_is_a_violation():
    unique, rows_by_file, malformed = _load_from(_fixture_bytes(""))
    bad = V.empty_file_violations(rows_by_file)
    assert len(bad) == 1, bad
    assert bad[0]["file"] == "dpo_pairs.jsonl", bad
    assert bad[0]["why"] == "no_verifiable_rows", bad
    assert not bad[0]["ok"], bad
    # THE TWIN, in the only form this defect has one: every OTHER signal the
    # gate owns is silent on this file, which is exactly why it used to pass
    # with a clean receipt. If any of them ever starts firing here, this test
    # has stopped being the thing that catches an empty file.
    assert rows_by_file == {"dpo_pairs.jsonl": []}, rows_by_file
    assert unique == {}, unique
    assert malformed == [], malformed
    assert V.partition_violations(list(unique.values())) == []


def test_a_blank_lines_only_pair_file_is_a_violation():
    """A file of newlines is not malformed -- blank lines are legal and there
    is a test above saying so -- so the malformed check cannot be what catches
    this one."""
    _, rows_by_file, malformed = _load_from(_fixture_bytes("\n\n   \n\t\n"))
    assert malformed == [], malformed
    assert [v["why"] for v in V.empty_file_violations(rows_by_file)] == \
        ["no_verifiable_rows"], rows_by_file


def test_a_file_with_a_parseable_row_is_not_flagged_as_empty():
    """The cry-wolf side. One row is something to certify, and a trailing
    blank line does not take it away."""
    _, rows_by_file, _ = _load_from(_fixture(json.dumps(PAIR_A), ""))
    assert V.empty_file_violations(rows_by_file) == []


def test_a_file_of_only_malformed_lines_is_reported_both_ways():
    """Two different true statements about one file: WHICH lines could not be
    read, and that the file as a whole certified nothing. Neither implies the
    other -- an empty file has no malformed line at all."""
    _, rows_by_file, malformed = _load_from(_fixture("{oops", "also not json"))
    assert len(malformed) == 2, malformed
    assert len(V.empty_file_violations(rows_by_file)) == 1, rows_by_file


def test_the_committed_pair_files_all_have_parseable_rows():
    """States what the retained bytes are, so the new check is known to be a
    fence rather than a change of verdict on the current data.

    The row COUNTS are deliberately not pinned -- a generation run is allowed
    to change them, and a test that failed on that would be crying wolf about
    the wrong thing. What is pinned is that all three named files are present
    and none of them is empty, which is the property this class is about."""
    _, rows_by_file, _ = V.load_pairs()
    assert sorted(rows_by_file) == sorted(V.FILES), rows_by_file
    assert V.empty_file_violations(rows_by_file) == []
    assert all(sl for sl in rows_by_file.values()), \
        {n: len(sl) for n, sl in rows_by_file.items()}


# --- 5. a receipt that outlived the gate that issued it -------------------
# THE TWIN, verbatim: the fingerprint scope as it stood before this class was
# closed. Whole-file hashes of the executor, the task source and the
# interpreter -- and nothing about verify_dataset.py, which is the file that
# decides what a violation IS, or about the frozen split it decides against.
_OLD_VERIFIER_FILES = ("forge.py",)
_OLD_TASK_SOURCE_FILES = ("screen_tasks.py", "task_bank.py",
                          "data/screen_results.jsonl")


def _fingerprint_before_the_fix(root: pathlib.Path) -> dict:
    fp = {n: dataset_gate.sha256_file(root / n)
          for n in _OLD_VERIFIER_FILES + _OLD_TASK_SOURCE_FILES}
    fp.update(dataset_gate.interpreter_fingerprint())
    return fp


@contextlib.contextmanager
def _repointed_at(root: pathlib.Path):
    """Point the gate's hashing at `root`. dataset_gate reads HERE at call time
    (`sha256_file(HERE / name)`), so this moves the whole fingerprint without a
    stub in front of it -- the real function runs over real files."""
    saved = dataset_gate.HERE
    dataset_gate.HERE = root
    try:
        yield root
    finally:
        dataset_gate.HERE = saved


def _mirror() -> pathlib.Path:
    """A byte-copy of every file the fingerprint reads, safe to edit.

    The two files this class adds are copied whether or not the gate currently
    hashes them (hence the union with the literal names, and the getattr): the
    fixture must still build with dataset_gate.py reverted to its pre-fix bytes,
    or the four tests below could not be re-run against the defect they were
    written for. The copy is asserted to fingerprint IDENTICALLY to the repo
    before any test mutates it, which is what makes it a redirect rather than a
    stub.
    """
    d = pathlib.Path(tempfile.mkdtemp(prefix="test_gate_receipt_"))
    (d / "data").mkdir()
    names = (set(dataset_gate.VERIFIER_FILES)
             | set(dataset_gate.TASK_SOURCE_FILES)
             | set(getattr(dataset_gate, "SPLIT_FILES", ()))
             | {"verify_dataset.py", "data/ruler_frozen.json"})
    for n in names:
        shutil.copyfile(ROOT / n, d / n)
    live = dataset_gate.verifier_fingerprint()
    with _repointed_at(d):
        assert dataset_gate.verifier_fingerprint() == live, \
            "the mirror does not fingerprint like the repo; it is not a redirect"
    return d


def _receipt(data_dir: pathlib.Path, fname: str, pairs: int, violations: int,
             fingerprint: dict) -> pathlib.Path:
    """A receipt in the shape verify_dataset.main() writes, built by the same
    two helpers, into a temp directory."""
    r = {"schema": dataset_gate.SCHEMA,
         "files": dataset_gate.build_file_entries(
             data_dir, {fname: {"pairs": pairs, "violations": violations}}),
         "verifier": fingerprint}
    dataset_gate.receipt_path(data_dir).write_text(json.dumps(r, indent=2))
    return data_dir / fname


def _refusal(paths, data_dir) -> str | None:
    """The gate's message if it refuses, None if it grants permission."""
    try:
        dataset_gate.require_verified(paths, data_dir)
        return None
    except SystemExit as e:
        return str(e)


def _pair_file(body: str) -> tuple[pathlib.Path, str]:
    d = pathlib.Path(tempfile.mkdtemp(prefix="test_gate_receipt_data_"))
    (d / "dpo_pairs.jsonl").write_text(body, encoding="utf-8", newline="")
    return d, "dpo_pairs.jsonl"


CLEAN_ROW = json.dumps({"prompt": "p", "chosen": "c", "rejected": "r",
                        "meta": {"tid": "atoi"}}) + "\n"


def test_the_fingerprint_names_the_gate_that_writes_the_receipt():
    """verify_dataset.py decides what a violation IS. A receipt that does not
    record its bytes cannot say which set of checks produced '0 violations'."""
    fp = dataset_gate.verifier_fingerprint()
    assert "verify_dataset.py" in fp, (
        "the fingerprint does not cover verify_dataset.py, so a receipt written "
        "by any earlier version of the gate is indistinguishable from one "
        f"written by this one; it covers {sorted(fp)}")
    assert fp["verify_dataset.py"] == dataset_gate.sha256_file(
        ROOT / "verify_dataset.py"), "not the sha256 of the file on disk"
    # The twin must still be blind, or this test has stopped testing anything.
    assert "verify_dataset.py" not in _fingerprint_before_the_fix(ROOT), \
        "twin lost its bug; the test is dead"


def test_a_receipt_from_the_previous_gate_is_refused_not_honoured():
    """THE RED. A receipt issued by the gate BEFORE the four checks above,
    over a pair file the new gate calls a violation, presented after the gate
    changed. Nothing in it is false; it simply answers an older question."""
    root = _mirror()
    with _repointed_at(root):
        data, fname = _pair_file("")           # 0 rows: class 4's violation
        p = _receipt(data, fname, 0, 0, _fingerprint_before_the_fix(root))
        # ...and now the gate's judgement changes: the checks land.
        with open(root / "verify_dataset.py", "ab") as fh:
            fh.write(b"\n# the four checks above land here\n")

        msg = _refusal([p], data)
        assert msg is not None, (
            "a receipt written by the previous gate still grants permission: "
            "the empty file it certified is a violation now, and nothing in "
            "the receipt records which gate wrote it")
        assert "verify_dataset.py" in msg, msg
        assert "VERIFIER changed" in msg, msg
        # THE TWIN: under the old scope this receipt still matches exactly.
        recorded = json.loads(
            dataset_gate.receipt_path(data).read_text())["verifier"]
        assert _fingerprint_before_the_fix(root) == recorded, \
            "twin lost its bug; the test is dead"


def test_the_fingerprint_names_the_frozen_split_the_pairs_were_checked_against():
    """The partition check reads data/ruler_frozen.json at verification time.
    Which split it read is part of what the receipt means."""
    fp = dataset_gate.verifier_fingerprint()
    assert "data/ruler_frozen.json" in fp, (
        "the fingerprint does not cover the frozen split, so a receipt does not "
        f"say which partition its pairs were checked against; it covers {sorted(fp)}")
    assert fp["data/ruler_frozen.json"] == dataset_gate.sha256_file(
        ROOT / "data" / "ruler_frozen.json"), "not the sha256 of the file on disk"
    assert "data/ruler_frozen.json" not in _fingerprint_before_the_fix(ROOT), \
        "twin lost its bug; the test is dead"


def test_a_receipt_does_not_survive_the_frozen_split_moving():
    """THE SECOND RED. A receipt that was correct when written, presented after
    a re-freeze moved one of its training tasks into the eval set. The pairs did
    not change and neither did the verifier; what changed is the answer to 'may
    this task be trained on', which is the question the receipt was asked."""
    root = _mirror()
    with _repointed_at(root):
        data, fname = _pair_file(CLEAN_ROW)
        p = _receipt(data, fname, 1, 0, dataset_gate.verifier_fingerprint())
        assert _refusal([p], data) is None, \
            "the control failed: a freshly issued receipt must be honoured"

        frozen = root / "data" / "ruler_frozen.json"
        spec = json.loads(frozen.read_text(encoding="utf-8"))
        moved = sorted(spec["training_pool"])[0]
        spec["training_pool"] = [t for t in spec["training_pool"] if t != moved]
        spec["ruler"] = sorted(set(spec["ruler"]) | {moved})
        frozen.write_text(json.dumps(spec, indent=2), encoding="utf-8")

        msg = _refusal([p], data)
        assert msg is not None, (
            f"the receipt still grants permission after training-pool task "
            f"{moved!r} became a frozen RULER task; a pair labelled with it "
            f"would now be trained on under a receipt that never checked it "
            f"against this split")
        assert "ruler_frozen.json" in msg, msg
        # THE TWIN: the old scope cannot see a split change at all.
        recorded = json.loads(
            dataset_gate.receipt_path(data).read_text())["verifier"]
        old = _fingerprint_before_the_fix(root)
        assert all(old[k] == recorded[k] for k in old), \
            "twin lost its bug; the test is dead"


def test_a_receipt_written_under_the_current_fingerprint_is_honoured():
    """The cry-wolf side. Widening the fingerprint refuses STALE receipts; a
    receipt issued by the gate on disk now, over data that has not moved, must
    still grant permission -- otherwise the fix is a brick, not a check."""
    root = _mirror()
    with _repointed_at(root):
        data, fname = _pair_file(CLEAN_ROW)
        p = _receipt(data, fname, 1, 0, dataset_gate.verifier_fingerprint())
        assert _refusal([p], data) is None, \
            "a receipt written under the live fingerprint was refused"


# --- 6. a receipt fingerprinted after the verdict instead of before -------
@contextlib.contextmanager
def _gate_run(root: pathlib.Path, on_check):
    """Point the gate AND its DATA directory at `root`, with check() replaced.

    Both have to move together: main() reads the frozen split through
    verify_dataset.DATA and hashes it through dataset_gate.HERE, and the
    defect is precisely that those two reads happen at different times.
    Pointing them at one byte-copy keeps every read and the receipt inside
    the temp root.
    """
    saved = (dataset_gate.HERE, V.DATA, V.check)
    dataset_gate.HERE, V.DATA, V.check = root, root / "data", on_check
    try:
        yield
    finally:
        dataset_gate.HERE, V.DATA, V.check = saved


def _clean_check(pair):
    """check() with the subprocesses taken out. It stands in for the minutes
    a real run spends there, and returning CLEAN is deliberate: the sharpest
    form of this defect is a PASSING receipt naming bytes that never
    produced it."""
    return {"tid": (pair.get("meta") or {}).get("tid"), "src": pair["_src"],
            "row": pair["_row"], "ok": True, "why": "ok"}


def _mutating_check(edit):
    """_clean_check, editing a file the first time through -- a change
    arriving while the verification runs."""
    def run(pair):
        if not getattr(run, "done", False):
            run.done = True
            edit()
        return _clean_check(pair)
    return run


def _run_main() -> tuple[int | None, str | None]:
    """(return code, refusal message). Stdout is swallowed: main() prints a
    full report, and these tests are about what it WRITES."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            return V.main(), None
        except SystemExit as e:
            return None, str(e)


def _root_with_one_pair() -> pathlib.Path:
    root = _mirror()
    (root / "data" / "dpo_pairs.jsonl").write_text(
        CLEAN_ROW, encoding="utf-8", newline="")
    return root


def test_a_split_that_moves_mid_verification_leaves_no_receipt():
    """THE RED. The frozen split is read at the top of the run and used to
    decide whether each pair may be trained on; the fingerprint was taken at
    the bottom. Move the split inside that window -- here, so the pair's own
    task becomes a frozen RULER task -- and the receipt names the NEW bytes
    beside a verdict computed against the old ones, under which that pair is
    an eval-set contamination."""
    root = _root_with_one_pair()
    frozen = root / "data" / "ruler_frozen.json"
    before = dataset_gate.sha256_file(frozen)

    def move_the_pairs_task_into_the_eval_set():
        spec = json.loads(frozen.read_text(encoding="utf-8"))
        spec["ruler"] = sorted(set(spec["ruler"]) | {"atoi"})
        frozen.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    moved = _mutating_check(move_the_pairs_task_into_the_eval_set)
    with _gate_run(root, moved):
        _rc, msg = _run_main()
        rp = dataset_gate.receipt_path(root / "data")
        assert not rp.exists(), (
            "a receipt was written naming split "
            + json.loads(rp.read_text())["verifier"][
                "data/ruler_frozen.json"]
            + f", while the verdict was computed against {before}")
        assert msg is not None, "main() completed and wrote nothing?"
        assert "CHANGED while it ran" in msg, msg
        assert "data/ruler_frozen.json" in msg, msg
        # THE TWIN, in the only form this defect has one: the fingerprint
        # the old gate took at WRITE time. Recomputed here, after the move,
        # it names bytes this verification never read.
        after = dataset_gate.verifier_fingerprint()["data/ruler_frozen.json"]
        assert after != before, "twin lost its bug; the split did not move"
        assert after == dataset_gate.sha256_file(frozen)


def test_a_pair_file_that_changes_mid_verification_leaves_no_receipt():
    """The same window, one file over, so the guard is the window and not a
    special case for the split. load_pairs() reads the pair files at the top
    of the run and build_file_entries() hashed them at the bottom, so a pair
    appended in between lands in the receipt's sha256 without ever having
    been executed -- the receipt then certifies bytes it did not check."""
    root = _root_with_one_pair()
    pairs = root / "data" / "dpo_pairs.jsonl"
    before = dataset_gate.sha256_file(pairs)

    def append_a_pair_nothing_will_execute():
        with open(pairs, "a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps({"prompt": "q", "chosen": "c",
                                 "rejected": "r",
                                 "meta": {"tid": "atoi"}}) + "\n")

    with _gate_run(root, _mutating_check(append_a_pair_nothing_will_execute)):
        _rc, msg = _run_main()
        rp = dataset_gate.receipt_path(root / "data")
        assert not rp.exists(), (
            "a receipt was written over dpo_pairs.jsonl at sha256 "
            + json.loads(rp.read_text())["files"]["dpo_pairs.jsonl"]["sha256"]
            + f", while the one pair it executed came from {before}")
        assert msg is not None and "dpo_pairs.jsonl" in msg, msg
        assert dataset_gate.sha256_file(pairs) != before, \
            "twin lost its bug; the pair file did not actually change"


def test_a_file_appearing_or_vanishing_inside_the_window_is_drift():
    """The snapshot is taken BEFORE load_pairs(), so it enumerates the pair
    files from FILES rather than from what was read. A file that arrives or
    leaves inside the window is then a key only one of the two snapshots
    has, and it is reported rather than tolerated."""
    was = ({"forge.py": "a" * 64}, {"dpo_pairs.jsonl": "x" * 64})
    now = ({"forge.py": "a" * 64}, {"dpo_pairs.jsonl": "x" * 64,
                                    "repair_pairs.jsonl": "y" * 64})
    lines = V.input_drift(was, now)
    assert len(lines) == 1 and "repair_pairs.jsonl" in lines[0], lines
    assert "(absent)" in lines[0], lines[0]
    assert V.input_drift(now, was)[0].endswith("(absent)"), \
        V.input_drift(now, was)
    assert V.input_drift(was, was) == []


def test_an_undisturbed_run_still_writes_a_receipt_that_is_honoured():
    """The cry-wolf side, and the one that makes this a check rather than a
    brick. Nothing moves, the two snapshots agree, and the receipt is written
    exactly as before -- naming the split, the gate and the pair file it was
    verified against, and still granting permission to train."""
    root = _root_with_one_pair()
    with _gate_run(root, _clean_check):
        rc, msg = _run_main()
        assert msg is None, msg
        assert rc == 0, rc
        r = json.loads(dataset_gate.receipt_path(root / "data").read_text())
        assert r["verifier"] == dataset_gate.verifier_fingerprint(), \
            "the receipt does not name the files as they stand on disk"
        assert r["files"]["dpo_pairs.jsonl"]["violations"] == 0, r["files"]
        assert _refusal([root / "data" / "dpo_pairs.jsonl"],
                        root / "data") is None


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as e:
                fails.append(name); print(f"FAIL {name}: {e}")
            except Exception as e:                                # noqa: BLE001
                fails.append(name)
                print(f"FAIL {name}: raised {type(e).__name__}: {e}")
    print(f"\n{len(fails)} failed")
    raise SystemExit(1 if fails else 0)
