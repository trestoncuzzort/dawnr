# Next verification work, grounded in the current implementation

Research checked 2026-10-10. Read `AGENTS.md`, the required September handoff and run plan, the October landscape
and expansion records, and the implementation before choosing changes. The configured local research mirror is
absent in this checkout environment; its search could not run. Primary sources below were fetched directly.

The highest-value work is strengthening the connection between a verified t task, the actual compiled flight
code, and the evidence a completed run leaves. Additional model-generated candidates are useful only after that
connection refuses incomplete or invalid results.

## What is already present

| Concern | Current source | Boundary |
|---|---|---|
| Vacuous or undefined preconditions | `t/interp.py`, `t/harness.py`, `t/test_vacuous_requires.py`, backend vacuity probes | Existing functionality; adding another generic vacuity checker duplicates it. |
| Weak specifications | `t/audit.py`, `t/spec_check.py`, `t/spec_quality.py`, `t/spec_gate.py` | Mutation rejection and bounded/reference-based evidence do not establish a complete natural-language requirement. |
| Counterexample-guided repair | `t/spec_repair.py`, `t/proof_repair.py`, `t/contract_repair.py` | Witness-fed model repair and grammar-generated strengthening already exist. A new generic repair loop is not the next missing feature. |
| Cross-backend disagreement | `t/kernel_disagreement.py` and engine matrix tooling | Shared solvers, parser and translation code leave common failure modes; agreement is not statistical independence. |
| Compiled PX4 correspondence | `t/flight/px4_diff.py`, `t/flight/px4_stmt.py` | Bounded input comparisons, pinned historical sources, sometimes extracted statements and stand-ins. Several templates use binary64 where production commonly uses binary32. |

The handoff's list of unbuilt features is historical. For example, current `contract_repair.py` already proposes
clauses that kill measured mutants and can submit the stronger contract to a prover. Implementation takes priority
over that older list.

## 1. Require complete execution before declaring correspondence

**Implemented and replayed against the pinned compiled C++ sources.** Both
comparison CLIs completed successfully on the lab after the strict-execution
change. Consumer synchronization and the subsequent source-identity changes
have their own validation below.

Read-only negative controls found three concrete instrument defects:

- `px4_stmt.run_cpp` returned a valid output prefix from a compiled process that terminated unsuccessfully on its
  second input. It did not check the executable's return code.
- `px4_stmt.check` compared with `zip(domain, output)` and used the returned row count as the denominator. One
  returned result for three scheduled inputs produced `1/1` for both original and fixed code; the known real
  counterexample had no result.
- Replacing every `px4_diff` compilation with an explicit compilation error still made its CLI return zero.

These controls demonstrate that failure could be accepted. They do not show that any particular historical
comparison was incomplete. The tests and registration are `t/test_flight_execution.py` and
`t/PREDICT-2026-10-10-flight-correspondence.md` in the engine; the eventual consumer sync brings them here.

Acceptance: successful process termination, exactly one correctly shaped result per scheduled input, and at least
one admissible comparison are all mandatory. Compilation failure, timeout, failed startup, signal termination,
prefix-only output, extra output, malformed output and an all-skipped run must fail. Complete integer comparisons,
the documented float-parameter narrowing case, and the real counterexample in original/fixed rows must still pass.

This follows the separation of termination, resource exhaustion and result interpretation used in
[BenchExec's resource accounting](https://github.com/sosy-lab/benchexec/blob/main/doc/resources.md).
That tool accounts for CPU and wall time separately and measures the whole process tree; a process's existence or
partial output is not a completed result. Full BenchExec isolation is a later operational choice, dependent on
host permissions.

## 2. Make a flight result replayable from identified bytes

**Implemented in `t/flight/evidence.py` and both comparison CLIs.** Before the
change, both caches trusted an existing path without checking its contents, and
the statement cache key omitted repository identity. The new manifest contains
48 expected source digests, derived from freshly fetched pinned GitHub source
and checked against Git's blob identities. Cached and downloaded bytes must
match before use; repository identity is part of the cache path. Unpinned
working-tree files are explicitly identified as observed bytes, not authenticated
upstream source.

The optional `--receipt` file records upstream repository/revision/source hashes,
task and wrapper hashes, compiler version/target/flags, input digests and counts,
skips, process outcomes and stdout/stderr digests. It identifies the artifacts
needed to repeat a comparison; it does not embed them as a standalone replay
bundle. The function runner uses temporary build files; replay regenerates them
from the identified task and wrapper logic. Compiler executable and
system-library bytes are explicitly outside this receipt's scope. Atomic cache
installation rejects incomplete or mismatched downloads; legacy cache entries
are migrated only after their reviewed digest matches. Recording an unknown
file's hash alone would not authenticate its upstream identity.

Acceptance and negative controls:

1. Offline replay from a complete cache reproduces the same comparisons and semantic receipt fields; elapsed
   time and incidental paths are not part of a deterministic identity.
2. Change one cached byte or truncate a download: refuse before compilation.
   Changing a task changes its recorded identity. Two repository identities
   cannot silently share one cache entry.
3. Change the compiler flags, a stand-in or a fixed working-tree file: the receipt changes and names the scope.
   An unavailable source or compiler produces an incomplete/error receipt, never an empty successful table.

This applies the artifact separation used by [SV-COMP's reproducibility materials](https://sv-comp.sosy-lab.org/reproduce.php):
tasks, benchmark definitions, tool packages, tool integration and witness format are all identified components.
The exact receipt schema proposed here is a design inference for dawnr, not an SV-COMP format claim.

## 3. Add a bounded native-code check with explicit machine semantics

**Implemented as an experimental adapter in `t/native_check.py`.** The pilot uses
the exact pinned `ObstacleMath::wrap_bin(int,int)` definitions from the original
source and the published fix. It extracts the unchanged body, omits the namespace
and includes, and parses it as C. The harness fixes `bin_count` at 72 and ranges
over all 32-bit signed `bin` inputs. These transformations and assumptions are
recorded rather than treating the harness as the entire production module.

[CBMC's official description](https://www.cprover.org/cbmc/) covers C/C++ memory safety, other undefined behavior
checks and assertions. The [CBMC research paper](https://arxiv.org/abs/2302.02384) describes its bit-precise
translation. This can complement t's mathematical or binary64 model on exactly the gaps the flight README names.
Use the pinned tool's supported language subset and report parser/library refusals; do not replace difficult
production code with an unlabelled idealization.

Acceptance and negative controls:

1. The historical buggy code yields a machine-readable counterexample which the compiled native harness replays.
   The proposed fix satisfies the same property under the same input assumptions.
2. A deliberately insufficient loop bound is reported as incomplete. Require successful unwinding assertions
   before presenting a loop result as covering all allowed executions. The
   [CBMC tutorial](https://diffblue.github.io/cbmc/cprover-manual/md_cbmc-tutorial.html) explicitly distinguishes
   this from bounded bug hunting.
3. Contradictory assumptions must fail the acceptance gate even if ordinary property checks succeed.
   [CBMC's assumption documentation](https://diffblue.github.io/cbmc/cprover-manual/md_modeling-assumptions.html)
   provides `--cover assume` for detecting when assumptions empty the reachable state space. Run that as its own
   coverage check; coverage success is not property proof.
4. A mutation reintroducing the original off-by-one or narrowing error must be detected. A missing tool, solver
   timeout or unsupported construct remains an explicit non-result. Compare compute cost before scaling beyond
   the pilot.

The original and a mutant restoring it yield a negative-index witness confirmed
by compiled execution, plus signed overflow confirmed by UBSan. The fixed
definition passes 14 scoped safety properties. Contradictory assumptions are
rejected as vacuous; an insufficient loop bound is incomplete. The lab suite
passes all 36 tests. See `t/PREDICT-2026-10-10-native-cbmc.md` and the identified
receipts in `t/native_fixtures/px4-wrap-bin/pilot-2026-10-10.json`. These are safety
properties, not the full mathematical modulo specification or a kernel-checked
SAT proof certificate.

This is CPU/SAT work suitable for a bounded shared-host allocation. It does not require a GPU. Model inference
can propose harnesses or repairs, but each proposal still passes these controls and the existing proof pipeline.

## What to postpone, and what not to claim

[Alive2](https://github.com/AliveToolkit/alive2) and its
[PLDI paper](https://web.ist.utl.pt/nuno.lopes/pubs/alive2-pldi21.pdf) provide bounded translation validation for
LLVM optimizations. That is useful if compiler transformation correctness becomes the question. It does not
directly prove that a manually transcribed t task describes a C++ module, so installing it is lower priority than
closing the measured correspondence defects.

No finite comparison sweep proves equivalence on untested inputs. No refuted mutant establishes that a
natural-language contract is the intended requirement. No successful binary64 check establishes binary32 flight
behavior. No extracted-statement harness establishes all surrounding caller invariants, concurrency, hardware or
timing behavior. Multiple front ends can share a solver or translation defect. A completed native test suite is
valuable regression evidence; it is not flight certification or a proof that the project is perfect.

## Integration evidence

The final identified flight adapters replayed successfully on the integration
host with GCC 13.3.0 as well as locally with GCC 16.2.1. The retained
[function receipt](evidence/2026-10-10-flight/px4-diff.json) accounts for all
7,062 planned/runtime rows across 27 cases;
[the statement receipt](evidence/2026-10-10-flight/px4-stmt.json) accounts for
all 1,490 rows across 14 cases. These JSON records preserve the reported scope
and explicit skips rather than presenting skipped routines as verified.

Two Bedrock models reviewed the flight, kernel, and runtime changes in six
bounded calls. Their 23 suggestions yielded one reproducible runtime routing
regression and 22 rejected hypotheses. Three failing-before controls confirmed
the routing fix. The [pilot read](../locallm/PREDICT-2026-10-10-bedrock-review.md)
records usage and dispositions; token-priced usage was $0.02611121, with AWS
billing authoritative. The review did not replace any native or formal checks.

The final engine pin includes the scoped native pilot, strict source comparisons,
and three backend repairs. Full 114-task Lean, Verus, and SPARK columns retained
every baseline outcome; targeted repaired cases passed their native positive
and negative controls. SPARK's `relu_all` twin still exhausts its proof budget.
The [evidence manifest](evidence/2026-10-10-flight/manifest.json) identifies the
separate column reports, lowering bytes and flight receipts. These reports do
not replace the canonical all-seven agreement matrix.

After synchronization, all 2,052 engine-owned files matched the committed engine
bytes. Dawnr's certificate, repair, specification-gate, flight and targeted
lowering integration suite passed **167 tests and 35 subtests**. Six local CBMC
integrations skipped because that binary is installed on the integration host;
the native pilot ran all six there successfully. Document-link checks passed.
