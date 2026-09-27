"""summarize.py: one table per question from a measure.py run directory (the base pass and every arm's persons).

    python3 locallm/dawnr_learning/summarize.py <out dir> [--md summary.md]

Reads only what measure.py wrote (<out>/base.json, <out>/<arm>/<person>/results.json)
and prints, per arm and person: the person's held-out style loss with the base
and with their adapter, the cross matrix (every adapter on every person's
style), held-out generation (edit cost, relative cost, adherence and the t
tool's verdicts), the learning curve on the fixed probe, the dev tiers, the
plain-code loss, and what each sleep's guards decided.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LOCALLM = Path(__file__).resolve().parent.parent
for _p in (str(LOCALLM), str(LOCALLM.parent / "t")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def load(out: Path) -> tuple[dict, dict]:
    base = json.loads((out / "base.json").read_text())
    arms = {}
    for arm_dir in sorted(p for p in out.iterdir() if p.is_dir()):
        people = {}
        for pdir in sorted(p for p in arm_dir.iterdir() if p.is_dir()):
            f = pdir / "results.json"
            if f.is_file():
                people[pdir.name] = json.loads(f.read_text())
        if people:
            arms[arm_dir.name] = people
    return base, arms


def fmt(x, nd=3):
    return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def summarize(out: Path) -> tuple[str, dict]:
    base, arms = load(out)
    lines, summary = [], {"base": {}, "arms": {}}
    bh = base["heldout"]
    summary["base"] = {"core": bh["core"], "n": bh["n"], "dev": base.get("dev"), "guard_loss": base["guard_loss"],
                       "canonical_val_loss": base["canonical_val_loss"], "style_loss": base["style_loss"],
                       "by_person": {k: {kk: v[kk] for kk in ("cost_mean", "rel_cost_mean", "adherence_mean",
                                                              "features")} for k, v in bh["by_person"].items()}}
    lines.append(f"# Per-person learning: {out.name}\n")
    lines.append(f"Base: held-out {bh['n']} prompts, t tool on its answers {bh['core']}; dev "
                 f"{(base.get('dev') or {}).get('tiers')}; plain-code loss {fmt(base['guard_loss'])}; canonical "
                 f"validation loss {fmt(base['canonical_val_loss'])}.\n")
    for arm, people in arms.items():
        s_arm = summary["arms"].setdefault(arm, {})
        lines.append(f"## {arm}\n")
        lines.append("| person | style loss base | adapter | own best of adapters | cost base | adapter | rel cost base "
                     "| adapter | adherence base | adapter | examples pass base | adapter | dev typed base | adapter "
                     "| plain-code loss | sleeps accepted |")
        lines.append("|" + "---|" * 16)
        for name, r in people.items():
            f = r["final"]
            own_b, own_a = base["style_loss"].get(name), f["style_loss"].get(name)
            bp, ap = bh["by_person"].get(name, {}), f["heldout"]["by_person"].get(name, {})
            accepted = sum(1 for s in r["sleeps"] if s.get("accepted"))
            s_arm[name] = {"style_loss": [own_b, own_a], "cost": [bp.get("cost_mean"), ap.get("cost_mean")],
                           "rel_cost": [bp.get("rel_cost_mean"), ap.get("rel_cost_mean")],
                           "adherence": [bp.get("adherence_mean"), ap.get("adherence_mean")],
                           "features": [bp.get("features"), ap.get("features")],
                           "examples_pass": [bh["core"]["examples_pass"], f["heldout"]["core"]["examples_pass"]],
                           "well_formed": [bh["core"]["well_formed"], f["heldout"]["core"]["well_formed"]],
                           "dev_typed": [(base.get("dev") or {}).get("at_least_typed"),
                                         (f.get("dev") or {}).get("at_least_typed")],
                           "guard_loss": [base["guard_loss"], f["guard_loss"]],
                           "canonical_val_loss": [base["canonical_val_loss"], f["canonical_val_loss"]],
                           "sleeps_accepted": accepted, "sleeps": len(r["sleeps"]), "curve": f.get("curve"),
                           "profile": f.get("profile"),
                           "cross": f["style_loss"], "sessions": [
                               {k: s[k] for k in ("session", "cost_mean", "kinds")} for s in r["sessions"]],
                           "sleep_records": [{k: s.get(k) for k in ("session", "steps", "best_step", "stop",
                                                                     "accepted", "behavior", "guard", "loss_base",
                                                                     "loss_adapter", "examples")}
                                             for s in r["sleeps"]]}
            # personal, not generic: on this person's style (a column), is their own adapter the lowest row?
            column = {row: people[row]["final"]["style_loss"].get(name) for row in people}
            own_best = (own_a <= min(v for v in column.values() if v is not None)
                        if own_a is not None and len(column) > 1 else None)
            s_arm[name]["own_adapter_best_on_own_style"] = own_best
            lines.append(f"| {name} | {fmt(own_b)} | {fmt(own_a)} | "
                         f"{'-' if own_best is None else ('yes' if own_best else 'no')} | "
                         f"{fmt(bp.get('cost_mean'), 1)} | {fmt(ap.get('cost_mean'), 1)} | "
                         f"{fmt(bp.get('rel_cost_mean'))} | {fmt(ap.get('rel_cost_mean'))} | "
                         f"{fmt(bp.get('adherence_mean'))} | {fmt(ap.get('adherence_mean'))} | "
                         f"{bh['core']['examples_pass']} | {f['heldout']['core']['examples_pass']} | "
                         f"{(base.get('dev') or {}).get('at_least_typed')} | {(f.get('dev') or {}).get('at_least_typed')} | "
                         f"{fmt(base['guard_loss'])} -> {fmt(f['guard_loss'])} | {accepted}/{len(r['sleeps'])} |")
        lines.append("")
        # the cross matrix: every adapter (row) on every person's style (column)
        names = list(people)
        lines.append("Cross matrix (held-out loss of each person's style, rows: whose adapter):\n")
        lines.append("| adapter | " + " | ".join(names) + " |")
        lines.append("|---|" + "---|" * len(names))
        lines.append("| base | " + " | ".join(fmt(base["style_loss"].get(n)) for n in names) + " |")
        for row in names:
            lines.append(f"| {row} | " + " | ".join(fmt(people[row]["final"]["style_loss"].get(n)) for n in names) + " |")
        lines.append("")
        lines.append("Learning curve on the fixed probe (own relative edit cost / adherence / examples pass), "
                     "after sleep 0 (base) .. N:\n")
        for name in names:
            curve = people[name]["final"].get("curve") or []
            lines.append(f"- {name}: " + "; ".join(
                f"{p['after_sleep']}: {fmt(p['rel_cost_mean'])} / {fmt(p['adherence_mean'])} / "
                f"{p['core']['examples_pass']}" for p in curve))
        lines.append("")
    return "\n".join(lines) + "\n", summary


def _person(summary, arm, name):
    return summary["arms"].get(arm, {}).get(name)


def check_predictions(summary: dict) -> list[str]:
    """Each registered prediction (locallm/PREDICT-learning-*.md) against the numbers, as a verdict line."""
    out = []
    names = ("ada", "bo", "cy", "di")

    def verdict(ok, text):
        out.append(f"- {'held' if ok else 'FALSIFIED'}: {text}")

    arms_a = [a for a in ("A-s1", "A-s2") if a in summary["arms"]]
    rows = [(a, n, _person(summary, a, n)) for a in arms_a for n in names if _person(summary, a, n)]
    if rows:
        cuts = sorted(1 - r["style_loss"][1] / r["style_loss"][0] for _a, _n, r in rows)
        median = cuts[len(cuts) // 2] if len(cuts) % 2 else (cuts[len(cuts) // 2 - 1] + cuts[len(cuts) // 2]) / 2
        worse = [f"{a}/{n}" for a, n, r in rows if r["style_loss"][1] >= r["style_loss"][0]]
        verdict(not worse and median >= 0.20, f"A1 own style loss lower for every person-seed, median cut >= 20%: "
                f"median {median:.0%}, not lower: {worse or 'none'} ({len(rows)} person-seeds)")
        best = sum(1 for _a, _n, r in rows if r.get("own_adapter_best_on_own_style"))
        verdict(best >= 7 * len(rows) / 8, f"A2 own adapter lowest on own style in >= 7 of 8: {best} of {len(rows)}")
        for a in arms_a:
            gains = {n: _person(summary, a, n)["adherence"][1] - _person(summary, a, n)["adherence"][0]
                     for n in names if _person(summary, a, n)}
            big = [n for n, g in gains.items() if g >= 0.1]
            verdict(len(big) <= 1, f"A3 ({a}) adherence gain < 0.1 for at least 3 of 4: gains "
                    + ", ".join(f"{n} {g:+.3f}" for n, g in gains.items()))
        bad = []
        for a, n, r in rows:
            if r["examples_pass"][1] < r["examples_pass"][0] - 3:
                bad.append(f"{a}/{n} held-out pass {r['examples_pass'][0]}->{r['examples_pass'][1]}")
            if r["dev_typed"][1] is not None and r["dev_typed"][1] < r["dev_typed"][0] - 5:
                bad.append(f"{a}/{n} dev typed {r['dev_typed'][0]}->{r['dev_typed'][1]}")
            if r["guard_loss"][1] > r["guard_loss"][0] + 0.05:
                bad.append(f"{a}/{n} plain-code loss {r['guard_loss'][0]:.3f}->{r['guard_loss'][1]:.3f}")
        verdict(not bad, f"A4 not worse (held-out pass >= base-3, dev typed >= base-5, plain code <= base+0.05): "
                f"{'; '.join(bad) or 'all within'}")
        stopped = sum(1 for _a, _n, r in rows for s in r["sleep_records"] if s.get("stop") == "behavior_guard")
        total = sum(len(r["sleep_records"]) for _a, _n, r in rows)
        verdict(stopped >= 4, f"A5 the behaviour guard stops >= 4 of the sleeps: {stopped} of {total}")
    if "B-s1" in summary["arms"]:
        b = {n: _person(summary, "B-s1", n) for n in names if _person(summary, "B-s1", n)}
        gains = {n: r["adherence"][1] - r["adherence"][0] for n, r in b.items()}
        verdict(sum(g >= 0.2 for g in gains.values()) >= 3, "B6 adherence gain >= 0.2 for at least 3 of 4: "
                + ", ".join(f"{n} {g:+.3f}" for n, g in gains.items()))
        drops = {n: r["examples_pass"][1] - r["examples_pass"][0] for n, r in b.items()}
        verdict(sum(d <= -5 for d in drops.values()) >= 3, "B7 held-out pass falls by >= 5 for at least 3 of 4: "
                + ", ".join(f"{n} {d:+d}" for n, d in drops.items()))
        costs = {n: r["cost"][1] - r["cost"][0] for n, r in b.items()}
        verdict(sum(c > 0 for c in costs.values()) >= 3, "B8 edit cost higher than base for at least 3 of 4: "
                + ", ".join(f"{n} {c:+.1f}" for n, c in costs.items()))
    for arm in ("P2", "P"):
        if arm not in summary["arms"]:
            continue
        p = {n: _person(summary, arm, n) for n in names if _person(summary, arm, n)}
        gains = {n: r["adherence"][1] - r["adherence"][0] for n, r in p.items()}
        verdict(all(g >= 0.3 for g in gains.values()), f"P1 ({arm}) adherence gain >= 0.3 for all 4: "
                + ", ".join(f"{n} {g:+.3f}" for n, g in gains.items()))
        cuts = {n: 1 - r["rel_cost"][1] / r["rel_cost"][0] for n, r in p.items()}
        verdict(all(c >= (0.15 if n == "ada" else 0.30) for n, c in cuts.items()),
                f"P2 ({arm}) relative cost cut >= 30% (ada 15%): " + ", ".join(f"{n} {c:.0%}" for n, c in cuts.items()))
        same = all(r["examples_pass"][1] == r["examples_pass"][0] and r["dev_typed"][1] == r["dev_typed"][0]
                   for r in p.values())
        verdict(same, f"P3 ({arm}) held-out pass and dev typed exactly the base's: " + ", ".join(
            f"{n} {r['examples_pass'][1]}/{r['dev_typed'][1]}" for n, r in p.items()))
        from dawnr_learning import persons as P
        wrong, undecided = [], []
        for n, r in p.items():
            truth = P.PERSONS[n]
            decided = {k: v["value"] for k, v in ((r.get("profile") or {}).get("inferred") or {}).items()}
            wrong += [f"{n}.{dim}={value}" for dim, value in decided.items() if value != getattr(truth, dim)]
            undecided += [f"{n}.{dim}" for dim in ("naming", "semicolons", "indent", "tool") if dim not in decided]
        verdict(not wrong and not undecided, f"P4 ({arm}) every decided dimension true, the four main ones "
                f"decided: wrong {wrong or 'none'}, undecided {undecided or 'none'}")
    if "C-s1" in summary["arms"]:
        c = {n: _person(summary, "C-s1", n) for n in names if _person(summary, "C-s1", n)}
        stopped = sum(1 for r in c.values() for s in r["sleep_records"]
                      if s.get("stop") == "behavior_guard" or s.get("accepted") is False)
        total = sum(len(r["sleep_records"]) for r in c.values())
        verdict(stopped >= 12, f"C1 the 24-prompt guard stops or refuses >= 12 of 16 sleeps: {stopped} of {total}")
        bad = [f"{n} pass {r['examples_pass'][0]}->{r['examples_pass'][1]}, dev {r['dev_typed'][0]}->{r['dev_typed'][1]}"
               for n, r in c.items() if r["examples_pass"][1] < r["examples_pass"][0] - 3
               or r["dev_typed"][1] < r["dev_typed"][0] - 5]
        verdict(not bad, f"C2 not worse (held-out pass >= base-3, dev typed >= base-5): {'; '.join(bad) or 'all within'}")
        gains = {n: r["adherence"][1] - r["adherence"][0] for n, r in c.items()}
        verdict(all(g < 0.1 for g in gains.values()), "C3 adherence gain < 0.1 for every person: "
                + ", ".join(f"{n} {g:+.3f}" for n, g in gains.items()))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--md", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)
    text, summary = summarize(a.out)
    text += "## The registered predictions\n\n" + "\n".join(check_predictions(summary)) + "\n"
    print(text)
    if a.md:
        a.md.write_text(text, encoding="utf-8")
    if a.json:
        a.json.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
