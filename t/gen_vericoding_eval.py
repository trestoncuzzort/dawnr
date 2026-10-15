#!/usr/bin/env python3
"""E3 Vericoding eval generation (integration-ready). For a model (merged student OR the UNTRAINED base,
under IDENTICAL prompts/decoding/revision) sample n completions per FROZEN kept task so the contract-anchored
grader can score pass@1 and an unbiased pass@k. The prompt is the engine's CANONICAL rendering of the frozen
contract with an empty body (no character clipping); a task whose rendered contract exceeds --max-prompt-chars
is PRESELECT-EXCLUDED and recorded, never silently clipped. The base model REVISION is pinned, and every
decoding seed/setting is recorded. Refuses an ineligible manifest (gate_ok must be True).

    ~/e3-venv/bin/python gen_vericoding_eval.py --model <dir|BASE> --tag T --manifest out/E3-eval-manifest.json \
        --veri-dir vericoding/dafny --n 10 [--temp 0.8 --top-p 0.95 --seed0 1234 --max-new 512 --limit 0]
"""
import argparse, json, os, sys, hashlib
from pathlib import Path
import torch
os.environ.setdefault("HF_HOME", os.path.expanduser("~/hf-cache"))
torch.set_num_threads(int(os.environ.get("E3_THREADS", "8")))
sys.path.insert(0, ".")
import tasks_io, surface
REV = "ea3f2471cf1b1f0db85067f1ef93848e38e88c25"
BASE = "Qwen/Qwen2.5-Coder-0.5B-Instruct"


def contract_prompt(frozen_task, max_chars):
    """Canonical render of the frozen contract with an EMPTY body; None if it exceeds the declared budget."""
    spec = {**frozen_task, "body": []}
    try:
        rendered = surface.print_task(spec)
    except Exception:
        return None
    if len(rendered) > max_chars:
        return None                                   # preselect-exclude; never clip the contract
    msg = ("Complete the body of this t task so it verifies against the given specification. "
           "Do not change the signature, requires, ensures or spec functions.\n\n" + rendered)
    return [{"role": "system", "content": "Write a t program for the task."}, {"role": "user", "content": msg}]


def task_hash(task):
    return hashlib.sha1(json.dumps(task, sort_keys=True, default=str).encode()).hexdigest()[:16]


def preflight(man, veri_dir, kept, max_prompt_chars, load_task):
    """BEFORE any model load: eligibility + mandatory content_hash + drift for every selected task, and
    RETAIN a validated snapshot (the loaded task and the rendered prompt) so generation never reopens a
    mutable source file. Returns (eligible snapshots, over-budget exclusions); raises PreflightError on a
    missing/drifted hash. Each snapshot: {row, task, msgs, prompt_hash}."""
    fail = []
    eligible, overbudget = [], []
    for row in kept:
        if not row.get("content_hash"):
            fail.append((row["name"], "missing-content-hash")); continue
        task = load_task(str(veri_dir / row["file"]))
        if task_hash(task) != row["content_hash"]:
            fail.append((row["name"], "content-hash-drift")); continue
        msgs = contract_prompt(task, max_prompt_chars)
        if msgs is None:
            overbudget.append({"task": row["name"], "reason": "prompt-exceeds-budget-or-unrenderable"}); continue
        prompt_hash = hashlib.sha1(json.dumps(msgs, sort_keys=True).encode()).hexdigest()[:16]
        eligible.append({"row": row, "task": task, "msgs": msgs, "prompt_hash": prompt_hash})
    if fail:
        raise PreflightError(fail)
    return eligible, overbudget


class PreflightError(Exception):
    pass


def control_gen_test():
    """Ineligible / missing-hash / drifted manifest must be refused BEFORE any tokenizer/model load.
    The loaders are replaced with a sentinel that records and raises, so reaching them is a failure."""
    import transformers, tempfile
    reached = {"n": 0}

    def sentinel(*_a, **_k):
        reached["n"] += 1
        raise AssertionError("loader reached despite preflight")
    oM, oT = transformers.AutoModelForCausalLM.from_pretrained, transformers.AutoTokenizer.from_pretrained
    transformers.AutoModelForCausalLM.from_pretrained = staticmethod(sentinel)
    transformers.AutoTokenizer.from_pretrained = staticmethod(sentinel)
    d = Path(tempfile.mkdtemp()); veri = d / "veri"; veri.mkdir()
    (veri / "t0.json").write_text(json.dumps({"t": 1, "name": "t0", "gate": "loops", "params": [],
        "returns": [{"name": "r", "type": "int"}], "requires": [], "ensures": [], "spec_funs": [], "body": []}))
    th = task_hash(tasks_io.load_task(str(veri / "t0.json")))
    (d / "r.jsonl").write_text("")
    res = {}
    argv = sys.argv
    try:
        for label, man in (("ineligible", {"gate_ok": False, "final_eligibility": {}, "eval_kept": [{"name": "t0", "file": "t0.json", "content_hash": th}]}),
                           ("missing-hash", {"gate_ok": True, "eval_kept": [{"name": "t0", "file": "t0.json"}]}),
                           ("drift", {"gate_ok": True, "eval_kept": [{"name": "t0", "file": "t0.json", "content_hash": "deadbeefdeadbeef"}]})):
            (d / "man.json").write_text(json.dumps(man))
            sys.argv = ["x", "--model", "BASE", "--tag", f"ctl-{label}", "--manifest", str(d / "man.json"),
                        "--veri-dir", str(veri), "--replies-unused", "--n", "1"]
            # --replies is required by argparse; supply a dummy path (preflight fails before it is read)
            sys.argv = ["x", "--model", "BASE", "--tag", f"ctl-{label}", "--manifest", str(d / "man.json"),
                        "--veri-dir", str(veri), "--n", "1"]
            res[label] = main()
    finally:
        transformers.AutoModelForCausalLM.from_pretrained = oM
        transformers.AutoTokenizer.from_pretrained = oT
        sys.argv = argv
    ok = {"ineligible exit5": res.get("ineligible") == 5, "missing-hash exit6": res.get("missing-hash") == 6,
          "drift exit6": res.get("drift") == 6, "loader never reached": reached["n"] == 0}
    for k, v in ok.items():
        print(f"{k}: [{'ok' if v else 'FAIL'}]")
    allok = all(ok.values())
    print("GENERATOR-CONTROL-TEST " + ("PASS" if allok else "FAIL"))
    return 0 if allok else 1


def snapshot_test():
    """A disk mutation AFTER preflight must NOT change the prompt used: the validated snapshot is retained."""
    import tempfile
    d = Path(tempfile.mkdtemp()); veri = d / "veri"; veri.mkdir()
    ens1 = [{"op": "==", "args": [{"var": "r"}, {"op": "+", "args": [{"var": "n"}, {"int": 1}]}]}]
    ens2 = [{"op": "==", "args": [{"var": "r"}, {"op": "+", "args": [{"var": "n"}, {"int": 2}]}]}]
    base = {"t": 1, "name": "inc", "gate": "loops", "params": [{"name": "n", "type": "int"}],
            "returns": [{"name": "r", "type": "int"}], "requires": [], "spec_funs": [], "body": []}
    (veri / "inc.json").write_text(json.dumps({**base, "ensures": ens1}))
    ch = task_hash(tasks_io.load_task(str(veri / "inc.json")))
    man = {"gate_ok": True, "eval_kept": [{"name": "inc", "file": "inc.json", "content_hash": ch}]}
    eligible, _ = preflight(man, veri, man["eval_kept"], 6000, tasks_io.load_task)
    snap_prompt = eligible[0]["msgs"][-1]["content"]
    (veri / "inc.json").write_text(json.dumps({**base, "ensures": ens2}))        # MUTATE after preflight
    re_prompt = contract_prompt(tasks_io.load_task(str(veri / "inc.json")), 6000)[-1]["content"]
    ok_changed = snap_prompt != re_prompt
    ok_snapshot = ("n + 1" in snap_prompt) and ("n + 2" not in snap_prompt)      # snapshot kept original contract
    ok_disk = "n + 2" in re_prompt
    for k, v in (("disk rendering changed by mutation", ok_changed),
                 ("retained snapshot keeps original contract", ok_snapshot),
                 ("mutated disk would have changed it", ok_disk)):
        print(f"{k}: [{'ok' if v else 'FAIL'}]")
    allok = ok_changed and ok_snapshot and ok_disk
    print("SNAPSHOT-TEST " + ("PASS" if allok else "FAIL"))
    return 0 if allok else 1


def main():
    if "--control-test" in sys.argv:
        return control_gen_test()
    if "--snapshot-test" in sys.argv:
        return snapshot_test()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--veri-dir", type=Path, required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--temp", type=float, default=0.8)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--seed0", type=int, default=1234)
    ap.add_argument("--max-new", type=int, default=512)
    ap.add_argument("--max-prompt-chars", type=int, default=6000)
    ap.add_argument("--limit", type=int, default=0, help="0 = full kept population; >0 = a labelled scoped diagnostic")
    a = ap.parse_args()
    man = json.loads(a.manifest.read_text())
    if not man.get("gate_ok"):
        print(f"REFUSED: manifest gate_ok is not True: {man.get('final_eligibility')}"); return 5
    kept = man["eval_kept"]
    scoped = bool(a.limit)
    if a.limit:
        kept = kept[: a.limit]
    # PREFLIGHT every selected task (eligibility + mandatory hash + drift) BEFORE loading any tokenizer/model.
    try:
        eligible, overbudget = preflight(man, a.veri_dir, kept, a.max_prompt_chars, tasks_io.load_task)
    except PreflightError as e:
        print(f"REFUSED before model load: {len(e.args[0])} task(s) missing/drifted hash: {e.args[0][:10]}"); return 6
    from transformers import AutoModelForCausalLM, AutoTokenizer
    model_path, rev = (BASE, REV) if a.model == "BASE" else (a.model, None)
    tok = AutoTokenizer.from_pretrained(model_path, revision=rev)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_path, revision=rev,
                                                 dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32)
    model.eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(dev)
    settings = {"tag": a.tag, "model": model_path, "revision": rev or "merged-adapter(base rev ea3f2471)",
                "scoped_diagnostic": scoped, "n": a.n, "temp": a.temp, "top_p": a.top_p, "seed0": a.seed0,
                "max_new": a.max_new, "max_prompt_chars": a.max_prompt_chars, "device": dev,
                "preflight_eligible": len(eligible), "preflight_overbudget": len(overbudget)}
    out = Path("out") / f"veri-eval-{a.tag}.replies.jsonl"
    out.parent.mkdir(exist_ok=True)
    (Path("out") / f"veri-eval-{a.tag}.settings.json").write_text(json.dumps(settings, indent=2))
    manifest_id = hashlib.sha1((json.dumps(man["eval_kept"], sort_keys=True)
                                + str(man.get("training_selection_hash", ""))).encode()).hexdigest()[:16]
    settings["manifest_id"] = manifest_id
    (Path("out") / f"veri-eval-{a.tag}.settings.json").write_text(json.dumps(settings, indent=2))
    excluded = list(overbudget)
    with out.open("w", encoding="utf-8") as fh:
        for ti, e in enumerate(eligible, 1):
            row, msgs = e["row"], e["msgs"]                    # VALIDATED SNAPSHOT; no reopening of source files
            text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            enc = tok(text, return_tensors="pt").to(dev)
            plans = [("greedy", 0, dict(do_sample=False))] + \
                    [(f"s{j}", a.seed0 + j, dict(do_sample=True, temperature=a.temp, top_p=a.top_p)) for j in range(a.n)]
            for label, seed, kw in plans:
                torch.manual_seed(seed)
                with torch.no_grad():
                    o = model.generate(**enc, max_new_tokens=a.max_new, pad_token_id=tok.pad_token_id, **kw)
                reply = tok.decode(o[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
                fh.write(json.dumps({"id": f"{row['name']}#{label}", "task": row["name"], "sample": label,
                                     "seed": seed, "reply": reply, "content_hash": row["content_hash"],
                                     "prompt_hash": e["prompt_hash"], "manifest_id": manifest_id}) + "\n")
                fh.flush()
            if ti % 10 == 0:
                print(f"  {a.tag} {ti}/{len(eligible)}", flush=True)
    (Path("out") / f"veri-eval-{a.tag}.excluded.json").write_text(json.dumps(excluded, indent=2))
    print(f"{a.tag}: wrote {out}; preselect-excluded {len(excluded)} (over-budget/drift); settings recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
