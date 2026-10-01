# Answering from retrieved documents on the chosen weights: registered 2026-10-01 14:23Z, before any answer

AMBITION's row "to know what it was not trained on" has a retriever (`DAWNR-RETRIEVAL.md`: BM25 ranks a
problem's own proved document first 35 times in 37) but no measurement of the model answering from what is
retrieved, and none of the thing that matters most here: whether it says so when the documents do not hold
the answer, rather than inventing one.

**Method, taken whole:** RGB (Chen et al., "Benchmarking Large Language Models in Retrieval-Augmented
Generation", AAAI 2024, arXiv:2309.01431; github.com/chen700564/RGB, data CC BY-NC-SA 4.0, used for
evaluation only and kept out of this repository). 300 English questions about news, each with five
documents of which a set share is noise. Ported in `locallm/rag_rgb.py` from its evalue.py with the same
document choice (seed 2333 a question), prompt (config/instruction.yaml), answer check and score; the tests
compare the document choice against evalue.py's own code. Differences: greedy decoding where RGB samples at
0.7; the model behind a llama.cpp server.

**Model:** the base, Qwen3.5-4B at Q4_K_M (Apache-2.0), on the lab's four CPU servers, thinking off: the
weights dawnr runs on. Every prompt fits the servers' 4,096-token context (the longest is 2,174 tokens by
the model's tokenizer).

**Runs:** noise rate 0, 0.2, 0.4, 0.6 and 0.8 (accuracy); noise rate 1, every document without the answer
(rejection: the reply contains "insufficient information"); and closed book, no documents and no system
turn, as evalue.py does with zero passages (what the model already knew).

**Published reference, the paper's Table 1 and 2 (English):** Qwen-7B-Chat 94.33 / 91.67 / 91.00 / 87.67 /
73.67 at noise 0 to 0.8, rejection 31.00 by the exact phrase; ChatGPT 96.33 / 94.67 / 94.00 / 90.00 / 76.00,
rejection 24.67. These are older models; they are what the benchmark's authors measured, nothing more.

## Predictions

84. At noise rate 0.4 the base answers at least 91% right.
85. At noise rate 0.8, at least 74%.
86. With no document holding the answer, it says the information is insufficient on at least 31% of the 300.
87. Closed book it answers under 50% right, and documents at noise rate 0 add at least 40 points: the
    documents, not memory, carry the answers.

Reported beside 86, not predicted: of the replies at noise rate 1 that do not reject, how many hold the true
answer anyway (from memory) and how many hold neither (an invention), counted by the same answer check.

Runs on the lab after the tools measurement gives the servers back (`~/scratch/rgb/run.sh`, sentinel
`RGB-DONE`).

## Amendment, 2026-10-01 14:27Z, before any answer: the gate for retrieved answers

The proofs are dawnr's filter for programs; the image gate (`locallm/PREDICT-2026-10-01-seeing.md`) is one
for what it says it sees. For what it says from documents the filter is a check, by a separate model, that
the documents support the reply: **AlignScore** (Zha et al., ACL 2023, arXiv:2305.16739;
github.com/yuh-zha/AlignScore and huggingface.co/yzha/AlignScore, both MIT). Its method, taken whole: the
context is split into chunks of about 350 words at sentence boundaries, the claim into sentences; each claim
sentence is scored against every chunk by the probability of ALIGNED from its three-way head; the score is the
mean over claim sentences of the best chunk (its `nli_sp` mode; the paper's Table 2: AlignScore-large 88.6
average AUC on SummaC, base 87.4). Here the context is the five documents the question was given and the claim
is the reply. AlignScore-large, ported to load its checkpoint without PyTorch Lightning (`locallm/rag_gate.py`).

**The rule, fixed now:** a reply is shown when it does not say the information is insufficient and its
AlignScore is at least 0.5. Other thresholds are reported, not chosen from.

88. With no document holding the answer (noise rate 1), the gate shows at most 20% of the replies that do
    not reject.
89. At noise rate 0.4 it keeps at least 80% of the right answers.
90. At noise rate 0.4 the share right among the replies it shows is higher than among all replies.

## Outcome, 2026-10-01 16:49Z: RGB's English set on the base (the gate's half follows)

The base Qwen3.5-4B at Q4_K_M on the lab's four CPU servers, greedy, thinking off; 300 questions a row, no
request failed. RGB's own scoring (`locallm/rag_rgb.py`, ported and tested against its evalue.py):

| noise rate | right | the base | Qwen-7B-Chat (paper) | ChatGPT (paper) |
|---|---:|---:|---:|---:|
| 0.0 | 294 of 300 | **98.0%** | 94.33 | 96.33 |
| 0.2 | 290 of 300 | **96.7%** | 91.67 | 94.67 |
| 0.4 | 287 of 300 | **95.7%** | 91.0 | 94.0 |
| 0.6 | 279 of 300 | **93.0%** | 87.67 | 90.0 |
| 0.8 | 259 of 300 | **86.3%** | 73.67 | 76.0 |
| no document holds the answer: says so | 92 of 300 | **30.7%** | 31.00 | 24.67 |
| no documents at all: right | 78 of 300 | **26.0%** |  |  |

84. **At noise rate 0.4 at least 91% right: holds.** 95.7%.
85. **At noise rate 0.8 at least 74%: holds.** 86.3%.
86. **With no document holding the answer it says so on at least 31%: falsified, by a hair.** 92 of 300,
    30.7%, by RGB's exact phrase. 16 more decline in other words the phrase does not match.
87. **Closed book under 50%, and documents at noise rate 0 add at least 40 points: holds.** 26.0% closed
    book, 98.0% with the documents: 72 points.

Of the 208 replies at noise rate 1 that do not reject, 76 contain the true answer although none of the five
documents does (from what the model already knew of these 2022 news events: in one only did a given
document hold it), and 132 contain neither. The numbers from the paper are older and larger models,
measured with sampling at 0.7 where this is greedy; they are context for the scale, not a race.

**Reading.** Given documents, the base answers from them nearly always and holds up as they fill with
noise. When they are silent it more often answers anyway, from memory or from nothing, than says it
cannot. That is the case the support check (predictions 88 to 90) is for; it scores these same replies
on the lab next.
