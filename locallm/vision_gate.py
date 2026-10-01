"""vision_gate.py: a claim that an object is in an image is shown only when an independent detector also
finds it (2026-10-01).

    python3 locallm/vision_gate.py --answers answers.jsonl --images DIR --out scored.jsonl --report report.json

The code gate shows an answer only when something that did not write it agrees (the provers, the tests, a
second program). For images: Woodpecker (Yin et al., arXiv:2310.16045) validates each object an MLLM claims
with an open-set detector before the claim stands, training-free. Here the claim is POPE's yes/no answer
(locallm/vision_pope.py's rows); the independent artifact is OWLv2 (google/owlv2-base-patch16-ensemble,
Apache-2.0; arXiv:2306.09683), asked for "a photo of a <object>" with every object POPE asks about that image
in one pass; its evidence is the highest score any box gets for the object. A "yes" is SHOWN when the model
says yes and the detector's evidence reaches the threshold; otherwise the gate says it cannot confirm. Nothing
is rewritten. POPE's metrics for the model alone, the detector alone, and the gate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import vision_pope  # noqa: E402

THRESHOLDS = (0.1, 0.2, 0.3)


def object_of(question: str) -> str:
    """'Is there a dining table in the image?' -> 'dining table' (POPE's own question form)."""
    m = re.match(r"Is there an? (.+?) in the image\??$", question.strip())
    return m.group(1) if m else question


def gate_metrics(rows: list[dict], threshold: float) -> dict:
    labels = [r["label"] for r in rows]
    model = [r["parsed"] for r in rows]
    detector = ["yes" if r["evidence"] >= threshold else "no" for r in rows]
    gate = ["yes" if m == "yes" and d == "yes" else "no" for m, d in zip(model, detector)]
    out = {"threshold": threshold, "the model": vision_pope.metrics(labels, model),
           "the detector": vision_pope.metrics(labels, detector), "the gate": vision_pope.metrics(labels, gate)}
    tp_model = out["the model"]["TP"]
    out["the gate keeps of the model's true yes"] = round(out["the gate"]["TP"] / tp_model, 4) if tp_model else None
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--answers", type=Path, required=True)
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--threads", type=int, default=8)
    a = ap.parse_args(argv)
    import torch
    from PIL import Image
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    torch.set_num_threads(a.threads)
    name = "google/owlv2-base-patch16-ensemble"
    processor = Owlv2Processor.from_pretrained(name)
    model = Owlv2ForObjectDetection.from_pretrained(name).eval()
    rows = [json.loads(l) for l in a.answers.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_image = defaultdict(list)
    for r in rows:
        by_image[r["image"]].append(r)
    done = {}
    if a.out.exists():
        for l in a.out.read_text(encoding="utf-8").splitlines():
            if l.strip():
                x = json.loads(l)
                done[x["question_id"]] = x
    started = time.monotonic()
    with a.out.open("a", encoding="utf-8") as f, torch.no_grad():
        for k, (image, rs) in enumerate(sorted(by_image.items())):
            todo = [r for r in rs if r["question_id"] not in done]
            if not todo:
                continue
            objects = sorted({object_of(r["question"]) for r in todo})
            img = Image.open(a.images / image).convert("RGB")
            inputs = processor(text=[[f"a photo of a {o}" for o in objects]], images=img, return_tensors="pt")
            logits = model(**inputs).logits[0]                      # (boxes, queries)
            best = torch.sigmoid(logits).max(0).values.tolist()     # the best box's score for each query
            evidence = dict(zip(objects, best))
            for r in todo:
                x = dict(r, object=object_of(r["question"]), evidence=round(float(evidence[object_of(r["question"])]), 5))
                f.write(json.dumps(x) + "\n")
                done[x["question_id"]] = x
            if (k + 1) % 50 == 0:
                print(f"vision_gate: {k + 1}/{len(by_image)} images ({time.monotonic() - started:.0f} s)", flush=True)
    scored = [done[r["question_id"]] for r in rows if r["question_id"] in done]
    report = {"questions": len(scored), "detector": name, "by threshold": [gate_metrics(scored, t) for t in THRESHOLDS],
              "seconds": round(time.monotonic() - started)}
    a.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({t["threshold"]: {"gate precision": t["the gate"]["precision"], "keeps": t["the gate keeps of the model's true yes"]}
                      for t in report["by threshold"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
