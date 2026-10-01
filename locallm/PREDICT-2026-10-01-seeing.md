# Seeing with the base's own vision input: registered 2026-10-01 11:01Z

## What this is

`AMBITION.md`'s row "to see" reads "later"; the plan of record (`internal/LADDER-PLAN-2026-10-01.md`)
names the base's own vision input if it has one. Qwen3.5-4B does: its GGUF release ships a vision
projector. This measures it on the failure this project exists to catch, applied to images: saying
something is there when it is not.

## What it stands on

POPE (Li et al., "Evaluating Object Hallucination in Large Vision-Language Models", arXiv:2305.10355;
github.com/RUCAIBox/POPE, MIT, its `evaluate.py` fetched 2026-10-01): balanced yes/no questions "Is there
a <object> in the image?" over 500 COCO val2014 images; the adversarial setting draws the absent objects
from those that most often co-occur with what is present, which is where models hallucinate most. An
answer is "no" when its first sentence contains "No", "not" or "no"; accuracy, precision, recall, F1 and
the share answered yes.

## The measurement (`locallm/vision_pope.py`)

- **Model**: the base Qwen3.5-4B at 4 bits (Q4_K_M) with its vision projector (F16) under llama.cpp on
  the lab's CPU, greedy, 16 new tokens, the question exactly as POPE writes it.
- **Questions**: POPE's adversarial COCO file, all 3,000 (1,500 yes, 1,500 no), images fetched by name.

## Predictions

69. F1 at least 0.80 on the adversarial setting. Falsified below 0.80.
70. It hallucinates less than it misses: precision at least recall (a model that answers "yes" too
    readily has precision below recall). Falsified if precision is below recall.

## Outcome, 2026-10-01 12:36Z

All 3,000 adversarial questions, four CPU servers on the lab, 72 minutes, no request failed:

| accuracy | precision | recall | F1 | answered yes | true yes | false yes | true no | false no |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.877 | 0.901 | 0.847 | **0.873** | 47.0% | 1,271 | 140 | 1,360 | 229 |

69. **F1 at least 0.80: holds.** 0.873.
70. **Precision at least recall: holds.** 0.901 against 0.847: when it errs it more often misses an
    object that is there than names one that is not.

**Reading.** The chosen base sees, offline on a CPU at 4 bits, and on POPE's hardest setting it
says an absent object is present on 140 of 1,500 questions (9.3%). That is the visual form of the
failure the gate exists for; nothing yet checks a claim about an image the way the provers check a
program, so this rate is what a person would see unchecked.
