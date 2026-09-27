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
from pathlib import Path


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
                           "cross": f["style_loss"], "sessions": [
                               {k: s[k] for k in ("session", "cost_mean", "kinds")} for s in r["sessions"]],
                           "sleep_records": [{k: s.get(k) for k in ("session", "steps", "best_step", "stop",
                                                                     "accepted", "behavior", "guard", "loss_base",
                                                                     "loss_adapter", "examples")}
                                             for s in r["sleeps"]]}
            others = {k: v for k, v in f["style_loss"].items()}
            lines.append(f"| {name} | {fmt(own_b)} | {fmt(own_a)} | "
                         f"{'yes' if own_a is not None and own_a <= min(others.values()) else 'no'} | "
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--md", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)
    text, summary = summarize(a.out)
    print(text)
    if a.md:
        a.md.write_text(text, encoding="utf-8")
    if a.json:
        a.json.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
