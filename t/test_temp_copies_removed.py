"""A private copy a check makes in the temporary folder must not outlive the check (PRIVACY.md, the row on copies of a
program being checked). Each path below runs with the temporary folder pointed at an empty folder and asserts the folder
is empty again after a check that succeeds, after one that fails, and after one that raises. A check killed with SIGKILL
cannot clean up; the next check removes its copy (t/check_scratch.py, tested in t/test_check_scratch.py)."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))


@pytest.fixture
def watch(tmp_path, monkeypatch):
    """An empty folder the tempfile module uses as the temporary folder; inputs live beside it, not in it."""
    folder = tmp_path / "watched"
    folder.mkdir()
    (tmp_path / "inputs").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    monkeypatch.setenv("TMPDIR", str(folder))
    return folder


def left(folder):
    """What a check left: the names in the temporary folder, plus the names inside dawnr's own scratch parent there.
    The parent itself is made once and kept, so it is not counted; a killed check's folders are removed by a sweep
    (t/test_check_scratch.py)."""
    names = []
    for p in folder.iterdir():
        if p.name.startswith("dawnr-checks-") and p.is_dir() and not p.is_symlink():
            names += [f"{p.name}/{q.name}" for q in p.iterdir()]
        else:
            names.append(p.name)
    return sorted(names)


def _outcomes(run_one):
    """Run `run_one(mode)` for mode in success, failure, exception; return {mode: (error name or None)}."""
    got = {}
    for mode in ("success", "failure", "exception"):
        try:
            run_one(mode)
            got[mode] = None
        except Exception as e:                                  # noqa: BLE001
            got[mode] = type(e).__name__
    return got


# --- the Dafny adapter -------------------------------------------------------------------------------------------

def _dafny_run(watch_dir, tmp_path, mode):
    import t.verifiers.dafny as d
    src = tmp_path / "inputs" / "task.dfy"
    src.write_text("method M() ensures true {}\n", encoding="utf-8")
    done = {"success": ("Dafny program verifier finished with 1 verified, 0 errors\n", 0),
            "failure": ("Dafny program verifier finished with 0 verified, 1 error\n", 4)}

    def kernel(argv, **kwargs):
        assert Path(argv[-1]).exists()
        if mode == "exception":
            raise RuntimeError("the prover could not be run")
        out, rc = done[mode]
        return subprocess.CompletedProcess(argv, rc, out, "")

    with patch.object(d, "DAFNY", "dafny"), patch.object(d, "_solver_args", return_value=[]), \
            patch.object(d, "version", return_value="dafny test"), patch.object(d, "run_tree", side_effect=kernel):
        return d.verify(src)


@pytest.mark.parametrize("mode", ["success", "failure", "exception"])
def test_dafny_adapter_removes_the_copy_it_hands_dafny(watch, tmp_path, mode):
    try:
        _dafny_run(watch, tmp_path, mode)
    except RuntimeError:
        assert mode == "exception"
    assert left(watch) == []


def test_dafny_adapter_removes_the_copy_after_a_wall_timeout(watch, tmp_path):
    import t.verifiers.dafny as d
    src = tmp_path / "inputs" / "task.dfy"
    src.write_text("method M() ensures true {}\n", encoding="utf-8")

    def kernel(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)

    with patch.object(d, "DAFNY", "dafny"), patch.object(d, "_solver_args", return_value=[]), \
            patch.object(d, "version", return_value="dafny test"), patch.object(d, "run_tree", side_effect=kernel):
        result = d.verify(src)
    assert result.outcome == d.Outcome.TIMEOUT
    assert left(watch) == []


def test_dafny_adapter_with_the_real_dafny_leaves_none_of_its_copies(watch, tmp_path):
    import t.verifiers.dafny as d
    if not d.DAFNY:
        pytest.skip("dafny is not installed (set T_DAFNY)")
    src = tmp_path / "inputs" / "task.dfy"
    src.write_text("method M() ensures true {}\n", encoding="utf-8")
    result = d.verify(src)
    assert result.ok
    # dafny's own runtime may make its own folder; the adapter's copies are in its `t_dafny-...` scratch folder
    assert [n for n in left(watch) if n.startswith("t_")] == []


# --- replaying an observation certificate ------------------------------------------------------------------------

REAL = "t 1\ntask q(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{ r := true; }"
TWIN = REAL.replace("r := true;", "r := false;")


def _obs(tmp_path):
    import obs_certificate as oc
    import lower_dafny
    import run_par
    pair = tmp_path / "inputs" / "p.json"
    witness = {"_kind": "value", "_ens": True, "n": 0}
    pair.write_text(json.dumps({"id": oc._pair_id(REAL, TWIN), "task": "q", "program": REAL, "twin": TWIN,
                                "witness": witness}))
    present = patch.object(run_par, "probe_backends", return_value=([], [("dafny", lower_dafny.lower, "dfy")]))
    return oc, pair, present


def _mint_fixture(oc, pair, present, tmp_path, cert_path):
    """Mint a certificate to replay, with the temporary folder elsewhere so the check under test starts from empty."""
    elsewhere = tmp_path / "inputs" / "mint-scratch"
    elsewhere.mkdir(exist_ok=True)
    with present, patch.object(tempfile, "tempdir", str(elsewhere)):
        oc.mint(str(pair), "dafny", str(cert_path), verify_override=_stub("success"))


def _stub(mode):
    import verifiers

    def vstub(path):
        assert Path(path).exists()
        if mode == "exception":
            raise RuntimeError("the prover could not be run")
        text = Path(path).read_text()
        outcome = verifiers.Outcome.REFUTED if "false" in text else verifiers.Outcome.VERIFIED
        return (outcome, mode != "failure")
    return vstub


@pytest.mark.parametrize("mode", ["success", "failure", "exception"])
def test_minting_an_observation_certificate_removes_its_folder(watch, tmp_path, mode):
    oc, pair, present = _obs(tmp_path)
    with present:
        try:
            oc.mint(str(pair), "dafny", str(tmp_path / "inputs" / "c.json"), verify_override=_stub(mode))
        except RuntimeError:
            assert mode == "exception"
    assert left(watch) == []


@pytest.mark.parametrize("mode", ["success", "failure", "exception"])
def test_replaying_an_observation_certificate_removes_its_folder(watch, tmp_path, mode):
    oc, pair, present = _obs(tmp_path)
    cert_path = tmp_path / "inputs" / "c.json"
    _mint_fixture(oc, pair, present, tmp_path, cert_path)
    cert = json.loads(cert_path.read_text())
    with present:
        try:
            oc.check(cert, verify_override=_stub(mode))
        except RuntimeError:
            assert mode == "exception"
    assert left(watch) == []


def test_replaying_with_the_real_adapter_path_removes_its_folder_when_the_prover_raises(watch, tmp_path):
    import verifiers
    oc, pair, present = _obs(tmp_path)
    cert_path = tmp_path / "inputs" / "c.json"
    _mint_fixture(oc, pair, present, tmp_path, cert_path)
    cert = json.loads(cert_path.read_text())
    with present, patch.object(verifiers, "cell_pair", side_effect=RuntimeError("no prover")):
        try:
            oc.check(cert)
        except RuntimeError:
            pass
    assert left(watch) == []


def test_lowering_that_raises_removes_the_certificate_folder(watch, tmp_path):
    oc, pair, present = _obs(tmp_path)
    cert_path = tmp_path / "inputs" / "c.json"
    _mint_fixture(oc, pair, present, tmp_path, cert_path)
    import lower_dafny
    import run_par
    boom = patch.object(run_par, "probe_backends",
                        return_value=([], [("dafny", lambda *a, **k: (_ for _ in ()).throw(ValueError("x")), "dfy")]))
    with boom:
        try:
            oc.check(json.loads(cert_path.read_text()), verify_override=_stub("success"))
        except ValueError:
            pass
    assert lower_dafny and left(watch) == []


def test_the_certificate_self_test_removes_its_folder(watch, capsys):
    import obs_certificate as oc
    import lower_dafny
    import run_par
    with patch.object(run_par, "probe_backends", return_value=([], [("dafny", lower_dafny.lower, "dfy")])):
        oc.self_test()
    assert left(watch) == []


# --- the direct-body certificate, the audit and the two run scripts --------------------------------------------

def _kernel_verdict(mode):
    def verdict(task, body, kernel, path):
        Path(path).write_text("lowered program\n", encoding="utf-8")
        if mode == "exception":
            raise RuntimeError("the prover could not be run")
        return "verified" if mode == "success" else "refuted"
    return verdict


@pytest.mark.parametrize("mode", ["success", "failure", "exception"])
def test_direct_body_adjudication_removes_its_folder(watch, mode):
    import audit
    import db_certificate
    with patch.object(audit, "_kernel_verdict", side_effect=_kernel_verdict(mode)):
        try:
            db_certificate._default_adjudicate({"name": "q"}, [], "dafny")
        except RuntimeError:
            assert mode == "exception"
    assert left(watch) == []


@pytest.mark.parametrize("mode", ["success", "failure", "exception"])
def test_audit_removes_its_kernel_copies_when_it_was_given_no_folder(watch, tmp_path, mode):
    import audit
    import tasks_io
    task = {"name": "q", "body": []}
    survivors = [{"op": "x", "body": [], "witness": {}}]
    with patch.object(tasks_io, "load_task", return_value=task), \
            patch.object(audit, "classify", return_value={"name": "q", "status": "ok", "survivors": survivors,
                                                         "mutants": 1, "killed": 0, "same": 0, "diverges": 0}), \
            patch.object(audit, "_changed_line", return_value=""), \
            patch.object(audit.harness, "witness", return_value="w"), \
            patch.object(audit, "_kernel_verdict", side_effect=_kernel_verdict(mode)):
        try:
            audit.audit_file(str(tmp_path / "inputs" / "q.t"), kernel="dafny")
        except RuntimeError:
            assert mode == "exception"
    assert left(watch) == []


def test_audit_keeps_the_folder_it_was_given(watch, tmp_path):
    import audit
    import tasks_io
    given = tmp_path / "inputs" / "given"
    with patch.object(tasks_io, "load_task", return_value={"name": "q", "body": []}), \
            patch.object(audit, "classify", return_value={"name": "q", "status": "ok", "survivors": [],
                                                         "mutants": 1, "killed": 1, "same": 0, "diverges": 0}), \
            patch.object(audit, "_kernel_verdict", side_effect=_kernel_verdict("success")):
        audit.audit_file(str(tmp_path / "inputs" / "q.t"), kernel="dafny", out_dir=str(given))
    assert len(list(given.iterdir())) == 1


_CELL_DRIVER = r'''
import sys
from pathlib import Path
from unittest.mock import patch
import audit, tasks_io
mode = sys.argv[1]
def verdict(task, body, kernel, path):
    Path(path).write_text("lowered program\n", encoding="utf-8")
    if mode == "exception":
        raise RuntimeError("the prover could not be run")
    return "verified" if mode == "success" else "refuted"
task = {"name": "q", "body": []}
with patch.object(tasks_io, "load_task", return_value=task), patch.object(audit, "_kernel_verdict", verdict):
    if sys.argv[2] == "e1":
        import e1_full_adjudicate as m
        rec = m._cell(("q.t", "REAL", None, "dafny", m.canon(task), "cfg"))
        print(rec["state"])
    else:
        import e2_cvc5 as m
        rec = m._cell_cvc5(("q.t", "REAL", None))
        print(rec["cvc5_state"])
'''


@pytest.mark.parametrize("script", ["e1", "e2"])
@pytest.mark.parametrize("mode", ["success", "failure", "exception"])
def test_run_scripts_remove_the_folder_of_each_cell(watch, tmp_path, script, mode):
    cwd = tmp_path / "inputs"                                   # e1_full_adjudicate makes ./out at import
    env = dict(os.environ, TMPDIR=str(watch), PYTHONPATH=str(HERE), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-c", _CELL_DRIVER, mode, script], cwd=cwd, env=env,
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert left(watch) == []


# --- the lifter ----------------------------------------------------------------------------------------------------

def _lift(tmp_path, mode, out_dir=None):
    import lifter as l
    scratch_seen = []

    def check(task, method, closure, record, scratch, timeout_s, callees=()):
        scratch = Path(scratch)
        scratch_seen.append(scratch)
        scratch.write_text("checker\n", encoding="utf-8")
        scratch.with_name(scratch.stem + ".check.dfy").write_text("checker\n", encoding="utf-8")
        scratch.with_name(scratch.stem + ".diff.dfy").write_text("diff\n", encoding="utf-8")
        if mode == "exception":
            raise KeyboardInterrupt
        if mode == "failure":
            return SimpleNamespace(refusal=l.Refusal(reason="lift-check-failed", token="x", line=1, stage="check"),
                                   record=record, interp_points=0, interp_first_value=None)
        return SimpleNamespace(refusal=None, record=record, interp_points=0, interp_first_value=None)

    source = tmp_path / "inputs" / "m.dfy"
    source.write_text("method M() {}\n", encoding="utf-8")
    method = SimpleNamespace(name="M", line=1)
    record = l._record_from_dict({"source_path": str(source), "method": "M", "rprint_sha256": "0" * 64})
    rewritten = SimpleNamespace(task={"name": "M"}, record=record, refusal=None, callees=())
    with patch.object(l.lift_resolve, "resolve", return_value=SimpleNamespace(refusal=None, rprint_text="r")), \
            patch.object(l.lift_parse, "parse", return_value=object()), \
            patch.object(l.lift_parse, "gradable_methods", return_value=[method]), \
            patch.object(l.lift_resolve, "check_against_source", return_value=([], None)), \
            patch.object(l.lift_classify, "classify", return_value=SimpleNamespace(closure=())), \
            patch.object(l.lift_rewrite, "rewrite", return_value=rewritten), \
            patch.object(l.lift_check, "check", side_effect=check):
        return l.lift_file(source, out_dir=out_dir), scratch_seen


@pytest.mark.parametrize("mode", ["success", "failure", "exception"])
def test_lifter_removes_its_scratch_checker_files_when_given_no_out_folder(watch, tmp_path, mode):
    try:
        _, seen = _lift(tmp_path, mode)
    except KeyboardInterrupt:
        assert mode == "exception"
    assert left(watch) == []


def test_lifter_keeps_the_files_it_writes_into_a_given_out_folder(watch, tmp_path):
    out = tmp_path / "inputs" / "out"
    _, seen = _lift(tmp_path, "success", out_dir=out)
    assert seen and seen[0].parent == out
    assert (out / "m.M.check.dfy").exists()
    assert left(watch) == []


# --- the sandbox ----------------------------------------------------------------------------------------------------

def test_sandbox_session_that_fails_to_start_removes_its_folder_at_once(watch):
    import py_sandbox
    held = []
    with patch.object(py_sandbox, "available", return_value=True), \
            patch.object(py_sandbox.Session, "_start", side_effect=py_sandbox.LoadError("did not start")):
        try:
            py_sandbox.Session("def f(x):\n    return x\n", "f")
        except py_sandbox.LoadError as e:
            held.append(e)                                      # the error holds the half-built session alive
        assert left(watch) == []


def test_sandbox_session_removes_its_folder_when_closed(watch):
    import py_sandbox
    with patch.object(py_sandbox, "available", return_value=True), \
            patch.object(py_sandbox.Session, "_start", return_value=None):
        s = py_sandbox.Session("def f(x):\n    return x\n", "f")
        assert left(watch) != []
        s.close()
    assert left(watch) == []


# --- the equivalence checkers' command lines --------------------------------------------------------------------

def _run_cli(script, argv, watch, monkeypatch):
    import runpy
    monkeypatch.setattr(sys, "argv", [script] + argv)
    refused = subprocess.CompletedProcess([], 1, "", "error: not run\n")
    with patch.object(subprocess, "run", return_value=refused):
        runpy.run_path(str(HERE / script), run_name="__main__")


def test_lean_equivalence_check_without_work_folder_leaves_no_file(watch, tmp_path, monkeypatch, capsys):
    import test_lift_lean as tl
    src = tl.prepost("n ≥ 1", "(n : Int)", "n + 1", "result = n + 1")
    task = {"t": 1, "name": "solve", "params": [{"name": "n", "type": "int"}],
            "returns": [{"name": "result", "type": "int"}],
            "requires": [{"op": ">=", "args": [{"var": "n"}, {"int": 1}]}],
            "ensures": [{"op": "==", "args": [{"var": "result"}, {"op": "+", "args": [{"var": "n"}, {"int": 1}]}]}],
            "body": [{"assign": ["result", {"op": "+", "args": [{"var": "n"}, {"int": 1}]}]}]}
    (tmp_path / "inputs" / "s.lean").write_text(src, encoding="utf-8")
    (tmp_path / "inputs" / "s.json").write_text(json.dumps(task), encoding="utf-8")
    _run_cli("lift_check_lean.py", [str(tmp_path / "inputs" / "s.lean"), str(tmp_path / "inputs" / "s.json")],
             watch, monkeypatch)
    assert "verdict" in capsys.readouterr().out
    assert left(watch) == []


def test_verus_equivalence_check_without_work_folder_leaves_no_file(watch, tmp_path, monkeypatch, capsys):
    import test_lift_verus as tv
    (tmp_path / "inputs" / "s.rs").write_text(tv.Harness.SRC, encoding="utf-8")
    (tmp_path / "inputs" / "s.json").write_text(json.dumps(tv.Harness.TASK), encoding="utf-8")
    _run_cli("lift_check_verus.py", [str(tmp_path / "inputs" / "s.rs"), str(tmp_path / "inputs" / "s.json")],
             watch, monkeypatch)
    assert "verdict" in capsys.readouterr().out
    assert left(watch) == []


def test_equivalence_check_keeps_a_work_folder_it_was_given(watch, tmp_path, monkeypatch, capsys):
    import test_lift_verus as tv
    (tmp_path / "inputs" / "s.rs").write_text(tv.Harness.SRC, encoding="utf-8")
    (tmp_path / "inputs" / "s.json").write_text(json.dumps(tv.Harness.TASK), encoding="utf-8")
    work = tmp_path / "inputs" / "work"
    _run_cli("lift_check_verus.py", [str(tmp_path / "inputs" / "s.rs"), str(tmp_path / "inputs" / "s.json"),
                                     "--work", str(work)], watch, monkeypatch)
    assert [p.name for p in work.iterdir()] == ["s_eq.rs"]
    assert left(watch) == []


# --- the self-checks of the certificate tools -------------------------------------------------------------------------

@pytest.mark.parametrize("module,function", [
    ("e1_pairs_aggregate", "control"), ("e1_pairs_aggregate", "pipeline_control"),
    ("e1_batch_cert", "control"), ("db_batch_cert", "control"), ("e1_pairs_gate2", "cmd_control")])
def test_certificate_self_checks_remove_their_folders(watch, module, function, capsys, monkeypatch):
    import importlib
    import lower_dafny
    import run_par
    m = importlib.import_module(module)
    monkeypatch.setattr(run_par, "probe_backends", lambda: ([], [("dafny", lower_dafny.lower, "dfy")]))
    fn = getattr(m, function)
    fn(None) if function == "cmd_control" else fn()
    assert left(watch) == []
