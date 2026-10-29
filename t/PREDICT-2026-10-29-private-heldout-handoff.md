# One private final reading after the registered seed decision

After the complete six-versus-three development comparison and the individual
precision/spec33 conditions select one seed, read the existing clean 182 once.
Keep the 17 clean / 12 all-seven floors and the final laptop condition unchanged.
An unsuccessful final reading never authorizes trying the other seed on this panel.

The handoff must independently recompute the decision from the frozen evidence
bundle, match the immutable choice record, and require the actual model digest to
equal that choice. Register an exclusive generation claim before launching a
model. Reusing the same claim may recover the same cached reading; a changed
seed, model, panel, procedure or decision must be refused. An existing complete
reading is consumed as evidence rather than generated again.

Use the current cloud development route and pinned decoder sources. The only new
panel is the registered clean 182: three Python attempts, one greedy plus four
sampled specifications, up to three kept specifications, and one greedy plus two
sampled implementations each. This remains at most 17 logical model requests per
problem. Preserve seed offset zero, maximum 1,024 response tokens, batch 16, four
parallel slots of 4,096 context tokens, and concurrency four. The fixed historical
score floors remain 17 and 12; they are not reselected from new baseline decodes.

Predictions before any final reading:

1. An unqualified, altered, incomplete or differently selected evidence bundle
   cannot create a generation claim.
2. A synthetic qualified bundle creates one immutable claim. Repeated identical
   preparation returns it; a changed seed/model/panel/decoder cannot replace it.
3. Completed-generation validation requires the exact protocol and request-cache
   completion records, all 182 problem entries and exact saved-answer accounting.
   A valid complete zero-answer reading remains zero coverage.
4. The private grade uses the frozen proof/reference procedure. Inputs and full
   outputs stay encrypted through GitHub, and public logs contain aggregates only.
5. The selected model must still pass the unchanged final score and laptop gates
   before packaging and publication. No setup test establishes model quality.

The implementation is prepared while training runs. It does not select a real
seed, decode the final panel or dispatch its grade before the prerequisites hold.
Sources: `release_seed_selection.py`, `release_grading_inputs.py`,
`v6_server_route.py`, `laptop_route.sh`, `v6-gcp-heldout.sh`, and `spec33.yml`.

The fixed decoder/data identities, settings and score floors are bound in
[the protocol receipt](../release/evidence/private-heldout-protocol-2026-10-29.json).
The metadata guard and private grading transport have 41 focused checks covering
choice integrity, an exclusive claim, altered procedures, complete zero-answer
output, incomplete/foreign evidence, a real encrypted round trip and archive
path rejection. These are synthetic checks; no model or prover ran locally.

The prepared `heldout.yml` workflow checks out the existing proof grader at
`1e033b50c2c53fb3d40932d9561e1a8eefe9aa7d` and the handoff code at the exact
workflow revision. It authenticates the encrypted input asset, rechecks the
selected seed and complete generation, and retains original answer bytes. Full
inputs, results and partial-failure diagnostics are sealed to the existing output
key. Its public summary contains counts and pending-audit/laptop flags only.
The workflow refuses another GitHub run attempt; dispatch still requires the
existing immutable journal so an ambiguous attempt is not silently repeated.

The workflow's YAML and shell blocks parse, but it has not graded a real final
reading. The new grader's matched baseline controls must finish before candidate
use. The operator assembler and GPU launcher are now prepared; actual selection,
deployment and invocation evidence are still pending. No real choice or claim
was created. The final artifact still needs independent content and origin audits
before its counts can satisfy a release condition.

The launcher runs the original decoder with the same server arguments. It
rechecks the exact selected model bytes, source files and ten server/library
fingerprints, holds the shared GPU lock, and observes the server process and
its listening socket before starting the client. It binds the complete output
to both observed child processes and unchanged model bytes. The private grading
transport now requires that invocation receipt as well as the selected choice.

The extended guard, transport and launch checks total 59 passes. The process
tests use a compiled HTTP health responder and a Python fixture writer, with no
model inference, reference execution or proof invocation. They verify one
completion, receipt recovery without another invocation, preserved cache bytes
after an explicit same-reading resume, and refusal of changed cache evidence or
a busy GPU lock. Initial tests caught a captured default port and a readiness
probe that mishandled TIME_WAIT; both were corrected before deployment.
The original claim and every attempt's diagnostics remain in place.
[Validation](../release/evidence/private-heldout-launch-validation-2026-10-29.json).

The exact tools are now installed outside the frozen running checkout. All
registered decoder files and server libraries match; every control module
imports from the isolated directory. A remote negative check rejects an
unqualified bundle before any child process starts. Training and the identity
observer retain their process and source identities. No actual choice or claim
exists. The private workflow is pinned at `r61-heldout-20261029`, revision
`1e2b20e516c0d0d4c14599c1178f3dcd3ce0e39e`, whose CI passed.
[Deployment evidence](../release/evidence/private-heldout-tools-deployment-2026-10-29.json).

A later CI run exposed a transient empty command line during child startup.
The local reproduction matched the other identity fields but read an empty
argument list, so the exact identity check refused it. Linux's command-line
reader can return no bytes before startup has populated those fields.
The launcher now waits up to two seconds for an empty argument list, preserving
the child PID and start time, and then requires every original identity check.
Nonempty wrong commands, exited children and changed process identities still
fail. The harmless fixture waits for its observed-client record before writing
results, replacing a fixed 200 ms sleep. All 64 focused controls pass.
The earlier unused deployment and workflow pin are preserved and superseded;
the corrected exact revision must pass CI before its replacement is used.
No model was selected and no final reading started.
[Observation fix](../release/evidence/private-heldout-observation-fix-2026-10-29.json).
