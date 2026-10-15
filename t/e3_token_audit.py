import json, os, sys
os.environ.setdefault("HF_HOME", os.path.expanduser("~/hf-cache"))
sys.path.insert(0, ".")
from transformers import AutoTokenizer
from train_lora_cpu import compact_prompt
tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-0.5B-Instruct"); tok.pad_token = tok.eos_token
for arm in ["raw", "graded", "all7"]:
    rows = [json.loads(l) for l in open(f"out/e3-arms/{arm}.jsonl")]
    inp = lab = 0
    for r in rows:
        m = compact_prompt(r.get("prompt"), r.get("task", ""))
        t = tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
        pi = len(tok(t, add_special_tokens=False)["input_ids"])
        ci = len(tok((r.get("chosen") or "") + tok.eos_token, add_special_tokens=False)["input_ids"])
        inp += pi + ci; lab += ci
    tasks = len({r["task"] for r in rows})
    print(f"{arm}: rows={len(rows)} input_toks={inp} label_toks={lab} tasks={tasks}")
