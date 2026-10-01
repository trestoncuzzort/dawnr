#!/usr/bin/env python3
"""t/rl_reward.py -- the tiered reward for reinforcement learning on locallm (2026-09-26).

The reward is the project's own grader, called one answer at a time; nothing
here re-implements a check. An answer walks the same road a held-out answer
does (t/spec_experiment.py extract_tag, cmd_tests; t/run_par.py; t/spec_check.py)
and its reward is the furthest tier it reaches:

    tier        reward  what it takes
    none         0.00   no t block, or the block does not parse
    parses       0.05   surface.parse accepts it, check_wf does not
    typed        0.10   well formed: check_wf accepts it (t's type check)
    tests        0.50   every one of the problem's own assertions passes in t's interpreter,
                        and no drawn input separates it from the problem's reference solution
    proved-weak  0.75   tests, and Dafny reads `verified / refuted` (real proved, twin refuted),
                        and the specification is not contradicted by the problem's own
                        solution or its own examples, and no lazy program satisfies it; but
                        a wrong output (a mutation of the right one) also satisfies it
    proved       1.00   the same with a specification no mutated output satisfies

The drawn-input tests and the proved-weak tier were added after reading 99
answers by hand (the inspection gate, t/RL-DESIGN-2026-09-26.md): without them
a wrong program that the problem's three assertions do not separate scored like
a right one, and a proof of an incomplete specification scored like a full one.

Composite, graded rewards follow the rule-based reward of DeepSeek-R1
(arXiv:2501.12948: an accuracy reward and a format reward, both from rules, no
neural reward model, because a learned one is hacked), with the format part
split so a malformed answer and a well-formed wrong answer score differently.
Group-relative advantages (GRPO, arXiv:2402.03300 section 4.1.2) only need the
order of rewards inside a group, so the numbers matter less than the ordering.

The top tier asks for more than a proof on purpose: this project measured that
every proof gate admits a wrong answer whose specification the model wrote
itself about 97 percent of the time (t/spec_check.py docstring, the ablation of
2026-09-17), so a reward of "Dafny verified" alone would pay for a proved
program that answers a different question. The specification checks are the
project's own (spec_check.check_task, check_points, exploit) and run on the CPU
in this process.

In the training loop only Dafny is asked (the fastest kernel); the seven are
for evaluation. Measured over the 12 r11/r9 locallm answer tables graded in all
seven kernels (3,066 rows): a row that is `verified / refuted` in Dafny is so in
all seven 2,210 times of 2,260 (97.8 percent), and no row is clean in all seven
without Dafny (0 of 806).

Rewards are cached by answer hash: sha256 of the task id and the extracted t
block, so an answer sampled twice is graded once (and run_par.py's own verdict
cache sits under that on the proving machine).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loop_filter                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

TIERS = {"none": 0.0, "parses": 0.05, "typed": 0.10, "tests": 0.50, "proved-weak": 0.75, "proved": 1.0}
ORDER = list(TIERS)
PROOF_KERNEL = "dafny"
CLEAN = "verified / refuted"
SPEC_DRAWS = 50
DRAWN_TESTS = 50
# Bumped whenever local_signals changes what it measures: a cached row of another
# version is re-graded (its proof is cheap to redo, run_par caches verdicts).
REWARD_VERSION = 3
# 3 (2026-10-01): `weak` is the gate's own rule, spec_check.complete() is False (both mutant families,
# near outputs and other inputs' answers, rejected at least 60% of the time: SAFE arXiv:2410.15756), where
# version 2 read spec_check's `weak` (any near-output mutant accepted: stricter on that family, blind to the
# other). The top tier now pays what the gate counts. The header promotion of spec_experiment.extract_tag
# is available, so a reward grades an answer as its measurement does.
SPLIT = HERE / "out" / "loop" / "split-v5.json"


# ----------------------------------------------------------------- prompts --

def rl_prompt_ids(split_path: Path = SPLIT, pool: dict | None = None,
                  dev_ids_path: Path = HERE / "r12-dev-ids.json") -> list[int]:
    """The problems RL may ask: the split's train ids, minus its eval ids, the
    r12 dev ids (whichever split they were drawn from), and every id the
    decontamination policy excludes from training; only ids the pool holds with
    at least one test point. Refuses if anything held out slips through."""
    split = json.loads(Path(split_path).read_text(encoding="utf-8"))
    pool = pool if pool is not None else se.pool(split.get("pool", "v1"))
    eval_ids = {int(i) for i in split["eval_ids"]}
    dev = loop_filter.r12_dev_ids(dev_ids_path)            # no split_path: every dev id, always
    policy = loop_filter.decontamination()
    blocked = eval_ids | set(dev) | set(policy.exclude_train_ids) | set(policy.overlap_eval_ids)
    ids = sorted(int(i) for i in split["train_ids"]
                 if int(i) not in blocked and int(i) in pool and pool[int(i)].get("points"))
    leak = set(ids) & blocked
    if leak:
        raise SystemExit(f"rl_prompt_ids: held-out ids in the prompt set: {sorted(leak)[:5]}")
    return ids


# ------------------------------------------------------------------ keying --

def answer_key(task_id: int, reply: str) -> str:
    """sha256 over the task id and the t block the grader would read."""
    block = se.find_block(reply)
    text = f"{int(task_id)}\n{block if block is not None else '<no-block>'}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def proof_name(task_id: int, fn: str, key: str) -> str:
    """A unique task name per answer, in the family extract_tag names, so
    loop_filter.problem_id still reads the pool id from it."""
    tid = int(task_id)
    prefix = (f"apps_{tid - se.APPS_BASE}" if tid >= se.APPS_BASE else
              f"he_{tid - se.HUMANEVAL_BASE}" if tid >= se.HUMANEVAL_BASE else f"mbpp_{tid}")
    name = f"{prefix}__{fn}__rl{key[:10]}"
    return name if se.fuzz_lower.NAME_RE.match(name) else f"{prefix}__rl{key[:10]}"


# ------------------------------------------------------------- CPU signals --

def overall_verdict(verdicts: list[str]) -> str:
    """spec_experiment.cmd_tests's reading of one task's point verdicts."""
    if verdicts and all(v == "pass" for v in verdicts):
        return "pass"
    if any(v in ("arity", "type") for v in verdicts):
        return "signature"
    if any(v in ("fail", "crash") for v in verdicts):
        return "fail"
    if any(v == "requires-excluded" for v in verdicts):
        return "requires-excluded"
    return "undefined"


def local_signals(task_id: int, reply: str, entry: dict, spec_seed: int = 1, promote_header: bool = False) -> dict:
    """Everything the CPU can say about one reply: extraction stage, tests, and
    (for a test-passing answer) the three specification checks. The t task is
    returned under "task" when the answer is well formed, for the prover."""
    import spec_check                                         # imports the interpreter stack
    out: dict = {"task_id": int(task_id)}
    block = se.find_block(reply)
    if block is None:
        return {**out, "stage": "no-block"}
    try:
        task = surface.parse(block)
    except Exception as e:                                      # noqa: BLE001  (extract_tag does the same)
        return {**out, "stage": "parse", "why": f"{type(e).__name__}: {e}"[:200]}
    task = se.rename_task(task, proof_name(task_id, entry["fn"], answer_key(task_id, reply)))
    try:
        errs = se.fuzz_lower.check_wf(task)
    except Exception as e:                                      # noqa: BLE001
        errs = [f"check_wf raised {type(e).__name__}: {e}"[:200]]
    if errs and promote_header and task.get("t") == 0:
        # spec_experiment.extract_tag --promote-header: `t 0` stated over a v1 form is the same program under
        # `t 1` (SPEC.md, v1 is a strict superset of v0); the promoted program is checked in full.
        promoted = dict(task, t=1)
        try:
            errs1 = se.fuzz_lower.check_wf(promoted)
        except Exception as e:                                  # noqa: BLE001
            errs1 = [f"check_wf raised {type(e).__name__}: {e}"[:200]]
        if not errs1:
            task, errs = promoted, []
            out["header_promoted"] = True
    if errs:
        return {**out, "stage": "wf", "why": "; ".join(errs)[:300]}
    out["stage"] = "task"
    out["task"] = task
    points = [se.run_point(task, p) for p in entry["points"]]
    verdicts = [p["verdict"] for p in points]
    out["tests"] = overall_verdict(verdicts)
    out["points_passed"] = sum(v == "pass" for v in verdicts)
    out["points"] = len(verdicts)
    if out["tests"] == "pass":
        out["drawn"] = drawn_tests(task, entry, DRAWN_TESTS, random.Random(spec_seed))
        spec = spec_check.check_task(task, entry, SPEC_DRAWS, random.Random(spec_seed))
        out["spec"] = {k: spec[k] for k in ("status", "draws", "completeness", "cross_completeness") if k in spec}
        out["spec"]["weak"] = spec_check.complete(spec) is False
        out["spec_points"] = spec_check.check_points(task, entry)
        out["exploit"] = spec_check.exploit(task, entry).get("exploited_by")
    return out


def drawn_tests(task: dict, entry: dict, n: int, rnd: random.Random) -> dict:
    """The program against the problem's own reference solution on drawn inputs.

    Added after the inspection gate of 2026-09-26 (t/RL-DESIGN-2026-09-26.md):
    MBPP ships three assertions, and 9 of the 32 test-passing answers read by hand
    were wrong programs that the three happen not to separate (`n % 2 == 0` for
    "has 28 days", the wrong set of 30-day months, a min-of-three that misses one
    ordering). This is differential testing against the reference, the extra
    tests of EvalPlus (arXiv:2305.01210), which found MBPP/HumanEval's own tests
    admit wrong programs at the same kind of rate. Inputs are drawn with
    spec_check.draw, shaped like the problem's own examples, so they carry the
    same unstated preconditions (a sorted example stays sorted).

    The reference is trusted only after it reproduces every one of the problem's
    own assertions when called the way the draws will call it. Since 2026-09-30
    that is the way its own assertions call it (spec_check.python_arguments: a
    str where the assertion passed one), so a string problem's solution gets a
    `str`; before, it got a list of character codes and either raised (skipped)
    or, comparing against character literals, silently computed another
    function that still reproduced the assertions. An input the program's
    `requires` excludes, or where it runs out of budget, says nothing; only a
    wrong value or a crash counts against it.
    """
    import copy
    import spec_check
    fn = spec_check.reference(entry["rec"], entry["fn"])
    if fn is None:
        return {"status": "no reference"}
    points = entry["points"]
    kinds = [k for k, _v in points[0]["args"]]
    examples = [v for _k, v in points[0]["args"]]
    ekind = points[0]["expected"][0]
    positions = spec_check.string_positions(entry)

    def call(args):
        with spec_check.deadline(2):
            return fn(*spec_check.python_arguments(copy.deepcopy(list(args)), positions))

    def as_expected(out):
        if (ekind == "bool") != isinstance(out, bool):
            return None
        try:
            value = spec_check.to_t(out, ekind)
        except TypeError:
            return None
        if ekind == "int" and not isinstance(value, int):
            return None
        if ekind in ("seq", "seq-of-seq") and not isinstance(value, tuple):
            return None
        return value

    for p in points:
        try:
            got = as_expected(call([v for _k, v in p["args"]]))
        except BaseException:                                   # noqa: BLE001  (Timeout included)
            return {"status": "reference does not run"}
        if got is None or got != se._as_interp_value(ekind, p["expected"][1]):
            return {"status": "reference does not reproduce its tests"}
    passed = failed = other = 0
    witness = None
    for _ in range(n):
        args = [spec_check.draw(k, rnd, ex) for k, ex in zip(kinds, examples)]
        if any(a is None for a in args):
            return {"status": f"cannot draw {kinds}"}
        try:
            want = as_expected(call(args))
        except BaseException:                                   # noqa: BLE001
            continue                                            # the reference refuses: undefined here
        if want is None:
            continue
        point = {"args": [(k, a) for k, a in zip(kinds, args)], "expected": (ekind, want)}
        verdict = se.run_point(task, point)["verdict"]
        if verdict == "pass":
            passed += 1
        elif verdict in ("fail", "crash"):
            failed += 1
            if witness is None:
                witness = {"args": args, "expected": want, "verdict": verdict}
        else:
            other += 1
    out = {"status": "fail" if failed else "pass", "passed": passed, "failed": failed, "other": other}
    if witness is not None:
        out["witness"] = json.loads(json.dumps(witness, default=list))
    return out


def tests_ok(sig: dict) -> bool:
    """The problem's own assertions pass, and no drawn input separates the
    program from the reference solution."""
    return sig.get("tests") == "pass" and sig.get("drawn", {}).get("status") != "fail"


def spec_ok(sig: dict) -> bool:
    """The specification is not shown wrong: not contradicted by the problem's
    reference solution on drawn inputs, not false at one of its own examples,
    and not satisfied by a lazy program that answers wrongly. "no reference" /
    "cannot draw" are not evidence against it and pass."""
    if sig.get("spec", {}).get("status") == "disagrees":
        return False
    sp = sig.get("spec_points", {})
    if sp.get("points_failed") or sp.get("over_constrained"):
        return False
    return sig.get("exploit") is None


def tier(sig: dict, proof: str | None = None) -> str:
    """The furthest tier one answer reaches. ``proof`` is the Dafny cell text
    (`verified / refuted` and so on) or None when not proved yet."""
    stage = sig.get("stage")
    if stage in (None, "no-block", "parse"):
        return "none"
    if stage == "wf":
        return "parses"
    if not tests_ok(sig):
        return "typed"
    if proof == CLEAN and spec_ok(sig):
        return "proved-weak" if sig.get("spec", {}).get("weak") else "proved"
    return "tests"


def reward(sig: dict, proof: str | None = None) -> float:
    return TIERS[tier(sig, proof)]


def needs_proof(sig: dict) -> bool:
    """Only an answer that passes its tests and whose spec is not already shown
    wrong can reach the top tier, so only those go to the prover."""
    return sig.get("stage") == "task" and tests_ok(sig) and spec_ok(sig)


# ------------------------------------------------------------------ cache --

class RewardCache:
    """answer key -> {"signals": ..., "proof": ...}, one JSON line per write,
    last line wins; the task body is not stored (it is re-derivable)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.rows: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    if row.get("version", 1) == REWARD_VERSION:
                        self.rows[row["key"]] = row

    def get(self, key: str) -> dict | None:
        return self.rows.get(key)

    def put(self, key: str, signals: dict, proof: str | None) -> None:
        row = {"key": key, "version": REWARD_VERSION,
               "signals": {k: v for k, v in signals.items() if k != "task"}, "proof": proof}
        self.rows[key] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


# ----------------------------------------------------------------- prover --

def lab_host() -> str:
    """T_LAB from the environment or the gitignored t/lab-workstation.conf."""
    if os.environ.get("T_LAB"):
        return os.environ["T_LAB"]
    conf = HERE / "lab-workstation.conf"
    if conf.exists():
        for line in conf.read_text(encoding="utf-8").splitlines():
            if line.startswith("T_LAB="):
                return line.split("=", 1)[1].strip().strip('"')
    return "local"


def prove(tasks: dict[str, dict], *, jobs: int = 2, host: str | None = None,
          batch: str = "b", remote_root: str = "rl-grade") -> dict[str, str]:
    """Dafny cells for many tasks at once: {task name: `real / twin` cell}.

    Runs t/run_par.py --kernels dafny on the proving machine (the lab by
    default; ``host="local"`` runs here). --jobs is cells in flight and each
    cell makes six concurrent Dafny calls (three flake runs of the real and of
    the twin), so --jobs 2 is about 12 prover processes. T_MIN_KERNELS=1
    because one kernel is asked on purpose; the table is never the committed one.
    """
    if not tasks:
        return {}
    host = host or lab_host()
    with tempfile.TemporaryDirectory(prefix="rl-prove-") as tmp:
        tdir = Path(tmp) / "tasks"
        tdir.mkdir()
        for name, task in tasks.items():
            (tdir / f"{name}.json").write_text(json.dumps(task, indent=1), encoding="utf-8")
        run = (f"T_MIN_KERNELS=1 T_SPARK_JOBS=1 python3 t/run_par.py --jobs {int(jobs)} --kernels {PROOF_KERNEL} "
               f"--tasks {{w}}/tasks --out {{w}}/out --table {{w}}/kernels.md")
        if host == "local":
            work = Path(tmp)
            cmd = run.format(w=shlex.quote(str(work)))
            r = subprocess.run(["bash", "-lc", cmd], cwd=HERE.parent, capture_output=True, text=True)
            table = work / "kernels.md"
        else:
            work = f"{remote_root}/{batch}"
            subprocess.run(["ssh", host, f"rm -rf {work} && mkdir -p {work}"], check=True)
            subprocess.run(["rsync", "-a", f"{tdir}/", f"{host}:{work}/tasks/"], check=True)
            cmd = f"cd ~/tup && bash -lc {shlex.quote(run.format(w='$HOME/' + work))}"
            r = subprocess.run(["ssh", host, cmd], capture_output=True, text=True)
            table = Path(tmp) / "kernels.md"
            got = subprocess.run(["rsync", "-a", f"{host}:{work}/kernels.md", str(table)])
            if got.returncode != 0:
                raise RuntimeError(f"prove: no table from {host} (run_par exit {r.returncode}): "
                                   f"{(r.stdout + r.stderr)[-800:]}")
        if r.returncode not in (0, 1):                     # 1 is a finding with the table written
            raise RuntimeError(f"prove: run_par exited {r.returncode}: {(r.stdout + r.stderr)[-800:]}")
        _cols, rows = se.parse_kernel_table(table)
    return {name: rows.get(name, {}).get(PROOF_KERNEL, "missing") for name in tasks}


# --------------------------------------------------------------- scoring --

def score_many(items: list[tuple[int, str]], pool: dict, cache: RewardCache, *,
               prove_fn=prove, promote_header: bool = False, **prove_kw) -> list[dict]:
    """Rewards for (task_id, reply) pairs: CPU signals for every uncached answer,
    one prover batch for the ones that need it, then the tiers. Returns one
    dict per item with key, tier, reward, signals and proof."""
    fresh: dict[str, dict] = {}
    keys = []
    for tid, reply in items:
        key = answer_key(tid, reply)
        keys.append(key)
        if cache.get(key) is None and key not in fresh:
            fresh[key] = local_signals(tid, reply, pool[int(tid)], promote_header=promote_header)
    to_prove = {sig["task"]["name"]: (key, sig["task"]) for key, sig in fresh.items() if needs_proof(sig)}
    cells = prove_fn({name: task for name, (_k, task) in to_prove.items()}, **prove_kw) if to_prove else {}
    proof_of = {key: cells.get(name) for name, (key, _t) in to_prove.items()}
    for key, sig in fresh.items():
        cache.put(key, sig, proof_of.get(key))
    out = []
    for (tid, _reply), key in zip(items, keys):
        row = cache.get(key)
        t = tier(row["signals"], row["proof"])
        out.append({"key": key, "task_id": int(tid), "tier": t, "reward": TIERS[t],
                    "signals": row["signals"], "proof": row["proof"]})
    return out


# -------------------------------------------------------------------- CLI --

def main(argv=None) -> int:
    """score ITEMS.jsonl ({"task_id", "reply"} per line) into RESULTS.jsonl, one
    line per item in order; the trainer runs this in a subprocess so no
    reference solution or interpreter ever runs inside the GPU process."""
    import argparse
    ap = argparse.ArgumentParser(description="score answers with the tiered RL reward")
    ap.add_argument("items", type=Path)
    ap.add_argument("results", type=Path)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--split", type=Path, default=SPLIT)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--batch", default="b")
    ap.add_argument("--local", action="store_true", help="prove here instead of on the lab")
    a = ap.parse_args(argv)
    split = json.loads(a.split.read_text(encoding="utf-8"))
    pool = se.pool(split.get("pool", "v1"))
    allowed = set(rl_prompt_ids(a.split, pool))
    items = [json.loads(line) for line in a.items.read_text(encoding="utf-8").splitlines() if line.strip()]
    bad = {int(i["task_id"]) for i in items} - allowed
    if bad:
        raise SystemExit(f"rl_reward: ids outside the RL prompt set: {sorted(bad)[:5]}")
    out = score_many([(int(i["task_id"]), i["reply"]) for i in items], pool, RewardCache(a.cache),
                     jobs=a.jobs, host="local" if a.local else None, batch=a.batch)
    tmp = a.results.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps({k: r[k] for k in ("key", "task_id", "tier", "reward", "proof")}) + "\n"
                           for r in out), encoding="utf-8")
    os.replace(tmp, a.results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
