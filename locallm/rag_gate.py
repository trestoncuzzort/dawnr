"""rag_gate.py: show a reply drawn from documents only when the documents support it (2026-10-01).

    python3 locallm/rag_gate.py score --weights alignscore-large.safetensors --data en.json \\
        --answers answers-0.4.jsonl [...] --out scores.jsonl
    python3 locallm/rag_gate.py report --data en.json --scores scores.jsonl [--answers ...] [--json r.json]

The check is AlignScore (Zha et al., ACL 2023, arXiv:2305.16739; github.com/yuh-zha/AlignScore, MIT;
checkpoints huggingface.co/yzha/AlignScore, MIT), `nli_sp` mode, ported from its src/alignscore/inference.py
`inference_per_example`: the context is split into sentences (nltk `sent_tokenize`) and joined into chunks of
about 350 words, the claim into sentences; every (chunk, claim sentence) pair goes through RoBERTa-large and
the three-way head, and the probability of ALIGNED (index 0) is the pair's score; the score is the mean over
claim sentences of the best chunk. Two differences, neither in the arithmetic: the checkpoint is read without
PyTorch Lightning (`export` keeps `base_model.*` and `tri_layer.*` of its state_dict, loaded weights-only), and
batches are padded to their longest pair rather than to 512 (the attention mask makes the two the same).

Here the context is the documents the question was given (joined by newlines, as the model saw them,
locallm/rag_rgb.py) and the claim is the reply. The rule registered in
locallm/PREDICT-2026-10-01-retrieval-on-the-base.md: shown when the reply does not say the information is
insufficient and its score is at least 0.5.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import rag_rgb  # noqa: E402

THRESHOLD = 0.5
REPORTED = (0.3, 0.5, 0.7, 0.9)
WORDS_A_CHUNK = 350


def sentences(text: str) -> list[str]:
    from nltk.tokenize import sent_tokenize
    return sent_tokenize(text)


def chunks(premise: str, split=sentences) -> list[str]:
    """inference_per_example: sentences grouped so a chunk holds about 350 words."""
    sents = split(premise) or [""]
    n_chunk = len(premise.strip().split()) // WORDS_A_CHUNK + 1
    n_chunk = max(len(sents) // n_chunk, 1)
    return [" ".join(sents[i:i + n_chunk]) for i in range(0, len(sents), n_chunk)]


def alignscore(premise: str, claim: str, align, split=sentences) -> float:
    """mean over claim sentences of the best chunk's P(ALIGNED); align(premises, hypos) -> list of floats."""
    parts = chunks(premise, split)
    claims = split(claim)
    if not claims:
        return 0.0                                     # an empty reply claims nothing and is not shown
    pre = [p for p in parts for _ in claims]
    hyp = [c for _ in parts for c in claims]
    probs = align(pre, hyp)
    best = [max(probs[i * len(claims) + j] for i in range(len(parts))) for j in range(len(claims))]
    return sum(best) / len(best)


class Aligner:
    """RoBERTa-large and AlignScore's three-way head, from the exported weights."""

    def __init__(self, weights: Path, device: str = "cpu", batch_size: int = 16, base: str = "FacebookAI/roberta-large"):
        import torch
        from safetensors.torch import load_file
        from transformers import AutoTokenizer, RobertaConfig, RobertaModel
        self.torch, self.device, self.batch_size = torch, device, batch_size
        cfg = RobertaConfig.from_pretrained(base)
        self.tok = AutoTokenizer.from_pretrained(base)
        self.model = RobertaModel(cfg)
        self.tri = torch.nn.Linear(cfg.hidden_size, 3)
        sd = load_file(str(weights))
        missing, unexpected = self.model.load_state_dict(
            {k[len("base_model."):]: v for k, v in sd.items() if k.startswith("base_model.")}, strict=False)
        assert not [m for m in missing if "position_ids" not in m], missing
        assert not unexpected, unexpected
        self.tri.load_state_dict({k[len("tri_layer."):]: v for k, v in sd.items() if k.startswith("tri_layer.")})
        self.model.to(device).eval(); self.tri.to(device).eval()

    def __call__(self, premises: list[str], hypos: list[str]) -> list[float]:
        torch, out = self.torch, []
        for i in range(0, len(premises), self.batch_size):
            p, h = premises[i:i + self.batch_size], hypos[i:i + self.batch_size]
            try:
                b = self.tok(p, h, truncation="only_first", padding=True, max_length=512, return_tensors="pt")
            except Exception:                          # inference.py: the claim alone is too long
                b = self.tok(p, h, truncation=True, padding=True, max_length=512, return_tensors="pt")
            b = {k: v.to(self.device) for k, v in b.items()}
            with torch.no_grad():
                pooled = self.model(**b).pooler_output
                out += torch.softmax(self.tri(pooled), dim=-1)[:, 0].float().cpu().tolist()
        return out


def export(ckpt: Path, out: Path) -> None:
    import torch
    from safetensors.torch import save_file
    sd = torch.load(ckpt, map_location="cpu", weights_only=True, mmap=True)["state_dict"]
    keep = {k: v.contiguous() for k, v in sd.items() if k.startswith(("base_model.", "tri_layer.")) and "position_ids" not in k}
    save_file(keep, str(out))


def rejected(reply: str) -> bool:
    return "insufficient information" in reply                # RGB's own rejection rule


def report(data: dict, rows: list[dict], scores: dict) -> dict:
    """Per noise rate: replies, rejections, right; then what each threshold shows and how much of it is right."""
    by_rate: dict = {}
    for r in rows:
        by_rate.setdefault((r["noise_rate"], r["passage_num"]), []).append(r)
    out = {}
    for (rate, pn), rs in sorted(by_rate.items()):
        name = "closed" if pn == 0 else str(rate)
        right = [rag_rgb.right(r["label"], rate) for r in rs]
        answered = [r for r in rs if not rejected(r["prediction"])]
        sec = {"replies": len(rs), "rejected": len(rs) - len(answered), "right": sum(right)}
        if rate == 1:
            holds = [r for r in answered if 1 in rag_rgb.checkanswer(r["prediction"], data[r["id"]]["answer"])]
            sec["answered, holding the true answer"] = len(holds)
            sec["answered, holding neither"] = len(answered) - len(holds)
        if pn:
            for t in REPORTED:
                shown = [r for r in answered if scores.get((r["id"], rate), 0.0) >= t]
                if rate == 1:
                    sec[f"shown at {t}"] = len(shown)
                else:
                    ok = [r for r in shown if rag_rgb.right(r["label"], rate)]
                    sec[f"shown at {t}"] = len(shown)
                    sec[f"shown and right at {t}"] = len(ok)
        out[name] = sec
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("--ckpt", type=Path, required=True); e.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("score")
    s.add_argument("--weights", type=Path, required=True); s.add_argument("--data", type=Path, required=True)
    s.add_argument("--answers", type=Path, nargs="+", required=True); s.add_argument("--out", type=Path, required=True)
    s.add_argument("--device", default="cpu"); s.add_argument("--threads", type=int, default=0)
    s.add_argument("--base", default="FacebookAI/roberta-large", help="RoBERTa-large's config and tokenizer: hub id or a folder")
    r = sub.add_parser("report")
    r.add_argument("--data", type=Path, required=True); r.add_argument("--scores", type=Path, required=True)
    r.add_argument("--answers", type=Path, nargs="+", required=True); r.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "export":
        export(a.ckpt, a.out); return 0
    data = {d["id"]: d for d in (json.loads(l) for l in a.data.read_text(encoding="utf-8").splitlines() if l.strip())}
    rows = [json.loads(l) for f in a.answers for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [x for x in rows if not x.get("error")]
    if a.cmd == "score":
        if a.threads:
            import torch; torch.set_num_threads(a.threads)
        done = set()
        if a.out.exists():
            done = {(x["id"], x["noise_rate"]) for x in map(json.loads, a.out.read_text().splitlines()) if x}
        align = Aligner(a.weights, a.device, base=a.base)
        with a.out.open("a", encoding="utf-8") as f:
            for x in rows:
                if x["passage_num"] == 0 or rejected(x["prediction"]) or (x["id"], x["noise_rate"]) in done:
                    continue
                docs = rag_rgb.select(data[x["id"]], x["noise_rate"], x["passage_num"])
                sc = alignscore("\n".join(docs), x["prediction"], align)
                f.write(json.dumps({"id": x["id"], "noise_rate": x["noise_rate"], "score": sc}) + "\n"); f.flush()
        return 0
    scores = {(x["id"], x["noise_rate"]): x["score"] for x in map(json.loads, a.scores.read_text().splitlines()) if x}
    rep = report(data, rows, scores)
    print(json.dumps(rep, indent=1))
    if a.json:
        a.json.write_text(json.dumps(rep, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
