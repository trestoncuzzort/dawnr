#!/usr/bin/env python3
"""Single source of truth for the E3 base model, its PINNED revision, and the training max length, so the
token/diversity matcher, the SFT trainer, the eval generator and the GPU probe all load a byte-identical
tokenizer at the same revision and preprocess at the same length. Change the base ONCE here (no silent drift).

ACCUM is the trainer's gradient-accumulation factor; it defines optimizer-step exposure in the audit so the
matcher reports the same optimizer budget the trainer will actually realise.
"""
import os
BASE = os.environ.get("E3_BASE", "Qwen/Qwen2.5-Coder-0.5B-Instruct")       # Apache-2.0
REV = os.environ.get("E3_BASE_REV", "ea3f2471cf1b1f0db85067f1ef93848e38e88c25")
MAXLEN = int(os.environ.get("E3_MAXLEN", "768"))
ACCUM = int(os.environ.get("E3_ACCUM", "8"))


def load_tokenizer():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, revision=REV)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    return tok
