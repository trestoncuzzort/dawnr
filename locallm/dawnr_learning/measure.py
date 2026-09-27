"""measure.py: does a person's adapter fit that person better, without making dawnr worse? (DAWNR-LEARNING.md)

    python3 locallm/dawnr_learning/measure.py --model <chat checkpoint dir> \
        --conversations <chat_data.py JSONL the checkpoint was mid-trained on> --out <dir> --arm A-s1 \
        --guard-text <the core's validation.txt> [--persons ada,bo,cy,di] [--sessions 4] [--per-session 10] \
        [--heldout-train 20] [--seed 1] [--replay-frac 0.25] [--lr 1e-3] [--dev 100] [--max-tokens 640]

The protocol is PRELUDE's (Gao et al., arXiv:2404.15269): every round, the
assistant answers, the simulated person edits the answer to their latent
preference (persons.py), and the edit distance between the answer and the edit
is the cost; a learner should drive the cost down round after round. Here a
round is a session of `--per-session` prompts, and between sessions the
person's adapter sleeps (sleep.train_adapter, rebuild mode) on everything the
person has kept so far, OPPU-style (arXiv:2402.04401: one LoRA per person on a
frozen base).

Every prompt is a training-side problem of the chat corpus (chat_data.py's
hash split): sessions and the train-side held-out set are disjoint problems
chosen by a fixed hash (the same for every arm and seed), and the validation-
side conversations (documents the base never trained on) are a second held-out
set. The replay pool is the base's training-side conversations minus every
problem a person is asked or evaluated on, so replay never shows the canonical
answer to a prompt the person is measured on. Every example a person produces
passes the held-out gates before a sleep uses it (sleep.gate_examples); dev
problems (t/r12-dev-ids.json) are only ever asked, never trained on.

What is measured, per person, after the last sleep, against the frozen base:

fit  * held-out loss (nats per assistant token) of the person's own version of
       the reference answers, on held-out prompts; the same for every other
       person's version (the cross matrix: a personal adapter should fit its
       own person best, not merely any style better);
     * greedy answers on held-out prompts: the edit cost to the person's
       version, and adherence to each preference (persons.style_report);
     * the edit cost per session (the learning curve; session 1 is the base).
core * the t tool on the held-out answers (parses, well formed, every example
       passes), style-invariant, so a new style is not scored as damage;
     * the dev problems (MBPP, English prompts): rl_reward tiers, as chat_eval.py;
     * held-out plain source code (the core's own validation text): loss with the
       adapter against the base's, the sleep's guard;
     * loss on the base's canonical validation conversations, reported but
       confounded by design: a person's style makes the canonical one less likely.

Written: <out>/base.json (the base pass, reused by every arm of the same
inputs), <out>/<arm>/<person>/results.json and beside it the person's store,
sleep records and final adapter. Nothing is claimed here; the prediction is
registered in a dated note before a run is reported (AGENTS.md rule 3).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent
ROOT = LOCALLM.parent
for p in (str(LOCALLM), str(ROOT / "t")):
    if p not in sys.path:
        sys.path.insert(0, p)

from dawnr_learning import persons as P  # noqa: E402
from dawnr_learning.feedback import PersonStore, final_program  # noqa: E402
from dawnr_learning.sleep import (BehaviorGuard, GuardWindows, Rows, SleepConfig, gate_examples,  # noqa: E402
                                  hash_unit, mean_loss, split_examples, train_adapter)

PROBLEM_SEED = 0          # which problems go where: fixed, so every arm and seed sees the same ones


def reference(conv: dict) -> str | None:
    import chat
    return chat.final_program(conv["messages"][1]["content"])


def user_of(conv: dict) -> str:
    return conv["messages"][0]["content"]


def eligible(conv: dict, people: list) -> bool:
    """Single-turn, its reference passes the t tool on its own examples, and every person can write it."""
    from dawnr_harness.checker import check
    if len(conv["messages"]) != 2:
        return False
    ref = reference(conv)
    if not ref or not check(ref, user_of(conv))[0]:
        return False
    try:
        return all(P.person_answer(p, ref, user_of(conv)) is not None for p in people)
    except Exception:                                        # noqa: BLE001  (counted by the caller as ineligible)
        return False


def choose(convs: list[dict], people: list, sessions: int, per_session: int, heldout_train: int,
           problem_seed: int = PROBLEM_SEED, guard_prompts: int = 8) -> dict:
    train = sorted([c for c in convs if c.get("split") == "train"],
                   key=lambda c: hash_unit(c.get("source", "") + user_of(c), problem_seed))
    picked, skipped = [], 0
    need = sessions * per_session + heldout_train
    for c in train:
        if len(picked) == need:
            break
        if eligible(c, people):
            picked.append(c)
        else:
            skipped += 1
    if len(picked) < need:
        raise SystemExit(f"only {len(picked)} eligible training-side problems, {need} needed")
    val = [c for c in convs if c.get("split") == "val" and eligible(c, people)]
    chosen = {"sessions": [picked[i * per_session:(i + 1) * per_session] for i in range(sessions)],
              "heldout_train": picked[sessions * per_session:], "heldout_val": val,
              "skipped_ineligible": skipped}
    used = {c.get("source") for c in picked} | {c.get("source") for c in val}
    pool = [c for c in convs if c.get("split") == "train" and c.get("source") not in used]
    # the behaviour guard's prompts: training-side, never a person's, never held out, never replayed
    ranked = sorted([c for c in pool if eligible(c, [])],
                    key=lambda c: hash_unit(c.get("source", "") + user_of(c), problem_seed + 1))
    chosen["guard_prompts"] = ranked[:guard_prompts]
    guard_sources = {c.get("source") for c in chosen["guard_prompts"]}
    chosen["replay_pool"] = [c for c in pool if c.get("source") not in guard_sources]
    return chosen


def ask_all(engine, tok, prompts: list[str], max_tokens: int) -> list[dict]:
    from chat_eval import ask
    return [ask(engine, tok, u, max_tokens) for u in prompts]


def judge_answer(got: dict, user: str) -> dict:
    from dawnr_harness.checker import check
    program = final_program(got["parts"]) if got["parts"] else None
    if not program:
        return {"parses": False, "well_formed": False, "examples_pass": False}
    ok, verdict = check(program, user)
    lines = verdict.split("\n")
    return {"parses": "parses: yes" in lines, "well_formed": "well formed: yes" in lines, "examples_pass": ok}


def dev_eval(engine, tok, n: int, max_tokens: int, split_path: Path) -> dict:
    """chat_eval.py's dev pass (the r12 dev ids, the r12 prompt, rl_reward tiers), with this module's answer rule."""
    import loop_filter
    import loop_locallm
    import rl_reward
    import spec_experiment as se
    from chat_eval import ask
    eval_ids = {int(i) for i in json.loads(split_path.read_text(encoding="utf-8"))["eval_ids"]}
    dev = sorted(loop_filter.r12_dev_ids())[:n]
    if set(dev) & eval_ids:
        raise SystemExit("dev ids overlap the held-out evaluation ids")
    pool = se.pool("v5")
    tiers = {t: 0 for t in rl_reward.ORDER}
    for tid in dev:
        entry = pool[tid]
        user = loop_locallm.problem_head(entry, with_examples=True).rstrip("\n")
        got = ask(engine, tok, user, max_tokens)
        program = final_program(got["parts"]) if got["parts"] else ""
        tiers[rl_reward.tier(rl_reward.local_signals(tid, program or "", entry))] += 1
    return {"asked": len(dev), "tiers": tiers, "at_least_typed": sum(tiers[t] for t in rl_reward.ORDER[2:]),
            "tests_passed": sum(tiers[t] for t in rl_reward.ORDER[3:])}


def style_targets(people: list, problems: list[dict]) -> dict:
    """{person: [conversation with that person's version of the reference answer]} for held-out problems."""
    out = {}
    for p in people:
        out[p.name] = [{"messages": [{"role": "user", "content": user_of(c)},
                                     {"role": "assistant", "content": P.person_answer(p, reference(c), user_of(c))}]}
                       for c in problems]
    return out


def score_answers(people: list, problems: list[dict], answers: list[dict], tok) -> dict:
    """For each person: mean edit cost, adherence and the verdict counts of these answers to these problems."""
    out = {}
    checks = [judge_answer(a, user_of(c)) for a, c in zip(answers, problems)]
    core = {k: sum(ch[k] for ch in checks) for k in ("parses", "well_formed", "examples_pass")}
    for p in people:
        costs, rel, adherence, feats, kinds = [], [], [], {}, {}
        for a, c in zip(answers, problems):
            r = P.react(p, user_of(c), a["parts"] or "", reference(c), tok)
            costs.append(r["cost"])
            rel.append(r["cost"] / max(r["target_tokens"], 1))
            kinds[r["feedback"]] = kinds.get(r["feedback"], 0) + 1
            rep = P.style_report(p, a["parts"] or "")
            if rep["adherence"] is not None:
                adherence.append(rep["adherence"])
            for k, v in rep["features"].items():
                if v is not None:
                    feats.setdefault(k, []).append(float(v))
        out[p.name] = {"cost_mean": sum(costs) / len(costs), "costs": costs, "rel_cost_mean": sum(rel) / len(rel),
                       "kinds": kinds, "adherence_mean": sum(adherence) / len(adherence) if adherence else None,
                       "features": {k: sum(v) / len(v) for k, v in feats.items()}}
    return {"core": core, "n": len(problems), "by_person": out}


def probe_point(person, problems: list[dict], answers: list[dict], tok, after_sleep: int) -> dict:
    """One point of a person's learning curve: their cost, relative cost and adherence, and the tool's verdicts."""
    scored = score_answers([person], problems, answers, tok)
    mine = scored["by_person"][person.name]
    return {"after_sleep": after_sleep, "cost_mean": mine["cost_mean"], "rel_cost_mean": mine["rel_cost_mean"],
            "adherence_mean": mine["adherence_mean"], "features": mine["features"], "core": scored["core"]}


def identity_of(args, chosen) -> dict:
    blob = json.dumps({"sessions": [[c.get("source") for c in s] for s in chosen["sessions"]],
                       "heldout_train": [c.get("source") for c in chosen["heldout_train"]],
                       "heldout_val": [c.get("source") for c in chosen["heldout_val"]]}, sort_keys=True)
    return {"problems_sha256": hashlib.sha256(blob.encode()).hexdigest(), "max_tokens": args.max_tokens,
            "dev": args.dev, "persons": args.persons, "problem_seed": args.problem_seed}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--conversations", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--arm", required=True, help="a name for this arm and seed, e.g. A-s1")
    ap.add_argument("--guard-text", type=Path, required=True)
    ap.add_argument("--persons", default="ada,bo,cy,di")
    ap.add_argument("--sessions", type=int, default=4)
    ap.add_argument("--per-session", type=int, default=10)
    ap.add_argument("--heldout-train", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--problem-seed", type=int, default=PROBLEM_SEED,
                    help="which problems go where; the registered runs use the default, the pilot another")
    ap.add_argument("--replay-frac", type=float, default=0.25)
    ap.add_argument("--lr", type=float, default=SleepConfig.lr)
    ap.add_argument("--rank", type=int, default=8)
    ap.add_argument("--epochs", type=float, default=SleepConfig.epochs)
    ap.add_argument("--min-steps", type=int, default=SleepConfig.min_steps)
    ap.add_argument("--max-steps", type=int, default=SleepConfig.max_steps)
    ap.add_argument("--guard-prompts", type=int, default=8,
                    help="training-side prompts the behaviour guard asks (0: no behaviour guard)")
    ap.add_argument("--behavior-tolerance", type=int, default=SleepConfig.behavior_tolerance)
    ap.add_argument("--dev", type=int, default=100)
    ap.add_argument("--max-tokens", type=int, default=640)
    ap.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json")
    ap.add_argument("--device", default=None)
    ap.add_argument("--gpu-max-gb", type=float, default=None,
                    help="cap this process's share of the card (torch.cuda.set_per_process_memory_fraction)")
    ap.add_argument("--base-only", action="store_true", help="run (or reuse) the base pass and stop")
    a = ap.parse_args(argv)

    import torch
    from checkpoint import load_checkpoint
    from engine import Engine
    from model import has_lora, load_lora_state, remove_lora
    from train import pick_device
    from dawnr_learning.adapters import base_identity

    started = time.monotonic()
    device = a.device or pick_device()
    if a.gpu_max_gb and device.startswith("cuda"):
        total = torch.cuda.get_device_properties(0).total_memory / 2 ** 30
        torch.cuda.set_per_process_memory_fraction(min(1.0, a.gpu_max_gb / total))
    people = [P.PERSONS[n] for n in a.persons.split(",")]
    convs = [json.loads(line) for line in a.conversations.read_text(encoding="utf-8").splitlines() if line.strip()]
    chosen = choose(convs, people, a.sessions, a.per_session, a.heldout_train, a.problem_seed, a.guard_prompts)
    heldout = chosen["heldout_train"] + chosen["heldout_val"]
    ident = identity_of(a, chosen)
    ident["base"] = base_identity(a.model)
    print(json.dumps({"problems": {k: (len(v) if isinstance(v, list) else v) for k, v in chosen.items()},
                      "identity": ident["problems_sha256"][:16]}), flush=True)

    model, tok, _ = load_checkpoint(a.model, device)
    block = model.config.block_size
    with a.guard_text.open(encoding="utf-8") as f:
        guard = GuardWindows(tok, f.read(400_000), min(512, block))
    canon_val = Rows(tok, [c for c in convs if c.get("split") == "val"], block)
    targets = style_targets(people, heldout)
    target_rows = {name: Rows(tok, rows, block) for name, rows in targets.items()}
    engine = Engine(model, tok)

    a.out.mkdir(parents=True, exist_ok=True)
    base_path = a.out / "base.json"
    base = json.loads(base_path.read_text()) if base_path.is_file() else None
    if base is None or base.get("identity") != ident:
        t0 = time.monotonic()
        answers = ask_all(engine, tok, [user_of(c) for c in heldout], a.max_tokens)
        base = {"identity": ident, "heldout": score_answers(people, heldout, answers, tok),
                "heldout_answers": [x["parts"] for x in answers],
                "style_loss": {n: mean_loss(model, r, device) for n, r in target_rows.items()},
                "canonical_val_loss": mean_loss(model, canon_val, device),
                "guard_loss": guard.loss(model, device),
                "dev": dev_eval(engine, tok, a.dev, a.max_tokens, a.split) if a.dev else None,
                "seconds": round(time.monotonic() - t0, 1)}
        base_path.write_text(json.dumps(base, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"base": {k: v for k, v in base.items() if k in ("style_loss", "canonical_val_loss",
                                                                              "guard_loss", "dev", "seconds")}}),
              flush=True)
    if a.base_only:
        return 0

    arm_dir = a.out / a.arm
    arm_dir.mkdir(parents=True, exist_ok=True)
    cfg = SleepConfig(r=a.rank, lr=a.lr, replay_frac=a.replay_frac, seed=a.seed, epochs=a.epochs,
                      min_steps=a.min_steps, max_steps=a.max_steps, behavior_tolerance=a.behavior_tolerance)
    replay = Rows(tok, chosen["replay_pool"], block) if a.replay_frac > 0 else None
    behavior = BehaviorGuard([user_of(c) for c in chosen["guard_prompts"]], a.max_tokens) \
        if chosen["guard_prompts"] else None
    results = {"arm": a.arm, "identity": ident, "config": asdict(cfg), "persons": {}}
    for person in people:
        pdir = arm_dir / person.name
        store = PersonStore(person.name, root=pdir)
        store.erase_all()
        state, per_session, sleeps = None, [], []
        base_probe = [{"parts": parts} for parts in base["heldout_answers"][:len(chosen["heldout_train"])]]
        curve = [probe_point(person, chosen["heldout_train"], base_probe, tok, after_sleep=0)]
        for s, problems in enumerate(chosen["sessions"], 1):
            if has_lora(model):
                remove_lora(model)
            if state is not None:
                load_lora_state(model, state)
            model.eval()
            answers = ask_all(engine, tok, [user_of(c) for c in problems], a.max_tokens)
            costs, kinds = [], {"up": 0, "edit": 0, "wrong": 0, "none": 0}
            for c, got in zip(problems, answers):
                msgs = [{"role": "user", "content": user_of(c)}]
                rid = store.add_answer(msgs, got["parts"] or "", session=f"s{s}", how="simulated",
                                       model={"adapter_after_sleep": s - 1})
                r = P.react(person, user_of(c), got["parts"] or "", reference(c), tok)
                kinds[r["feedback"] or "none"] += 1
                if r["feedback"] is None:
                    continue
                costs.append(r["cost"])
                if r["feedback"] == "up":
                    store.rate(rid, True, how="simulated")
                elif r["feedback"] == "edit":
                    store.edit(rid, r["target"], how="simulated")
                else:
                    store.wrong(rid, note="that's wrong", correction=r["target"], how="simulated")
            per_session.append({"session": s, "cost_mean": sum(costs) / max(len(costs), 1), "costs": costs,
                                "kinds": kinds})
            print(json.dumps({"person": person.name, "session": s, "cost_mean": per_session[-1]["cost_mean"],
                              "kinds": kinds}), flush=True)
            if has_lora(model):
                remove_lora(model)
            examples, excluded = store.training_examples(check=True)
            examples, refused = gate_examples(examples, a.split)
            train_ex, val_ex = split_examples(examples, cfg.val_frac, cfg.seed)
            rows_t, rows_v = Rows(tok, train_ex, block), (Rows(tok, val_ex, block) if val_ex else None)
            new_state, rec = train_adapter(model, tok, rows_t, rows_v, replay, cfg, device, guard=guard,
                                           behavior=behavior,
                                           extra_evals={"canonical_val": canon_val})
            rec.update({"session": s, "examples": len(examples), "excluded": excluded, "refused": refused,
                        "accepted": new_state is not None})
            sleeps.append(rec)
            print(json.dumps({"person": person.name, "sleep": s, "steps": rec["steps"], "best": rec["best_step"],
                              "stop": rec["stop"], "person_val": [rec["loss_base"]["person_val"],
                                                                 rec["loss_adapter"]["person_val"]],
                              "guard": rec["guard"].get("rise"), "behavior": rec["behavior"],
                              "accepted": new_state is not None, "seconds": rec["seconds"]}), flush=True)
            if new_state is not None:
                state = new_state
            if s < len(chosen["sessions"]):
                # the learning curve on one fixed probe (the train-side held-out prompts), after every sleep:
                # session costs mix problems of different lengths, so they are reported but not the curve
                if has_lora(model):
                    remove_lora(model)
                if state is not None:
                    load_lora_state(model, state)
                model.eval()
                probe = ask_all(engine, tok, [user_of(c) for c in chosen["heldout_train"]], a.max_tokens)
                curve.append(probe_point(person, chosen["heldout_train"], probe, tok, after_sleep=s))
                print(json.dumps({"person": person.name, "curve": curve[-1]}), flush=True)
        # final evaluation with the last adapter the guard accepted
        if has_lora(model):
            remove_lora(model)
        if state is not None:
            load_lora_state(model, state)
        model.eval()
        answers = ask_all(engine, tok, [user_of(c) for c in heldout], a.max_tokens)
        n_probe = len(chosen["heldout_train"])
        curve.append(probe_point(person, chosen["heldout_train"], answers[:n_probe], tok,
                                 after_sleep=len(chosen["sessions"])))
        final = {"heldout": score_answers(people, heldout, answers, tok), "curve": curve,
                 "heldout_answers": [x["parts"] for x in answers],
                 "style_loss": {n: mean_loss(model, r, device) for n, r in target_rows.items()},
                 "canonical_val_loss": mean_loss(model, canon_val, device),
                 "guard_loss": guard.loss(model, device),
                 "dev": dev_eval(engine, tok, a.dev, a.max_tokens, a.split) if a.dev else None,
                 "adapter_accepted": state is not None}
        results["persons"][person.name] = {"sessions": per_session, "sleeps": sleeps, "final": final}
        if state is not None:
            torch.save(state, pdir / "final-adapter.pt")
        (pdir / "results.json").write_text(json.dumps({"arm": a.arm, "identity": ident, "config": asdict(cfg),
                                                       "person": person.name, **results["persons"][person.name]},
                                                      indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"person": person.name, "style_loss": final["style_loss"],
                          "own_cost": final["heldout"]["by_person"][person.name]["cost_mean"],
                          "core": final["heldout"]["core"], "dev": final["dev"],
                          "guard": final["guard_loss"]}), flush=True)
    if has_lora(model):
        remove_lora(model)
    print(json.dumps({"done": a.arm, "persons": list(results["persons"]),
                      "seconds": round(time.monotonic() - started, 1)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
