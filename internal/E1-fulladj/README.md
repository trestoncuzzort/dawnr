# E1 fully-adjudicated direct-body matrix (11,088 cells)

Raw verdicts for the fix the 2026-10-14 correction required: every one-edit mutant adjudicated BODY-ONLY
in every one of the 7 kernels, no real-verified gating, no early stop, four states
(verified / refuted / unverifiable-with-reason / not-run), a missing observation never a rejection.

`E1MAN-<tag>.json` freezes the survivors (body + bodyhash + task-AST hash); `E1FULL-<tag>.jsonl` is the
per-cell state-only record `{path, which, kernel, config_id, src_hash, state, raw}`; `E1FULL-<tag>.meta.json`
carries the config (Dafny/Z3/SPARK + engine-pin/harness). Tags: vcd (Vericoding 5929), df (DafnyBench
4361), hev (HumanEval 616), auto (Autonomy 182) = 11,088. Harness `t/e1_full_adjudicate.py`.

Coverage / survivor-verification curve (recomputable from the rows): real coverage 95.1%→43.8%, survivor
verification 72.5%→17.6% across k=1..7; four-state tally 6837 verified / 3995 unverifiable-with-reason /
256 unobserved-infra. Each row's body-only adjudication is replayable by `t/db_certificate.py` (reloads
the task, re-hashes identity, re-adjudicates, attaches the fresh Result as a new observation under the
current engine); full set minted + structurally audited by `t/db_batch_cert.py`.
