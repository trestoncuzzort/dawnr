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

## Amendment, 2026-10-01 13:07Z, before any detector has run: the gate for images

The code gate shows an answer only when something that did not write it agrees. The same for images:
Woodpecker (Yin et al., arXiv:2310.16045, read) validates every object an MLLM claims with an open-set
detector before the claim stands, training-free, and gains 24 to 31 accuracy points on POPE for the
models it was tried on. Here nothing is rewritten: a "yes, there is a <object>" is SHOWN only when OWLv2
(google/owlv2-base-patch16-ensemble, Apache-2.0, card fetched) also gives some box at least the threshold
score for "a photo of a <object>"; otherwise the gate says it cannot confirm it (`locallm/vision_gate.py`).
The threshold is the model card's own example, 0.1; 0.2 and 0.3 are reported beside it. The same 3,000
adversarial questions and the base's answers above.

77. At 0.1, of the "yes" answers the gate shows, at least 95% are right (the model alone: 90.1%).
    Falsified below 95%.
78. At 0.1 the gate keeps at least 85% of the model's right "yes" answers. Falsified below 85%.

## Outcome of the image gate, 2026-10-01 13:35Z

OWLv2 scored every object POPE asks about in each of the 500 images (28 minutes on 8 CPU threads):

| threshold | "yes" shown | of them right (precision) | false "yes" shown | the model's right "yes" kept |
|---|---:|---:|---:|---:|
| the model alone | 1,411 | 0.901 | 140 | |
| 0.1 (the card's example) | 1,345 | **0.917** | 112 | **97.0%** |
| 0.2 | 985 | 0.947 | 52 | 73.4% |
| 0.3 | 706 | 0.977 | 16 | 54.3% |

77. **At 0.1 at least 95% of what the gate shows is right: falsified.** 91.7%: at the card's threshold
    the detector agrees with most of the model's mistakes too.
78. **At 0.1 it keeps at least 85% of the model's right answers: holds.** 97.0%.

**Reading.** An independent detector does what the provers do for code, at a price that has to be
chosen: at 0.3 the false claims shown fall from 140 to 16 (precision 97.7%) and half of the true
ones are withheld as unconfirmed; at 0.1 almost nothing true is lost and a fifth of the false
claims are stopped. The detector alone at 0.1 is worse than the model (precision 0.789), so it is
the agreement of two independent judges that helps, not the second judge. Unlike a proof, neither
judge here is sound; the threshold is a trust level, stated with the answer, the way the code gate
states how many provers agreed.
