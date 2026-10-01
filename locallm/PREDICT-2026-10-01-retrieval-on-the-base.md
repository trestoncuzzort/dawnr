# Answering from retrieved documents on the chosen weights: registered 2026-10-01 14:41Z, before any answer

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
