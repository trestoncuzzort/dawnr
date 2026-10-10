# T77: examine the expected SPARK two-loop failure

Registered before running the expected-failure test directly or changing it,
from `afffe36`. The test expects two loops to fall back to contracted `F`.
The current lowering has explicitly generated uncontracted certificate clones
for multiple loops since 2026-09-18. Prediction: the expected failure is an
obsolete source-shape assertion, rather than evidence that multiple loops
cannot be lowered. This must be established, not assumed to make the suite green.

Install the repository's pinned GNATprove FSF 16.1.0 release from its publisher,
check its archive SHA-256, and record its version. Inspect the failing assertion
and emitted source. A replacement test must check both loop clones and the
uncontracted certificate call; do not restore the less capable old lowering
merely to satisfy the old text assertion.

Kernel bars: a well-formed two-loop task with a meaningful postcondition proves;
a measured wrong variant is refuted by an accepted certificate; a correct body
with a fabricated violating witness must not be refuted. Use three repeats for
each kernel outcome. If a lowering repair is needed, run the whole SPARK column
before claiming success. The canonical seven-kernel table stays unchanged.

Prior work: `t/lower_spark.py::certificate`, its dated multiple-loop clone
extension, the expected-failure test and T75's recorded gap; SPARK's
[loop-invariant guide](https://docs.adacore.com/spark2014-docs/html/ug/en/source/how_to_write_loop_invariants.html)
explains that loop invariants supply the information available after a loop.
The existing uncontracted clones avoid trusting a twin's unproved invariant.

The direct call failed only on the expected text `(not (F (`. The source
already contains W_1_Cert, W_2_Cert and F_Cert, with neither loop clone borrowing
a Pre/Post. No lowering change was needed for that behavior.

The publisher's GNATprove archive passed SHA-256
`82528bef29857e239373fcc36732837d743f5a00805d502c70455422ffc97191` and reports
FSF 16.1.0 / Why3 1.8.2+git. A new well-formed two-phase counting task proves
`r == 2*n`, and its measured wrong second-loop body is refuted, in three agreeing
runs each. The fabricated witness on the correct body was declined in all
three runs, with no certificate postcondition proved. It exhausted the existing
20,000-step budget, so its verdict is TIMEOUT, not the test's initial overly
specific UNPROVED expectation. The negative control now admits these two valid
refusals and requires an actual unproved certificate goal; malformed input or
a tool failure is not a passing negative control. No budget or contract changed.

The obsolete expected-failure assertion is replaced by explicit checks of both
uncontracted loop clones and their use by the certificate. The affected suite
passes 15 tests and three kernel subtests with `T_SPARK_JOBS=1 python -m pytest
-q t/test_lower_spark_loop_cert.py t/test_spark_multiloop_kernel.py`.
Clean checkout `21528a1` repeated all 15 passing tests and three kernel subtests.
Generated sources, their hashes and the command are preserved under
`t/evidence/2026-10-10-spark/`. This closes the obsolete expected failure with
direct checks of its replacement behavior; it does not establish a full SPARK
column or a complete audit of the lowering.
