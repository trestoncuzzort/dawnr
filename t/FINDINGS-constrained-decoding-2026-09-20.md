# Constrained decoding was 100x slower for a fixable reason, 2026-09-20

Decoding the 235B against `t/t.gbnf` through vLLM ran at **4.8 to 9.6 tokens a
second aggregate** against **about 430 unconstrained**: 4 answers in five minutes
where the same model writes 232 in 2 minutes 22 seconds. That made
grammar-constrained generation unusable, which matters because decoding against
t's own grammar is a roadmap step (WS-22.4) and the arm that answers "the model
cannot emit syntax the parser refuses".

It is not the price of constrained decoding. It is one grammar-authoring
mistake, and the mask engine that forgives it is already installed.

## Measured, on the lab, CPU only, no server restart

One real `t` program, the Qwen3-235B tokenizer, 151,669 tokens of vocabulary,
mask cost per generated token:

| engine | grammar | compile | mean per token | max |
|---|---|---|---:|---:|
| xgrammar | `t/t.gbnf` | 103 ms | **101.3 ms** | 625 ms |
| xgrammar | `t/t.simpleid.gbnf` | 58 ms | 92.3 ms | 556 ms |
| **llguidance** | `t/t.gbnf`, lexified | 1,128 ms | **0.602 ms** | 1.52 ms |

**168 times** cheaper per token. Both engines refuse the same token of the same
program, so they agree about the language; this is engine cost alone.

XGrammar's own paper (arXiv:2411.15100) targets **under 200 microseconds** a
token for a Python DSL. We measured 101,300. That is 500 times off its design
point, which is the signature of a pathology rather than a limit.

## Why

`t/t.gbnf` states a LEXICAL constraint as CFG rules. "An identifier is a word
that is not a keyword" is compiled by `t/make_grammar.py` into 108 `id-N` rules,
each a character class followed by `idrest` with a nullable alternative. Add
`ws ::= [ \t\r\n]*` between nearly every pair of symbols, `idrest ::=
[A-Za-z0-9_]*`, and right-recursive `neg ::= "not" sp neg | cmp`, and the parser
frontier stays large and context-dependent, so xgrammar's adaptive token-mask
cache never hits. The upstream evidence is explicit:

- xgrammar issue 235: the same shape, in vLLM, "outputs 50 tokens/s without
  guided_grammer, but when apply this grammer it outputs 2 tokens/s".
- xgrammar issue 852: the mechanism, "the matcher state changes on every
  accepted token and the adaptive token-mask cache never hits", with production
  grammars at about 55 ms a fill.
- XGrammar-2 (arXiv:2601.04426) Table 2 prices exactly this trie-as-EBNF
  translation at 1,008 ms of compile for 5 tags and 15,483 ms for 100.

Removing the trie is **not** the fix: `t.simpleid.gbnf` still costs 92.3 ms,
because `ws`, `idrest` and the right recursion remain. The trie is not too big,
it is on the wrong side of the lexer/parser line, along with several other
rules.

## The fix, and one thing to know about it

llguidance separates a lexer from the parser and promotes every terminal-only
rule to a lexeme, so the trie becomes a DFA instead of 108 rules walked per
token. vLLM 0.29 ships it as the `guidance` backend and its own converter does
the promotion: 131 terminals, 27 parser rules.

Two steps, no change to what the language accepts:

1. `t/t.lark.gbnf` is `t/t.gbnf` with `|` continuation lines joined, because
   vLLM's `gbnf_to_lark` ends an alternative list at a newline and raw
   `t/t.gbnf` fails conversion with `Expected name at line 42`. One
   substitution: `re.sub(r'\n\s*\|', ' |', src)`.
2. Serve with `--structured-outputs-config.backend guidance`.

**`auto` had been choosing xgrammar all along.** vLLM resolves `auto` by trying
`validate_xgrammar_grammar` first, our GBNF passes, and guidance is never
reached. The backend is a server-launch decision; a request cannot override it.

Not yet measured end to end: the throughput on a real serving run. The 168x is
mask cost on one program on CPU, which is the term that was dominating, not a
promise about tokens a second. `t/t.simpleid.gbnf` stays as the control that
isolates the trie from everything else.

## The 168x, confirmed end to end on the 235B, 2026-09-20 evening

The mask cost above was measured on `t/t.gbnf` alone, without a model. It was then
paid for real. `qwen235-heldout-g1`, the constrained arm registered in
`t/PREDICT-2026-09-20-constrained-235b.md`, was launched against the loaded
Qwen3-235B server with `--grammar t/t.gbnf` and nothing else changed from the
control:

    generate: 1/232 (1 asked this run, 374 s, 373.8 s each)

**374 seconds per reply**, against a control arm that answered the same 232
problems in minutes. The prediction is arithmetic, not hindsight: 101.3 ms per
token times a reply of about 3,700 tokens is 375 s. And the tell is where the time
went. All four RTX 6000 Ada sat at **0% utilisation** for the duration, because
xgrammar computes its mask on the CPU and the GPU waits; the same four cards read
100% within seconds of the arm being stopped.

Three things follow.

**The arm was stopped after 3 answers, and that is the right call rather than a
failure.** At 374 s per reply with 16 in flight it would have taken about 1.5
hours of a server two other jobs were waiting on, to measure a quantity the
preregistration explicitly excluded: "This arm runs on whichever backend the
loaded server has and its wall-clock is therefore not a measurement of what
constrained decoding must cost." The 3 answers are kept; they are not a column.

**WS-21 move 1 is blocked on a server flag, not on code.** Every other piece
exists: the grammar, its two-directional check (2,121 accepted, 590 refused),
`spec_experiment.py generate --grammar`, the preregistration and its decision
rule. What it needs is a server started with
`--structured-outputs-config.backend guidance`, and the arm then costs 0.602 ms
per token of mask instead of 101.3.

**The GPU-idle reading is the part worth keeping.** A 168x number measured on a
grammar in isolation could be dismissed as microbenchmarking. Four cards at 0%
while a 235B model waits on a CPU mask is the same number as a system property,
and it says the choice of mask engine is not an optimisation detail but the
difference between an arm that runs and one that does not.
