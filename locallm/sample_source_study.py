"""Descriptive, fixed, post-hoc completions; not a correctness benchmark."""
import argparse
import json
from pathlib import Path

from checkpoint import load_checkpoint, sample

PROMPTS = {
    "python": "def count_positive(values):\n    \"\"\"Return how many elements are greater than zero.\"\"\"\n",
    "rust": "pub fn count_positive(values: &[i32]) -> usize {\n",
    "lean": "theorem add_zero_demo (n : Nat) : n + 0 = n := by\n",
    "documentation": "A sequence is an ordered collection of elements. To find its length,\n",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("preserve existing samples; choose a new output")
    import torch
    torch.set_num_threads(4)
    with args.out.open("x") as stream:
        for seed in (1337, 7, 42):
            for architecture in ("modern", "gpt"):
                model, tokenizer, _ = load_checkpoint(args.study / f"{architecture}-seed{seed}", args.device)
                for category, prompt in PROMPTS.items():
                    text = sample(model, tokenizer, prompt, 96, temperature=0)
                    stream.write(json.dumps({"seed": seed, "architecture": architecture,
                                             "category": category, "prompt": prompt, "text": text}) + "\n")
                    stream.flush()
                del model
                torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
