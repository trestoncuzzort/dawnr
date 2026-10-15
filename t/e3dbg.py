import sys, json, os, torch
os.environ["HF_HOME"]=os.path.expanduser("~/hf-cache")
sys.path.insert(0,".")
from train_lora_cpu import SFT
from transformers import AutoTokenizer, AutoModelForCausalLM
tok=AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-0.5B-Instruct"); tok.pad_token=tok.eos_token
rows=[json.loads(l) for l in open("out/e3-arms/all7.jsonl")][:5]
ds=SFT(rows,tok)
print("examples:",len(ds),"seqlens:",[len(e["input_ids"]) for e in ds.ex],"labeltoks:",[sum(1 for x in e["labels"] if x!=-100) for e in ds.ex])
m=AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-Coder-0.5B-Instruct",dtype=torch.float32)
for i in range(len(ds)):
    b={k:torch.tensor([ds.ex[i][k]]) for k in ("input_ids","attention_mask")}; b["labels"]=torch.tensor([ds.ex[i]["labels"]])
    print(f"ex{i} loss:",float(m(**b).loss))
