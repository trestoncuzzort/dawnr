"""The r12 data queue's embedded programs, run on fixtures the way the queue runs them.

`bash t/r12_data_queue.sh _py NAME | python3 - ARGS` from the repository root, so a
test here exercises the exact bytes the queue ships to the lab. Standard library only.
Sources behind the guards: gnu.org/software/parallel/parallel.html (admission, not
policing), luigi.readthedocs.io/en/stable/luigi_patterns.html (a step is done when its
sentinel says so), bazel.build/remote/caching (rows keyed by the content they graded),
docs.python.org/3/library/json.html (raw_decode and "Extra data").
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUEUE = HERE / "r12_data_queue.sh"
KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
CLEAN = "verified / refuted"


def program(name: str) -> str:
    return subprocess.run(["bash", str(QUEUE), "_py", name], check=True, capture_output=True, text=True).stdout


def run(name: str, *args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-", *args], input=program(name), capture_output=True, text=True,
                          cwd=str(cwd))


def run_with_stdin(name: str, data: str, *args: str) -> subprocess.CompletedProcess:
    """Programs that read facts on stdin get the program through a file instead."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(program(name))
    try:
        return subprocess.run([sys.executable, fh.name, *args], input=data, capture_output=True, text=True,
                              cwd=str(ROOT))
    finally:
        os.unlink(fh.name)


def facts(**over) -> str:
    base = {"nproc": 120, "load1": 8.0, "stopped": [], "orphans": [], "generating": [], "frozen_live": []}
    base.update(over)
    return json.dumps(base)


def table(rows: dict, cols=KERNELS) -> str:
    lines = ["# t cross-kernel agreement, test", "", "| task | " + " | ".join(cols) + " |",
             "|" + "---|" * (len(cols) + 1)]
    for name, cells in rows.items():
        lines.append("| " + " | ".join([name] + [cells.get(k, CLEAN) for k in cols]) + " |")
    return "\n".join(lines) + "\n"


TASK = {"t": 1, "name": "mbpp_5__f", "params": [{"name": "a", "type": "int"}],
        "returns": [{"name": "r", "type": "int"}], "requires": [], "ensures": [], "body": []}


class ScriptShape(unittest.TestCase):
    def test_bash_accepts_the_script_and_every_program_parses(self):
        subprocess.run(["bash", "-n", str(QUEUE)], check=True)
        for name in ("facts", "gate", "sentinel", "extract_check", "repair", "plan", "check_table", "merge",
                     "spec_verify", "dev_ids", "verify_dev", "status"):
            compile(program(name), name, "exec")

    def test_the_script_names_no_machine(self):
        import re
        text = QUEUE.read_text(encoding="utf-8").replace("user@host", "")
        self.assertIsNone(re.search(r"\b[a-z0-9_.-]+@[a-z0-9.-]+\.[a-z]{2,}\b|\b\d+\.\d+\.\d+\.\d+\b|/home/[a-z]", text))


class LiftStepTests(unittest.TestCase):
    """The recovered lift's step (lift-2026-09-26-recovered) does exactly what the lift's step does, on its
    own directories. Both step functions run here with the queue's helpers stubbed to print their
    arguments, under set -u, and the two traces must match once the one name is changed."""

    STUBS = r"""set -u
RD=t/out/r12-data; LAB=local; REPO=tup
refuse() { printf 'REFUSED %s\n' "$*"; exit 3; }
check_or_refuse() { printf 'check_or_refuse %s\n' "$*"; return 1; }
admit() { printf 'admit %s\n' "$*"; CELLS=4; }
store() { printf 'store %s\n' "$*"; }
fetch() { printf 'fetch %s\n' "$*"; }
lab() { printf 'lab %s\n' "$*"; }
lab_py() { printf 'lab_py %s\n' "$*"; }
mark_step() { printf 'mark_step %s\n' "$*"; }
default_work_dir() { printf '/dev/shm/tup-grade\n'; }
echo() { :; }
"""

    def trace(self, step: str, dirs: str) -> list[str]:
        import re
        text = QUEUE.read_text(encoding="utf-8")
        body = re.search(rf"^{step}\(\) {{\n.*?^}}\n", text, re.S | re.M)
        self.assertIsNotNone(body, f"no function {step} in the queue")
        # the step's grading line reads REMOTE_EV under set -u: the queue itself must assign it
        remote_ev = re.search(r"^REMOTE_EV=.*$", text, re.M)
        self.assertIsNotNone(remote_ev, "r12_data_queue.sh does not assign REMOTE_EV, which its lift steps read")
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / f"{dirs}.meta"
            (Path(tmp) / dirs).mkdir(parents=True)
            (meta / "staged").mkdir(parents=True)
            (meta / "lift-census.json").write_text("{}")
            script = self.STUBS + remote_ev.group(0) + "\n" + body.group(0) + f"{step}\n"
            r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, cwd=tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout.splitlines()

    def test_the_recovered_step_mirrors_the_lift_step_on_its_own_directories(self):
        import re
        lift = self.trace("step_lift_2026_09_26", "t/out/lifted-tasks-2026-09-26")
        recovered = self.trace("step_lift_2026_09_26_recovered", "t/out/lifted-tasks-2026-09-26-recovered")
        self.assertEqual(recovered, [re.sub(r"2026-09-26(?!-recovered)", "2026-09-26-recovered", line) for line in lift])
        self.assertTrue(any("lifter.py --dir t/out/lifted-tasks-2026-09-26-recovered.meta/staged" in line
                            for line in recovered))
        self.assertTrue(recovered[-1].startswith("mark_step lift-2026-09-26-recovered "))

    def test_the_recovered_step_is_dispatched_and_moves_files_only_through_the_helpers(self):
        import re
        text = QUEUE.read_text(encoding="utf-8")
        self.assertIn("lift-2026-09-26-recovered) step_lift_2026_09_26_recovered ;;", text)
        self.assertIn("bash t/r12_data_queue.sh lift-2026-09-26-recovered", text)
        body = re.search(r"^step_lift_2026_09_26_recovered\(\) \{\n.*?^\}\n", text, re.S | re.M).group(0)
        self.assertIsNone(re.search(r"\b(rsync|ssh|scp)\b|\$SSH", body))
        self.assertIn("default_work_dir", body)


class GateTests(unittest.TestCase):
    def decide(self, data, *args):
        r = run_with_stdin("gate", data, *args)
        return r.returncode, json.loads(r.stdout)

    def test_a_quiet_lab_admits_grading_with_the_headroom_in_cells(self):
        rc, out = self.decide(facts(), "--grading")
        self.assertEqual(rc, 0)
        self.assertEqual(out["cells"], 12)              # min(12, floor((84-8)/4)=19)

    def test_load_above_seventy_percent_refuses(self):
        rc, out = self.decide(facts(load1=85.0))
        self.assertEqual(rc, 3)
        self.assertIn("load", out["reasons"][0])

    def test_a_stopped_process_an_orphan_and_a_live_frozen_pid_each_refuse(self):
        for over in ({"stopped": [[1, "python3"]]}, {"orphans": [[2, "z3"]]}, {"frozen_live": [3]}):
            rc, out = self.decide(facts(**over))
            self.assertEqual(rc, 3, over)
            self.assertEqual(len(out["reasons"]), 1)

    def test_generation_blocks_grading_only(self):
        gen = facts(generating=[[9, "python3"]])
        self.assertEqual(self.decide(gen)[0], 0)
        self.assertEqual(self.decide(gen, "--grading")[0], 3)

    def test_zero_cells_refuses_grading_because_jobs_zero_means_every_core(self):
        rc, out = self.decide(facts(load1=82.0), "--grading")   # within 4 of the 84 line: floor(2/4)=0
        self.assertEqual(rc, 3)
        self.assertIn("--jobs 0", out["reasons"][0])
        self.assertEqual(self.decide(facts(load1=82.0))[0], 0)  # a light step may still run


class SentinelTests(unittest.TestCase):
    def test_done_matches_inputs_and_refuses_changed_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "in.txt"
            inp.write_text("a")
            args = ["s1", "--dir", f"{tmp}/done", "--inputs", str(inp)]
            gone = ["s1", "--dir", f"{tmp}/done", "--inputs", f"{tmp}/absent.txt"]
            self.assertEqual(run("sentinel", "check", *gone).returncode, 1)     # an absent output: not done
            self.assertEqual(run("sentinel", "write", *gone).returncode, 3)     # never recorded as done
            self.assertEqual(run("sentinel", "check", *args).returncode, 1)
            self.assertEqual(run("sentinel", "write", *args).returncode, 0)
            self.assertEqual(run("sentinel", "check", *args).returncode, 0)
            inp.write_text("b")
            r = run("sentinel", "check", *args)
            self.assertEqual(r.returncode, 3)
            self.assertIn("different inputs", r.stdout)
            self.assertEqual([p.name for p in (Path(tmp) / "done").iterdir()], ["s1.json"])

    def test_a_check_naming_fewer_paths_than_its_mark_reads_as_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp, out = Path(tmp) / "in.txt", Path(tmp) / "out.md"
            inp.write_text("a")
            out.write_text("table")
            both = ["s1", "--dir", f"{tmp}/done", "--inputs", str(inp), str(out)]
            self.assertEqual(run("sentinel", "write", *both).returncode, 0)
            self.assertEqual(run("sentinel", "check", *both).returncode, 0)
            self.assertEqual(run("sentinel", "check", "s1", "--dir", f"{tmp}/done", "--inputs", str(inp)).returncode, 3)

    def test_every_step_checks_the_same_paths_its_mark_records(self):
        """The sentinel digests every path it is given, so a check naming fewer paths than the mark
        wrote never matches, and a finished step refused the queue on resume as done with different
        inputs (found 2026-09-26 in chunk-, spec-, build-r12, build-r12v6 and the two lift steps).
        verifyVT in snowleopard/build (src/Build/Trace.hs) verifies exactly what recordVT stored."""
        import re
        import shlex
        text = QUEUE.read_text(encoding="utf-8")

        def calls(verb: str) -> dict[str, list[list[str]]]:
            found: dict[str, list[list[str]]] = {}
            for m in re.finditer(rf"\b{verb} (.+?)(?:; then|\s*\|\||$)", text, re.M):
                words = shlex.split(m.group(1))
                found.setdefault(words[0], []).append(words[1:])
            return found

        checks, marks = calls("check_or_refuse"), calls("mark_step")
        self.assertGreaterEqual(len(marks), 10)
        self.assertEqual(sorted(checks), sorted(marks), "a step is checked or marked under a name the other never uses")
        for step, marked in marks.items():
            self.assertEqual(checks[step], marked, f"{step}: the check names other paths than the mark records")


class RepairTests(unittest.TestCase):
    def record(self, tid, reply):
        return {"task_id": tid, "fn": "f", "model": "m", "digest": "d", "pool_version": "v1",
                "prompt_version": "v1", "options": {"temperature": 0, "seed": 1}, "messages": [],
                "reply": reply, "prompt_tokens": 1, "reply_tokens": 1, "eval_s": 0.0, "wall_s": 1.0,
                "done_reason": "stop"}

    def make(self, tmp, torn_ok=True):
        raw = Path(tmp) / "src" / "raw"
        raw.mkdir(parents=True)
        short = json.dumps(self.record(7, "short"), indent=1)
        longer = json.dumps(self.record(7, "a much longer reply " * 20), indent=1)
        (raw / "5.json").write_text(json.dumps(self.record(5, "fine"), indent=1))
        (raw / "7.json").write_text(short + longer[len(short):] if torn_ok else short + "garbage")
        return raw

    def test_a_torn_file_becomes_its_leading_record_and_the_source_is_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = self.make(tmp)
            before = {p.name: p.read_bytes() for p in raw.iterdir()}
            r = run("repair", "src", "dst", "--root", tmp, "--mode", "drop")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual({p.name: p.read_bytes() for p in raw.iterdir()}, before)
            dst = Path(tmp) / "dst" / "raw"
            self.assertEqual(sorted(p.name for p in dst.iterdir()), ["5.json"])   # drop mode omits it
            shutil.rmtree(Path(tmp) / "dst")
            # repair mode needs the pool for the prompt check; a record with empty messages cannot pass it,
            # so the refusal path is what a fixture without a pool exercises
            r = run("repair", "src", "dst", "--root", tmp, "--mode", "repair", "--pool", "v1")
            self.assertEqual(r.returncode, 3)
            self.assertIn("messages differ", r.stdout)
            self.assertFalse((Path(tmp) / "dst" / "raw").exists())

    def test_a_tail_that_is_not_a_record_end_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, torn_ok=False)
            r = run("repair", "src", "dst", "--root", tmp, "--mode", "drop")
            self.assertEqual(r.returncode, 3)
            self.assertIn("tail", r.stdout)


class TableTests(unittest.TestCase):
    def test_check_table_refuses_a_row_mismatch_a_missing_column_and_a_dead_kernel(self):
        with tempfile.TemporaryDirectory() as tmp:
            t, m = Path(tmp) / "k.md", Path(tmp) / "m.json"
            m.write_text(json.dumps({"names": ["a", "b"]}))
            t.write_text(table({"a": {}, "b": {"spark": "timeout / refuted"}}))
            r = run("check_table", str(t), str(m))
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(json.loads(r.stdout)["timeouts"], 1)
            t.write_text(table({"a": {}}))
            self.assertEqual(run("check_table", str(t), str(m)).returncode, 3)
            t.write_text(table({"a": {}, "b": {}}, cols=KERNELS[:6]))
            self.assertEqual(run("check_table", str(t), str(m)).returncode, 3)
            t.write_text(table({"a": {"lean": "malformed / malformed"}, "b": {"lean": "MALFORMED / x"}}))
            r = run("check_table", str(t), str(m))
            self.assertEqual(r.returncode, 3)
            self.assertIn("malformed", json.loads(r.stdout)["problems"][0])


class DevIdsFileTests(unittest.TestCase):
    """The committed t/r12-dev-ids.json, checked against its own recorded rule."""

    def setUp(self):
        self.path = HERE / "r12-dev-ids.json"
        if not self.path.exists():
            self.skipTest("t/r12-dev-ids.json not built yet (bash t/r12_data_queue.sh dev-ids)")
        self.dev = json.loads(self.path.read_text(encoding="utf-8"))

    def test_one_hundred_distinct_train_ids_below_the_humaneval_base(self):
        ids = self.dev["dev_ids"]
        self.assertEqual(len(ids), self.dev["n"])
        self.assertEqual(len(set(ids)), len(ids))
        split = json.loads((HERE / "out" / "loop" / "split-v5.json").read_text())
        train = {int(i) for i in split["train_ids"]}
        self.assertTrue(all(i in train and i < 100000 for i in ids))
        self.assertEqual(hashlib.sha256((HERE / "out" / "loop" / "split-v5.json").read_bytes()).hexdigest(),
                         self.dev["inputs"]["split_sha256"])

    def test_no_dev_id_is_on_the_decontamination_list(self):
        # the merged policy: the hand list of 2026-09-21 plus the behavioural
        # duplicates of 2026-09-25, as loop_filter.decontamination() reads them
        import loop_filter
        merged = loop_filter.decontamination()
        listed = set(merged.exclude_train_ids) | set(merged.overlap_eval_ids)
        self.assertFalse(listed & set(self.dev["dev_ids"]),
                         f"dev ids on the merged exclusion list: {sorted(listed & set(self.dev['dev_ids']))}; "
                         f"regenerate t/r12-dev-ids.json (bash t/r12_data_queue.sh dev-ids)")

    def test_the_choice_recomputes_from_the_recorded_eligible_list_and_salt(self):
        ordered = sorted(self.dev["eligible_in_hash_order"],
                         key=lambda t: hashlib.sha256(f"{self.dev['salt']}:{t}".encode()).hexdigest())
        self.assertEqual(ordered, self.dev["eligible_in_hash_order"])
        self.assertEqual(sorted(ordered[:self.dev["n"]]), self.dev["dev_ids"])

    def test_verify_dev_refuses_a_corpus_naming_a_dev_id_and_passes_a_clean_one(self):
        tid = self.dev["dev_ids"][0]
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.txt"
            bad.write_text(f"t 1\ntask dafny_synthesis_task_id_{tid}__f(a: int) returns (r: int)\n{{\n}}\n")
            r = run("verify_dev", str(bad), "--dev", str(self.path))
            self.assertEqual(r.returncode, 3)
            self.assertIn("REFUSED", r.stdout)
            good = Path(tmp) / "good.txt"
            good.write_text("t 1\ntask clover_thing__f(a: int) returns (r: int)\n{\n}\n")
            self.assertEqual(run("verify_dev", str(good), "--dev", str(self.path)).returncode, 0)


class LetLiftStepTests(unittest.TestCase):
    """lift-2026-09-26-let: the stems the 2026-09-26 lift refused as let-expressions,
    through t/lift_corpora.py's gates again (2026-09-26)."""

    def test_its_programs_parse_and_the_step_is_dispatched(self):
        for name in ("refused_stems", "lift_corpora_only"):
            compile(program(name), name, "exec")
        text = QUEUE.read_text(encoding="utf-8")
        self.assertIn("lift-2026-09-26-let) step_lift_2026_09_26_let ;;", text)
        body = text.split("step_lift_2026_09_26_let() {", 1)[1].split("\n}\n", 1)[0]
        # the queue runs under set -u and only t/grade_lab.sh sets REMOTE_EV
        self.assertNotIn("$REMOTE_EV", body)
        self.assertIn("${REMOTE_EV:-", body)
        for helper in ("store ", "fetch ", "lab ", "default_work_dir"):
            self.assertIn(helper, body)
        self.assertNotIn("rsync", body)
        self.assertNotIn("ssh", body)

    def test_refused_stems_lists_the_files_refused_for_one_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = Path(tmp) / "lift"
            records.mkdir()
            for stem, reason in (("vericoding_DA0002", "let-expression"), ("vericoding_DA0001", "let-expression"),
                                 ("vericoding_DA0003", "higher-order"), ("humaneval_dafny_004_x", None)):
                refusal = {"reason": reason, "token": "var", "line": 3, "stage": "parse"} if reason else None
                (records / f"{stem}.outcome.json").write_text(json.dumps(
                    {"methods": [], "parse_refusal": refusal, "resolve_refusal": None, "source_path": stem}))
            out = Path(tmp) / "stems.txt"
            r = run("refused_stems", str(records), "let-expression", "--out", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(out.read_text().split(), ["vericoding_DA0001", "vericoding_DA0002"])

    def test_lift_corpora_only_refuses_without_a_stem_list(self):
        r = run("lift_corpora_only", "--out", "x", "--split", "y")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--only-stems is required", r.stderr)


if __name__ == "__main__":
    unittest.main()
