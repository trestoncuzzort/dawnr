"""measure_profile.py: the same protocol as measure.py, with the style profile as the learner instead of an adapter.

    python3 locallm/dawnr_learning/measure_profile.py --model <chat checkpoint dir> \
        --conversations <its chat_data.py JSONL> --out <the run dir measure.py wrote base.json to> --arm P \
        [--persons ada,bo,cy,di] [--sessions 4] [--per-session 10] [--heldout-train 20] [--dev 100]

The base answers every prompt once (its answers do not depend on the person:
no weights change), and the person's profile (profile.py), re-inferred from
their store after every session, rewrites each answer before the person sees
it. Everything else is measure.py's: the same problems (the same registered
set and problem seed), the same reactions and scores, the same fixed probe for
the learning curve, and the same base pass (<out>/base.json, which must exist
and match). Dev answers are generated once and rewritten per person, then
graded as measure.py grades them. Written: <out>/<arm>/<person>/results.json,
in measure.py's shape, so summarize.py reads both.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent
ROOT = LOCALLM.parent
for p in (str(LOCALLM), str(ROOT / "t")):
    if p not in sys.path:
        sys.path.insert(0, p)

from dawnr_learning import measure as M  # noqa: E402
from dawnr_learning import persons as P  # noqa: E402
from dawnr_learning import profile as PR  # noqa: E402
from dawnr_learning.feedback import PersonStore, final_program  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--conversations", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--arm", default="P")
    ap.add_argument("--persons", default="ada,bo,cy,di")
    ap.add_argument("--eligible-persons", default="ada,bo,cy,di")
    ap.add_argument("--sessions", type=int, default=4)
    ap.add_argument("--per-session", type=int, default=10)
    ap.add_argument("--heldout-train", type=int, default=20)
    ap.add_argument("--dev", type=int, default=100)
    ap.add_argument("--max-tokens", type=int, default=640)
    ap.add_argument("--problem-seed", type=int, default=M.PROBLEM_SEED)
    ap.add_argument("--guard-prompts", type=int, default=8, help="only to reproduce measure.py's problem split")
    ap.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json")
    ap.add_argument("--device", default=None)
    a = ap.parse_args(argv)

    import loop_filter
    import loop_locallm
    import rl_reward
    import spec_experiment as se
    from checkpoint import load_checkpoint
    from engine import Engine
    from train import pick_device
    from dawnr_learning.adapters import base_identity

    started = time.monotonic()
    device = a.device or pick_device()
    people = [P.PERSONS[n] for n in a.persons.split(",")]
    everyone = [P.PERSONS[n] for n in a.eligible_persons.split(",")]
    convs = [json.loads(line) for line in a.conversations.read_text(encoding="utf-8").splitlines() if line.strip()]
    chosen = M.choose(convs, everyone, a.sessions, a.per_session, a.heldout_train, a.problem_seed, a.guard_prompts)
    heldout = chosen["heldout_train"] + chosen["heldout_val"]
    ident = M.identity_of(a, chosen)
    ident["base"] = base_identity(a.model)
    base = json.loads((a.out / "base.json").read_text())
    if base.get("identity") != ident:
        raise SystemExit("base.json was made for other inputs; run measure.py's base pass for these first")

    # the base's answers to every session prompt and every dev problem, once (cached beside base.json)
    cache = a.out / "base-extra.json"
    extra = json.loads(cache.read_text()) if cache.is_file() else None
    if extra is None or extra.get("identity") != ident:
        model, tok, _ = load_checkpoint(a.model, device)
        engine = Engine(model, tok)
        session_prompts = [M.user_of(c) for s in chosen["sessions"] for c in s]
        sessions = [x["parts"] for x in M.ask_all(engine, tok, session_prompts, a.max_tokens)]
        dev_ids = sorted(loop_filter.r12_dev_ids())[:a.dev]
        pool = se.pool("v5")
        dev_prompts = [loop_locallm.problem_head(pool[t], with_examples=True).rstrip("\n") for t in dev_ids]
        dev = [x["parts"] for x in M.ask_all(engine, tok, dev_prompts, a.max_tokens)]
        extra = {"identity": ident, "sessions": sessions, "dev_ids": dev_ids, "dev": dev}
        cache.write_text(json.dumps(extra) + "\n", encoding="utf-8")
        del model, engine
    else:
        _m, tok, _ = load_checkpoint(a.model, "cpu")
        del _m
    pool = se.pool("v5")

    def dev_tiers(answers: list) -> dict:
        tiers = {t: 0 for t in rl_reward.ORDER}
        for tid, parts in zip(extra["dev_ids"], answers):
            program = final_program(parts) if parts else ""
            tiers[rl_reward.tier(rl_reward.local_signals(tid, program or "", pool[tid]))] += 1
        return {"asked": len(answers), "tiers": tiers, "at_least_typed": sum(tiers[t] for t in rl_reward.ORDER[2:]),
                "tests_passed": sum(tiers[t] for t in rl_reward.ORDER[3:])}

    arm_dir = a.out / a.arm
    base_session = extra["sessions"]
    for person in people:
        pdir = arm_dir / person.name
        store = PersonStore(person.name, root=pdir)
        store.erase_all()
        profile = {"inferred": {}, "pinned": {}}
        n_probe = len(chosen["heldout_train"])
        base_probe = [{"parts": parts} for parts in base["heldout_answers"][:n_probe]]
        curve = [M.probe_point(person, chosen["heldout_train"], base_probe, tok, after_sleep=0)]
        per_session, sleeps, k = [], [], 0
        for s, problems in enumerate(chosen["sessions"], 1):
            costs, kinds = [], {"up": 0, "edit": 0, "wrong": 0, "none": 0}
            for c in problems:
                user = M.user_of(c)
                shown = PR.apply(profile, base_session[k] or "", user)
                k += 1
                rid = store.add_answer([{"role": "user", "content": user}], shown or "", session=f"s{s}",
                                       how="simulated", model={"profile_after_sleep": s - 1})
                r = P.react(person, user, shown or "", M.reference(c), tok)
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
            profile = PR.refresh(store)                        # the profile's "sleep": inference, no weights
            sleeps.append({"session": s, "accepted": True, "profile": profile, "steps": 0, "best_step": None,
                           "stop": "profile", "behavior": None, "guard": {}, "loss_base": {}, "loss_adapter": {},
                           "examples": profile.get("examples")})
            print(json.dumps({"person": person.name, "session": s, "cost_mean": per_session[-1]["cost_mean"],
                              "kinds": kinds, "profile": PR.effective(profile)}), flush=True)
            if s < len(chosen["sessions"]):
                probe = [{"parts": PR.apply(profile, parts or "", M.user_of(c))}
                         for parts, c in zip(base["heldout_answers"][:n_probe], chosen["heldout_train"])]
                curve.append(M.probe_point(person, chosen["heldout_train"], probe, tok, after_sleep=s))
        answers = [{"parts": PR.apply(profile, parts or "", M.user_of(c))}
                   for parts, c in zip(base["heldout_answers"], heldout)]
        curve.append(M.probe_point(person, chosen["heldout_train"], answers[:n_probe], tok,
                                   after_sleep=len(chosen["sessions"])))
        dev_answers = [PR.apply(profile, parts or "", loop_locallm.problem_head(pool[t], with_examples=True).rstrip("\n"))
                       for t, parts in zip(extra["dev_ids"], extra["dev"])]
        final = {"heldout": M.score_answers(everyone, heldout, answers, tok), "curve": curve,
                 "heldout_answers": [x["parts"] for x in answers],
                 "style_loss": {}, "canonical_val_loss": base["canonical_val_loss"],
                 "guard_loss": base["guard_loss"], "dev": dev_tiers(dev_answers),
                 "dev_base_same_answers": dev_tiers(extra["dev"]), "adapter_accepted": None,
                 "profile": profile, "profile_words": PR.describe(profile)}
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "results.json").write_text(json.dumps({"arm": a.arm, "identity": ident, "learner": "profile",
                                                       "person": person.name, "sessions": per_session,
                                                       "sleeps": sleeps, "final": final}, indent=1) + "\n",
                                           encoding="utf-8")
        print(json.dumps({"person": person.name, "own_cost": final["heldout"]["by_person"][person.name]["cost_mean"],
                          "adherence": final["heldout"]["by_person"][person.name]["adherence_mean"],
                          "core": final["heldout"]["core"], "dev": final["dev"]["at_least_typed"],
                          "profile": PR.describe(profile)}), flush=True)
    print(json.dumps({"done": a.arm, "seconds": round(time.monotonic() - started, 1)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
