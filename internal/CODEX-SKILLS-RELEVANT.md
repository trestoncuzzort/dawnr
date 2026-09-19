# Which of the pulled skills are worth carrying into this project

Written 2026-09-19 against `/home/t/lab-pull/claude/skills` (145 skills) and
`/home/t/lab-pull/claude/agents` (33 agents), read alongside `README.md`, `ROADMAP.md` and
`internal/HANDOFF-2026-09-19.md`.

**The number first: 10 of the 145 skills earn a place here, and 0 of the 33 agents.** The 33 agents are
all `gsd-*` and all spawned by a `/gsd:*` orchestrator against a `.planning/` directory this project does
not have. 67 of the 145 skills are that same cluster. Of the remaining 78, most are a scientific-publishing
and data-science toolbox (posters, Zotero, PubMed, UMAP, SHAP, Bayesian modelling, discrete-event
simulation) aimed at a wet-lab or a paper pipeline, not at a verifier matrix.

The ten fall into four groups. Only the first two change what the next run measures; the other two change
what it costs and how it reads.

---

## 1. The statistics of a three-answer difference (3 skills)

This is the largest gap the survey found, and it is not a tooling gap. The project's decisions currently
turn on differences of one to three answers out of 232 (`3` against `4` under the grammar, `6` against `3`
for the prover, `5` against `3` for prompt v4), and the handoff says so in the right places ("three answers
wide and needs seeds before it is a claim"). What is missing is the arithmetic that says how wide is wide
enough. These three supply it, and they are already the right shape: the held-out set is 232 fixed
problems every model answers, which is a paired binary design, not two independent samples.

### `statistical-analysis`

Guided test selection with assumption checks and effect sizes. `references/test_selection_guide.md` lines
18 and 87 name the test this project needs and has never used: **McNemar's test for a binary outcome on
paired groups**. Every comparison in `t/score_heldout.py` is exactly that — the same 232 problems, clean or
not clean, under two models or two arms — so the honest statistic is the count of *discordant* problems
(clean under one arm and not the other), not the difference of two totals. Apply it first to the two open
comparisons in handoff section 8: `phi4-mini-g` against `student-r6-g3k` when both finish, and prompt v4
against v3 on the untrained 1.5B. It is a column `score_heldout.py` could carry beside `clean` and
`converts`.

### `statistical-power`

Sample size and minimum detectable effect, with `scripts/power.py` wrapping statsmodels behind one
interface; `test="two_proportions"` and `test="one_proportion"` are supported, and Cohen's *h* conversion
is automatic. Two live questions answer directly to this. First, handoff 8.3: "two or three seeds of
`prover-v2-7b`" — the MDE at n=232 with a base rate near 1.3 percent says whether two or three seeds can
resolve 6 from 3 at all, or whether the answer is that no feasible number of seeds will and the claim has
to rest on the conversion rate instead. Second, the preregistration habit in handoff section 9: a
`PREDICT-*.md` that names the number that would falsify it is strictly better when that number came from a
power calculation rather than from a guess. The skill's own warning applies here too — do not compute
post-hoc power on a run that already happened; report the MDE or the interval.

### `experimental-design`

Design before data: randomization, blocking, factorial layout, and the failure modes that no analysis can
repair. The immediate application is handoff 8.1, which is written as two separate one-factor-at-a-time
runs ("v4 with the division correction alone, and v4 with the refusal rules alone"). That is a 2×2 with two
cells missing: it cannot see whether the two changes interact, and `references/factorial_and_doe.md` covers
the full 2^k layout that would. Its pseudoreplication warning is worth reading against this project
specifically, because sampling *k* answers per problem and counting them as *k* independent trials is the
mistake it names, and `pool_pick.py` and the rounds-4-and-5 "more answers per problem" result both live
near that line.

---

## 2. The background-run cluster (4 skills, one job)

`workflow-salvage`, `workflow-watchdog`, `workflow-nanny`, `idle-repair`. These overlap heavily and should
be treated as one capability with four entry points. They matter here because handoff section 2a is
literally four agents mid-flight with uncommitted work, and section 2 is four detached generation runs on
the lab workstation that a night's sleep is spent waiting on.

- **`workflow-salvage`** is the one to install first, because it closes a gap that loses real work:
  `journal.jsonl` records an agent only when it *completes*, so an agent killed mid-flight reads as having
  produced nothing, while its full transcript survives in `agent-<id>.jsonl`. Its rule — salvage before
  `TaskStop`, never report a run's work as lost without running it — is the correct rule for the four
  agents in 2a, whose combined prize the handoff puts at nearly half the training pool.
- **`workflow-nanny`** arms a `Monitor` on the first tick after a launch and attaches a diagnosis
  (`tool-wait`, `looping`, `awaiting-input`, `rate-limited`, `truncated`, `quiet`) to the idle alert, so a
  run that dies in its first thirty seconds is not confused with one that is thinking. `workflow-watchdog`
  is the read-only probe for a run already in flight, with the `RUNNING / IDLE / STALLED / DONE` verdicts
  and the per-agent loop flag. **`idle-repair`** is the same diagnosis for background `Bash` tasks and the
  resume-from-cache repair.
- All four repeat one rule this project already believes: resume from cache, never restart, and never
  invent what a missing agent would have returned. That is the same discipline as trap 1 in handoff
  section 6 (`pkill -f` matching the shell that runs it) and the same as "if an agent's report contradicts
  its regression bar, believe the bar".

**Portability caveat, and it matters for handing these to codex.** These four read the Claude Code
transcript layout directly: `workflow-watchdog/scripts/probe.sh` sets `ROOT="$HOME/.claude/projects"`,
`workflow-nanny/scripts/wf_lib.py` globs `~/.claude/projects/*/*/subagents/workflows/wf_*`, and
`idle-repair/scripts/probe.sh` walks the same tree. Under a runner that does not write that tree they
degrade to prose. Copy them, but expect the scripts to need a path argument before they run anywhere else.

---

## 3. The shared lab workstation (1 skill)

### `cpu-yield`

Suspends our compute with `SIGSTOP` instead of killing it, logs a timestamped apology per freeze, and
thaws on every exit path. It was written for this exact box: it names the 120 CPU threads, and
`scripts/yield-watch.sh` is portable bash with no Claude-specific paths, so it is the one skill in this
list that runs unchanged under any runner. It applies to `t/run_par.py --jobs 32`, which is the project's
heaviest CPU fan-out, and to the finding already recorded in handoff section 3 that `--jobs 64`
oversubscribed the machine 2:1 and made SPARK's wall-clock backstop fire on cells that verify fine alone.
A freeze turns that into a pause rather than a corrupted grading run. `--verdict` prints measured headroom
per resource before a run starts, which is a better gate than the current practice of starting and seeing.

**Two things to fix before anyone acts on it.**

1. **It contradicts the operator's later instruction about the GPUs.** The skill states that GPU 0 is
   exclusively allotted to this project, cites a confirmation dated 2026-08-26, and says in bold not to
   throttle, yield or defer GPU-0 work. `HANDOFF-2026-09-19.md` section 3, written three weeks later, says
   all four 48 GB cards are shared with another user whose tensor-parallel job sits on all four, and that
   ours must give way the moment they ask. Both cannot be current. An agent that loads this skill and
   believes it will saturate a card against a standing instruction. Resolve it in the skill text, not in
   the reader's head.
2. **Its documented defaults do not match its script.** `SKILL.md` gives `LOAD_STOP` as 70 percent of
   nproc in the tunables list and 85 percent in the verdict table; the script defaults to
   `LOAD_STOP=85`. `SKILL.md` gives `LOAD_OK` as 40 percent, the script uses 70. `SKILL.md` gives
   `OTHERS_BUSY` a default of 100 percent, the script sets it to 0 and comments that this disables the old
   rule. The script is the truth in all three; the prose is stale. This is the same class of defect as the
   six the 2026-09-19 audit caught, so it should be treated the same way.

---

## 4. Two house rules already written for this machine (2 skills)

### `workflow-model-policy`

Not a library, a policy, and one the operator wrote: the current line is dated 2026-09-06 and says Sonnet
at medium effort for build, fix and measure agents that have a written contract and a test, and the session
model for design, reconciliation, adversarial review and diagnosing stalls. That maps cleanly onto how the
four agents in handoff 2a were commissioned — each given one file set, a measured target and a regression
bar, which is precisely the "written contract and a test" half. It is worth carrying forward because it
encodes an answer already decided, and because it warns about the inheritance failure mode (an `agent()`
call with no `model` silently inherits the parent's tier). Note the file keeps two superseded policies above
the current one; read the top block and ignore the rest.

### `unslop-text`

A guardrail against the AI register, grounded in a corpus of what readers name as a giveaway, and explicit
that it has no house style and will not write for anyone. The recurring chore it fits is this project's
largest non-code output: every run produces a `PREDICT-*.md`, a `PREREG-*.md`, a `WITNESS-*.md`, a
`NOTES-home.md`, a handoff and usually a README edit, and those documents are the claim. Its most useful
section is the one on the over-corrected register — the staccato, lowercase, "here's the thing" voice that
an agent lands in when told to sound less like an agent — which is a real risk given handoff section 9's
instruction to lead with the honest number unhedged.

**Subordinate it to handoff section 9, which is the actual style authority here.** In particular, do not
let its em-dash rule loose on existing files: `README.md` and `ROADMAP.md` use the em dash deliberately and
consistently, and a sweep that removes them would be a large diff that changes no meaning.

---

## What was rejected, and why

- **The whole `gsd-*` cluster: 67 skills and all 33 agents.** It is a complete, self-contained
  project-management system with its own roadmap file, phase directories, milestone archive, verification
  reports and knowledge graph. This project already has one, and the handoff names it: `internal/ROADMAP-LOG.md`
  is the roadmap of record and `ROADMAP.md` is its public face. Adopting GSD would not add a process, it
  would fork the roadmap of record into two, and the second copy would be the one nobody updates. Rejected
  on those grounds, not on quality.
- **The scientific-publishing set** (`latex-posters`, `pptx-posters`, `venue-templates`, `research-grants`,
  `scientific-writing`, `scientific-slides`, `peer-review`, `citation-management`, `pyzotero`,
  `literature-review`, `paper-lookup`, `paperclip`, `paperzilla`, `scholar-evaluation`, `sci-docx`,
  `sci-pdf`, `sci-pptx`, `sci-xlsx`). No paper is being written and the frontier survey
  (`t/FRONTIER-2026.md`) is done.
- **The general data-science libraries** (`polars`, `dask`, `vaex`, `zarr-python`, `networkx`,
  `torch-geometric`, `umap-learn`, `shap`, `pymc`, `pymoo`, `simpy`, `aeon`, `scikit-learn`, `statsmodels`,
  `seaborn`, `matplotlib`, `d3-viz`, `timesfm-forecasting`, `exploratory-data-analysis`). The project's
  data is a few hundred rows of verdicts in markdown tables. `statsmodels` is the one worth remembering,
  because `statistical-analysis` and `statistical-power` both call into it.
- **Everything web, image and document** (`exa-search`, `parallel-web`, `generate-image`, `infographics`,
  `scientific-schematics`, `markitdown`, `liteparse`, `database-lookup`). Not on any path here.
- **The RL and simulation set** (`stable-baselines3`, `pufferlib`, `pytorch-lightning`, `matlab`,
  `sympy`, `uncertainty-and-units`, `optimize-for-gpu`, `modal`). `optimize-for-gpu` targets CPU-bound
  NumPy and SciPy; this project's CPU cost is seven external provers, which it cannot touch. `modal` would
  move work off the lent lab cards, but the operator's instruction of 2026-09-18 is that all work runs on
  the lab workstation, so that is a decision to raise, not a skill to install.

## Near misses, listed so nobody re-derives them

- **`transformers`** — the project already lives further inside this library than the skill goes. The skill
  pins 5.12 and covers `AutoModel`, pipelines and `Trainer`; the handoff's traps are transformers 5.17's
  `LlamaTokenizer` eating spaces, trl 1.13 removing `use_logits_to_keep`, and an xgrammar mask narrower
  than the logits. None of those is in it, and nothing in it is new here.
- **`hugging-science`** — its stated domains include theorem proving and it has a `mathematics` and a
  `scientific-reasoning` topic, so it is the one discovery tool that might name a proof-pretrained base
  model beyond DeepSeek-Prover-V2, which is the single question handoff 8.3 turns on. Unverified: the
  catalog was not fetched, so whether it actually lists such models is unknown. Worth one look, not a
  recommendation.
- **`unslop-code`** — its top three tells are boilerplate, hallucinated APIs and over-engineering, none of
  which describes the six instrument defects the 2026-09-19 audit found. Those were logic that silently
  made a number wrong, which no scanner catches and no style rule prevents.
- **`hypothesis-generation`, `scientific-critical-thinking`, `experimental-design`'s neighbours** — the
  first two describe a discipline this project already practises better than the skills do, in writing,
  with dated preregistrations and a column for the answers that prove and are still wrong.
- **`skill-seekers` / `skill-builder`** — could turn `t/SPEC.md`, `t/COMMAND.md` and `t/GRADER.md` into a
  skill so an agent stops re-reading them each session. Plausible and untested, and it would need to be
  regenerated whenever SPEC moves, which is a new chore in exchange for a saved one.
