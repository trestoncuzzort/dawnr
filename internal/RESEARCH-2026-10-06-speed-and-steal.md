# Speed, and what to take from the open work: the sweep of 2026-10-06

The question (the operator, 2026-10-06 ~05:00Z): how do we speed this up, and which ideas from the many similar
open projects can we lift. The method: one workflow of eight Sonnet agents (seven scouts with narrow briefs and
no local commands, one checker that re-fetched every number), 630k tokens, four minutes. The checker confirmed
most figures and corrected four; the corrections are applied below. Every scout listed what it could not find;
those lists are kept (section 6) so nobody mistakes a gap for a negative result.

What is ours: the measurement of where the time actually goes (section 1) was taken from our own server logs
after the workflow returned, because no scout could run anything. Everything in sections 2–5 is a lead with a
source, to be measured here before it changes a default.

## 1. Where the time goes today (our logs, the untaught dawnr 4B, the lab's CPUs)

The reading of the 660 fresh tasks ran on eight CPU-only servers, six cores each, 7,209 model calls:

| what | seconds | share |
|---|---|---|
| generation (3,405,853 tokens) | 73,680 | 67% |
| prompt processing, calls under 1,500 tokens (6,591 calls, median 123 tokens) | 18,600 | 17% |
| prompt processing, the first call of a task (618 calls, median 2,334 tokens) | 16,957 | 16% |

- **The cache holds inside a conversation.** Within a task, each call processed only the new suffix (median 123
  tokens). The "cache falls to zero" failure the scouts found for hybrid models (section 3) did not occur inside
  a conversation here.
- **The shared prefix is paid again for every new conversation.** 2,334 tokens on the first call of every task,
  although the previous task's conversation held the same 2,260-token system-and-tools prefix. On six CPU cores
  that is ~27 s before the first token of every task. The server's checkpoint spacing defaults to 8,192 tokens,
  so no checkpoint exists inside the prefix; a new conversation that shares the prefix cannot restore it and
  reprocesses from zero. The fix to test is `--checkpoint-min-step 256 --ctx-checkpoints 64` (registered as S1).
- **Generation: 19.8 tokens/s median per call** (6 cores, MTP drafting at n-max 3), with draft acceptance
  0.83–1.0 and a mean accepted length of 2.2–3.5. Acceptance that high says n-max can go up (registered as S2);
  no source has a CPU number for drafting at all, so S3 measures drafting against none.
- **Training (the laptop's 8 GB card):** 2.0 min per step of 16 rows, 2,900 tokens each, of which ~2,260 are the
  same prefix in every row. 78% of every training token is the prefix, computed sixteen times per step.

## 2. The ranked queue (the checker's ten, with decisions)

| # | lead | source | decision |
|---|---|---|---|
| 1 | Checkpoints inside the prefix so a new conversation restores it (`-cms 256 -ctxcp 64`) | Particula write-up; llama.cpp issue 22384 | **running now (S1)** |
| 2 | MTP n-max sweep: 5 against 3 against none, same tasks, same cores | llama.cpp PR 22673; Unsloth's MTP page | **running now (S2, S3)** |
| 3 | Shared-prefix training: run the prefix once per step, the suffixes as a microbatch | arXiv:2606.01143 (RL, 2.9–4.4×); arXiv:2511.00413 (SFT, up to 6.2×) | the big lever for training; no public code; our own build after F is read |
| 4 | Pad or bucket row lengths so fla's Triton kernels do not recompile | fla issue 758 | fla 0.5.2 still carries the unused `NB` constexpr in both l2norm kernels (read 10/6); at our lengths NB takes a few dozen values, so the cost is a few dozen compiles per run; bucket rows to multiples of 256 in F2 and time the first 20 steps |
| 5 | Cap kept conversations per task at 3; keep only judged passes | SWE-smith (arXiv:2504.21798) | already our rule (per-family cap, passes only); keep |
| 6 | Mix ~20% general conversations into agent SFT | AgentTuning (arXiv:2310.12823) | for F2, only from Apache/MIT-model output; needs a general pool we do not have yet |
| 7 | Select medium-difficulty rows by the student's own loss; keep parallel-call rows | ToolACE (arXiv:2409.00920) | for F2: one forward pass over the rows, compare against random at equal size |
| 8 | Windows policy fails closed: literal PowerShell only, deny URL launches and forced deletes | Codex `powershell_tree_sitter.rs`, `windows_dangerous_commands.rs` | after the freeze lifts (dawnr_agent/system.py is frozen until F is read) |
| 9 | `-NoProfile -NonInteractive` and a timeout on every PowerShell recipe | Microsoft about_powershell_exe | after the freeze lifts; cheap |
| 10 | A twin-solution audit of the 66 judges (mutate the oracle, count rejections) | SWE-ABS (arXiv:2603.00520), STING (arXiv:2604.01518) | the proof families already have broken twins; extend to files/edit/data/git; a CI check that each family admits its oracle and rejects the untouched start |

Not taken, and why:

- **Packing, 8-bit optimizers, Unsloth, Liger** for training speed: rows are near-uniform in length (packing gains
  little), the optimizer step is negligible for rank-16 LoRA, Unsloth itself warns against 4-bit on Qwen3.5 and
  needs 10 GB for bf16 LoRA (we have 8), Liger's fused loss is already covered by response-only masking. A
  one-flag Liger A/B is allowed if idle time appears; expect a few percent.
- **Architect/editor split, bash-only agent**: every gain Aider reports came from a different or stronger
  model in each role; a same-model 4B split doubles generation. Bash-only breaks per-tool approvals.
- **Whole-trajectory DPO (ETO)**: flat on tau-bench in the one paper with our model family. If a preference
  stage is ever tried, it is the step-level one (Agentic-DPO, arXiv:2607.10601: Qwen3.5-9B tau-bench retail 21.7%
  SFT → 41.4%) after an SFT baseline is measured, and only on tasks where the student has both a pass and a fail.
- **GUI automation (pywinauto, WinAppDriver)**: needs Windows-side Python or an admin service; a model driving a
  GUI is the harm case we avoid.
- **KV cache q4_0**: 8.3% output similarity to f16 in the one benchmark found; q8_0 only if memory binds, and
  gated on the 161 tasks.

## 3. Inference speed on consumer machines (scout findings, checked)

| finding | measured | source |
|---|---|---|
| MTP drafting from the model's own head: `--spec-type draft-mtp --spec-draft-n-max N`; n_parallel must be 1; prompt processing 40–50% slower | 27B/35B on GPUs: n-max 3, 7.0 → 21.6 tok/s at 90.8% acceptance; n-max 2 ~2.4× at 82.6%; RTX 3060 laptop 22.97 → 42.45 tok/s. No 4B number anywhere | llama.cpp PR 22673 |
| Starting values: n-max 2, try 1–6; ~2 GB extra memory on large models | 1.4–2.2× on GPUs; a tutorial's RTX 3090 run 38.86 → 56–67 tok/s (its flags are not on that page: checker) | Unsloth MTP page; DataCamp tutorial |
| Hybrid models cannot truncate state; without a covering checkpoint the server logs "forcing full prompt re-processing" (at `-lv 4`), resets n_past to 0 and erases all checkpoints | 15 checkpoints (~2.19 GiB) erased, n_past 12,134 → 0 (27B); 12,146 tokens reprocessed (~11 s) → 31 tokens (115 ms) after a code fix | Particula write-up; llama.cpp issue 22384 |
| A changing header at the start of the system prompt loses the whole cache | after removing it: 212 new tokens in 511 ms (27B, RTX 4090, `--ctx-checkpoints 128 --checkpoint-min-step 128`) | one practitioner's post |
| A 71-request hybrid session: rolling checkpoints, two full clears | hit rate 95.9%, 2.9M tokens saved; generation 30–35 tok/s (hardware unstated) | a published server log |
| `--cache-reuse` is KV shifting, which recurrent layers cannot do; slot save/restore can keep the processed prefix across server starts | flag reference only | llama.cpp server README |
| N-gram self-speculation (`ngram-mod`, combinable with draft-mtp) | GPT-OSS-120B 181 → 446 tok/s (2.5×) on repetitive output; "favorable cases" only | llama.cpp PR 18471; docs/speculative.md |
| KV q8_0 vs f16 | 81.6% output similarity, 7% slower; q4_0 8.3% similarity | one blog benchmark (7B, RTX 5060 Ti) |
| Agent CLIs' prefixes: one hosted CLI sends ~33k tokens before the task; another ~6,900; dawnr's prefix is ~2,300 | 268k vs 72k input tokens per passing task over five runs | a wire-level comparison post |

dawnr already keeps the volatile text (task, cwd, date) after the system-and-tools block, which is why the cache
holds within a conversation (section 1). The two things not yet done: a checkpoint inside the prefix (S1) and
saving the processed prefix slot at install time so the first call of a session is warm (`--slot-save-path` is
already passed; nothing saves or restores yet).

## 4. Training speed on an 8 GB card (scout findings, checked)

| finding | measured | source |
|---|---|---|
| Schedule-level shared-prefix reuse: prefix forward once, suffixes as a microbatch reading the prefix K/V, prefix backward once on the accumulated gradient; exact to floating point | up to 4.395× (2.930× conservative), peak memory −59.1%; RL training, Llama3-8B/Qwen3-8B/Qwen3-MoE; no code link | arXiv:2606.01143 |
| Tree Training: the same idea for SFT of agent trajectories that share prefixes; the abstract says it handles SSM layers | up to 6.2× end-to-end (dense and MoE, SFT and RL); no repository named | arXiv:2511.00413 |
| fla's gated-delta-rule kernel: an unused kernel argument made Triton recompile on every new sequence length | no timing in the issue | fla issue 758 |
| causal-conv1d for the short conv in each delta-net layer | no benchmark; sm_120 under WSL unverified; profile first, build only if the torch fallback is over ~5% of the step | Dao-AILab/causal-conv1d |
| Padding-free packing | 1.4–2× on short, variable rows; ours are near-uniform 2,900 | HF packing blog; TRL docs |
| Unsloth | 1.5× on Qwen3.5 claimed; bf16 LoRA 4B needs ~10 GB; QLoRA not recommended on Qwen3.5 by Unsloth | Unsloth Qwen3.5 page |
| Liger-Kernel's Qwen3.5 patch: RMSNorm, SwiGLU, fused CE; not the delta-net; incompatible with TRL's chunked_nll | +20% on 8×A100 LLaMA-3-8B; no consumer number | Liger README |
| Gradient checkpointing off if memory allows removes the recompute pass | the scout's estimate 25–33% of step time, not measured | Unsloth long-context post; TRL docs |

The order of trials for F2's trainer, each a 20-step A/B on the laptop: fla recompile check (bucket lengths to
multiples of 256), gradient checkpointing off (fail fast in 3 steps), Liger on; then the shared-prefix build,
gated on a numeric match of loss and gradient norm against the current trainer on the same batch. Qwen3.5's
delta-net layers carry a recurrent state instead of K/V, so the prefix state to carry is the recurrent state
plus the conv state; whether fla returns a gradient for `initial_state` is the first thing to check.

## 5. Teaching a small agent: recipes, data, verifiers (scout findings, checked)

**Recipes with measured small-model results.**

| finding | measured | source |
|---|---|---|
| Resolved-only rejection sampling, at most 3 trajectories per task; easy, repeatedly solved tasks hurt | 6,457 → 5,016 trajectories; 500 → 10.8%, 1,000 → ~12%, 5,016 → 40.2% on SWE-bench Verified (32B) | SWE-smith, arXiv:2504.21798 |
| Filter on reward, mix general data (η=0.2) | unfiltered 1.34 vs filtered 1.96 held-in; agent-only η=1.0: 2.47 held-in but 0.87 held-out vs 1.40 mixed | AgentTuning, arXiv:2310.12823 |
| Dual-layer verification; medium-complexity rows by the model's own loss; LoRA r16 α32 lr 1e-4, 3 epochs | BFCL-v3 59.22 (8B); medium difficulty best; dropping parallel-call rows hurt multi-tool use | ToolACE, arXiv:2409.00920 |
| Validate the task blueprint before generating the dialogue | phase-1 success 28% → 70%; xLAM-2 3B 38.2 on tau-bench against Llama-3.1-70B 38.2 | APIGen-MT, arXiv:2504.03601 |
| A few hundred judged trajectories move an agent; LoRA lr 5× the full-FT rate | 491 trajectories: 32B 7.0 → 20.6 on Verified; lr 1e-4 full / 5e-4 LoRA r64 | SWE-Gym, arXiv:2412.21139 |
| Smaller models need more samples; 500 is the low end, still rising at 1,000 | Llama-2-7B HotpotQA EM 14.8 → 26.2 on 500 trajectories | FireAct, arXiv:2310.05915 |
| Sample several tool calls at inference and run the one most agree on; cuts invalid calls most for the smallest students | 0.5B matched 1.5B, 1.5B matched 3B, 3B matched 7B (QA and math) | agent distillation, arXiv:2505.17612 |
| Rejection sampling's gain is in distinct correct paths, larger for weaker models | GSM8K LLaMA-7B 35.9 → 49.3; k saturates fast (k=12 41.6, k=100 41.7) | RFT, arXiv:2308.01825 |
| More passes over a small set beats one pass over more; stop on a held-out slice, not on loss | 128 epochs × 400 samples beat 1 epoch × 51,200 by 12–26 points (long-CoT, Qwen3-4B among others) | arXiv:2602.11149; LIMA |
| Step-level preferences (expert action vs the student's own next action) with an SFT anchor; whole-trajectory DPO flat | Qwen3.5-9B tau-bench retail SFT 21.7, ETO 20.9, Agentic-DPO 41.4; 2B and 4B results exist | arXiv:2607.10601 |
| Mix teacher demonstrations with teacher continuations from the student's own states; pure on-policy and pure teacher both suboptimal | optimum 50–90% on-policy depending on budget (non-monotonic) | arXiv:2607.04574 |
| Self-improvement on own filtered trajectories | WebArena 7.14 → 9.36 (a 72B base, not a small model: checker) | arXiv:2405.20309 |
| Shortest-pass selection is mostly an efficiency gain; selection barely beats random under ~1,000 rows | SWE-TRACE 4B 33.6 → 37.8 with 21.5% fewer tokens (60K samples) | arXiv:2604.14820 |

What this means for F2 (after F is read): same gate, same teachers; rows deduplicated by tool-call sequence with at
most 2–3 distinct passes per task and the fewest-calls pass as tiebreaker; the weak families oversampled with a
per-family cap; rows ranked by the base 4B's loss with both tails dropped, against random at equal size; 2 epochs
with a checkpoint each half epoch chosen on held-out families; a dozen families withheld entirely (already the
rule: 13). A general-conversation share needs a pool written by Apache/MIT models that we do not have yet.

**Task factories and verifiers.**

| finding | measured | source |
|---|---|---|
| Bug injection validated by fail-to-pass: procedural AST edits 40.2% yield at $0, combining two validated bugs 96.9% at $0, model rewrites 35–56% at $0.38–3.93 | 50k instances, 128 repos | SWE-smith |
| Back-translate the instruction from the failing check's output; fewer than 20% of tests discriminate between candidate patches for most problems | 4,578 environments; execution-only verifiers plateau near 43%, hybrid 51% | R2E-Gym, arXiv:2504.07164 |
| Every task ships an oracle solution; the judge must pass it and fail the untouched start | ~100 tasks (format only) | Terminal-Bench README |
| Weighted checkpoints and partial credit per multi-step task | 175 tasks; best agent 30.3% full, 39.3% partial | TheAgentCompany, arXiv:2412.14161 |
| Explore first, derive the task from the state diff afterwards; chain 2–6 tasks | ~40% of 20k mobile and ~35% of 10k desktop explorations became verified tasks | AutoPlay, arXiv:2509.25047; OS-Genesis |
| Diversity of environments beat task count; unit-test every tool for success, expected refusal and state change | 16 domains, 2,560 tasks; +12.5% on tau2-Bench (8B); monotonic from 2 to 16 domains | ScaleEnv, arXiv:2602.06820 |
| Mutants of the oracle that pass the old tests expose weak judges | 50.2% of SWE-bench Verified instances strengthened; 19.71% of previously passing agent patches rejected; top agent 78.80 → 62.20 | SWE-ABS, arXiv:2603.00520 |
| Variants of the reference patch (32 operators) that survive the tests get new tests | 77% of instances had a survivor; agents' resolved rate −4.2 to −9.0 | STING, arXiv:2604.01518 |

The twin-solution audit (queue item 10) is the cheapest of these and the one that protects both the 1,990 training
rows and the fresh-task number: a judge that accepts a wrong answer poisons both.

**Harness.** Aider: code in JSON arguments hurt every model tested (GPT-3.5 whole-file 46% against ~19% for JSON
diffs, but from different model snapshots: checker); weak models default to whole-file output; forgiving patch
application cut edit errors 9×; no line numbers. SWE-agent's ablations (GPT-4 Turbo): a lint gate on edits
(18.0 → 15.0 without), a 100-line viewer window, summarized search, the last five observations as context. The
GPT-4.1 guide's three reminders (keep going, use tools rather than guess, plan between calls) gave ~20% on one
vendor's own model, unreplicated. dawnr already has the edit gate (dry run and check), plain-text edits, and a
short tool list; the testable items are a whole-file write for small files, an observation window, and the three
reminders as an A/B on the 161 and the factory, each after the freeze lifts.

**Windows and cross-platform.** Codex keeps a deny list, not a safe list, for Windows (`powershell`, `explorer`,
`mshta`, `rundll32`, browsers; any http(s) URL passed to Start-Process/start/Invoke-Item; `Remove-Item -Force`,
`del /f`, `rd /s /q`), and lowers PowerShell to argv through a tree-sitter grammar that fails closed on variables,
subexpressions, smart quotes and comments, with no cmdlet allowlist. Microsoft documents `-NoProfile
-NonInteractive -Command`, `reg query` as the read-only registry call, WSL interop's rules (`.exe` required, runs
as the Windows user with no sandbox, `cmd.exe /C` for built-ins, `wsl.conf [interop]`), and reading the theme
through UISettings; it does not document the Personalize registry values or the `ImmersiveColorSet` broadcast
string (community practice). BurntToast is archived (2026-09-25); NirCmd is closed source. For dawnr: recipes with
typed slots rather than free PowerShell (already the design), the deny shapes added to the ask tier, every
PowerShell recipe non-interactive with a timeout, an interop check that says how to enable it.

## 6. What the scouts could not find (kept as gaps)

- Any measured MTP, n-gram or thread-count result for a 4B on a CPU, or for `--cache-reuse` on a hybrid model.
- Public code for either shared-prefix training paper; any fla-against-torch timing for the gated delta rule;
  torch.compile on a hybrid model; causal-conv1d on sm_120 under WSL.
- SWE-smith's fine-tuning hyperparameters; ToolACE's sample count; Jan-nano's recipe; SmolLM3's tool-data mix;
  Qwen3-Coder-Next's environment training; licences of most datasets (not read).
- Any 4B-scale measurement of the harness choices (edit format, observation window, reminders); the pages of
  several hosted CLIs (404s); OpenHands' stuck detection.
- A Codex Windows safe-command list (none exists at main); Microsoft pages for the dark-mode registry values,
  toasts from unpackaged apps, screenshots; Apple's TCC and `defaults` pages.
- Any KTO/ORPO result on tool use under 8B; a clean "shortest trajectory" ablation at small scale; an epoch rule
  for ~2k tool-call rows with a shared long prefix.

## 7. What runs now, and what comes after

Running (registered in `locallm/PREDICT-2026-10-05-assistant.md`, section S): four lab CPU servers, six cores each,
the same eight tasks one after another: the product's flags; plus checkpoints inside the prefix; plus n-max 5;
no drafting. Read: first-call prompt tokens of tasks 2–8 (S1), tokens per second written (S2, S3), tasks done
unchanged (S4). If S1 holds, `bin/dawnr` gets the two flags (a receipt first); if S2 holds, n-max moves to 5; if
S3 fails on the CPU, drafting becomes a GPU-only default.

After F is read (the laptop's taught adapter, ~08:00Z): the queue above in order, each item its own
registration, the freeze lifted.

## Appendix: every finding as the scouts returned it (checked numbers corrected in the body above)

### inference-speed-consumer

- **MTP drafting: flags, n-max, and what it costs on prompt processing** — https://github.com/ggml-org/llama.cpp/pull/22673
  - what: llama.cpp mainline supports the model's own MTP head via --spec-type draft-mtp with --spec-draft-n-max N (default 3) and --draft-p-min (default 0.00). The MTP head loads from the same GGUF. The PR notes MTP supports only n_parallel=1, prompt processing is typically 40-50% slower (device-to-host embedding transfers), and extra memory is about 2.5 GiB VRAM on a 27B/35B (smaller for a 4B, not measured).
  - measured: PR: n-max 3 gave 7.0 -> 21.6 tok/s at 90.8% acceptance; n-max 2 gave ~2.4x at 82.6% acceptance; RTX 3060 laptop 22.97 -> 42.45 tok/s (1.85-1.90x), all on Qwen3.6 27B / 35B-A3B, not a 4B. Not found: any 4B number.
  - here: Sweep --spec-draft-n-max 1,2,3,4 on the 161-task set; record tok/s written, the draft acceptance line in the server log, and time-to-first-token on a cold 2,300-token prefix. Because prompt processing slows 40-50%, check that the prefix-heavy agent loop does not lose more on prefill than it gains on decode. Our own log says 95k of 100k tokens came from cache, so prefill should be rare.
  - risk: Prefill penalty could erase the gain on turns that miss the cache; n_parallel must be 1; the n-max sweet spot differs per hardware. License: MIT (llama.cpp).
- **Recommended MTP starting values from Unsloth and a benchmark write-up** — https://unsloth.ai/docs/models/mtp
  - what: Unsloth's guide gives --spec-type draft-mtp --spec-draft-n-max 2 as the starting point and says to test 1-6. A DataCamp tutorial used n-max 3 with q8_0 KV and flash attention on.
  - measured: Unsloth: Qwen3.6-27B MTP 160 tok/s and 35B-A3B 240 tok/s on an RTX 6000; 1.4-2.2x on GPU generally; gains smaller on low-memory-bandwidth devices; ~2 GB extra memory. DataCamp (https://datacamp.com/tutorial/multi-token-prediction-llama-cpp, fetched): Qwen3.6-27B Q4_K_M on RTX 3090, 38.86 -> 65-67 tok/s simple prompt, 56-61 tok/s complex prompt (1.44-1.71x), flags -fa on -ctk q8_0 -ctv q8_0 -np 1 -b 2048 -ub 512. No acceptance-rate sweep given.
  - here: Use n-max 2 as the baseline arm and 3 as the second arm; the desktop CPU run previously gave 21.7-23.5 tok/s with the 0.8B draft, so compare MTP against that on the same CPU too.
  - risk: All numbers are GPU and 27B+; CPU or 8 GB laptop gain for a 4B is unmeasured. Qwen sampling advice (temp 0.7, top-p 0.8, min-p 0) may differ from our harness's sampler.
- **Prompt cache on Qwen3.5 hybrid models: cache can silently fall to zero** — https://particula.tech/blog/prompt-reprocessing-swa-hybrid-models-kv-cache
  - what: Qwen3.5 is hybrid (Gated DeltaNet + attention), so llama.cpp cannot truncate its state and relies on context checkpoints. When no checkpoint covers the resume point, the server logs 'forcing full prompt re-processing due to lack of cache data' (visible only at -lv 4), resets n_past to 0 and erases all checkpoints. Current flags: -ctxcp/--ctx-checkpoints (default 32), -cms/--checkpoint-min-step (default 8192), -cram/--cache-ram (default 8192 MiB). --checkpoint-every-n-tokens was removed by PR #22929.
  - measured: Production case: 15 checkpoints of 149.6 MiB erased (~2.19 GiB), n_past 12,134 -> 0, on a 65,536-slot Qwen 27B with q8_0 KV. A second source (https://github.com/ggml-org/llama.cpp/issues/22384, fetched) reports 15K-token turns taking ~15 s instead of milliseconds on Qwen3.6-27B, fixed by a code patch: 12,146 tokens reprocessed (~11 s) down to 31 tokens (115 ms) on an RTX 3090.
  - here: Our harness already sees 95% cache reads, but verify per turn: run the server with -lv 4 and grep for 'forcing full prompt'. Then add --checkpoint-min-step 128 (or 256) and --ctx-checkpoints 64 so the 2,260-token prefix gets a checkpoint, and compare uncached prefill tokens per call before and after.
  - risk: A default min-step of 8192 means a 2,900-token conversation may never get a mid-prompt checkpoint. Small steps use RAM (about 150 MiB per checkpoint on a 27B; a 4B is smaller, not measured). The issue-22384 fix may or may not be in the build we run; I did not check the build.
- **A stable prefix matters more than any flag (llama.cpp prompt-cache restore evidence)** — https://mykolaaleksandrov.dev/posts/2026/06/claude-code-llamacpp-prompt-cache-fix/
  - what: A real agent CLI against llama.cpp lost the whole cache because a changing header sat at the start of the system prompt. Removing it restored 'restored context checkpoint, prompt eval time = 511.40 ms / 212 tokens'.
  - measured: Qwen3.6-27B Q4_K_XL, RTX 4090, 170k context, flags --cache-ram 15000 --ctx-checkpoints 128 --checkpoint-min-step 128 with MTP on: 212 new tokens in 511 ms after the fix versus full reprocessing before.
  - here: In dawnr, put everything volatile (dates, cwd, task text, any counters) after the tools block; keep system+tools byte-identical across calls and sessions. Test: log prompt-eval tokens for call 2..N of one task, expect only the new suffix.
  - risk: Low. Only constraint is that the volatile parts must really be moved to the end. Source is one blog post, single machine.
- **Cache hit behavior on a long Qwen3.5 session with rolling checkpoints** — https://gist.github.com/huytd/3a1dd7a6a76fac3b19503f57b76dbe65
  - what: A server log from a 71-request llama.cpp session on Qwen3.5 shows rolling 8-checkpoint prompt cache, with two full clears when LCP similarity dropped to 0.813.
  - measured: 128k context, n_batch 4096, flash attention on, cache 8192 MiB: hit rate 95.9%, 2,907,967 tokens saved, cold prefill ~1,484-1,509 tok/s, warm incremental ~500-1,100 tok/s, generation 30-35 tok/s. Hardware not stated in what I read.
  - here: Treat any edit to earlier turns (history trimming, summarising old tool results) as a cache-clear risk; trim only at the tail or restart the session. Measure the fraction of calls with a full reprocess.
  - risk: Anecdotal log, hardware unknown. Our 20-task run gave 95,199 of 100,852 prompt tokens from cache, the same order.
- **--cache-reuse and cache_prompt: what the server docs say** — https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
  - what: cache_prompt defaults true (reuses the common prefix). --cache-reuse N (default 0) is the minimum chunk size to reuse via KV shifting. --cache-ram default 8192 MiB. --slot-save-path plus /slots/{id}?action=save|restore|erase persist a slot's cache to a file. --kv-unified is on when slots are auto.
  - measured: none given (flag reference only). Not found: a measurement of --cache-reuse on a hybrid model; KV shifting needs the ability to remove ranges, which the recurrent layers do not allow, so I would not expect it to help (inference, not verified).
  - here: Use slot save/restore for the one thing it is good for here: save the slot after the 2,260-token system+tools prefix is processed (curl POST /slots/0?action=save with --slot-save-path set) and restore it at dawnr start, so the first call of a session is not cold. Measure first-call time-to-first-token with and without. Leave --cache-reuse at 0 unless the log shows it is used.
  - risk: Slot files are tied to the exact model and prefix tokens; a changed prompt makes them useless. One older tutorial (https://github.com/ggml-org/llama.cpp/discussions/13606) calls persistent slots unsafe for production and slot-similarity switching unpredictable; with -np 1 that is moot.
- **N-gram self-speculation (no draft model) and its flags** — https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md
  - what: ngram-simple, ngram-map-k, ngram-mod and ngram-cache draft from the existing token history. ngram-mod uses a ~16 MB hash pool shared across slots, defaults n-match 24, n-min 48, n-max 64, and is documented for code iteration, reasoning repetition and summarisation. ngram-simple: size-n 12, size-m 48, min-hits 1. Types can be listed comma-separated in --spec-type.
  - measured: Docs give only acceptance rates (0.57576 and 0.70312 in examples), no speedups. The PR (https://github.com/ggml-org/llama.cpp/pull/18471, fetched) reports GPT-OSS-120B Python translation 181 -> 446 tok/s (2.5x, 76.8% accepted) and Qwen3-235B with heavy offload 11.77 -> 21 tok/s (1.8x), only 'in favorable cases with large repeated sections'.
  - here: Our agent edits files and quotes tool output back, which is the favourable case. Try --spec-type draft-mtp,ngram-mod (combined) with --spec-ngram-mod-n-match 12 or lower (24 is long for short outputs) on the 'changing files' and 'answering from files' task groups; compare tok/s on those groups only.
  - risk: Whether draft-mtp and ngram types combine well in the same server is not shown in the docs I read; wasted drafts cost verification time on a small CPU. Needs a measurement, not an assumption.
- **KV cache quantization q8_0 / q4_0: quality and speed** — https://inventivehq.com/blog/kv-cache-quantization-quality-benchmark
  - what: -ctk/-ctv accept f32, f16, bf16, q8_0, q4_0, q4_1, iq4_nl, q5_0, q5_1; default f16. flash-attn default is 'auto'. A quantized V cache has required flash attention in llama.cpp (not confirmed on the page I fetched).
  - measured: Qwen2.5-Coder-7B-Instruct Q4_K_M, 8,192 context, greedy, 12 prompts, RTX 5060 Ti 16 GB: output similarity to f16 81.6% for q8_0 and 8.3% for q4_0; generation 81.8 (f16), 76.4 (q8_0), 80.3 (q4_0) tok/s. On an M3 Max q4_0 was 42% slower. Another source's perplexity claim (+0.0043 for q8_0) came from a search snippet only, so I do not count it.
  - here: At 2,900 tokens per row and short contexts a 4B KV cache is small, so the saving is mostly memory on the 8 GB card; test only if VRAM is binding. Run -ctk q8_0 -ctv q8_0 against f16 on the 161 tasks and require no task lost. Do not use q4_0.
  - risk: Quality loss can change tool-call JSON subtly; q8_0 was 7% slower here. Single-source benchmark on a different model.
- **How agent CLIs size their system prompt and tools (token counts)** — https://dev.to/ashraf_chowdury09/claude-code-burns-33k-tokens-before-it-even-reads-your-prompt-45p2
  - what: A wire-level measurement of Claude Code vs OpenCode first requests. Claude Code: system prompt 27,344 chars, 27 tool schemas 99,778 chars, about 33K tokens. OpenCode: system 9,324 chars, 10 tools 20,856 chars, about 6,900 tokens. Our 2,300 tokens is already about a third of OpenCode's.
  - measured: 5-run benchmark: Claude Code ~268,000 input tokens per passing task vs OpenCode ~72,000 (3.7x); cache writes over five requests 53,839 vs 1,003 tokens because Claude Code's system bytes shifted between requests. Small sample, one machine, July 2026. The article does not discuss lazy or deferred tool loading; I found no measured source for it.
  - here: Measure tokens per tool in dawnr's tools block, then cut the longest descriptions and drop tools not needed for the task class (select a tool subset per mode, fixed per session so the prefix stays stable). Gate: no loss on 141/161. Each 100 tokens saved is about 4% of the prefix; the bigger win is keeping it stable (finding 4).
  - risk: Shrinking tool text can hurt tool-call accuracy of a 4B; per-turn tool changes break the cache. Blog-level source, not a paper.
- **CPU threads and batch sizes: what could and could not be verified** — https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
  - what: Server defaults: --threads -1 (auto), --threads-batch same as --threads, --batch-size 2048, --ubatch-size 512, flash-attn auto.
  - measured: none given. The benchmark discussion I fetched (https://github.com/ggml-org/llama.cpp/discussions/4167) held only Apple Metal numbers and gave no CPU thread guidance. Not found: a measured physical-cores-versus-hyperthreads rule or a 4B CPU tok/s sweep.
  - here: Our own CPU run used 12 threads on a 24-core desktop. Sweep --threads 6/8/12 for decode and --threads-batch 12/24 for prefill with llama-bench or the task set, measuring tok/s and prefill tok/s. Try -ub 256 vs 512 vs 1024 for the 2.3k prefill.
  - risk: Little published evidence, so gains are unknown; more threads can slow decode when memory-bandwidth bound.

Not found: Any measured MTP tok/s for a 4B Qwen3.5 model (all numbers found are 27B-35B on GPUs); Measured CPU-only MTP or n-gram speedup; Measured effect of --cache-reuse on hybrid/recurrent models; A measured physical-cores-vs-hyperthreads rule for llama.cpp CPU decode; A measured KV q8_0 effect on Qwen3.5-4B tool-call accuracy; Measured lazy/deferred tool-loading savings for a small-model agent; The Medium MTP article (HTTP 403) and the aiweekly/cloudmagazin pages were not fetched; I did not read the last three sections of PREDICT-2026-10-05-assistant.md past line 60 and only skimmed DAWNR-AGENT.md; README.md was not read (time spent on sources)

### training-speed-small-gpu

- **Shared-prefix reuse (Schedule-Level, arXiv:2606.01143): the biggest lever, but no code found** — https://arxiv.org/pdf/2606.01143
  - what: Run the shared prompt prefix forward once, run each suffix as an ordinary microbatch reading the prefix K/V while accumulating prefix-side gK/gV, then run the prefix backward once on the accumulated gradient. Equivalent to baseline training within floating-point tolerance. Implemented in verl for RL (GRPO), tested on Llama3-8B, Qwen3-8B, Qwen3-MoE-30B-A3B. Your rows share about 2,260 of 2,900 tokens (78%) across ALL rows, so the prefix would be computed once per optimizer step instead of 16 times.
  - measured: Up to 4.395x speedup (2.930x under conservative benchmarking) on dense models; up to 59.1% lower peak memory in phase B; Llama3-8B token capacity 17,920 to 29,696. Hardware, prefix and suffix lengths were not legible in my fetch of the PDF (the abstract page https://arxiv.org/abs/2606.01143 gave the same headline numbers). No code link found in either page.
  - here: The paper's attention is standard softmax K/V. Qwen3.5 is a hybrid: most layers are gated-delta-rule, whose prefix state is a recurrent state plus a conv state, not K/V. So the schedule has to carry the final recurrent state of the prefix into each suffix and accumulate its gradient (the fla kernels take initial_state, but I did not verify that they return a gradient for it). A simpler first test is available because your prefix is identical for every row and LoRA weights are fixed within a step: compute the prefix once with grad, keep the K/V and recurrent states, and run the 16 suffixes (~640 tokens each) against it. Measure: seconds per step and peak VRAM at equal loss, then check that the loss and LoRA gradient norm on a fixed batch match the baseline to bf16 tolerance. Upper bound from token counts alone: 16x2,900=46.4k tokens per step down to about 2,260+16x640=12.5k, roughly 3.7x less compute.
  - risk: High engineering cost and no reference implementation found. Delta-rule state gradients through the prefix are the unverified part. Gradient mistakes would be silent, so gate on a numeric equivalence test. Liger and Unsloth do not provide this.
- **Tree Training (arXiv:2511.00413): shared-prefix reuse for SFT of agentic data** — https://arxiv.org/pdf/2511.00413v3
  - what: Reuses the forward and backward work of common prefixes across trajectories in SFT, targeted at agent rollouts that share a prefix and branch. It is the nearest SFT-side prior art to your tool-use conversations. The search result also listed a Notion page 'packing tree training' that I did not fetch.
  - measured: 1.28x to 1.90x wall-clock training speedup depending on model scale and dataset (as summarised by my fetch; my fetch did not recover conditions). The paper names no repository.
  - here: Read the full paper for how it handles the backward pass (the search snippet describes a gradient restoration with a per-token compensation term). That may be easier to port than the K/V-cache schedule. Measure the same way as finding 1. Its gains are lower than the RL paper's because its prefixes are partial overlaps. Yours is a fixed 78% prefix, so expect the high end or better.
  - risk: No code found. Written for softmax-attention models; the hybrid delta-rule layers are untested.
- **flash-linear-attention (fla) for the gated delta rule, and the Triton recompile trap** — https://github.com/fla-org/flash-linear-attention/issues/758
  - what: Triton kernels for linear attention including chunk_gated_delta_rule, the layer type in Qwen3.5/Qwen3-Next. transformers' modeling_qwen3_5.py uses fla's kernel if importable and otherwise a pure-torch fallback (torch_chunk_gated_delta_rule). You have fla installed, so you are on the fast path for that op. fla issue 758 reports that l2norm_fwd_kernel has an unused NB argument that triggers Triton recompilation whenever the sequence length changes. Rows of different length therefore recompile during training.
  - measured: No timing given in the issue. The README (https://github.com/fla-org/flash-linear-attention) gives no fla-vs-torch number for gated delta rule; it only says chunked implementations often beat FlashAttention2 on GB200. I found no measured fla-vs-torch-reference speed for this layer, so you will need to measure it yourself.
  - here: Check your fla version is >=0.4.2 (the Swift guide asks for it), then pad or bucket every row to a few fixed lengths (for example multiples of 256) and watch step time for the first 20 steps. If the early steps are much slower than steady state, recompilation is the cause. A/B on 5 steps: bucketed lengths against free lengths.
  - risk: Low. Padding adds a few percent of tokens. Check that padded positions stay masked from the loss.
- **causal-conv1d for the short conv inside each delta-net layer** — https://github.com/Dao-AILab/causal-conv1d
  - what: CUDA depthwise causal conv1d (kernel sizes 2, 3, 4; fp16/bf16/fp32), BSD-3-Clause. The Qwen3.5 layer uses it if present and otherwise a torch fallback. The Swift Qwen3.5 guide recommends installing it from the Dao-AILab repo with --no-build-isolation.
  - measured: No benchmark on the page. The Swift guide (https://swift.readthedocs.io/en/v4.2/BestPractices/Qwen3_5-Best-Practice.html) gives no per-package speedup either. Nothing about Blackwell (sm_120) is on the page.
  - here: Profile first: torch.profiler on one step, and read how much time the torch conv fallback takes. If it is under about 5% of step time, skip the build, because a source build on WSL against cu128/sm_120 is the risky part. Otherwise build it with TORCH_CUDA_ARCH_LIST=12.0 and compare step time.
  - risk: Compile failure on Blackwell is possible; I did not verify sm_120 support. Small expected gain if the conv is cheap.
- **Padding-free packing and position_ids: do the hybrid layers support it?** — https://huggingface.co/blog/packing-with-FA2
  - what: HF DataCollatorWithFlattening and TRL padding_free/packing flatten rows into one sequence with position_ids, so there is no padding compute. TRL requires FlashAttention 2 or 3 for padding_free, and packing with the bfd strategy enables it automatically. Two sources conflict on Qwen3.5: modeling_qwen3_5.py in transformers main passes cu_seqlens (from cu_seq_lens_q) to the gated-delta chunk function, which implies support. The Swift guide says transformers' GatedDeltaNet does not support packing or padding_free and suggests group_by_length instead.
  - measured: HF blog (llama2-7B, mistral-7B, granite-8B-code): 2x throughput on FLAN (short, high variance), 1.4x on OrcaMath, memory down 20% and 6%. Unsloth (https://unsloth.ai/docs/blog/3x-faster-training-packing.md): 1.7x to 3x typical, 5x at best, on Qwen3-32B/8B and Llama3 8B with alpaca-cleaned at max_length 1024. TRL options confirmed at https://huggingface.co/docs/trl/main/en/sft_trainer. Source for the cu_seqlens claim: https://github.com/huggingface/transformers/blob/main/src/transformers/models/qwen3_5/modeling_qwen3_5.py
  - here: Your rows are about 2,900 tokens each with little length variance, so padding is probably a small part of your cost and this gain will be well below the quoted 2x to 5x. It also fights finding 1, because packing mixes rows. Only test it if rows vary in length. Check by comparing mean row length to the padded batch length. If they differ by more than 15%, test padding_free with FA2 against a baseline on a fixed 5 steps, and compare the loss for two packed rows against the same two rows run alone.
  - risk: Silent cross-contamination if the layers ignore the boundaries. FlashAttention 2 on sm_120 under WSL may not be installed.
- **Unsloth: fast kernels, but its Qwen3.5 guidance runs against your QLoRA setup** — https://unsloth.ai/docs/models/qwen3.5/fine-tune
  - what: Apache-2.0 core (AGPL for the Studio UI) with custom Triton kernels, a chunked/fused loss, offloaded gradient checkpointing, padding-free batching by default. It supports the Qwen3.5 family including 4B, and runs on WSL.
  - measured: Qwen3.5 training claimed 1.5x faster and 50% less VRAM than FA2 setups; 4B bf16 LoRA needs about 10 GB VRAM. The page says QLoRA (4-bit) is NOT recommended on Qwen3.5 because of larger than normal quantization differences. Repo (https://github.com/unslothai/unsloth) claims 2x faster, 70% less VRAM in general. The 1.5x claim has no stated hardware or sequence length in the fetched text.
  - here: 10 GB for bf16 LoRA exceeds your 8 GB card, so you stay on 4-bit, which is the option Unsloth warns against; check your held-out panel for loss from 4-bit before leaning on any speedup. Try Unsloth only as a 20-step A/B on the same data: step time and peak VRAM against your current HF Trainer. It would replace the model loading and trainer wrapper, so shared-prefix work would have to be redone on top of it.
  - risk: Quality risk from 4-bit on this model family per Unsloth's own statement. Its speed claims were measured on larger cards. Moving your pipeline onto Unsloth patches is a sizable change.
- **Liger-Kernel: Qwen3.5 patch covers RMSNorm, SwiGLU and fused linear cross-entropy, not the delta-net** — https://github.com/linkedin/Liger-Kernel/blob/main/README.md
  - what: BSD-2-Clause Triton kernels; apply_liger_kernel_to_qwen3_5 patches RMSNorm, SwiGLU, CrossEntropyLoss and FusedLinearCrossEntropy. It does not mention the gated delta net or Qwen3-Next. Enabled in HF Trainer with use_liger_kernel.
  - measured: Headline: +20% multi-GPU throughput and -60% memory, on LLaMA 3-8B, batch 8, bf16, FSDP, 8 A100s. No single or consumer GPU numbers in the README. In TRL the default loss_type is chunked_nll, which already drops ignored-label tokens before lm_head and chunks the cross-entropy; it is not compatible with use_liger_kernel (https://huggingface.co/docs/trl/main/en/sft_trainer).
  - here: Since response-only loss masks about 80% of your tokens, chunked_nll already saves most of the lm_head memory. Liger's extra gain on your setup is therefore likely small (norm and MLP fusion). Test: use_liger_kernel=True against the current run for 10 steps, comparing seconds per step and peak memory. Expect a few percent. It is a one-flag change if you are on the TRL or HF Trainer path.
  - risk: Low. The fused CE and chunked_nll cannot both be on.
- **Gradient checkpointing variants: offloading, and TRL activation_offloading** — https://unsloth.ai/docs/blog/500k-context-length-fine-tuning.md
  - what: Unsloth's offloaded checkpointing moves activations to CPU RAM, now with CUDA streams. TRL SFTConfig has activation_offloading=False by default and gradient_checkpointing=True by default. Checkpointing makes every step recompute the forward, which costs roughly a third more compute.
  - measured: Unsloth: overhead at most 0.1% for its enhanced version versus 1 to 3% for the April 2024 one; chunked loss 60% lower VRAM and 3.2x longer context; chunk sizes are tuned automatically to free VRAM. No tokens per second figures given.
  - here: These save memory, not time. They only help if memory is what forces you to checkpoint. At batch 1 and 2,900 tokens on a 4B in 4-bit, test gradient_checkpointing=False with per-device batch 1: if it fits in 8 GB, you remove the recompute pass (about 25 to 33% of step time in general; my estimate, not measured here). If it does not fit, selective checkpointing of only the full-attention layers is the next experiment.
  - risk: OOM on 8 GB. Make it fail fast with a 3-step test.
- **8-bit and paged optimizers (bitsandbytes)** — https://huggingface.co/docs/bitsandbytes/main/en/optimizers
  - what: bnb.optim.Adam8bit and paged variants replace 32-bit Adam states with 8-bit blocks. Tensors under 4,096 elements stay at 32-bit.
  - measured: Docs claim 75% less optimizer memory and '4x faster than a standard optimizer'. That speed claim is about the optimizer step only, without conditions. The docs also warn that gains scale with parameter count, not activation memory.
  - here: With rank-16 LoRA the trainable parameters number in the tens of millions, so the optimizer step is a negligible share of a 2-minute step. Expect no meaningful speedup; skip this for speed. Use optim=paged_adamw_8bit only if you are VRAM-bound.
  - risk: None for speed because the gain is negligible; small quality risk.

Not found: No public implementation of schedule-level shared-prefix reuse (2606.01143) or Tree Training (2511.00413) in TRL, Unsloth, Liger or Axolotl was found; neither paper page named a repo, and TRL's SFT docs show no shared-prefix option.; No measured fla versus torch-reference speed for chunk_gated_delta_rule was found (fla README gives only GB200 comparisons against FlashAttention2).; No torch.compile measurement for Qwen3.5 or hybrid models was fetched; I did not search it down.; Whether causal-conv1d builds on Blackwell sm_120 under WSL was not found.; Unsloth blog pages at unsloth.ai/blog/long-context and /blog/packing returned 403; I used the docs mirror instead.

### small-agent-models

- **SWE-smith / SWE-agent-LM: resolved-only rejection sampling, cap repeats per task** — https://arxiv.org/html/2504.21798
  - what: Claude 3.7 Sonnet ran on 8,686 synthetic task instances (17,906 attempts, 36% resolved). Only resolved trajectories were kept, with at most 3 trajectories per task instance, leaving 5,016 for SFT of Qwen2.5-Coder-Instruct 7B and 32B. Learning rate, epochs and LoRA-vs-full are in appendix F.1 and I could not extract them.
  - measured: SWE-agent-LM-32B 40.2% on SWE-bench Verified. Capping repeats cut the pool from 6,457 to 5,016 and the paper says easy, repeatedly solved tasks degrade performance. Training on 500, 1,000 and 5,016 trajectories improved roughly logarithmically. Pass rates by task source on 745 or fewer trajectories each: PR-mirror 9.2, LM-rewrite 8.8, procedural 8.6, LM-modify 5.7. Cost to build about $1,360. The page described the paper as CC BY-SA 4.0 (the paper licence, not necessarily the data).
  - here: Cap the number of kept conversations per practice-task family or instance at 3 in the 1,400-row set, so easy families do not dominate. Measure on the 161 hand-written tasks plus fresh practice tasks, against the uncapped set at equal row count.
  - risk: Teacher was Claude, which fails our Apache/MIT-only rule for training data. Only the recipe idea transfers. The SWE-smith data licence was not read.
- **AgentTuning: filter on reward and mix general data (eta 0.2)** — https://arxiv.org/html/2310.12823
  - what: AgentInstruct has 1,866 GPT-4 trajectories over six tasks with chain-of-thought rationales, kept only when reward r=1 (r>=2/3 for Mind2Web). It was mixed with 57,096 ShareGPT conversations. Settings: lr 5e-5 for 7B and 13B, batch 64, sequence length 4,096, AdamW, cosine schedule, 2% warmup. The mix ratio eta=0.2 was picked by scanning 0 to 1 on the 7B model.
  - measured: Unfiltered data scored 1.34 on held-in tasks against 1.96 filtered. Agent-only training (eta=1.0) scored 2.47 held-in but 0.87 held-out, against 1.40 held-out for the mixed run. Abstract: AgentLM-70B is comparable to GPT-3.5-turbo on unseen agent tasks.
  - here: Add a small share (about 20%) of non-agent chat or document-QA conversations to the 1,400 rows so the 4B keeps its general ability and does not overfit the tool format. Compare held-out task pass rate and a general-chat sanity set, with and without the mix.
  - risk: Trained models are 7B or larger on Llama-2 and the loss was full fine-tuning, not QLoRA r16. The ShareGPT mix used here is not licence-clean for us; we would need our own or Apache-model-generated general data.
- **ToolACE: dual-layer verification and medium-complexity selection, with a LoRA recipe** — https://arxiv.org/html/2409.00920
  - what: A synthesis pipeline over 26,507 APIs in 390 domains. Dialogs come from a user/assistant/tool multi-agent setup. A rule checker (executability, format) and a model checker (hallucination, consistency) filter them. Complexity is measured by the model's own loss on the target tokens. SFT of LLaMA-3.1-8B-Instruct with LoRA rank 16, alpha 32, lr 1e-4, 3 epochs, batch 48.
  - measured: ToolACE-8B scores 59.22% on BFCL-v3 overall (rank 3 at the time), AST 89.27%, executable 90.07%, relevance 85.37% and irrelevance 83.81%. Ablations: medium-difficulty data was best, more API diversity helped, and dropping parallel-call data hurt multi-tool use. Model licence on Hugging Face was noted as CC-BY-NC-ND-4.0 in a secondary summary; I did not read the model card.
  - here: Score each of the 1,400 conversations by the base 4B's own loss on the response tokens, drop the easiest and hardest tails, train on the middle. This costs one forward pass over the data. Compare against random selection at the same row count. LoRA r16 at lr 1e-4 for 3 epochs is close to what we already run.
  - risk: Fetch summary did not report total sample count or the exact size of each ablation effect. Training data here is GPT-4-class output, not licence-clean for us. The loss-based selection is an idea we can copy, not data.
- **APIGen-MT / xLAM-2: verify the task blueprint before generating the dialog** — https://arxiv.org/html/2504.03601
  - what: Phase 1 builds a task blueprint with ground-truth actions and checks it with a committee of LLM reviewers and format/execution checks, with feedback loops. Phase 2 simulates the human-agent dialog. 5,000 trajectories (APIGen-MT-5k), average 6 user turns and 7 tool calls. Full fine-tune with DeepSpeed ZeRO-3, bf16, AdamW, at most 3 epochs, sequence length 4,096 (from a secondary summary of the PDF; learning rate not disclosed).
  - measured: Agentic feedback raised Phase-1 success from 28% to 70%. tau-bench overall: xLAM-2-8b 46.7%, 3b 38.2%, 1b 21.8%, against Llama 3.1 70B at 38.2%. Data and models are CC BY 4.0 (the xLAM-2 base models are Llama or Qwen, so check each base licence).
  - here: Our factory already has judges for 66 task families. Add an acceptance gate that validates the task (ground truth reachable, judge agrees on a reference solution) before a teacher conversation is accepted, not just validating the final answer. Measure the share of rows removed and the fresh-task pass rate.
  - risk: Teacher models there were commercial LLMs. xLAM-2 gains are on tau-bench (retail and airline), a different domain from ours. Full fine-tune does not fit an 8 GB card.
- **SWE-Gym: small verified set, LoRA vs full recipe numbers** — https://arxiv.org/html/2412.21139
  - what: 2,438 executable Python tasks. Only 491 successful trajectories were collected by rejection sampling from GPT-4o and Claude 3.5 Sonnet, then used to fine-tune Qwen2.5-Coder 7B, 14B, 32B. Recipe: lr 1e-4 full or 5e-4 LoRA (rank 64), 32,768 context, up to 5 epochs, global batch 8.
  - measured: 32B on SWE-Bench Verified 7.0% to 20.6% (+13.6), on Lite 3.0% to 15.3%. A trained verifier gave Best@8 29.8% and Best@16 32.0%. Models and data CC BY 4.0. OpenHands LM 32B (37.2% on Verified, base Qwen2.5-Coder 32B, fine-tuned on resolved agent trajectories) builds on this; its licence was not stated on the page I read (https://www.openhands.dev/blog/introducing-openhands-lm-32b----a-strong-open-coding-agent-model).
  - here: Confirms that a few hundred judged conversations can move an agent a lot. For QLoRA on the 4B use a higher LoRA learning rate than full fine-tuning (they used 5x higher) and test 1e-4, 2e-4 and 5e-4 over 2 to 3 epochs on a 10% holdout of conversations.
  - risk: Gains are from a low base (7%) on coding. Our base is already 141/161, so headroom is much smaller. Teacher outputs from GPT-4o/Claude are not allowed as our training data.
- **FireAct: LoRA on a few hundred successful trajectories, sample-count scaling** — https://arxiv.org/html/2310.05915
  - what: 500 successful GPT-4 ReAct few-shot trajectories for single-task fine-tuning of Llama-2-7B and 13B. LoRA with int8, lr 3e-4, batch 16, 30 epochs for Llama models, 3 epochs for GPT-3.5. Multi-method mixing (ReAct plus CoT) was tested.
  - measured: HotpotQA EM: Llama-2-7B 14.8 to 26.2 (+11.4), 13B 21.2 to 34.4 (+13.1). Mixing methods helped GPT-3.5 (39.2 to 41.0) but different models liked different mixes and CodeLlama sometimes got worse. Smaller models needed more samples: non-trivial scores at 500, still improving toward 1,000.
  - here: Treat the 1,400 rows as the lower end for a 4B. Plot held-out pass rate at 350, 700 and 1,400 rows to see whether we are still on the rising part of the curve before paying for more teacher data. Do not mix several output styles unless a held-out test shows it helps.
  - risk: 2023 models and an older task (QA). The 30-epoch setting is from tiny data and would likely overfit 1,400 long rows.
- **Agent distillation (NeurIPS 2025): first-thought prefix and self-consistent action sampling** — https://arxiv.org/html/2505.17612
  - what: Qwen2.5-32B-Instruct teacher; about 2,000 filtered trajectories from 1,000 HotPotQA and 2,000 MATH questions (wrong ones dropped). Students 0.5B to 7B in the Qwen2.5-Instruct family, LoRA rank 64 on all linear layers, 2 epochs, batch 8, lr 2e-4. A first-thought prefix improves teacher trajectory quality; self-consistent action generation (N=8, temperature 0.4, majority vote on observations) cuts invalid code at inference.
  - measured: From the abstract page: 0.5B matched 1.5B CoT-tuned, 1.5B matched 3B, 3B matched 7B. Text says self-consistency cut code parse and execution errors, most for 0.5B. First-thought gains were mixed (big at MATH level 5, worse on some categories). I did not see per-run numeric tables.
  - here: The inference trick is cheap to test with llama.cpp: sample a few candidate tool calls and only run the one most candidates agree on (or the one that parses and passes the sandbox dry run). Measure the invalid-call rate and pass rate on the 161 tasks. Data side: Qwen2.5-32B-Instruct is Apache-2.0, though it is not one of our current teachers.
  - risk: Tasks are QA and math, not file or shell work. Extra samples cost latency (65 tok/s on the laptop card). Per-run effect sizes not extracted.
- **Devstral Small, Qwen3-Coder-Next, Jan-nano, SmolLM3, Nemotron: licences and what they disclose** — https://huggingface.co/datasets/nvidia/Nemotron-Post-Training-Dataset-v1
  - what: Devstral Small (Apache 2.0) was trained on real GitHub issues, built with All Hands AI, run in the OpenHands scaffold. Qwen3-Coder-Next is 80B total with 3B active, Apache 2.0, 256k context, hybrid Gated DeltaNet and attention. Jan-nano is a fine-tune of Qwen3-4B for tool and MCP use, Apache-2.0. SmolLM3 supports XML and Python tool formats, and its SFT was 1.8B tokens (1B non-reasoning, 0.8B reasoning). Nemotron post-training v1 has a 310,051-sample tool-calling split from DeepSeek-R1-0528 and Qwen3-235B-A22B, CC BY 4.0, with prompt curation that removed inconsistent, easily guessed and syntactically wrong entries.
  - measured: Devstral Small 46.8% on SWE-bench Verified (https://mistral.ai/news/devstral). Qwen3-Coder-Next 70.6% on Verified, 44.3% on SWE-bench Pro, 36.2% on Terminal-bench 2.0 (https://huggingface.co/Qwen/Qwen3-Coder-Next). SmolLM3 numbers: https://huggingface.co/blog/smollm3, which gave no tool-data mix. Jan-nano: https://huggingface.co/janhq/Jan-nano, which gave no training method, data or scores. None of these pages gave a recipe in numbers.
  - here: The Nemotron tool-calling split (CC BY 4.0, outputs from Qwen3-235B-A22B and DeepSeek-R1) could be a source of general tool-format conversations. A sample of a few thousand could be checked against our tool interface and judges. I did not read the dataset's exact per-sample licence terms beyond the page statement, or whether outputs were verified.
  - risk: DeepSeek-R1-0528 and Qwen3-235B outputs: confirm both teachers' licences allow training on outputs (R1 is MIT; check Qwen3-235B model card). Format mismatch with our tool schema is likely.

Not found: SWE-smith appendix F.1 hyperparameters (lr, epochs, LoRA vs full, seq length): the page fetched did not show them; ToolACE total sample count and per-ablation effect sizes: not extracted; APIGen-MT learning rate: not disclosed in what I read; no rejection percentage for the committee review; Jan-nano training recipe, data and SimpleQA score: the Hugging Face page gave none; SmolLM3 tool-calling SFT mix and its licence: not given on the blog page; Qwen3-Coder-Next executable-environment and RL training details: the model card gave none; OpenHands LM 32B licence and exact SFT recipe: not on the blog page; Nemotron agentic model recipes (Nano or Super tool-use post-training): I only read the dataset card, not the model papers; SWE-smith trajectory dataset licence: only the paper's CC BY-SA 4.0 was seen

### data-selection-and-objectives

- **Self-improvement on web agent tasks: filtered own trajectories, mixed in-domain + out-of-domain** — https://arxiv.org/html/2405.20309
  - what: Fine-tune a base agent on its own trajectories after unsupervised filtering (drop self-declared impossible, refusals, env errors). Three mixtures tested. Fetch summarizer's mixture labels (A in-domain, B in+out of domain, C out-of-domain only) were not cross-checked against the paper text, so treat labels as unconfirmed.
  - measured: WebArena functional correctness: base 7.14%, mixture A 8.87%, B 9.36% (the paper's '31% relative improvement'), C 6.16%. Capability score 15.44 base, 19.12 for A and B, 16.91 for C. Filtering took 812 trajectories to 58 plausible ones, raising precision from 7.1% to 91.9%. Mixture C gave ~1.6x longer trajectories and ~3.9x more invalid actions. Gains are small in absolute terms (+2 pts) and the base model's scale is not stated in what I read.
  - here: Cheap check: take the 660 fresh tasks, keep only student passes (judge-labelled, so the filter is exact, unlike the paper's heuristic). Train arm 1 = teacher rows only vs arm 2 = teacher + student own passes, same steps. Score on the 161 hand tasks and fresh-family tasks.
  - risk: Absolute gains are tiny and the base was weak (7%); our student passes ~78%, so own-pass data may add little new signal and mostly reinforce what it already does.
- **Rejection-sampling fine-tuning (RFT): gain is driven by number of DISTINCT correct paths, bigger for weaker models** — https://ar5iv.labs.arxiv.org/html/2308.01825
  - what: Sample k solutions per question from SFT models, keep correct ones, de-duplicate by reasoning-path (equation list), fine-tune on the union. Math (GSM8K), LLaMA 7B-33B.
  - measured: GSM8K, LLaMA-7B: SFT 35.9% to 49.3% with rejection samples pooled from several models (12.84 distinct paths/question). LLaMA2-7B 41.6 to 50.3; LLaMA-13B 43.0 to 52.1; LLaMA2-13B 50.0 to 55.4 (gain shrinks with stronger base: +13.4, +8.7, +9.1, +5.4). Single-model k scaling for 7B: k=1 37.6, k=12 41.6, k=100 41.7 (saturates fast). Distinct paths per question 5.2 per 7B model at k=100. Math only, not agents.
  - here: For each task, keep up to N (2-3) judged-pass trajectories that differ in tool-call sequence, not duplicates. Pool teacher passes (GLM-5 + Qwen3-Coder-Next) and student passes; de-dup by normalised tool-call sequence. Measure rows kept vs held-out family pass rate.
  - risk: Math reasoning paths are not agent trajectories; diversity of tool sequences may matter less than diversity of tasks. Our 1,400 rows are already two teachers, so some of the multi-model diversity gain is already taken.
- **STaR (self-taught reasoner): iterate generate, keep correct, rationalise failures with the answer, retrain** — https://arxiv.org/abs/2203.14465
  - what: Loop: sample rationales, fine-tune on correct ones, for failures re-generate given the correct answer (rationalization), repeat from the base model each round.
  - measured: Only the abstract was fetched: 'significantly improves' over direct-answer fine-tuning and matches fine-tuning a 30x larger model on CommonsenseQA. No per-condition numbers were available in what I read; full paper not read.
  - here: The rationalization step maps to our 438 weak-family teacher rows: they are the 'teacher shown the answer/with strong help' data for tasks the student fails. Retrain from the base each round on teacher + student passes rather than stacking adapters.
  - risk: Numbers not verified; STaR was single-turn QA with few-shot prompting, not tool agents. Training on rationalized (answer-leaked) traces can teach post-hoc justification; for agents the teacher passes are real tool interaction so this is less of an issue.
- **Trajectory-level DPO (ETO): SFT first, then DPO on student failure vs expert-success pairs** — https://arxiv.org/html/2403.02502
  - what: Behavioural cloning on expert trajectories, then iterate: student rolls out on training tasks, build (success, failure) pairs, DPO, repeat. Llama-2-7B-Chat main model.
  - measured: Llama-2-7B-Chat: WebShop seen 67.4 vs SFT 63.1; ScienceWorld seen 65.0 vs SFT 53.0, unseen 72.4; ALFWorld 68.6 vs SFT 60.0. Authors report average reward +8% (WebShop) and +9.5% (ScienceWorld) over SFT, and +22% on unseen ScienceWorld tasks. Environments are text-game, not file/PC tool-use.
  - here: Pairs on the same task: teacher pass (chosen) vs student fail (rejected), or student pass vs student fail on the same task from the 660 fresh runs (we have both). Train SFT first, then a short DPO (beta ~0.1, 1 epoch) on pairs only from tasks with at least one pass and one fail. Measure the 161 tasks plus fresh families.
  - risk: DPO needs a reference model pass (extra memory on 8 GB; with LoRA the adapter-off pass is the reference, workable but ~2x step time at ~2,900 tokens/row). Whole-trajectory pairs share a 2,260-token prefix and long sequences, which is where DPO is known to be unstable; see next finding.
- **Agentic-DPO: step-level preferences from expert action vs the student's own one-step negative, with SFT anchor** — https://arxiv.org/html/2607.10601
  - what: For each state in an expert trajectory, the chosen action is the expert's and the rejected action is sampled from the current student; DPO plus an SFT anchor loss, refreshed over rounds. Directly measured on Qwen3.5 2B/4B/9B and tool use.
  - measured: Qwen3.5-9B: StableToolBench SFT 78.5%, trajectory-level DPO (ETO) 92.5%, Agentic-DPO 94.1%. tau-bench retail SFT 21.7%, ETO 20.9%, Agentic-DPO 41.4%. Mind2Web step success SFT 45.6, ETO 56.8, Agentic-DPO 64.4. Config: batch 16, 5 refresh rounds, K=4 negatives, SFT anchor lambda 0.5, beta 0.008; pools ~3,786 pairs (tool/tau) to 7,362 (Mind2Web); matched PPA+SFT at 25% of data. Hardware 4x A6000. 2B and 4B results existed but I did not capture their numbers.
  - here: We have teacher rows (expert actions) and the student's own wrong actions on the same states: replay the student on the teacher's prefixes, sample 4 next actions, treat judge-failing/different tool calls as rejected. Add as a short stage after SFT with a 0.5x SFT anchor. This is the one DPO variant with measured tool-use results on our exact model family.
  - risk: Needs the student served for sampling at every refresh (we have llama.cpp so this is cheap), but the paper's compute was 4 GPUs; on a 5050 at ~2 min/16 rows the DPO stage costs hours. Negatives are 'not the expert action', which can punish valid alternative actions; the SFT anchor mitigates it. Preprint dated 2026, single group, not independently replicated.
- **Divergence-point preference learning for multi-turn tool agents (own trajectories, QLoRA rank 16)** — https://arxiv.org/html/2606.23112
  - what: Find the step where a successful and a failed trajectory of the same task diverge (state match or prefix alignment), filter by action correctness, DPO only on that point, under the same tool-graph context used at inference.
  - measured: Qwen3.5-9B, 4-bit NF4 QLoRA rank 16, tau2-bench 375 tasks: weighted avg reward baseline 0.304, with ToolGraph 0.338, plus DPO round 2 checkpoint 0.355. Airline 0.600 to 0.713, retail 0.219 to 0.319, telecom flat. No SFT or RFT baseline on same model, so DPO's marginal value over simply SFT-ing on the passes is NOT measured. Gains come mostly from the orchestration, DPO added ~+0.017.
  - here: Same recipe as our setup (QLoRA r16). For tasks where student has both a pass and a fail, cut both at the first diverging tool call and use only that step as a DPO pair, with identical system+tools prefix to inference. Compare against plain SFT on the pass.
  - risk: Evidence that DPO beats SFT-on-passes is absent here; the DPO increment is small. Train-inference prompt mismatch was a failure mode they hit; our prefix is fixed so this is manageable.
- **Mix teacher-prefix and student-prefix data; pure on-policy and pure teacher both suboptimal** — https://arxiv.org/html/2607.04574
  - what: Teacher continues from states the student actually reaches (short bounded continuations) alongside plain teacher demos. Students Qwen2.5-3B (HotpotQA), Qwen3-0.6B (ALFWorld), Qwen3-8B (Terminal-Bench-Dev).
  - measured: ALFWorld optimal fraction of student-prefix data was ~90% at 147K tokens, ~50% at 296K, ~90% at 562K (non-monotonic, noisy); authors say a mix is essential and on-policy-only is suboptimal. On Terminal-Bench-Dev, with 10% of a 15,209-trace corpus plus short on-policy teacher continuations, 16-19% matched the full-corpus baseline of 17.3% that used RL. Success filtering and critical-state filtering cut retained tokens but cost more teacher inference; recommended only when training compute is scarce (ours is). Training used 8 epochs on HotpotQA.
  - here: Our compute is the scarce side, so success-filter. Concrete: replay student on the 660 fresh tasks; where it fails mid-way, have a cheap teacher (Bedrock) write only the next few turns from the student's own state, judge the end result. Mix about 1:1 with teacher full-run rows by token count (the paper has no single right ratio).
  - risk: Requires new teacher calls (Bedrock cost) and a replay harness for mid-trajectory takeover; no stable ratio exists, so a 1:1 start is a guess to be tuned on a held-out family.
- **Shortest successful trajectory selection: measured on large corpora, mostly efficiency not accuracy** — https://arxiv.org/html/2604.14820
  - what: HyperEyes progressive rejection sampling keeps the shortest successful trajectory per query (271K tasks to 30K demos). SWE-TRACE and P2T prune trajectories per step. Separate paper: curation by error-retry rate.
  - measured: SWE-TRACE (selection by step-wise oracle progress, not strictly 'shortest'): 4B standard SFT 33.6% resolve, 74 steps, 33.0M tokens vs cascaded 37.8%, 66 steps, 25.9M tokens (+4.2 pts, -10.8% steps, -21.5% tokens); 30B 56.4 to 59.2. 60K samples. HyperEyes (https://arxiv.org/html/2605.07177): 30K demos by shortest-success, claims 5.3x fewer tool calls, but no clean ablation of the shortest rule alone was in what I read. Code-agent LoRA study (https://www.alphaxiv.org/abs/2607.17205.md; Qwen2.5-Coder-7B, QLoRA r64, 2 epochs): at 500-1,000 trajectories quality-filter vs random gap <1% (doubling data gave ~12.7% CE-loss reduction); only at 2,000 trajectories did top-quality selection separate (3.6% gap, p=0.016); error-retry rate alone captured the dominant signal. That study measures CE loss, not task success.
  - here: Cheap and safe: when a task has several judged passes, keep the one with fewest tool calls / fewest error-retries; skip it as a way of discarding data below ~2k rows, since the code-agent study found selection barely beats random at 500-1,000. Test as a tiebreaker only. Measure median tool calls per pass and pass rate.
  - risk: At our data size, selection effects are likely within noise; shortest-only can delete verification and recovery steps that the judge-checked answers rely on. Our paper evidence is on 30B/32B-class models and large corpora.
- **Difficulty-aware rejection tuning (DART-Math): allocate more correct samples to hard queries** — https://arxiv.org/html/2407.13690v2
  - what: Vanilla rejection sampling over-represents easy queries. Uniform keeps k correct per query (k=40); Prop2Diff gives up to 192 correct responses to the hardest queries, using fail rate as difficulty. About 590K samples per dataset, synthesized with DeepSeekMath-7B-RL.
  - measured: Mistral-7B on MATH: vanilla rejection tuning 38.7%, Uniform 43.5%, Prop2Diff 45.5%. Math only. A separate search result (arxiv 2604.06298, not fetched, snippet only so not counted as a source) claims hard samples yield diminishing returns for small models in GRPO; not verified.
  - here: We have per-task student pass/fail on 660 fresh tasks, i.e. a free difficulty measure (fail rate over several student samples). Make the 438 weakest-family rows count by oversampling (2-3 rows per hard task, distinct trajectories), cap per-family share so no family exceeds ~15% of rows, hold out whole families to check transfer.
  - risk: Duplicating or over-weighting hard tasks that even the teacher passes only occasionally risks training on lucky or noisy passes; DART's gains were with 590K samples, much larger than our 1.8K. Hard families may be hard for tool-capability reasons that data does not fix.
- **Epochs and overfitting on 1-2k examples: more epochs on a small set can help; LIMA-style 15 epochs; stop on held-out, not loss** — https://arxiv.org/html/2602.11149
  - what: Evidence on repeated passes over small SFT sets. LIMA fine-tunes on 1,000 examples for 15 epochs; the repetition paper shows many epochs on few samples beat one epoch on many.
  - measured: Repetition paper (long-CoT math/science SFT; Olmo3-7B, Qwen3-8B, Qwen3-4B): at fixed 51,200 updates, 128 epochs on 400 samples beats 1 epoch on 51,200 by 12-26 pts on AIME/GPQA; gains plateau near full memorisation (~100% token accuracy), diminishing at 32-64 epochs; training token accuracy is the suggested stopping signal; less forgetting than scaling unique data. LIMA (https://arxiv.org/html/2305.11206): 1,000 examples, 65B, 15 epochs, lr 1e-5 decayed to 1e-6, batch 32, residual dropout up to 0.3; perplexity did not track generation quality so checkpoint chosen on a 50-example dev set; doubling data without more prompt diversity did not help. Code-agent LoRA study above: 2 epochs. A search snippet (not a fetched source) mentioned 3 epochs good and 4 overfitting on another task; not verified.
  - here: Our budget is ~2 min per 16-row step, so 1,840 rows = ~115 steps per epoch (~3.8 h). Do 2 epochs saving a checkpoint each half-epoch, evaluate each on a dev slice of held-out families (not training-loss), pick the best; do not go to 3+ unless dev still rising.
  - risk: Both epoch papers are on long-CoT or chat data, not tool-call rows with a shared 2,260-token prefix (most of every row is repeated, response-only loss leaves ~640 supervised tokens), so repetition tolerance may differ. Overfitting to the 66 families shows up on held-out families, not in loss.
- **Held-out transfer: keep general data in the mix, and mixed training transfers better than agent-only** — https://arxiv.org/html/2310.12823
  - what: AgentTuning mixes 1,866 verified agent trajectories with general instructions. Separate result: a 122B model SFT+RL on 363 MCP tasks transfers to unrelated benchmarks.
  - measured: AgentTuning: best agent fraction eta=0.2 (20% agent + 80% general); held-out agent tasks improved 76% (7B), 57% (13B), 176% (70B) relative; AgentLM-70B scored 0.98 on held-out tasks with agent-only data vs 1.40 mixed. Cross-benchmark paper (https://arxiv.org/html/2608.00181, Qwen3.5-122B-A10B, single run, descriptive only): Toolathlon +9.6 pp, tau2-bench +5.3, BFCL-V4 +3.5, SWE-Bench Pro +5.8, Terminal-Bench 2 +2.8, with no external benchmark in training. Gains in the second paper are for a 122B model and one run; relevance to a 4B is unproven.
  - here: Our own held-out-family transfer test: withhold 10-12 of the 66 families entirely from training, train, and compare pass rate on withheld vs seen families and vs the untouched base (78% on fresh tasks). Also run a regression check on non-agent chat/doc questions; if general behaviour drops, mix in a small slice of general instruction data (Apache/MIT-model output only).
  - risk: With only 66 families, withholding a dozen shrinks the training data; AgentTuning's 20% ratio is for a general-instruction pool we do not have under the licence rule, so a self-written pool is needed.
- **ORPO / KTO on pass-fail pairs: no measured tool-use result found; small-model evidence is chat-only** — https://arxiv.org/html/2403.07691
  - what: ORPO folds an odds-ratio penalty into the SFT loss, no reference model. KTO uses binary good/bad labels with no pairing.
  - measured: ORPO paper: models OPT 125M-1.3B, Phi-2 2.7B, Llama-2-7B, Mistral-7B on UltraFeedback; AlpacaEval 2.0: Phi-2 6.35%, Llama-2 9.44%, Mistral-ORPO-beta 12.20%; MT-Bench 7.32. ORPO trained 10 epochs at ~8e-6. Win rate vs DPO rose with scale (41.7% at 125M, 70.9% at 1.3B). Chat alignment only. A small-model SFT/DPO study (https://arxiv.org/abs/2603.20100, only a search snippet, not fetched) says DPO adds small gains over strong SFT at GPT-2 scale; not counted as a source. KTO: no paper fetched; no tool-use number found.
  - here: Reference-free ORPO would save the DPO reference pass on our 8 GB card and use pass/fail pairs directly in one stage with the SFT rows, but there is no evidence for tool use; treat as a second-priority ablation after Agentic-DPO-style pairs.
  - risk: Unvalidated for agents; 10-epoch recipe is long for our step time and it can disturb a model already close to the ceiling.

Not found: Any measured KTO result on tool-use or agent trajectories with a model under 8B (only a search snippet for ORPO/KTO in chat; nothing fetched).; A clean ablation isolating 'shortest successful trajectory' alone at small scale; HyperEyes bundles it with RL and the code-agent curation study measured CE loss, not task success.; A measured ratio of teacher passes to own passes for a 4B tool agent; the one paper with a mix study (arxiv 2607.04574) found non-monotonic optima (50-90% on-policy by budget) with no single rule.; Direct evidence for hard-example upweighting on tool-use agents under 8B; DART-Math is math with 590K samples and the small-model-hard-samples-GRPO claim was only a snippet.; Epoch recommendations specific to ~2k tool-call rows with a shared long prefix and response-only loss.; The full text of STaR was not read, only the abstract page; per-dataset numbers not captured. Several PDF fetches returned binary, so numbers came via arXiv HTML or ar5iv summaries (summarizer-model extraction, not independently re-read). The Agentic-DPO 2B/4B Qwen3.5 numbers were not captured.

### task-factories-and-verifiers

- **SWE-smith: four bug-injection routes, validated by fail-to-pass** — https://arxiv.org/html/2504.21798
  - what: Synthesizes task instances from any Python repo by injecting a bug and keeping it only if it breaks at least one previously passing test. Four routes: LM Modify, LM Rewrite, procedural AST edits (13 transforms), combine-bugs, and PR mirroring (revert a PR with an LM).
  - measured: 50k instances from 128 repos (abstract at arxiv.org/abs/2504.21798). Validation yield by route: LM Modify 56% (17,887 instances, $0.38/candidate), LM Rewrite 35% (4,173, $3.93), procedural 40.2% (15,641, $0), combine-bugs 96.9% (10,092, $0), PR mirroring 33.8% (2,344, $5.53). 2-minute test limit per candidate. Model trained on it: 40.2% pass@1 on SWE-bench Verified. Limitation: Python-centric AST code.
  - here: For dawnr's code-with-tests and edits families, add a procedural 'break it' generator: take a working fixture, apply AST/line mutations (flip operator, drop loop, off-by-one), and keep a task only if the family's tests go pass->fail. Then 'combine' two validated breaks in one file for harder tasks. Measure yield per mutation operator and 4B solve rate by number of combined bugs.
  - risk: Procedural bugs are unnatural; fail-to-pass says a test notices, not that the fix is unique, so weak tests will still accept wrong fixes.
- **R2E-Gym SWE-GEN: tasks from commits, synthetic issue by back-translation** — https://arxiv.org/html/2504.07164
  - what: Builds executable tasks from commits with no human issue or tests. Filters commits (max 5 non-test files, 100 edited lines, 2000-char patch, 10 statement changes, plus LLM judge), generates tests where missing, validates that they fail before and pass after, and writes the problem statement from failing test output without leaking the solution.
  - measured: Over 8.1K tasks (8.7K per the abstract); 4,578 environments after decontaminating against SWE-bench, 2.5x more than issue-based collection. Finding: for most problems less than 20% of tests discriminate between candidate patches, so execution-only verifiers plateau near 43%; hybrid execution plus execution-free verifier reaches 51% on SWE-bench Verified.
  - here: Back-translation fits our factory: for each family, derive the instruction text from the judge's failing output (what the check says is wrong) rather than hand-writing it, then compare 4B solve rate against hand-phrased instructions. Also copy the size caps as a difficulty filter.
  - risk: Synthetic issue text may leak the answer or drift from the judge; needs a leak check.
- **SWE-Gym and SWE-rebench: real tasks at 2.4k and 21k** — https://arxiv.org/abs/2505.20411
  - what: SWE-Gym: 2,438 real Python tasks, each with executable environment and unit tests. SWE-rebench: automated continuous pipeline extracting interactive tasks from GitHub, with fresh tasks used for contamination-free evaluation.
  - measured: SWE-rebench: over 21,000 tasks, NeurIPS 2025, shows some models inflated by contamination. SWE-Gym (https://arxiv.org/abs/2412.21139, abstract only): 2,438 instances; fine-tuning gave up to 19% absolute on SWE-bench Verified/Lite and 32.0%/26.0% with a trained verifier. Only abstracts were read; validation details not found.
  - here: Mostly confirms scale targets. The one transferable idea is a rolling fresh split: regenerate a held-out slice of the 66 families with new seeds and fixtures each week so the 78% fresh-task number cannot be memorised.
  - risk: Abstract-level reading only; real-repo tasks do not map to dawnr's desktop and document families.
- **Terminal-Bench task format: instruction, Dockerfile, tests, oracle solution** — https://github.com/laude-institute/terminal-bench
  - what: Each task has task.yaml (English instruction and metadata), a Dockerfile, test scripts run inside the sandbox, and a reference oracle solution script. The harness runs the tests in Docker to decide success.
  - measured: About 100 tasks in beta (README at fetch time). The README page gave no validation rates; a docs page at tbench.ai/docs/task-format returned 404.
  - here: Require every dawnr family to ship an oracle solution and to prove the judge passes it and fails an untouched start state before the family is admitted. Count how many of the 66 families already have this; add a CI check that runs oracle->pass and no-op->fail.
  - risk: Oracle-passes-and-no-op-fails is necessary only; it does not catch wrong-but-passing.
- **TheAgentCompany: weighted checkpoints, partial credit, 29% LLM-judged** — https://arxiv.org/html/2412.14161
  - what: 175 workplace tasks, each with checkpoints worth points; deterministic Python evaluators for most, an LLM evaluator for subjective deliverables.
  - measured: 175 tasks; full score binary, partial = 0.5*Result/Total + 0.5*Sfull; about 29% (51 tasks) use Claude-3.5-Sonnet as evaluator; about 3,000 person-hours over 2 months, with screenshot proof, lead review and independent checkpoint-weight review; best agent Gemini-2.5-Pro 30.3% full, 39.3% partial.
  - here: Give each multi-step family (git, files plus documents) a checkpoint list with weights and report partial credit next to pass/fail. Use it to find where the 4B fails (it may complete 3 of 4 checkpoints) and to pick which steps to oversample in training data.
  - risk: LLM evaluators conflict with 'checked by something that did not write it' if the same model family is used; keep deterministic checks.
- **OS-Genesis and AutoPlay: derive tasks from exploration, then verify** — https://arxiv.org/html/2509.25047v1
  - what: OS-Genesis lets an agent explore a GUI first, derives the task description afterwards from what happened, and filters trajectories with a reward model. AutoPlay explores, then generates tasks from the exploration trajectories, and an MLLM verifier checks them.
  - measured: AutoPlay: about 20k mobile tasks over 20 apps giving about 8k successful trajectories (roughly 40%); about 10k desktop tasks over 13 Ubuntu apps giving about 3.5k (roughly 35%); AndroidWorld 40.1% (7B), OSWorld 14.5% (72B). OS-Genesis (https://arxiv.org/abs/2412.19723, abstract only): reverse task synthesis plus trajectory reward model, ACL 2025; no sizes read. AgentSynth (https://arxiv.org/abs/2506.14205, abstract only): over 6,000 tasks by chaining subtasks, $0.60 per trajectory, success 18% at difficulty 1 to 4% at level 6.
  - here: Reverse synthesis for the 'computer' family: let GLM-5 or Qwen3-Coder-Next explore a throwaway sandbox home with the approved commands, record the final state diff, then write the task from the diff and make the judge check that diff (state-based, no LLM verifier). Chain 2 to 6 existing families into one task as AgentSynth does and measure solve rate by chain length.
  - risk: AutoPlay and OS-Genesis verify with models, which is the weakness we want to avoid; only the state-diff-as-judge variant is acceptable. GUI work is not dawnr's setting.
- **Self-play and synthesized-environment papers: ScaleEnv, SPADE, AutoForge** — https://arxiv.org/html/2602.06820v1
  - what: ScaleEnv builds domains with tools, DB tables and a tool-dependency graph, unit-tests every tool (success with right state change, expected rejection of bad input, unexpected failure), and instantiates tasks by graph expansion verified by executing code against the real DB. SPADE and AutoForge generate environments with easily verifiable tasks.
  - measured: ScaleEnv: 16 domains, about 50 tools and 5-20 tables each, 2,560 tasks; about 546k tokens per domain foundation, about 93.2k per task; Qwen3-SE gains on tau2-Bench +12.5% (8B) and +4.1% (32B); more domains helped monotonically from 2 to 16, i.e. diversity of environments beat task count. SPADE (https://arxiv.org/pdf/2608.19197): got only a general description, no numbers. AutoForge (https://arxiv.org/abs/2512.22857): abstract only, no numbers.
  - here: Add environment diversity rather than more tasks per family: generate new fixture worlds (different file trees, CSV schemas, git histories) per family from a seed, with a tool-level test for each approved command that checks success, expected refusal and state change. Then compare 1,400 rows over 66 worlds against the same rows over 200 worlds.
  - risk: Token cost per domain is high for a team using hosted teachers; SPADE and AutoForge not read deeply.
- **SWE-ABS: mutants of the solution expose wrong-but-passing work** — https://arxiv.org/abs/2603.00520
  - what: Strengthens tests in two stages: coverage-driven augmentation via program slicing, then mutation-driven adversarial tests built from plausible-but-incorrect patches that pass the old tests.
  - measured: On SWE-bench Verified (500): 50.2% of instances strengthened; 19.71% (2,184 patches in the companion count) of previously passing top-30-agent patches rejected; top agent 78.80% -> 62.20%. Only the abstract page was read, not the method section.
  - here: Run a twin-solution audit over the 66 judges: for each family, mutate the oracle solution (drop a case, wrong edge, extra file touched, leave a stray file) and check the judge rejects each mutant. Report a per-family mutant-kill rate; any family below 100% on non-equivalent mutants gets a stronger check.
  - risk: Equivalent mutants inflate the survivor count; needs an equivalence screen.
- **STING: surviving variants of the reference patch diagnose weak judges** — https://arxiv.org/html/2604.01518v1
  - what: Makes semantically altered variants of the ground-truth patch with 32 operators in 7 categories (10 attempts each) plus LLM-written behaviour-different variants, filters by AST normalisation, LLM equivalence screen and diff, runs the existing tests, and writes new tests targeting every variant that survives.
  - measured: On SWE-bench Verified: 77% of instances have at least one surviving variant; 1,316 candidate tests generated, 1,014 kept over 211 instances; patch-region line coverage +10.8 points, branch +9.5; top-10 agents' resolved rate dropped 4.2-9.0% with 329 accepted patches now rejected.
  - here: Same loop as SWE-ABS but automated: for each family, generate variants of the oracle, record survivors, and add a judge assertion that kills each. Metric: fraction of families with a surviving variant before and after, and the change in 4B pass rate on the same outputs (expect it to fall; that is the point). Our 'broken twin' idea in t already does this for proofs, so extend it to file, edit, data and git families.
  - risk: LLM-written variants using GPT-5-mini in the paper; we would need a permissive model (GLM-5 or Qwen3-Coder-Next) and the operator-based path alone is safer.

Not found: WebArena / BrowserGym task generation: not fetched, no source read; Terminal-Bench docs page (tbench.ai/docs/task-format) returned 404; only the GitHub README was read, no validation rates; SWE-smith validation details beyond the four strategy table were read from arxiv HTML; SWE-Gym, SWE-rebench, OS-Genesis, AgentSynth, AutoForge pages were abstracts only (no pipeline validation rates); SPADE paper: only a vague summary came back, no dataset sizes or rates; UTBoost and PatchDiff style papers were seen in a search but not fetched; Licences of all datasets and code not read

### harness-techniques

- **Plain-text edits beat JSON-wrapped code (Aider)** — https://aider.chat/2023/07/02/benchmarks.html
  - what: Aider found asking a model to put code inside JSON function-call arguments hurts it, in syntax (escaping) and in the quality of the code itself. Plain markdown or text blocks win.
  - measured: GPT-3.5: whole-file plain text 46% first-attempt vs JSON function-call diff about 19%. The 2024 follow-up (133 exercises, four strong models) found all four worse with JSON, Sonnet worst, GPT-4o about 0.4% down. That follow-up was at https://aider.chat/2024/08/14/code-in-json.html and had no weak-model data.
  - here: Check whether any dawnr tool takes file or code content inside JSON arguments (write_file or edit). If so, A/B on the 161 tasks and the factory a variant where content sits in a delimited plain-text block. Report edit-failure rate and pass rate. Do it on the 4B first, since JSON escaping is probably the failure point.
  - risk: The numbers come from GPT-3.5 and large models. No 4B data was found. Qwen's native tool-call template may already handle string arguments better than the tested models did. Changing the format means regenerating the 1,400 training rows, or at least their tool-call text.
- **Weak or unknown models default to the simplest edit format ('whole')** — https://aider.chat/docs/leaderboards/edit.html
  - what: Aider defaults to whole-file output for lesser-known models. Diff formats save tokens but demand more of the model. udiff exists because it cut GPT-4 Turbo's lazy elision.
  - measured: Leaderboard: Qwen2.5-Coder 3B 39.1%, 1.5B 31.6%, 0.5B 14.3%, all on whole. Gemini-exp-1206 scored 80.5% on whole vs 69.2% on diff, and o1-mini 70.7% vs 61.1%. No Qwen3 4B/8B entry was found; the only Qwen3 on the page was 32B at 40.0% on diff. The default-to-whole statement is at https://aider.chat/docs/leaderboards/notes.html.
  - here: For small files (say under 150 lines), offer a rewrite-whole-file tool, or make it the default, next to the patch or edit tool. Measure edit-apply failure rate and token cost per task on the 4B.
  - risk: Whole-file output costs tokens and is slow at 65 tok/s. It also invites accidental changes to untouched lines. The existing second looks for lost files and changed tests would need to catch that.
- **Architect/editor split (Aider)** — https://aider.chat/2024/09/26/architect.html
  - what: One model plans the change in prose and a second turns it into edits. Aider's reason is that a single prompt makes a model split its attention between solving and obeying the edit format.
  - measured: On Aider's code-editing benchmark, GPT-4o alone 71.4% (diff) and with GPT-4o as both architect and editor 75.2%. o1-mini 61.1% became 71.4% with a deepseek editor. gpt-4o-mini 55.6% became 60.2%, so the weakest model also gained. Best result: o1-preview plus an o1-mini or deepseek editor on whole, 85.0%.
  - here: Two-pass on the same 4B: pass 1 writes a plan with no tools; pass 2 applies it with tools. The prefix is shared, so the KV cache should keep the cost down. Compare against the single-pass 141/161.
  - risk: Every gain Aider reported came from different or stronger models in each role. Nothing shows a same-model 4B split helps, and the split doubles the tokens generated at 65 tok/s. Test on the practice factory first.
- **Tool interface ablations (SWE-agent)** — https://arxiv.org/html/2405.15793v3
  - what: The agent-computer interface design alone moved scores. The ablated pieces were a lint gate on edits, summarized search, a 100-line viewer window, and a context made of the last 5 observations.
  - measured: GPT-4 Turbo, SWE-bench Lite. Baseline 18.0%. Without the lint gate 15.0%. Search variants: iterative 12.0%, none 15.7%. Viewer window: 30 lines 14.3%, full file 12.7%. Context: full history 15.0%, no demonstration 16.3%. The paper reports a 64% relative gain over plain shell use.
  - here: Compare dawnr's read tool against these. Check for a read window of about 100 lines. Check for search that returns a short summarized list rather than iterative stepping. Check that old tool observations are dropped from context beyond the last few. Our 2,260-token prefix leaves little context on a 4B, so the observation-trimming test is the cheapest. Measure pass rate on the factory.
  - risk: These are GPT-4 Turbo results on Python repo tasks. Dropping history can hurt tasks that need earlier output. dawnr already has an edit gate (checker or parser, per DAWNR-AGENT.md), so that part is already covered.
- **Unified-diff lessons: no line numbers, forgiving application (Aider)** — https://aider.chat/docs/unified-diffs.html
  - what: Aider reports that line numbers hurt models, that a patch applier that tolerates imperfect diffs is essential, and that asking for whole coherent functions beats surgical line edits. Codex's apply_patch follows the same rule: context identifies the location, with no line numbers.
  - measured: GPT-4 Turbo lazy-coding benchmark: search/replace 20% vs unified diff 61%, with 3x fewer lazy comments. Removing flexible patching gave a 9x increase in editing errors. Not asking for coherent function-level edits gave a 30-50% increase in edit errors. The no-line-numbers rationale for apply_patch is at https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide, with no number attached. Codex's own apply_patch spec pages returned 404 and were not read.
  - here: Audit dawnr's edit tool. Does it need exact string match, or line numbers? Add fallback matching (whitespace-normalised, anchor on a unique context line) and, when a match fails, return the closest matching lines so the model can repair. Track the edit-apply failure rate in the 1,400 training rows and in live runs.
  - risk: Fuzzy matching can apply an edit in the wrong place. Keep the dry run and the hash pin as the safety net. Numbers are from GPT-4-era models.
- **Agentic reminders in the system prompt (OpenAI GPT-4.1 guide)** — https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide
  - what: Three short instructions: keep going until the task is done (persistence), use tools rather than guess, and plan and reflect between calls. OpenAI also reports that native tool schemas beat schemas pasted into the prompt.
  - measured: OpenAI's internal SWE-bench Verified rose by close to 20% with the three reminders (GPT-4.1, no table given). API-parsed tool descriptions beat pasted schemas by 2% on SWE-bench Verified.
  - here: Check dawnr's system prompt for the three sentences. Add them to the shared prefix; the cost is a few tokens on a prefix that is cached anyway. Measure on the 161 tasks and the factory. The training rows were written under whatever prompt GLM-5 saw, so if the prompt changes, regenerate or filter rows to match.
  - risk: The 20% is unreplicated, was measured on a model trained for these instructions, and is from a vendor. A 4B might ignore them, or the prefix change could mismatch the fine-tune.
- **mini-SWE-agent: bash only, no tool-calling interface** — https://mini-swe-agent.com/latest/
  - what: The agent has one tool, bash, with the command parsed from text rather than via the model's tool-calling interface. Each action runs in a fresh subprocess (no stateful shell), history is linear, and the agent class is about 100 lines.
  - measured: About 74% on SWE-bench Verified with Gemini 3 Pro, per the docs; the claim that it beats Claude Code on DeepSWE comes from the same page. I found no ablation against other agents, and no small-model number.
  - here: Not a switch to bash-only for dawnr, which needs approvals per tool. The testable part is the stateless subprocess per action and the linear history. Check that dawnr's run_command never relies on shell state (cwd, env) from a previous call, and measure how many failures come from that.
  - risk: Frontier-model result with a big model's shell knowledge. A 4B would very likely do worse with one open-ended tool, and bash-only would break dawnr's per-tool approval and sandbox design.
- **OpenHands: CodeAct action space (stuck detection not found)** — https://arxiv.org/html/2407.16741
  - what: The agent acts through three primitives: Python cell, bash command, browser action. The paper presents code as the universal action rather than many typed tools.
  - measured: CodeActAgent: SWE-Bench Lite 26.0% (claude-3.5-sonnet), HumanEvalFix 79.3% (gpt-4o), WebArena 14.8%, ML-Bench 76.5%. No ablation of the action space and no small-model number.
  - here: Nothing direct. It supports keeping dawnr's tool count low (8). Stuck detection was NOT in the pages I could read, so there is no measured comparison for dawnr's repeated-plan stop.
  - risk: Different model scale and task set. The docs page https://docs.openhands.dev/openhands/usage/architecture/runtime covers only the Docker runtime, with nothing on loops.
- **Repo map: ranked, budgeted summary of the codebase (Aider)** — https://aider.chat/docs/repomap.html
  - what: A tree-sitter map of classes and functions with signatures, files ranked by a graph algorithm over dependencies, fit to a token budget (default 1,000) that adapts to the chat.
  - measured: None on the page. It points to a separate blog post, which I did not fetch.
  - here: For tasks over a directory of code, give the model a ranked 500-1,000 token outline (file names plus def/class signatures) in the first turn instead of letting it search blindly. Measure the number of read calls and the pass rate on the file and code tasks.
  - risk: No measurement behind it. Takes a parser per language, and the tokens come out of an already tight context.

Not found: Claude Code's published tool count, prompt structure and retry behaviour were not read: no usable page was fetched.; Goose and Cline/Roo tool-description pages: the fetched URLs returned 404 (Goose tool-permissions page, Cline generic-system-prompt.ts), so nothing is reported on them.; Codex CLI apply_patch spec and approval-mode docs: both raw and github URLs returned 404 or only an install page. Only the rationale from the OpenAI GPT-4.1 cookbook was read.; OpenHands stuck-detection and loop handling: not in the paper or runtime page I read.; Aider leaderboard has no Qwen3 4B/8B/14B entries and no small-model edit-format comparison. Small-model numbers are Qwen2.5-Coder 0.5B-3B on whole only.; SWE-agent ablation numbers came through a summarising fetch of the arXiv HTML, so the percentages should be checked against the paper tables before citing.; Nothing found on 4B-scale agents under these harness choices. All the measurements are from GPT-4-class or larger models.

### windows-and-cross-platform-control

- **Codex classifies Windows commands as DANGEROUS (deny-list), not safe (allow-list)** — https://raw.githubusercontent.com/openai/codex/main/codex-rs/shell-command/src/command_safety/windows_dangerous_commands.rs
  - what: In current Codex main the Windows logic lives in codex-rs/shell-command/src/command_safety/windows_dangerous_commands.rs. Dangerous executables: powershell/pwsh (and .exe), explorer, mshta, rundll32, browsers (chrome, msedge, firefox, iexplore). A URL (http:// or https://) passed to Start-Process/start/saps/Invoke-Item, to a ShellExecute or Shell.Application COM call, or to rundll32 url.dll,FileProtocolHandler is dangerous. Remove-Item/ri/rm/del with -Force is dangerous. In CMD: start with a URL, del/erase /f, and rd/rmdir with both /s and /q. Chained commands are split on & && | || and each segment is checked. Wrapper nesting deeper than 8 levels is treated as dangerous (fail closed). The old windows_safe_commands.rs path in the brief returned 404 on main; the directory listing shows no such file now.
  - measured: none given
  - here: Add these as extra deny shapes to dawnr's look/act tier for Windows interop: any explorer.exe or start with an http(s) URL needs approval, since online is meant to be explicit via --online; any Remove-Item or del with -Force or /f, and rd /s /q, is always ask. Measure by adding 6 to 10 practice tasks that include these shapes and checking they are blocked while explorer.exe . (a local path) still passes.
  - risk: Codex lists explorer as dangerous in general; blocking explorer.exe outright would break the Microsoft-documented explorer.exe . idiom, so only the URL form should be gated. Test strings are paraphrased from a model-summarised fetch, not read verbatim.
- **Codex PowerShell parser: tree-sitter lowering to argv, fail closed, separate policy** — https://raw.githubusercontent.com/openai/codex/main/codex-rs/shell-command/src/command_safety/powershell_tree_sitter.rs
  - what: powershell_tree_sitter.rs lowers a literal PowerShell script to argv-like word vectors only if every parse node is on an explicit allowlist (program, statement_list, pipeline, command, string/array/integer literals). It rejects variables, subexpressions, unicode smart quotes/dashes, #requires, using declarations, dynamic escapes, parse recovery and comments inside tokens. It deliberately contains no cmdlet safelist; callers apply the policy to the lowered words. A python-side oracle (powershell_parser.ps1) exists only for tests.
  - measured: none given
  - here: Where dawnr accepts a powershell.exe -Command string from the model, require it to be a literal with no $ variables, no subexpressions and no pipes to dynamic code, else refuse and ask. Prefer having dawnr pick from fixed recipes and fill typed slots (matches the existing argv-shape allowlist design) instead of parsing free PowerShell. Measure: fraction of Windows practice tasks still passing with recipes only.
  - risk: Reimplementing a PowerShell parser is large; the recipe-with-slots approach avoids it but is less flexible. The summary of rejected constructs came from a small-model summary of the file.
- **What WSL interop actually lets a Linux CLI do (Microsoft docs)** — https://learn.microsoft.com/en-us/windows/wsl/filesystems
  - what: From WSL, tool.exe runs as the active Windows user with the same permission rights as the WSL process, appears in Task Manager, and arguments pass unmodified. Windows tools need the .exe extension, matching case, and must be executable; batch and CMD built-ins need cmd.exe /C. explorer.exe . opens the current dir; powershell.exe /c start . is an alternative. Interop can be switched off per distro with wsl.conf [interop] enabled=false and appendWindowsPath=false, or for one session by echoing 0 to /proc/sys/fs/binfmt_misc/WSLInterop (root). WSLENV shares environment variables with /p /l /u /w flags.
  - measured: none given (reference docs)
  - here: dawnr's Windows detection should check that interop is on (run cmd.exe /C ver and see exit code) and tell the owner how to enable it if not, rather than failing silently. Recipes should use full names with .exe and quote arguments; use wslpath to convert paths before passing them to Windows programs. Add a test: interop disabled gives a clear refusal.
  - risk: Because interop commands run as the real Windows user with no sandbox, bubblewrap does not contain them; the approval layer is the only guard, so Windows recipes must stay allowlisted.
- **wsl.conf interop switches and defaults** — https://learn.microsoft.com/en-us/windows/wsl/wsl-config
  - what: [interop] enabled (default true) controls whether WSL can launch Windows processes; appendWindowsPath (default true) controls whether Windows PATH entries are added. Available from Windows 10 1809. Changes need the distro fully stopped (about 8 seconds, or wsl --shutdown). [automount] enabled=false stops /mnt/c mounting. Documented in the same page: WSL2 networkingMode, firewall, and the 8-second rule.
  - measured: none given
  - here: Offer the owner a documented hardening choice: dawnr can ship a setting that calls Windows programs only by absolute /mnt/c/Windows/System32/... path so it still works with appendWindowsPath=false. Test the recipes both ways on the Acer Nitro box.
  - risk: Absolute paths may differ with a non-default root; read automount root from /etc/wsl.conf.
- **Claude Code on Windows: native vs WSL, and where sandboxing exists** — https://code.claude.com/docs/en/setup
  - what: Docs table: native Windows has no sandboxing; WSL 2 supports sandboxing; WSL 1 does not. Native without Git for Windows uses a PowerShell tool as the shell; with Git for Windows it uses Git Bash and the PowerShell tool is alongside. Install is a one-line script per shell; WSL uses the Linux installer inside the distro.
  - measured: none given
  - here: Confirms dawnr's choice (run in WSL2 where bubblewrap works, call Windows by name). State in docs that WSL1 is unsupported for the sandbox, and have the Windows installer check wsl.exe -l -v for version 2.
  - risk: Approval mechanics for the PowerShell tool were on a separate page not fetched, so how commands are approved there is not verified.
- **Codex on Windows: native sandbox (elevated or unelevated) versus WSL** — https://learn.chatgpt.com/docs/windows/windows-sandbox
  - what: Codex's native Windows sandbox has an elevated mode (dedicated lower-privilege sandbox users, filesystem permission boundaries, firewall rules, local policy changes) and an unelevated fallback (ACL filesystem boundaries and environment controls). It restricts filesystem writes outside the working folder and network access without approval. WSL is recommended when Linux tooling is needed.
  - measured: none given
  - here: dawnr's WSL2 route needs neither; but a dawnr act tier that calls powershell.exe could run it with a restricted environment and a non-interactive flag (see next finding). No change needed to the sandbox design; note that Codex also treats Windows-side containment as ACL/user based, which dawnr does not replicate.
  - risk: Page was a summary of the redirect target; the earlier URL developers.openai.com/codex/windows redirected here.
- **powershell.exe flags for unattended, non-hanging calls** — https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_powershell_exe
  - what: Microsoft documents -NoProfile (skip profile), -NonInteractive (Read-Host or confirmation prompts error instead of hanging), -ExecutionPolicy (session only, does not change the registry), -EncodedCommand (Base64 of UTF-16LE for complex quoting), -Command - to read from stdin, and -File. From cmd.exe a -Command string is always a string, and exit code is 0 or 1 unless exit $LASTEXITCODE is used.
  - measured: none given
  - here: Make every dawnr PowerShell recipe start as powershell.exe -NoProfile -NonInteractive -Command ... with a timeout, and prefer stdin (-Command -) over quoting. Measure: hang rate and quoting failures on the Windows practice tasks before and after.
  - risk: Documented page is for Windows PowerShell 5.1; pwsh.exe (7.x) differs, so detect which exists. -ExecutionPolicy Bypass is not needed for -Command and should not be added.
- **Dark mode, broadcast, and what Microsoft does and does not document** — https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-windows-themes
  - what: Microsoft documents reading the theme through UISettings.GetColorValue(Foreground) (light foreground means dark mode) and ColorValuesChanged, and DWMWA_USE_IMMERSIVE_DARK_MODE for title bars. The page does not document registry values (AppsUseLightTheme, SystemUsesLightTheme) as a supported way to set the theme; that part is community practice. Microsoft documents that a changer broadcasts WM_SETTINGCHANGE with SendMessageTimeout to HWND_BROADCAST, wParam NULL, lParam a string (for example 'Environment'), and that a broadcast can wait up to timeout times the number of unresponsive windows; SMTO_ABORTIFHUNG avoids waiting on hung windows. Set-ItemProperty -Path HKCU:\... -Name -Value -Type DWord is the documented way to write a registry value.
  - measured: none given
  - here: Recipe: read the two HKCU Personalize values with reg.exe query (documented read-only form), set both with Set-ItemProperty -Type DWord, then broadcast WM_SETTINGCHANGE (lParam 'ImmersiveColorSet' is the community-reported string and is not in the Microsoft page) with SMTO_ABORTIFHUNG and a 5000 ms timeout via Add-Type P/Invoke. Verify by reading the values back and by UISettings foreground colour. Test that Explorer and Settings repaint on the Nitro machine.
  - risk: The registry value names and the ImmersiveColorSet string were not confirmed on a Microsoft page I fetched, so they are community knowledge; some apps repaint only on restart. Write only HKCU, never HKLM.
- **reg.exe query is the documented read-only registry call** — https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/reg-query
  - what: reg query <keyname> [/v name] [/s] [/f data] with roots HKLM, HKCU, HKCR, HKU, HKCC; exit code 0 success, 1 failure; a remote computer form (\\host\HKLM\...) exists and should be refused.
  - measured: none given
  - here: Put reg.exe query with an HKCU/HKLM key and /v in the look tier (auto-approve), and refuse a first argument starting with two backslashes, and /s on a root key (large output). Reg add/delete go to the ask tier.
  - risk: Recursive /s output on large hives is slow and large; cap output.
- **UI automation libraries: pywinauto and WinAppDriver** — https://pywinauto.readthedocs.io/en/latest/
  - what: pywinauto automates the Windows GUI with win32 and uia backends (pip install; depends on pywin32 and comtypes), with auto-waits of up to 5 seconds by default; its docs say nothing about elevated, session or remote limits. WinAppDriver is a Selenium-style service for UWP, WinForms, WPF and Win32 apps on Windows 10, listens on 127.0.0.1:4723, needs Developer Mode and must be started as administrator by default.
  - measured: none given
  - here: Do not add either to the default tier: both need Windows-side Python or an admin service, and a model driving a GUI is a harm risk. If added later, run pywinauto as a Windows Python script under the look tier (list windows, read control text only) and keep clicks in ask. WinAppDriver source: https://github.com/microsoft/WinAppDriver (fetched).
  - risk: WinAppDriver admin requirement and Developer Mode widen the attack surface; the repo page I read described it as maintained but I did not check release dates. pywinauto from WSL needs a Windows Python install.
- **Toast, volume and screenshot: what is documented versus community** — https://github.com/Windos/BurntToast
  - what: Toast: BurntToast (PowerShell Gallery) wraps Windows notification APIs with proper AppUserModelID branding but its repository was archived on 2026-09-25 (read-only). Volume: Microsoft documents the Core Audio APIs (the foundation for endpoint volume) but only as C++ reference; NirCmd setsysvolume takes 0 to 65535 (0x8000 is half) and is a closed-source community tool. Screenshots: no Microsoft page was fetched; not verified.
  - measured: none given
  - here: Prefer a documented fixed route: for notifications, a PowerShell recipe using the Windows.UI.Notifications ToastNotificationManager with an AUMID, instead of depending on an archived module. For volume, either a recipe that uses Core Audio through Add-Type or ship nircmd only if the owner installs it. Test each on the Nitro box and record success.
  - risk: Archived BurntToast gets no fixes; NirCmd is third-party binary the owner must trust; the toast-from-unpackaged-app page (learn.microsoft.com .../send-local-toast-desktop-cpp-wrl) returned 404, so AUMID requirements are only from the BurntToast README.
- **macOS: osascript and the shortcuts CLI** — https://support.apple.com/guide/shortcuts-mac/run-shortcuts-from-the-command-line-apd455c82f02/mac
  - what: osascript runs AppleScript or other OSA scripts from -e or a file, with -l to pick the language. Community examples (ss64): set volume output volume 50, set volume output muted TRUE, tell application "System Events" to tell appearance preferences to set dark mode to not dark mode. Apple's guide documents do shell script with quoted form to escape strings. Apple documents the shortcuts tool: shortcuts run NAME [-i path] [-o path], shortcuts list, shortcuts view, shortcuts sign; exit code 0 or 1; avoid prompts in shortcuts used from scripts.
  - measured: none given
  - here: If dawnr gains a macOS tier, use fixed osascript strings with typed slots (a number 0 to 100) and shortcuts run as the owner's pre-approved named actions, which fits the allowlist-of-argv-shapes design. I did not fetch a documented defaults write page or Apple's TCC prompts page, so those are not covered.
  - risk: osascript can run arbitrary do shell script, so only fixed templates may be allowed; Automation permission prompts (TCC) were not verified from an Apple page. The ss64 examples are community, not Apple documentation.

Not found: Codex's windows_safe_commands.rs at a recent tag: the path from the brief returned 404 on main; the directory command_safety lists is_dangerous_command.rs, windows_dangerous_commands.rs, powershell_tree_sitter.rs, powershell_parser.rs but no safe-command file, and the tree-sitter module states it has no cmdlet allowlist. No read-only PowerShell cmdlet safelist was found there. Not searched at older tags.; OpenHands on Windows (what runs, how approvals work): not fetched.; Microsoft documentation of the AppsUseLightTheme/SystemUsesLightTheme registry values: not found on the page fetched; the 'ImmersiveColorSet' broadcast string is not on the WM_SETTINGCHANGE page.; Documented Windows 11 screenshot command line (Snipping Tool, Graphics.CopyFromScreen): not fetched.; Microsoft toast-from-unpackaged-app page (404) and Apple pages for defaults(1) and TCC automation permission: not found or not fetched.; Core Audio IAudioEndpointVolume reference page: only the overview was fetched, with no code or command line.
