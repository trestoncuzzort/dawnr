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

## Outcome of the gate, 2026-10-01 17:30Z: AlignScore-large on every reply, the rule of 14:27Z

1,680 replies scored on the lab's CPU (`locallm/rag_gate.py`); a reply is shown when it does not say the
information is insufficient and its score is at least 0.5. Other thresholds reported, not chosen from:

| noise rate | replies | rejected | right | shown / right at 0.3 | shown / right at 0.5 | shown / right at 0.7 | shown / right at 0.9 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 300 | 2 | 294 | 295 / 292 | 273 / 270 | 193 / 192 | 79 / 79 |
| 0.2 | 300 | 2 | 290 | 295 / 287 | 279 / 274 | 190 / 187 | 85 / 83 |
| 0.4 | 300 | 3 | 287 | 295 / 285 | 275 / 266 | 187 / 182 | 90 / 87 |
| 0.6 | 300 | 6 | 279 | 290 / 275 | 259 / 245 | 171 / 163 | 68 / 64 |
| 0.8 | 300 | 15 | 259 | 280 / 255 | 240 / 219 | 145 / 133 | 49 / 44 |
| 1.0 | 300 | 92 | 92 | 196 | 144 | 63 | 12 |

88. **With no document holding the answer it shows at most 20% of the replies that do not reject:
    falsified.** It shows 144 of 208 (69.2%).
89. **At noise rate 0.4 it keeps at least 80% of the right answers: holds.** 266 of 287 (92.7%).
90. **At noise rate 0.4 the share right among what it shows is higher than among all replies: holds,
    barely.** 96.7% (266 of 275) against 95.7% (287 of 300).

**What 88's 144 are, measured.** RGB's answer check is an exact substring, so "Świątek" misses "Swiatek"
and "21st October" misses "October 21". Read again with diacritics, ordinal suffixes and case folded, the
five noise-rate-1 documents hold the answer for 19 of the 300 questions (2 by the exact check); that
accounts for 17 of the 144 shown. The other 127 were shown although their documents lack the answer; 45
of them state the right answer anyway (from what the model knew), and the rest state something else. Read
by hand, the shown replies quote the documents at length and put one answer sentence among the quotes,
sometimes a wrong one ("Xander Schauffele (referred to as Scheffler in the text)").

**Reading, and what it does not yet say.** AlignScore's score is the mean over a reply's sentences of each
one's best support, by design ("taking the average prevents a single inconsistent claim sentence from
dominating the final score", the paper, 3.2): right for grading a summary, the opposite of what a gate wants, where one
unsupported sentence is the failure. That is the suspected cause of 88; it is measured next (the same
scores with the minimum over sentences in place of the mean) and stays a suspicion until then.

## The suspected cause of 88, measured, 2026-10-01 18:08Z: not the mean (this corrects the reading above)

Every reply rescored on the lab with each sentence's best support kept (`rag_gate.sentence_support`; the mean
at 0.5 reproduces the registered 144 and 266 exactly). Post hoc, on the same 300 questions, so nothing here
is a new rule:

| rule | noise 1: shown of answered | noise 1: shown, documents lack it | noise 0.4: right kept | noise 0.4: right among shown |
|---|---:|---:|---:|---:|
| mean >= 0.3 | 196 (94%) | 178 (94%) | 285 of 287 (99%) | 285 of 295 (96.6%) |
| mean >= 0.5 | 144 (69%) | 127 (67%) | 266 of 287 (93%) | 266 of 275 (96.7%) |
| mean >= 0.7 | 63 (30%) | 50 (26%) | 182 of 287 (63%) | 182 of 187 (97.3%) |
| mean >= 0.9 | 12 (6%) | 7 (4%) | 87 of 287 (30%) | 87 of 90 (96.7%) |
| min >= 0.3 | 80 (38%) | 68 (36%) | 203 of 287 (71%) | 203 of 209 (97.1%) |
| min >= 0.5 | 39 (19%) | 29 (15%) | 149 of 287 (52%) | 149 of 153 (97.4%) |
| min >= 0.7 | 18 (9%) | 12 (6%) | 110 of 287 (38%) | 110 of 113 (97.3%) |
| min >= 0.9 | 9 (4%) | 5 (3%) | 64 of 287 (22%) | 64 of 65 (98.5%) |

Scoring only each reply's first sentence (where it usually states the answer) traces the same line: 30%
of the no-answer replies shown at 0.9 for 66% of the right answers kept.

**Reading.** The minimum over sentences cuts the no-answer replies shown, but it cuts right answers at the
same rate, and so does the first sentence alone: every way of reading the scores lies on one trade-off,
roughly "to show a third of the no-answer replies, give up a third of the right ones". So the mean was not
the cause, as the reading above suspected. What the check cannot do on this data is tell an answer the
documents state from an answer the model knew that sits on the documents' topic: RGB's documents without
the answer are about the same event (a 2022 French Open document beside "Świątek won the 2022 French
Open"), and AlignScore scores the reply as consistent with them. A gate for retrieved answers needs the
answer itself located in a document, not the reply's overall agreement with them; that is the next
registration, on the 93 integration questions RGB holds that these 300 do not.

## Amendment, 2026-10-01 18:10Z, before any answer to these questions exists: a gate that finds the answer's quote

**Method:** GopherCite's inline evidence (Menick et al., "Teaching language models to support answers with
verified quotes", arXiv:2203.11147, 2.1): the answer is written `%<Claim>%(Document title)%[Quote from
document]%`, and the quote is checked to be verbatim from the document it names ("constrained sampling
ensures that the model quotes are verbatim from the claimed source"; here the check is post hoc, by
parsing). The base is prompted for that form (RGB's system prompt plus the syntax and one example; it is
not fine-tuned for it as GopherCite was). A reply is shown when it parses, every quote is found word for
word in a given document (whitespace folded), and every content word of every claim is in its quote
(diacritics, case and ordinal suffixes folded; the last rule is ours, invented: GopherCite judges support
with raters and a reward model). Two claims are allowed for questions that ask two things.

**Questions:** the 93 of RGB's information-integration set (`en_int.json`) that are not among the 300
used above, in the plain layout (one document from each positive group first, as its evalue.py takes
them; then the rest). Noise rate 1 (five documents without the answer) and 0.4. The base at Q4_K_M on
the lab's CPU, greedy.

101. With no document holding the answer, the quote gate shows at most 20% of the replies that do not
     say the information is insufficient.
102. At noise rate 0.4 it shows at least 60% of the replies that are right by RGB's answer check.
103. Of what it shows at noise rate 0.4, a larger share is right than of all replies.

Reported beside them: AlignScore's mean on the same replies, and how often the base keeps the syntax.
