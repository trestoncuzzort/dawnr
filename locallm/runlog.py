"""runlog.py — an append-only record of every run, so evidence accumulates.

    python runlog.py              # summary of everything recorded
    python runlog.py --kind train # just training runs
    python runlog.py --last 20    # the most recent 20
    python runlog.py --review     # the digest to hand a reviewer

Every training run, experiment, benchmark and leakage scan appends one line to
runs.jsonl. Nothing is ever overwritten or deleted by this module.

Why: result files that get overwritten by the next run cannot show a trend, and
a number quoted from memory is not evidence. Twenty runs recorded with their
configuration, their machine and their timing are reviewable; the same twenty
runs printed to a terminal that has since been closed are not.

What a record deliberately includes:
  - a fingerprint of the CORPUS, so runs on different text are never compared
  - a fingerprint of the SPLIT, because the corpus fingerprint cannot tell two
    runs on different holdouts apart, and every prereg here assumes they match
  - the DEVICE and model configuration, so a slower number is attributable
  - the DATA device where it differs, because a corpus that fell back to host
    memory changes both the ms/step and the batch sequence
  - wall clock and ms/step, so a change in speed is visible
  - the leakage verdict where one applies, so a val loss is never read without
    knowing whether it means anything
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = Path(os.environ.get("LOCALLM_RUN_LOG", HERE / "runs.jsonl"))


def corpus_fingerprint(text: str) -> dict:
    return {"chars": len(text), "vocab": len(set(text)),
            "sha1": hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:12]}


def split_fingerprint(val_frac: float, seed: int, val_text: str | None) -> dict:
    """Identity of the HOLDOUT, which corpus_fingerprint cannot carry.

    THE CORPUS IS NOT THE SPLIT. corpus_fingerprint hashes the text, so two
    runs that held back completely different validation sets record the same
    fingerprint: measured on a 17,298-character corpus, holdouts of 1,728,
    1,688 and 3,458 characters (seed 1337, seed 4242, val_frac 0.2) all
    recorded chars 17298 / vocab 22 / sha1 ce31645cb012. Meanwhile both preregs
    assert every arm was scored on an IDENTICAL holdout, and nothing in
    runs.jsonl could confirm or refute it.

    The seed and val_frac alone would not do it either: they are the REQUEST,
    and group_split's answer to the same request changes if the corpus changes
    or the splitter does. The hash of the val text is the answer, so the record
    carries both.

    val_text is None on the ungrouped path, where the split is positional over
    tokens and there is no held-out TEXT to hash. That records as None rather
    than as the hash of an empty string, because "there was no text" and "the
    text was empty" are different facts.
    """
    return {"val_frac": val_frac, "seed": seed,
            "val_chars": None if val_text is None else len(val_text),
            "val_sha1": None if val_text is None else
            hashlib.sha1(val_text.encode("utf-8", "ignore")).hexdigest()[:12]}


def record(kind: str, **fields) -> None:
    """Append one run. Never raises into the caller: a logging failure must not
    take down a training run that otherwise succeeded."""
    try:
        row = {"ts": datetime.now().isoformat(timespec="seconds"), "kind": kind}
        row.update(fields)
        row.setdefault("host", platform.node())
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception as e:                      # noqa: BLE001
        print(f"[runlog] could not record this run: {e}", file=sys.stderr)


def load() -> list[dict]:
    if not LOG.is_file():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue                            # a torn line must not lose the rest
    return out


def _g(row: dict, *path, default=""):
    cur = row
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def summary(rows: list[dict]) -> None:
    if not rows:
        print("No runs recorded yet. Train something, or run bench_device.py.")
        return

    kinds = {}
    for r in rows:
        kinds.setdefault(r.get("kind", "?"), []).append(r)
    print(f"{len(rows)} runs recorded in {LOG.name}")
    print("  " + "  ".join(f"{k}: {len(v)}" for k, v in sorted(kinds.items())))
    corpora = {_g(r, "corpus", "sha1") for r in rows if _g(r, "corpus", "sha1")}
    if len(corpora) > 1:
        print(f"  NOTE: {len(corpora)} different corpora appear here. Runs on "
              f"different text are not comparable.")
    print()

    train = kinds.get("train", [])
    if train:
        print("TRAINING RUNS")
        print(f"  {'when':16} {'device':6} {'model':>16} {'steps':>6} "
              f"{'train':>7} {'val':>7} {'leak':>6} {'wall':>7}")
        print("  " + "-" * 78)
        for r in train[-40:]:
            cfg = r.get("config", {})
            model = f"{cfg.get('n_layer','?')}L{cfg.get('n_head','?')}H{cfg.get('n_embd','?')}D"
            val = _g(r, "metrics", "val_loss", default=None)
            print(f"  {r.get('ts','')[5:16]:16} {r.get('device','?'):6} {model:>16} "
                  f"{str(cfg.get('steps','?')):>6} "
                  f"{_g(r,'metrics','train_loss',default=float('nan')):7.4f} "
                  f"{(f'{val:.4f}' if isinstance(val,(int,float)) else '   -  '):>7} "
                  f"{str(_g(r,'leakage','verdict',default='-'))[:6]:>6} "
                  f"{_g(r,'metrics','wall_s',default=0):6.0f}s")
        print()

    for kind, label in (("experiment", "EXPERIMENTS"), ("benchmark", "BENCHMARKS"),
                        ("leakage", "LEAKAGE SCANS")):
        group = kinds.get(kind, [])
        if not group:
            continue
        print(label)
        for r in group[-15:]:
            if kind == "experiment":
                # A WITHHELD VERDICT IS NOT A MISSING ONE. An experiment whose
                # holdout cannot carry a claim now records verdict null and the
                # reason beside it (baselines.withhold_claims), and printing the
                # null as an empty column would file it with the rows that
                # simply predate the field.
                v = _g(r, "metrics", "verdict", default=None)
                why = _g(r, "metrics", "ineligible_reason", default=None)
                if v is None and why:
                    v = f"VERDICT WITHHELD -- {why}"
                print(f"  {r.get('ts','')[5:16]}  {r.get('name','?'):22} "
                      f"{v if v is not None else ''}")
            elif kind == "benchmark":
                res = r.get("results", {})
                best = ", ".join(f"{k.split('/')[-1]} {v.get('ms_per_step','?')}ms"
                                 for k, v in list(res.items())[:3])
                print(f"  {r.get('ts','')[5:16]}  {r.get('device','?'):6} {best}")
            else:
                # THE SIGNAL THAT DECIDED, not the first one printed. The
                # verdict is the worst of three signals, and this column showed
                # the CONTENT fraction alone: a holdout every document of which
                # is a verbatim copy of a training document reads
                # `CONTAMINATED  content 0.00%`, because copies shorter than a
                # 50-character fingerprint are invisible to the content arm.
                # Rows written before leakage.Report.record() existed carry no
                # reason at all; that is said outright rather than presenting
                # their content fraction as though it were the deciding one.
                why = _g(r, "leakage", "reason", default="")
                if not why:
                    frac = _g(r, "leakage", "content_frac", default=None)
                    why = ("deciding signal not recorded"
                           + (f" (content {frac:.2%})"
                              if isinstance(frac, (int, float)) else ""))
                print(f"  {r.get('ts','')[5:16]}  {_g(r,'leakage','verdict'):13} "
                      f"{_g(r,'corpus','chars',default=0):>9,} chars  {why}")
        print()


def review(rows: list[dict]) -> None:
    """The digest meant for someone who did not watch any of it happen."""
    print("=" * 70)
    print("RUN LOG REVIEW DIGEST")
    print("=" * 70)
    if not rows:
        print("Nothing recorded.")
        return
    print(f"records      {len(rows)}")
    print(f"first        {rows[0].get('ts','?')}")
    print(f"last         {rows[-1].get('ts','?')}")
    devices = sorted({r.get("device", "?") for r in rows} - {"?"})
    print(f"devices      {', '.join(devices) or 'not recorded'}")
    # data_device, where it was recorded: a run whose corpus did not fit and
    # fell back to host memory cut its batches on the CPU and drew them from
    # the CPU random stream. Its ms/step is not comparable with a run that
    # fitted, and its batch sequence is not the same one either.
    moved = sorted({f"{r.get('device', '?')} model / {r['data_device']} corpus"
                    for r in rows if r.get("data_device")
                    and r["data_device"] != r.get("device")})
    if moved:
        print(f"             {', '.join(moved)} — corpus not on the training "
              f"device, so ms/step and batch order differ from a run that fitted")

    corpora = {_g(r, "corpus", "sha1"): _g(r, "corpus", "chars")
               for r in rows if _g(r, "corpus", "sha1")}
    print(f"corpora      {len(corpora)}  " +
          ", ".join(f"{k} ({v:,} chars)" for k, v in list(corpora.items())[:4]))

    # THE HOLDOUT IS NOT THE CORPUS. This digest used to point at the corpus
    # fingerprint and the config and stop there, and both can be identical
    # across two runs that held back completely different validation text:
    # measured on a 17,298-character corpus, holdouts of 1,728, 1,688 and 3,458
    # characters all recorded chars 17298 / vocab 22 / sha1 ce31645cb012. The
    # reader this page is written for did not watch any of it happen and cannot
    # tell those apart from the corpus line, so the split gets its own.
    #
    # AND THE HOLDOUT IS NOT THE REQUEST EITHER. The key here was (val_sha1,
    # val_chars, val_frac, seed), which is the content AND the two fields
    # split_fingerprint's own docstring calls the REQUEST. val_frac and seed do
    # not identify a holdout, because group_split answers different requests
    # with the same text: measured over 320 grouped splits of this project's own
    # sources, the markdown corpus returns the identical 15-character holdout
    # (val_sha1 51c7fa5fba92) for val_frac 0.0002 at seed 4242 and at seed
    # 20260901, and an identical 3-character one at four different seeds. So
    # two runs scored on byte-identical validation text under different seeds
    # counted as two holdouts and printed the warning below, which is false, and
    # false in the expensive direction -- it tells a reviewer to discard a
    # comparison that is in fact sound. Measured on the bytes before this
    # change: two rows, val_sha1 ce31645cb012 / 1,728 chars, seeds 1337 and
    # 4242, reported "holdouts 2 named" and warned.
    #
    # Identity is now the CONTENT alone. val_frac and seed stay on the record
    # and stay on the page -- they say what was asked for, and two requests
    # answered with the same text is worth seeing -- they just do not get to
    # split one holdout into two.
    #
    # AND MATCHING HOLDOUT TEXT IS NOT COMPARABILITY. The line under a shared
    # holdout used to end "so these runs are comparable", which is a claim about
    # the whole run made from one of the three things it needs. Two runs on
    # DIFFERENT corpora can share a held-out document -- the key here is the
    # hash of the val text, and nothing about it involves the corpus or the
    # config. Measured on two fabricated rows, corpus sha1 aaaaaaaaaaaa
    # (10,000 chars, 4L4H256D, 2000 steps) and bbbbbbbbbbbb (90,000 chars,
    # 6L6H384D, 8000 steps), both recording val_sha1 deadbeefcafe: this digest
    # printed "corpora 2" four lines above and "so these runs are comparable"
    # underneath, and the closing paragraph of the same page tells the reader
    # that same corpus is not same split and same split is not same
    # configuration. So the line now states only what was checked -- the
    # held-out TEXT matched -- and counts the corpora and configurations inside
    # the group so the reader can see the rest for himself.
    holdout_rows = [r for r in rows if r.get("kind") in ("train", "experiment")]
    if holdout_rows:
        named: dict[tuple, dict] = {}
        unnamed = 0
        for r in holdout_rows:
            sf = r.get("split_fingerprint")
            sha = sf.get("val_sha1") if isinstance(sf, dict) else None
            if not sha:
                # No split recorded, a positional split with no held-out TEXT
                # to hash, or arms that disagreed about which holdout they had.
                unnamed += 1
                continue
            key = (sha, sf.get("val_chars"))
            e = named.setdefault(key, {"runs": 0, "requests": [],
                                       "corpora": [], "configs": []})
            e["runs"] += 1
            for field, value in (
                    ("requests", (sf.get("val_frac"), sf.get("seed"))),
                    ("corpora", _g(r, "corpus", "sha1", default=None)),
                    ("configs", json.dumps(r.get("config"), sort_keys=True,
                                           default=str))):
                if value not in e[field]:
                    e[field].append(value)
        print(f"holdouts     {len(named)} named"
              + (f", {unnamed} of {len(holdout_rows)} run(s) name none"
                 if unnamed else ""))
        for (sha, chars), e in list(named.items())[:4]:
            size = f"{chars:,} chars" if isinstance(chars, int) else f"{chars} chars"
            asked = "; ".join(f"val_frac {vf}, seed {sd}" for vf, sd in e["requests"])
            print(f"             {sha}  {size}, asked for as {asked}"
                  f"   {e['runs']} run(s)")
            if len(e["requests"]) > 1:
                print(f"             {'':12}   ^ {len(e['requests'])} different "
                      f"requests, ONE holdout: the same held-out TEXT came back "
                      f"each time")
            if e["runs"] > 1:
                spans = (f"{len(e['corpora'])} corpus/corpora and "
                         f"{len(e['configs'])} configuration(s)")
                same = len(e["corpora"]) == 1 and len(e["configs"]) == 1
                print(f"             {'':12}   ^ that is the HOLDOUT TEXT "
                      f"matching, and nothing else: these {e['runs']} run(s) "
                      f"span {spans}"
                      + (", so what remains to check is the endpoint itself."
                         if same else
                         " -- a val loss from one does not compare with a val "
                         "loss from another."))
        if len(named) > 1:
            print("  WARNING: these runs were NOT all scored on the same "
                  "held-out text. A val loss from one does not compare with a "
                  "val loss from another, however well their corpus "
                  "fingerprints match.")
        if unnamed:
            print(f"  {unnamed} run(s) do not name a single holdout — no split "
                  f"recorded, a positional split with no held-out text to hash, "
                  f"or arms that disagreed — so no val loss on those rows can "
                  f"be attributed to one.")

    train = [r for r in rows if r.get("kind") == "train"]
    if train:
        losses = [(_g(r, "metrics", "train_loss", default=None), r) for r in train]
        losses = [(l, r) for l, r in losses if isinstance(l, (int, float))]
        if losses:
            best_l, best_r = min(losses, key=lambda t: t[0])
            cfg = best_r.get("config", {})
            print(f"\nbest train loss  {best_l:.4f}  "
                  f"({cfg.get('n_layer')}L{cfg.get('n_head')}H{cfg.get('n_embd')}D, "
                  f"{cfg.get('steps')} steps, {best_r.get('device')}, "
                  f"{best_r.get('ts','')[:16]})")
        # ONLY A RECORDED "CLEAN" COUNTS AS TRUSTWORTHY. The empty string used
        # to be allowlisted here beside "CLEAN", which meant a run whose scan
        # CRASHED (train.py wrote {} and the verdict came back "") was reported
        # as trustworthy, and so was a row from a version that never scanned at
        # all. Absence of a verdict is not evidence of a clean split; it is
        # absence of evidence, and this digest exists for someone who did not
        # watch any of it happen and cannot tell the two apart. The reasons are
        # named rather than summed, so "2 of 3" does not hide what the 2 were.
        reasons = Counter(_g(r, "leakage", "verdict", default="") or "not recorded"
                          for r in train)
        untrusted = sum(n for v, n in reasons.items() if v != "CLEAN")
        detail = ", ".join(f"{v} {n}" for v, n in sorted(reasons.items())
                           if v != "CLEAN")
        print(f"runs whose val loss is NOT trustworthy: {untrusted} of {len(train)}"
              + (f"   ({detail})" if detail else ""))

    print("\nWhat this digest does NOT establish: that any two runs above are")
    print("comparable. Check the corpus fingerprint, the HOLDOUT above it and")
    print("the config before reading a difference between two lines as a")
    print("result. Same corpus is not same split, and same split is not same")
    print("configuration.")
    print("=" * 70)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", help="filter: train, experiment, benchmark, leakage")
    ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--review", action="store_true", help="digest for a reviewer")
    ap.add_argument("--json", action="store_true", help="dump raw records")
    args = ap.parse_args()

    rows = load()
    if args.kind:
        rows = [r for r in rows if r.get("kind") == args.kind]
    if args.last:
        rows = rows[-args.last:]

    if args.json:
        print(json.dumps(rows, indent=2))
    elif args.review:
        review(rows)
    else:
        summary(rows)


if __name__ == "__main__":
    main()
