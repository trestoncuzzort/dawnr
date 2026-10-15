#!/usr/bin/env python3
"""Merge a LoRA adapter into its base on CPU (gen_eval_cpu loads a full model, not an adapter).
    python3 e3_merge.py --base <id> --adapter <dir> --out <dir>
"""
import argparse
import pathlib

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    base = AutoModelForCausalLM.from_pretrained(a.base, dtype=torch.float32, device_map={"": "cpu"})
    merged = PeftModel.from_pretrained(base, a.adapter).merge_and_unload()
    outd = pathlib.Path(a.out); outd.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(outd))
    AutoTokenizer.from_pretrained(a.adapter).save_pretrained(str(outd))
    print(f"MERGED {a.adapter} -> {outd}")


if __name__ == "__main__":
    main()
