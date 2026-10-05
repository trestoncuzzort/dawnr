# What enterprise small models do, what they do not, and what dawnr builds from that (2026-10-05)

The operator, 2026-10-05: "how can we do what enterprise small models are not doing and also doing and implement
all of that", then "think as big as possible and implement test and add everything we can ... i want this project
to mean something and be usable for everyone". This file is the plan that answers both. Each build below gets its
own registration before it is measured and its own row here when it lands. Research receipt 21a93580b0dc holds
the fetched pages this section rests on.

## 1. What the enterprise small models ship (read from their own cards, 2026-10-05)

| | Phi-4-mini (3.8B, MIT) | Granite 4.0 (3B to 32B, Apache-2.0) | Qwen3.5-4B (Apache-2.0), our base | Mistral Small 3.2 (24B, Apache-2.0) |
|---|---|---|---|---|
| tool / function calling | yes | yes (BFCL v3 57 to 65) | yes (BFCL-V4 50.3) | yes |
| output held to a schema | by the runtime | by the runtime | by the runtime (llama.cpp turns a JSON Schema into a grammar) | by the runtime |
| answers from documents | "may be possible to resolve ... under RAG settings" | RAG listed; a second model (Granite Guardian) judges groundedness | by prompt | by prompt |
| languages | 23 | 12 | 201 claimed | 24 |
| vision | separate model | separate models | built in | built in |
| context | 128K | 128K | 262K | 128K |
| guard rails | safety post-training | Granite Guardian: an 8B model scores jailbreak, tool-call hallucination, groundedness as yes/no | none listed | system prompt |
| the model file | hashes | cryptographically signed checkpoints, ISO 42001 audit, bug bounty | hashes | hashes |

What they share: breadth (tools, schemas, documents, images, languages, long context, every runtime), a signed or
hashed model file, and benchmark tables they ran themselves.

## 2. What none of them ships

1. **A check of the answer by something that did not write it.** Phi's card says it plainly: "users may experience
   factual incorrectness", and developers should "evaluate and mitigate for accuracy" themselves. Where a check
   exists (Granite Guardian) it is a second language model's yes or no.
2. **A refusal that names the check that failed.** A schema-valid tool call or JSON object says the shape is right,
   not that the content is.
3. **A record a third party can replay.** The model file is signed; no answer is.
4. **The audit of their own numbers.** No card registers a prediction before measuring, publishes a contamination
   audit of its training rows against its test set, or carries a correction.
5. **Provenance per training row.** Described in prose, not listed.

dawnr already does 1, 2, 4 and 5 for one kind of answer (a function with a specification, proved). The plan is to
do all five for every kind of answer an ordinary person asks a small model for, on the base's own breadth.

## 3. The rule every build follows

An answer is shown only when something that did not write it agrees, the refusal says which check stopped it, and
what is shown can be replayed without the model. No language model is ever the check (measured 2026-10-01: a
model judge of support added nothing). What cannot be checked is either refused or shown marked as unchecked,
never passed off.

## 4. The builds

| # | what a person gets | what the enterprise models do here | the check dawnr adds | state |
|---|---|---|---|---|
| 1 | `--certificate FILE` on `ask` and `prove`; `dawnr check FILE` | sign the model file | the answer's own record (program, specification, tests, the Python, the independent Python behind the specification) replayed on the reader's machine with the reader's provers and no model; an altered one fails | **built 2026-10-05** (`t/certificate.py`) |
| 2 | the Python handed back refuses inputs outside what was proved | hand back code | `ValueError` outside the `requires`, `TypeError` for another type, and the guard itself run beside the interpreter | **built 2026-10-05** (`t/to_python.py`) |
| 3 | `dawnr verify FILE.py`: your own Python function, proved or broken | write new code | the function is its own oracle: a `t` twin that answers as it does on drawn inputs, a specification held against it, a proof; or the input where it breaks what you said | next |
| 4 | `dawnr extract`: fields out of your documents | JSON that fits a schema | every field carries a sentence of the document word for word (forced by the decoder), the value must be in that sentence, and a field with no support stays empty | next |
| 5 | `dawnr calc`: a question with numbers | answer in prose | the model writes the arithmetic, an exact evaluator computes it, the formula is shown to be read | next |
| 6 | checked tool calls | emit calls; judge them with a guard model | a call is released only when it fits the declared schema and each argument is in the request, or the missing one is asked for | next |
| 7 | a local API and a page in the browser | an OpenAI-style endpoint | the same gate behind HTTP, each reply carrying its check, for programs and for people who do not use a terminal | after 3 to 6 |
| 8 | the model picked by the machine: 4B, 9B, 27B | one size per card | the answer rate is the bottleneck (18 of 182 shown by the published 4B; the prompted 27B 33); the installer picks the largest that fits | waits on the lab's cards |
| 9 | questions in other languages | 12 to 201 languages claimed | the gate does not read the language: the same tests and proofs decide; measured, not claimed | waits on the lab's cards |
| 10 | signed releases and a data card per release | signed checkpoints | the release's files signed as the repository's `SHA256SUMS` already is; every training row's source and licence listed | with the next release |

Not built, and why: ISO 42001 certification (an external paid audit); a guard model (rule 3: a model is not a
check; the harness's permissions and the forced forms do that job); long context (the checked forms retrieve a
few passages, and a longer window checks nothing).

## 5. What is in the way, and what is done about each

- **The answer rate.** Most questions are refused. Levers, in the order they are measured: the round-4 student
  (training now), a 9B student on the same rows, the prompted 27B for 24 GB cards, more attempts with the
  provers' own diagnostics fed back, and build 3, which starts from code the person already has.
- **Cards.** Three lab cards, all training until about 11:30 UTC; the desktop's card falls off the bus under load
  (the untried fix needs the firmware setting or root, which only the operator has). Measurements that need a
  model wait for a card or run on the desktop's CPU.
- **Paid compute.** Bedrock stays behind the capped proxy inside the free credit; EC2 cards need the paid plan,
  which is the operator's decision.
- **One pair of hands.** Builds that are separate modules are written and tested one after another, each pushed
  with its tests and checked on CI before the next.

## 6. Order of work

1 and 2 (done), then 3, 4, 5, 6 as separate modules with their registrations, then 7 over all of them, with 8
and 9 started the moment a lab card is free. The release gate for dawnr v6 runs unattended in between.
