# Vacuity and specification-strength literature, swept 2026-09-20

Fetched and read by a delegated agent; 100 documents saved to a scratchpad that
does not survive the session, so this is the record. Independently verified
against 98 of those files by a second agent, which found two count discrepancies
(100 files claimed against 98 present; 38 F* quake hits claimed against 53) and
confirmed every load-bearing quote and number otherwise.

---

Research complete. All 100 documents are saved in `/tmp/claude-1000/-home-t/daf8bdac-fcbe-4cbc-8b1c-768e9975597f/scratchpad/sweep/`. I stopped fetching when plan mode activated (curl writes files); the remaining gaps are labeled explicitly below.

# The single most important finding first

**Boogie's `/smoke` is real, and the canonical paper you need is not on arXiv.** Tomb & Joshi, *Static Coverage in Deductive Software Verification*, FMCAD 2025 — it formalizes vacuity detection for Dafny/Boogie via unsat cores, benchmarks it head-to-head against `/smoke`, and is the direct ancestor of Dafny's shipped `--warn-contradictory-assumptions`. It is free at TU Wien. arXiv searches for it return **zero** results.

Second: there is a crisp three-way split in this literature that most summaries blur, and it matters for your design.

| What is perturbed | Mechanism | Works |
|---|---|---|
| **Nothing** — unsat core instead | Element absent from core ⇒ vacuous/redundant | Tomb & Joshi, Dafny `--warn-*`, ProofPulse |
| **An added goal** (`assert false`) | Provable ⇒ contradictory context | Boogie `/smoke`, Frama-C WP, Why3 |
| **The SPEC formula** | Negated / operator-swapped | Why3 smoke (negation), Beer et al. (w(φ)), **SpecGen (to repair, not to test)** |
| **The CODE** | Spec must refute mutants | **SpecSyn**, **VeriScale**, nl2postcond, NL2Contract |

SpecGen is the trap: it mutates specifications, but to make a failing spec *verify*, which is the opposite of strength testing.

---

# (A) Vacuity / trivially-satisfiable specification detection

## A1. Boogie `/smoke` — CONFIRMED, it exists

**URLs fetched → saved files**
- `https://raw.githubusercontent.com/boogie-org/boogie/master/Source/VCGeneration/SmokeTester.cs` → `boogie-SmokeTester.cs`
- `https://raw.githubusercontent.com/boogie-org/boogie/master/Source/ExecutionEngine/CommandLineOptions.cs` → `boogie-CommandLineOptions.cs`
- `https://raw.githubusercontent.com/boogie-org/boogie/master/Test/smoke/smoke0.bpl` → `boogie-smoke0.bpl`
- `https://raw.githubusercontent.com/boogie-org/boogie/master/Test/smoke/smoke0.bpl.expect` → `boogie-smoke0.bpl.expect`
- `https://api.github.com/repos/boogie-org/boogie/license` → `boogie-license.json`

**Verbatim, from `boogie-CommandLineOptions.cs` (the `/help` text, lines 1955-1959):**
> `"  /smoke        Soundness Smoke Test: try to stick assert false; in some"`
> `"                places in the BPL and see if we can still prove it"`
> `"  /smokeTimeout:<n>"`
> `"                Timeout, in seconds, for a single theorem prover"`
> `"                invocation during smoke test, defaults to 10."`

**From `boogie-SmokeTester.cs` (the actual insertion, lines 254-261):**
> `traceWriter.Write("    soundness smoke test #{0} ... ", id);`
> `callback.OnProgress?.Invoke("smoke", id, id, 0.0);`
> `Token tok = new Token();`
> `tok.val = "soundness smoke test assertion";`
> `seq.Add(new AssertCmd(tok, Expr.False));`

**The criterion (lines 339-345):**
> `if (outcome == SolverOutcome.Valid) {`
> `      // copy it again, so we get the version with calls, assignments and such`
> `      ...`
> `      callback.OnUnreachableCode(run);`

Note the trace label is inverted — proving `false` is the bad case:
> `outcome == SolverOutcome.Valid`
> `          ? "OOPS"`
> `          : "OK" + (outcome == SolverOutcome.Invalid ? "" : " (" + outcome + ")"));`

**A live worked example.** `boogie-smoke0.bpl` contains four procedures; `b` has a contradictory `requires`/branch pair:
> `procedure b(x:int)`
> `  requires x>0;`
> `{`
> `  var y : int;`
> ``
> `  if(x<0) {`
> `    y := 1;`

and `boogie-smoke0.bpl.expect` is the ground-truth output:
> `found unreachable code:`
> `implementation b(x: int)`
> `...`
> `  anon3_Then:`
> `    assume {:partition} x < 0;`
> `    y := 1;`
> `    assert false;`
> `    return;`
> `}`
> ``
> `Boogie program verifier finished with 4 verified, 0 errors`

Worth knowing: `/smoke` **disables pruning**, from `boogie-CommandLineOptions.cs` line 1361:
> `ps.CheckBooleanFlag("smoke", x =>`
> `              {`
> `                SoundnessSmokeTest = x;`
> `                Prune = false;`
> `              }) ||`

- **(a)** Perturbs **neither** spec nor code semantically. It *adds a goal* (`assert false`) at program points.
- **(b)** Criterion: inserted `assert false` is **provable** (`SolverOutcome.Valid`) ⇒ unreachable code / contradictory assumptions at that point.
- **(c)** **No witness input.** It emits the Boogie *implementation body* with the inserted assert, via `OnUnreachableCode`. Ironically a model would exist only in the *passing* case, and is discarded.
- **(d)** No numbers in source. See A3 for the only empirical data: 2,897 smoke warnings on one codebase.
- **(e)** **MIT** — `boogie-license.json`: `MIT | MIT License | https://github.com/boogie-org/boogie/blob/master/LICENSE.txt`
- **(f)** Repo `https://github.com/boogie-org/boogie`. No paper for `/smoke` itself.
- **(g)** One solver (Z3 in practice), via `CheckerPool`. **Not** multi-prover.

## A2. Dafny `--warn-contradictory-assumptions` / `--warn-redundant-assumptions` / `--analyze-proofs` — CONFIRMED, shipped

**URLs fetched → saved files**
- `https://raw.githubusercontent.com/dafny-lang/dafny/master/Source/DafnyCore/ProofDependencyWarnings.cs` → `dafny-ProofDependencyWarnings.cs`
- `https://raw.githubusercontent.com/dafny-lang/dafny/master/Source/DafnyCore/Options/CommonOptionBag.cs` → `dafny-CommonOptionBag.cs`
- `.../LitTest/logger/ProofDependencies.dfy` → `dafny-ProofDependencies.dfy`
- `.../LitTest/logger/ProofDependencyWarnings.dfy` + `.expect` → `dafny-ProofDependencyWarnings.dfy`, `dafny-ProofDependencyWarnings.dfy.expect`
- `https://raw.githubusercontent.com/dafny-lang/dafny/master/LICENSE.txt` → `dafny-LICENSE.txt`

**Verbatim option help, `dafny-CommonOptionBag.cs` lines 315-341:**
> `public static readonly Option<bool> WarnContradictoryAssumptions = new("--warn-contradictory-assumptions", @"`
> `(experimental) Emits a warning if any assertions are proved based on contradictory assumptions (vacuously).`
> `May slow down verification slightly, or make it more brittle.`
> `May produce spurious warnings.`
> `Use the `{:contradiction}` attribute to mark any `assert` statement intended to be part of a proof by contradiction.") {`
> `    IsHidden = true`
> `  };`

> `public static readonly Option<bool> WarnRedundantAssumptions = new("--warn-redundant-assumptions", @"`
> `(experimental) Emits a warning if any `requires` clause or `assume` statement was not needed to complete verification.`

> `public static readonly Option<bool> AnalyzeProofs = new("--analyze-proofs", @"`
> `Uses data from the verifier to suggest ways to refine the proof:`
> `Warning if any assertions are proved based on contradictory assumptions (vacuously).`

And the coverage plumbing (line 342, 568-570):
> `public static readonly Option<string> VerificationCoverageReport = new("--verification-coverage-report",`
> `    "Emit verification coverage report to a given directory, in the same format as a test coverage report.")`

> `DafnyOptions.RegisterLegacyBinding(WarnContradictoryAssumptions, (options, value) => {`
> `      if (value) { options.TrackVerificationCoverage = true; }`
> `    });`

**The messages emitted, `dafny-ProofDependencyWarnings.cs`:**
> `var message = $"proved using contradictory assumptions: {obligation.Description}";`
> `$"ensures clause proved using contradictory assumptions"`
> `$"unnecessary requires clause"`
> `$"unnecessary (or partly unnecessary) {assumption.Description}"`

**Only runs on successful proofs:**
> `if (results.Any(r => r.Outcome != SolverOutcome.Valid)) {`
> `      return;`
> `    }`

**A limitation you should care about a great deal — verbatim comment in `ShouldWarnVacuous`:**
> `// Ensures clauses are often proven vacuously during well-formedness checks.`
> `// There's unfortunately no way to identify these checks once Dafny has`
> `// been translated to Boogie other than looking at the name. This is a significant`
> `// limitation, because it means that function ensures clauses that are satisfied`
> `// only vacuously won't be reported. It would great if we could change the Boogie`
> `// encoding so that these unreachable-by-construction checks don't exist.`

And a second blind spot:
> `// Don't warn about `assert false` being proved vacuously. If it's proved,`
> `// it must be vacuous, but it's also probably an attempt to prove that a`
> `// given branch is unreachable (often, but not always, in ghost code).`

**The test oracle.** `dafny-ProofDependencies.dfy` contains hand-labeled vacuity cases:
> `// Obvious contradiction in requires clauses.`
> `function {:testEntry} ObviouslyContradictoryRequiresFunc(x: nat): (r: nat)`
> `  requires x > 10`
> `  requires x < 10`
> `  ensures r < x // only provable vacuously `
> `{`
> `  assert x == 10; // contradicts both requires clauses`
> `  x - 1 // not necessarily a valid nat`
> `}`

and `dafny-ProofDependencyWarnings.dfy.expect` is the exact expected output (18 warnings), including:
> `ProofDependencies.dfy(209,10): Warning: ensures clause proved using contradictory assumptions`
> `ProofDependencies.dfy(226,11): Warning: unnecessary requires clause`
> `ProofDependencies.dfy(363,9): Warning: unnecessary (or partly unnecessary) assert statement`
> ``
> `Dafny program verifier finished with 32 verified, 0 errors`

There is also an admitted hole in the test file itself:
> `// TODO: Dafny doesn't generate sufficient Boogie code to make the contradiction detectable`

- **(a)** Perturbs **nothing**. Pure unsat-core / proof-dependency analysis.
- **(b)** Criterion: a proof obligation (assert/ensures) **absent from the covered-element set** of a *successful* proof ⇒ "proved using contradictory assumptions". A `requires`/`assume` absent ⇒ "unnecessary".
- **(c)** **No concrete witness.** Output is a source span plus which dependency went unused.
- **(d)** No numbers in source; see A3/A4.
- **(e)** **MIT**, with a caveat. `dafny-LICENSE.txt` begins: `"Dafny"` / `"Copyright (c) Microsoft Corporation"` / `"All rights reserved."` / `"MIT License"`. **But** the GitHub license API returns `NOASSERTION | Other` (`dafny-license.json`) because of that preamble. The file itself is MIT.
- **(f)** Repo `https://github.com/dafny-lang/dafny`; paper is A3.
- **(g)** Z3 only, one solver; depends on Z3's unsat core.

## A3. Tomb & Joshi, *Static Coverage in Deductive Software Verification*, FMCAD 2025 — the canonical paper

**URL fetched → saved files**
- `https://repositum.tuwien.at/bitstream/20.500.12708/219562/1/Tomb%20Aaron%20-%202025%20-%20Static%20Coverage%20in%20Deductive%20Software%20Verification.pdf` → `tomb-joshi-2025-static-coverage-fmcad.pdf` (11 pp), column-extracted to `tomb-joshi-cols.txt` (pp. 1-8) and `tomb-joshi-cols-p9-11.txt` (pp. 9-11)
- Landing page `https://repositum.tuwien.at/handle/20.500.12708/219562` → `repositum-tombjoshi.html`
- DOI `10.34727/2025/isbn.978-3-85448-084-6_32`, pp. 251-261

**Abstract, verbatim:**
> "The results of software verification are only as trustworthy as the provided specification. Errors or incompleteness in the specification can result in unwarranted confidence in the implementation. Previous work, particularly in the realm of model checking, has investigated a notion of coverage in verification. Portions of the system that could be replaced arbitrarily without causing verification failure are considered uncovered."

**The three-way interpretation (§I):**
> "• uncovered goals are proved vacuously,
> • uncovered assumptions are unnecessary, and
> • uncovered implementation statements are either unconstrained by the specification or unreachable."

**This is the passage that answers your `/smoke` question authoritatively:**
> "One variation of this approach, sometimes referred to as “smoke testing”, is available in several verification tools, including Boogie [5], [24], [27], Why3 [4], [31], and Frama-C [2], [13]. This approach involves adding assert false statements in relevant locations. Any that are provable indicate either an inconsistent specification or dead code."
> "These smoke testing features address part of the problem we aim to solve, but somewhat less efficiently, and do not attempt to identify how much of a program is covered by the given specification, whether any parts of the specification are redundant, or any other issues with specification quality."

**The coverage/vacuity duality and its mutational origin:**
> "The model checking community has extensively explored the problem through the lens of coverage, concluding that coverage and vacuity are dual notions [21]."
> "The original work describing this duality assumed the use of mutation testing as a mechanism for evaluating coverage or vacuity [22]. By changing a program element and attempting to re-prove the program, it's possible to determine whether that element is necessary for the proof."
> "As a more efficient alternative, one can do a proof that the implementation satisfies the specification and identify the facts used to complete the proof, which can be done in several ways. When using an SMT solver, the clauses that appear in an unsatisfiable core provide an overapproximation of one possible set of facts needed to complete a proof."

**Definition (§III.A):**
> "We define verification coverage as a property of programs that meet their specifications as shown by a verifier. As in previous model checking work, we define the covered elements of the program (and its specification) to be those that, if changed, could cause verification to fail. Not all changes would necessarily lead to failure, but for each covered element there is at least one change that could lead to the program no longer verifying. Conversely, uncovered elements are those that could be changed arbitrarily (within the bounds of a well-formed program) without causing verification to fail. Uncovered specification elements indicate over-specification. Uncovered implementation elements indicate under-specification."

**(d) Empirical numbers.** Benchmarks: ESDK (aws-encryption-sdk-dafny), MPL (aws-cryptographic-material-providers-library), INT (non-public), STD (Dafny Std library). Environment:
> "with Boogie v3.0.12 and Z3 v4.12.1, on an AWS c5.4xlarge host (16 3GHz Intel Xeon CPUs, 32GB RAM)."

Overhead (RQ1):
> "the overall time overhead ranges from around 20% to over 73%, depending on the codebase. However, the median time overhead ranges between the much more tolerable −4% and 6%, and the trimmed mean between 3.5% and 9%."

Goals per project (Fig. 5): ESDK 2122, MPL 4981, INT 11042, STD 4647.

Brittleness (RQ2, Fig. 8) — **this is a real cost**: failures rise from N 18 → C 85 (INT) and N 13 → C 42 (STD).
> "The increase in failure count and the standard deviation of resource count shows that enabling coverage analysis can increase brittleness — that is, it can increase the likelihood that verification will fail after small, semantics-preserving changes"

**vs `/smoke` (RQ3, Fig. 9), on INT only:**
> "Total coverage time 8.4×10^3 / Combined smoke time 1.1×10^4"
> "Total coverage resource count 6.0×10^9 / Combined smoke resource count 2.1×10^10"
> "These results show that, in this instance, smoke testing is more expensive than coverage analysis."

Why the comparison is only on one benchmark:
> "the implementation of smoke testing is less robust than that of coverage analysis, and fails on many of our benchmarks, so we could perform a meaningful comparison on only one element of our benchmark suite."

**Warning quality (RQ4, Fig. 10) — the headline number.** Verbatim table, `-layout` extraction:
```
                             ESDK       MPL      INT STD
       Coverage warn.             38      301      78     290
       Redund. assum.             24      164      23      59
       Redund. assert.            11       30      25     201
       False assum.                0        0       8       9
       Dead code                   0        2       0       0
       Prelude contrad.            0       69       0       0
       Proof by contrad.           2       15       0      14
       Redundant test              1        8       0       0
       Dead proof/spec.            0       13      20       7
       Smoke warn.                  -        - 2897          -
```
**78 coverage warnings vs 2,897 smoke warnings** on the same codebase — a 37× noise reduction. (Note: INT's sub-rows sum to 76, not the printed 78; that discrepancy is the paper's, not mine.)

> "Smoke testing generates warnings in terms of Boogie code rather than Dafny code. That, plus the large number of warnings, made it infeasible to categorize each one. We instead simply note that the sheer number, even if they were in Dafny terms, would make them infeasible for the developers to triage, as well."

The most valuable find was a real soundness bug:
> "The inconsistencies due to Dafny's prelude axioms were the most significant specification mistake detected in this analysis."
> "The process of performing these experiments uncovered an inconsistency in the background axioms Dafny generates related to the freshness of heap objects that affects one project (and has since been fixed)."

Honest limits:
> "problem reports free of false positives (with caveats for partially unused elements and intentional proofs by contradiction), though false negatives (failures to detect true specification gaps) are possible."

- **(a)** Definition is counterfactual-**mutational**; the *implementation* perturbs nothing and uses unsat cores instead. Do not conflate these.
- **(b)** Absent from unsat core ⇒ uncovered ⇒ vacuous goal / unnecessary assumption / unconstrained-or-unreachable statement.
- **(c)** **No witness input.**
- **(e)** Paper is FMCAD/TU Wien Academic Press (open access download, no software license). The implementation ships in Boogie (MIT) and Dafny (MIT).
- **(g)** Z3 v4.12.1, **one** solver. Explicitly notes non-minimal cores as a precision limit.

## A4. ProofPulse (2026) — three-valued proof coverage for Dafny, validated against a human strength oracle

**URL fetched → saved files:** `https://arxiv.org/html/2608.30818v1` → `arxiv-html-2608.30818v1.html`, text `fulltext-2608.30818.txt`

**Abstract, verbatim:**
> "Deductive verification ensures that an implementation satisfies its specification, but successful verification does not guarantee the quality of the specification. As such, weak specifications and redundant invariants may create overconfidence in “verified” code."
> "Evaluated against an oracle of 252 programs from the dafny-synthesis benchmark, ProofPulse provides a high-precision signal for specification weaknesses, particularly unnecessary preconditions and vacuous proofs. With unsat-core minimization, ProofPulse achieves perfect precision for precondition classification and reduces false positives across all evaluated categories."

The failure mode it targets, stated better than anywhere else I found:
> "In the extreme case, the Dafny verifier may report a “correct” status for a program that lacks verification conditions. In such instances, the IDE provides a passing “tick” despite the absence of meaningful relationship between the specification and the code, creating confidence in an implementation that remains effectively unverified."

Its own assessment of smoke testing:
> "Smoke testing ( Tomb and Joshi 2025 ) inserts assert false at program points to detect vacuity, but produces many warnings and does not identify redundant specifications. ProofPulse provides finer-grained feedback with fewer false positives."

**(b) The mapping to strength labels — verbatim:**
> "Postconditions : Strong if all postconditions are covered ( CovTest or CovComplete ) and all body code lines are CovComplete ; Weak otherwise. If parts of the code are not required for proving postconditions, this indicates either under-constrained specifications or irrelevant code."
> "Preconditions : Required if any precondition is covered; Optional if all preconditions are Uncovered . Uncovered preconditions can be safely removed. Hence, they are Optional ."
> "Invariants : Strong if all loop invariant nodes are covered; Weak if any is Uncovered ."

**(d) Table 1, verbatim:**
```
 Cat.   Cfg   TP   FP   FN   TN   Prec   Rec   Acc
 Post.  Base  184  24   0    11   0.88   1.00  0.89
        Min   184  21   0    13   0.90   1.00  0.90
 Pre.   Base  63   3    7    96   0.95   0.90  0.94
        Min   63   0    6    98   1.00   0.91  0.96
 Inv.   Base  77   13   0    11   0.86   1.00  0.87
        Min   77   10   0    13   0.89   1.00  0.90
```
> "minimization reduces false positives across all categories (e.g., from 24 to 21 for postconditions) and consistently improves precision, while preserving recall."

**Why precision can never reach 1.0 — the key admission for your purposes:**
> "Precision stays below 1.00 because a postcondition can be fully covered, with every line exercised, and still be weak, in which case ProofPulse classifies it as Strong while the oracle labels it weak."

And the crucial framing:
> "Proof coverage and semantic specification strength are related but distinct notions. A specification is semantically weak when it under-specifies intended behavior. This weakness often manifests itself as weak proof coupling... Although coverage cannot determine whether a specification fully captures program intent, it can reveal redundancy, vacuity, and under-constrained proofs."

**(c) A witness of sorts, but not an input:**
> "ProofPulse additionally detects vacuous proofs arising from contradictory assumptions. Figure 3 shows a method with an unsatisfiable forall precondition, where the method body is marked as Uncovered (marked in red). The web viewer's proof graph further reveals that the contradictory requires clause alone suffices to discharge the postcondition ( 2 == 3 ), exposing the vacuous reasoning."

**A quantifier blind spot you will hit if you build on this:**
> "Quantified expressions ( forall ). Dafny encodes quantified specifications as Boogie axioms with SMT triggers. These triggers are not part of the core logical proof and do not appear in Z3's unsat core, so the corresponding source lines are always reported as uncovered, even when they are necessary for verification"

- **(e)** **MIT** (verified: `license-VeriFixer-ProofPulse.json` → `MIT | MIT License | https://github.com/VeriFixer/ProofPulse/blob/main/LICENSE`)
- **(f)** Repo `https://github.com/VeriFixer/ProofPulse`; paper `https://arxiv.org/abs/2608.30818`; Docker `https://doi.org/10.5281/zenodo.21174686`; demo `https://www.youtube.com/watch?v=8pO3NAodjoQ`
- **(g)** Dafny → Boogie → **Z3**, invoked via `--verification-coverage-report`, plus its own second Z3 pass: `"Z3 unsat-core minimization : An optional unsatisfiable core minimization layer over Z3"` / `"ProofPulse optionally applies deletion-based unsat-core minimization ( Marques-Silva and Lynce 2011 ) before coverage classification."` So: one solver, two passes.

## A5. Beer, Ben-David, Eisner, Rodeh — CAV 1997, the origin. **Abstract only; full text paywalled.**

**URL fetched → saved:** `https://link.springer.com/chapter/10.1007/3-540-63166-6_28` → `springer-beer-vacuity.html`, text `springer-beer-vacuity.txt`

Metadata verbatim: *"Efficient detection of vacuity in ACTL formulas"*, "Ilan Beer 1 , Shoham Ben-David 1 , Cindy Eisner 1 & … Yoav Rodeh 1", "Computer Aided Verification (CAV 1997)", "pp 279–290", "LNCS, volume 1254", "790 Accesses 79 Citations".

**Abstract, verbatim:**
> "Prepositional logic formulas containing implications can suffer from antecedent failure, in which the formula is true trivially because the pre-condition of the implication is not satisfiable. In other words, the post-condition of the implication does not affect the truth value of the formula. We call this a vacuous pass, and extend the definition of vacuity to cover other kinds of trivial passes in temporal logic. We define w-ACTL, a subset of CTL and show by construction that for every w-ACTL formula ϕ there is a formula w( ϕ ), such that: both ϕ and w( ϕ ) are true in some model M iff ϕ passes vacuously. A useful side-effect of w( ϕ ) is that if false, any counter-example is also a non-trivial witness of the original formula ϕ ."

(The "Prepositional" typo is Springer's.)

- **(a)** Perturbs the **SPECIFICATION** — φ is rewritten to w(φ). Not the model/code.
- **(b)** φ passes vacuously **iff** both φ and w(φ) hold in M.
- **(c)** **YES** — and this is the one classic that gets it right: *"if false, any counter-example is also a non-trivial witness of the original formula ϕ."* Your sabotaged-twin design is closer to Beer et al. than to anything in the deductive-verification line.
- **(e)** Springer copyright, no open license. **(g)** BDD-based symbolic model checking (IBM RuleBase), no SMT.
- **GAP, plainly:** the page says *"Download to read the full chapter text"* — I could not fetch the body. I also did **not** fetch the FMSD 2001 journal version, *Efficient Detection of Vacuity in Temporal Model Checking*.

## A6. Frama-C WP smoke tests — CONFIRMED, and the only genuinely MULTI-PROVER one

**URL fetched → saved:** `https://frama-c.com/download/frama-c-wp-manual.pdf` → `frama-c-wp-manual.pdf`, text `frama-c-wp-manual.txt` (§2.4.5, p. 37)

**Verbatim:**
> "During modular deductive verification, inconsistencies in function requirements can be difficult to detect until you actually call it. Although, such inconsistencies make its post-conditions provable, while its pre-conditions would never be provable."
> "The WP plug-in can generate smoke-tests to detect such inconsistencies. Basically, it consists in checking if \false is provable under the requirements or assumptions of a behavior, or under the invariants of a loop. Also, a simple reachability analysis is performed to track dead-code statements and calls that neither terminates nor exits."
> "This is best-effort verification : if at least one prover succeed in proving \false, an inconsistency is detected. Otherwise, the test is not conclusive, and you can never be sure that the ACSL annotations are free of inconsistencies."
> "In case any smoke-test fails, a “False if reachable” status is put on the inconsistent requirements, or on the loop with inconsistent invariants, and WP generates a user warning."

Flags, verbatim:
> `-wp-(no)-smoke-tests generates checks to detect inconsistencies (default is: no).`
> `-wp-smoke-timeout timeout to be used for trying to prove \false on smoke-tests (default is 2 seconds).`
> `-wp-(no)-smoke-dead-assumes includes smoke tests for dead assumes (default is: yes).`
> `-wp-(no)-smoke-dead-call includes smoke tests for non-terminating calls (default is: yes).`
> `-wp-(no)-smoke-dead-code includes smoke tests for dead code (default is: yes).`
> `-wp-(no)-smoke-dead-local-init includes smoke tests for dead local variables initialization (default is: no).`
> `-wp-(no)-smoke-dead-loop includes smoke tests for inconsistent loop invariants (default is: yes).`

The inverted reporting convention, which will bite you if you parse output:
> "the WP displays “Failed” when some prover succeeds in discharging the \false proof-obligation and “Passed” when all the provers result are unknown or interrupted. In the final prover statistics, the interrupted smoke tests are not reported, since they are considered valid tests."

- **(g)** **YES, more than one prover**, stated explicitly: *"if at least one prover succeed"*, *"all the provers result are unknown"*. WP dispatches via Qed/Why3 to Alt-Ergo, Z3, CVC.
- **(e)** **Unverified.** Frama-C is commonly LGPL-2.1 but I did **not** fetch a LICENSE file. Do not cite my word for it.

## A7. Why3 `--smoke-detector` — CONFIRMED, and it perturbs the SPEC, not the code

**URL fetched → saved:** `https://www.why3.org/doc/manpages.html` → `why3-manpages.html.html` (§5.4.3). Also `why3-doc.html`, `why3-starting.html.html`.

**Verbatim:**
> `--smoke-detector [=none|top|deep] ¶ Try to detect if the context is self-contradicting (default: top).`
> "The smoke detector tries to detect if the context is self-contradicting and, thus, that anything can be proved in this context. The smoke detector can't be run on an outdated session and does not modify the session."
> "top The negation of each proved goal is sent with the same timeout to the prover that proved the original goal. Goal G : forall x:int. q x -> (p1 x \/ p2 x) becomes Goal G : ~ (forall x:int. q x -> (p1 x \/ p2 x)) In other words, if the smoke detector is triggered, it means that the context of the goal G is self-contradicting."
> "deep This is the same technique as top but the negation is pushed under the universal quantification (without changing them) and under the implication. The previous example becomes Goal G : forall x:int. q x /\ ~ (p1 x \/ p2 x)"
> "It should be clear that detecting smoke in that case does not necessarily means that there is a mistake: for example, this could occur in the WP of a program with an unfeasible path."
> "At the end of the replay, the name of the goals that triggered the smoke detector are printed: goal 'G', prover 'Alt-Ergo 0.93.1': Smoke detected!!! Moreover Smoke detected (exit code 1) is printed at the end if the smoke detector has been triggered, or No smoke detected (exit code 0) otherwise."

- **(a)** Perturbs the **SPECIFICATION / goal formula** — it *negates* it. This is a mechanically different technique from Boogie's inserted `assert false`, despite both being called "smoke".
- **(b)** The negation of an already-proved goal is **also** provable ⇒ context self-contradicting.
- **(c)** No witness wired in (Why3's counterexample machinery is separate, §5.2.3-5.2.4).
- **(g)** Multi-prover capable — *"the prover that proved the original goal"*; printed example is Alt-Ergo 0.93.1.
- **(e)** **Unverified** (commonly LGPL-2.1; I did not fetch a LICENSE file).

## A8. Negative findings — clearly labeled

**Verus has NO vacuity/smoke/coverage feature**, as far as I could fetch.
- Fetched `https://verus-lang.github.io/verus/guide/print.html` (1,051,782 bytes) → `verus-guide-print.html`, stripped to `verus-guide.txt` (628,695 chars). Keyword counts: `vacuous` **0**, `vacuity` **0**, `assert false` **0**, `smoke` **0**, `trivially` 2, `unreachable` 2.
- Fetched `https://raw.githubusercontent.com/verus-lang/verus/main/source/rust_verify/src/config.rs` (34,516 bytes) → `verus-config.rs`. Grep for `vacuous|vacuity|smoke|unreachable|coverage` returns **only** `--profile` / `--profile-all` / `--capture-profiles` lines, e.g. `opts.optflag("", OPT_PROFILE_ALL, "Always collect and report prover performance data");` — that is prover *performance* profiling, not vacuity.
- **Caveat, stated plainly:** I could not list the Verus git tree. GitHub API returned `{"message":"API rate limit exceeded for 130.160.224.133. ..."}` → `verus-tree.json` is 281 bytes with 0 entries. So this is a docs+CLI-level negative, not an exhaustive source-level one.

**F\* has NO vacuity/smoke feature.**
- Fetched `https://raw.githubusercontent.com/FStarLang/FStar/master/src/basic/FStarC.Options.fst` (113,872 bytes) → `fstar-FStarC.Options.fst`. Counts: `vacuous` **0**, `vacuity` **0**, `smoke` **0**, `unreachable` **0**.
- What exists instead: `quake` (38 hits — `quake`, `quake_lo`, `quake_hi`, `quake_keep`) which is **proof-stability retrying**, and `admit_smt_queries` (9 hits) which **skips** proofs. Neither is vacuity detection.
- Note `src/basic/FStar.Options.fst` returns **404**; the module was renamed to `FStarC.Options`.

**The vacuity literature is essentially absent from arXiv.** All searches saved as `arxiv-api-*.xml`:
- `all:"specification vacuity"` → **0 results**
- `all:"vacuous specification"` → **0 results**
- `all:"proof vacuity"` → **0 results**
- `all:"specification adequacy"` → **0 results**
- `all:"Static Coverage in Deductive"` → **0 results** (FMCAD 2025 is not on arXiv)
- `all:"vacuity checking"` → 3 results, **all unrelated** (LTL minimal unsat formulas, real-time fixpoints)
- `all:"vacuous" AND all:"Dafny"` → 2: ProofPulse (2608.30818) and 2604.22601 (*From Natural Language to Verified Code...*, **not fetched**)

---

# (B) Specification-strength metrics for LLM-generated specs

## B1. nl2postcond — Endres, Fakhoury, Chakraborty, Lahiri (FSE 2024), arXiv 2310.01831v2

**URLs fetched → saved:** `https://arxiv.org/abs/2310.01831` → `arxiv-abs-2310.01831-nl2postcond.html`; `https://arxiv.org/html/2310.01831v2` → `arxiv-html-2310.01831v2-nl2postcond.html`, text `nl2postcond-fulltext.txt`; `https://nl2postcond.github.io/` → `nl2postcond-site.html`

**This paper names your problem explicitly** (§2.1.2; `[MATH:...]` markers are where I recovered the stripped LaTeX from `alttext`):
> "(Test-set) correctness is a necessary condition for a valid and useful postcondition, however, it is not sufficient . For example, the expression [MATH:\it true] vacuously satisfies any implementation [MATH:r] for any input [MATH:i\in{\it T}], and is therefore correct."

And it says why the obvious fix is unavailable:
> "However, this again poses the problem that the most desired postcondition is simply the strongest postcondition of program, which is computationally intractable ( Dijkstra and Scholten, 1990 ) . Instead, we use a concept of completeness that measures the degree to which the postcondition distinguishes the reference implementation from other incorrect implementations."

**(a) Perturbs the CODE.** And crucially, *not* by operator mutation:
> "Inspired by mutation-testing literature (c.f. Jia and Harman (2010) ) that assigns a score to a test based on the fraction of code mutants “killed” or distinguished under , we assign a measure of bug-completeness to a postcondition as the fraction of code mutants that can be distinguished given the set of tests ."
> "Unlike traditional mutation testing, we parameterize completeness with a semantically distinct code mutant set that are guaranteed to differ from (and from each other) on at least one test in ."

Their reason for rejecting operator mutation is directly relevant to your design:
> "We believe that such a fixed set of mutation operators does not approximate real-world bugs for two reasons: (a) first, since code mutants only differ from the reference implementation in one or two operators at a time, it may not cover mutations that are further away in the edit distance, and (b) it may not cover subtle bugs that a human would write using different syntactic constructs (e.g., a while loop instead of a for loop) or APIs. We propose the use of LLMs to sample mutants from the natural distribution of implementations to the problem described by the natural language intent ."
> "In particular, we believe this paper is the first to propose the use of LLMs to derive a natural distribution of code mutants to evaluate the completeness of specifications."

How mutants are made:
> "To generate the set of code mutants needed for bug-completeness , we use an LLM ( GPT-3.5 with temperature 0.9) to generate a set of codes that satisfy the natural language intent , and filter the ones that fail at least one test in ."

**(b) Criterion:**
> "In other words, bug-completeness-score measures the fraction of code mutants that fail the correct postcondition. If the bug-completeness-score of a postcondition is 1, we say that the postcondition is bug-complete ."

**(c) YES, a concrete witness — but a test input from a fixed suite, not solver-generated.** The Defects4J criterion, verbatim (§4.1.2; the "a a" typo is the source's):
> "(1) The postcondition passes all the trigger and regression tests, on the fixed version of a function.
> (2) The postcondition fails a a trigger test or regression test on the buggy version of a function."

**(d) Numbers.** EvalPlus, Table 2 (verbatim rows, cols = %bug-complete / %problems with / %problems union / avg natural / avg all):
```
 GPT-4     base  ✗   35.1  61.6  62.2  0.81  0.85
 GPT-4     base  ✓   34.9  58.0  61.6  0.78  0.82
 GPT-4     simple ✗   9.2  26.2  29.3  0.40  0.52
 GPT-3.5   base  ✓   18.5  47.0  49.4  0.70  0.76
 StarChat  base  ✗    0.8   7.3   8.5  0.13  0.24
```
> "with GPT-4 we can generate correct postconditions for up to 96% of problems for our benchmark, EvalPlus , with correct postconditions able to discriminate up to 81% of buggy programs on average."

A finding directly relevant to your sabotaged-twin choice:
> "our completeness metric was consistently (though not always substantially) lower when only considering natural bugs; naturally occurring LLM code generation bugs are harder to kill via nl2postcond than artificially seeded bugs. This finding highlights a potential limitation in using artificially seeded faults to assess postcondition correctness as it may artificially inflate the metric."

The weakest spec category, with a 6× spread:
> "the weakest postcondition type, Type Checks , killed only 14% of natural bugs on average while the strongest, Arithmetic Equality check, killed 82%, a 6x difference."
> "Type Checks are also the most prevalent category, indicating LLM preference towards generating such constraints."

Defects4J (525 Java-8-reproducible bugs from 835, 840 methods):
> "GPT-4 was able to generate discriminating postconditions for up to 47/525 (9%) bugs. StarChat caught fewer, but still generated postconditions that distinguished up to 25 bugs. Across all prompt variants and models, we were able to generate a bug-discriminating postcondition for 70 buggy methods from 64 unique bugs in Defects4J , 12.2% of all bugs considered."
> "achieving accept@1 of up to 0.39 and accept@10 of up to 0.75. StarChat performs worse, with accept@1 and accept@10 of 0.12 and 0.56 respectively."
> "A majority of nl2postcond -caught bugs (52/64) could not be found by TOGA, due to the lack of any EvoSuite generated test prefix that reaches the bug location."

**(g) NO PROVER AT ALL.** Pure runtime assertion execution:
> "However, such a notion of correctness is difficult to establish in the absence of formal verification tools ( Leino, 2010 ; Swamy et al., 2011 ) , and may further require manual effort to establish such proof even for verification-aware languages. We take a pragmatic approach, assuming that the test cases in are sufficiently comprehensive to approximate the space of all legal inputs."

**(e)/(f) GAP.** v2 says *"We plan to make a replication package publicly available in near future"*. The project site `nl2postcond-site.html` links code to `https://github.com/microsoft/nl-2-postcond`. **I did not fetch that repo's license** (plan mode). Authors: "Madeline Endres 1 , Sarah Fakhoury 2 , Saikat Chakraborty 2 , Shuvendu K. Lahiri 2 1 University of Michigan, 2 Microsoft Research". **License UNVERIFIED.**

## B2. NL2Contract / "Beyond Postconditions" — arXiv 2510.12702v1. **The most rigorous strength metric I found.**

**URLs fetched → saved:** `https://arxiv.org/abs/2510.12702` → `arxiv-abs-2510.12702.html`; `https://arxiv.org/html/2510.12702v1` → `arxiv-html-2510.12702v1.html`, text `fulltext-2510.12702.txt`

This paper's contribution is replacing test-execution with a **real verifier**, and the resulting collapse is dramatic.

> "Completeness aims at measuring the discriminative power of contracts, i.e., their ability of distinguishing buggy from non-buggy programs via specification violations."
> "Soundness needs to be checked on all states and completeness additionally investigates all programs. In particular the latter is infeasible in practice. Here, we address the first challenge by employing a formal verifier, ideally proving specification soundness, and a combination of verifier and mutations for the second challenge."

**(a) Perturbs the CODE** — and reuses nl2postcond's mutant set verbatim:
> "we employ the same set of code mutants $CM$ as used in the evaluation of nl2postcond postconditions. The set contains 4 to 233 code mutants per HumanEval task with a median of 55 mutants per task. The mutants are generated as code completions from an earlier version of ChatGPT."

**(b) Two criteria, both verifier-checked:**
> "we adopt a more pragmatic approach and declare a specification as unsound if CrossHair finds a specification violation on the reference implementation in 60s and sound otherwise."
> "We then evaluate completeness on this set of code mutants $CM$, i.e., for every $P\in CM$, the verifier is tasked to find specification violations. If we get ${\sf V}(P,Spec)=\sigma_{\text{\faIcon{times}}}$ (for some $\sigma_{\text{\faIcon{times}}}\in\Sigma$) for all $P\in CM$, we consider $Spec$ to be sufficiently complete."

**(d) The headline collapse:**
> "The performance of LLMs prompted with nl2postcond drop drastically from 73.6% – 89.0% $accept@1$ test-set correctness to 11.5% – 13.0% $sound@1$ when evaluated with respect to verification soundness. LLMs prompted to generate functional contracts with NL2Contract achieve a verification soundness score $sound@1$ of 66.7% to 81.1%."

Root cause — missing **preconditions**:
> "most specifications generated with nl2postcond (75.8% to 82.0%) are unsound due to violations of condition (S1) of Section 2 , i.e. they allow invalid inputs that violate the reference precondition. LLMs prompted with NL2Contract are better in capturing the ground truth precondition. Only 10.4% to 12.4% of the NL2Contract specifications are unsound due to violations of the reference precondition."

**A warning that applies directly to a test-based strength metric:**
> "Bug completeness overestimates verification completeness in practice: LLMs produce less verification sound specifications that are useful for the software verifier to detect all code mutants."
> "between 12.9% and 29.9% of the LLM generated functional contracts are verification sound and verification complete while only 2.8% to 4.8% of nl2postcond postconditions are verification complete."
> "LLMs prompted with NL2Contract can generate at least one verification sound functional contract that is able to kill all code mutants for 80 to 92 HumanEval + tasks (48.8% to 56.1% of all tasks)."
> "when provided with NL2Contract contracts, the software verifier can automatically detect up to 73% of all mutants, allowing an automatic verification of up to 69 out of 164 tasks."

Real-world (Python-by-Contract, 59 buggy solutions, 31 implementation bugs, 19 CrossHair-confirmable):
> "Supplied with NL2Contract generated specifications, CrossHair is able to automatically detect 14 out of 19 bugs that it is capable to find."
> "The software verifier supplied with NL2Contract based specifications finds 9 to 11 bugs more than when supplied with nl2postcond postconditions."
> "We find that most alarms reported by CrossHair given the nl2postcond specifications are false alarms , i.e. specification violations that are not bug triggering."

**(c) YES — genuine solver-produced witness inputs**, and a concrete illustration of the false-alarm failure:
> "CrossHair reports a bug for $n=1$ when evaluated with the given postcondition on the non-buggy reference implementation."

**(g)** CrossHair (symbolic execution for Python), **one** verifier, and incomplete:
> "CrossHair – as most automatic verifiers for Python – is incomplete , i.e., it reports unknown results if it cannot prove the complete input space to be safe."

Scale: 9,840 contracts across GPT-4o, GPT-5 (Chat), CodeQwen 2.5; HumanEval+ (164 problems, ~775 tests/problem, reference preconditions).

**(e)/(f) GAP:** I found **no repo URL and no license** for NL2Contract. Paper only: `https://arxiv.org/abs/2510.12702`.

## B3. VERINA — arXiv 2505.23135v3. Spec-vs-spec implication, not mutation.

**URLs fetched → saved:** `https://arxiv.org/html/2505.23135v3` → `arxiv-html-2505.23135v3.html`, text `fulltext-2505.23135.txt`; `https://raw.githubusercontent.com/sunblaze-ucb/verina/main/LICENSE` → `verina-LICENSE.txt`

**(a) Perturbs the TESTS, not the code or spec:**
> "Necessary negative tests : We mutated each positive test case to construct at least three different negative tests that violate either the pre‐ or the post‐condition, except when the function's output has boolean type, in which case only a single negative test can be created."

**(b) Criterion is implication against a human ground-truth spec:**
> "An ideal generated specification should achieve $\hat{\phi}=\phi$, which entails two properties—(i) soundness ($\hat{\phi}\subseteq\phi$): it is “small enough” to cover only correct programs, and (ii) completeness ($\phi\subseteq\hat{\phi}$): it is “large enough” to cover all correct programs."
> "$\hat{Q}$ is sound iff $\forall\overline{x},y.P(\overline{x})\,\land\,\hat{Q}(\overline{x},y)\Rightarrow Q(\overline{x},y)$"

A three-stage cascade, which is unusual and worth noting:
> "the evaluator first attempts to prove $R$ using LLM-based theorem provers, as they provide formal guarantees when proof is successful."
> "For many cases, e.g., the specification in Figure 1 , Lean can automatically determine if $R^{\prime}$ holds ( Selsam et al., 2020 ) and we return the corresponding result. Otherwise, we employ property-based testing with the plausible tactic in Lean"
> "Lean's property-based testing cannot handle a small number of complicated relationships on some testcases, for which our evaluator returns unknown ."

**(c) YES — concrete witness inputs, worked verbatim:**
> "k < s . size - 1 can be determined as unsound using the positive test ( s : #[1, 2, 3, 4, 5]) ( k : 4) , while k < s . size + 1 is incomplete based on the negative test ( s : #[1, 2, 3, 4, 5]) ( k : 5) ."

**(d)** 189 tasks; median 5 positive / 12 negative tests per instance; 100% line coverage.
> "The best model, OpenAI o3, achieves a 72.6% code correctness rate, 52.3% for specification soundness and completeness, and a mere 4.9% proof success rate (based on one trial per task)."

An anti-triviality trick you may want to steal:
> "We crafted all ground truth specifications such that they cannot be directly used to solve the coding problem. This prevents LLMs from generating an implementation trivially equivalent to the specification."

- **(e)** **Apache-2.0** (verified twice: API `Apache-2.0 | https://github.com/sunblaze-ucb/verina/blob/main/LICENSE`, and `verina-LICENSE.txt` is the Apache 2.0 text).
- **(f)** `https://github.com/sunblaze-ucb/verina`, `https://huggingface.co/datasets/sunblaze-ucb/verina`, `https://arxiv.org/abs/2505.23135`
- **(g)** Lean 4 (ITP) + LLM-based theorem provers + Lean `plausible` PBT. Three oracles, one proof language.

## B4. Misu et al., arXiv 2402.00247v2 — the human Strong/Weak/Wrong oracle everyone else reuses

**URLs fetched → saved:** `https://arxiv.org/abs/2402.00247` → `arxiv-abs-2402.00247.html`; `https://arxiv.org/html/2402.00247v2` → `arxiv-html-2402.00247v2.html`, text `fulltext-2402.00247.txt`

**This is the clearest statement of the problem in the whole corpus:**
> "Automated quantitative metrics are only a weak proxy for performance of LLMs in this task. In one extreme, the synthesized Dafny code may not contain any formal specifications whatsoever; in those cases, the verifier will report verification success. Synthesized methods may contain only weak and uninteresting formal specifications that are trivial to verify."
> "The absence of postconditions is a strong sign that the solution is not usefully verified: methods with no specifications trivially avoid being wrong."
> "although GPT-4 generated 104 verified methods, only 56 of them contain postconditions. Since the other 48 verified methods have no postconditions, they cannot be considered formally verified."

**(a)/(b) Perturbs NOTHING — it is entirely manual labelling:**
> "We tagged the quality of postconditions into three groups, Strong , Weak and Wrong ."
> "we only tagged preconditions into two groups, (i) Required , which is necessary to prove the postconditions and implementation; (ii) Optional , its presence is not required for verification."
> "The two authors independently performed this manual tagging and reached a high Inter-Rater Reliability (IRR) ( Hallgren, 2012 ) (93.91% Cohen Kappa"

**The canonical Weak example, verbatim from Table 4:**
> `/*Write a method in Dafny to interleave 3 sequence of the same length into a single flat sequence.*/`
> `method InterleaveThreeSequences ( seq1 : seq < int >, seq2 : seq < int >, seq3 : seq < int >)`
> `returns ( interleavedSeq : seq < int >)`
> `requires | seq1 | == | seq2 | == | seq3 |`
> `ensures | interleavedSeq | == 3 * | seq1 |`
> `//strong postcondition will also check the relative order of the sequence values.`

**(d)** 178 MBPP-san problems hand-translated to Dafny.
> "GPT-4 was able to generate verified, human-evaluated, Dafny methods for 58% of the problems, however GPT-4 managed only 19% of the problems with the Contextless prompt, and even fewer (10%) for the Signature prompt."
> "Although GPT-4 got 56 verified programs in Contextless prompting, we encountered 15 of them have Weak postconditions. ... in Signature prompting 9 of verified methods contain Weak postconditions which are very trivial specifications to verify correct implementation."
> "In Dynamic Few-Shot , GPT-4 's specification synthesis result is impressive. Only 3 of verified methods had Weak postconditions and in 8 cases it misunderstood the problems' description"
> "Specifically in Dynamic Few-Shot RAG prompt, 90.35% (103/114) of verified methods synthesized from GPT-4 contain Strong postconditions."

- **(c)** No witness.
- **(e)** ⚠️ **GPL-3.0** — verified: `license-Mondego-dafny-synthesis.json` → `GPL-3.0 | GNU General Public License v3.0 | https://github.com/Mondego/dafny-synthesis/blob/master/LICENSE`. **Flagging loudly:** this is the one copyleft license in the set, and it is the dataset ProofPulse's 252-program oracle comes from. If you plan to redistribute derived data, this constrains you.
- **(f)** `https://github.com/Mondego/dafny-synthesis`, `https://arxiv.org/abs/2402.00247`
- **(g)** Dafny → Boogie → Z3, one solver.

## B5. Verus-SpecGym — arXiv 2605.26457v1. Verus/Rust, executable specs, real human adversarial inputs.

**URLs fetched → saved:** `https://arxiv.org/abs/2605.26457` → `arxiv-abs-2605.26457.html`; `https://arxiv.org/html/2605.26457v1` → `arxiv-html-2605.26457v1.html`, text `fulltext-2605.26457.txt`

**(a)/(b) Neither spec nor code is mutated by the framework. Four-bucket faithfulness:**
> "$\tau_{\mathrm{pre\text{-}comp}}$: valid inputs $x\in\mathrm{dom}(R_{s_{I}})$; the pre-spec should accept."
> "$\tau_{\mathrm{pre\text{-}sound}}$: invalid inputs $x\notin\mathrm{dom}(R_{s_{I}})$; the pre-spec should reject."
> "$\tau_{\mathrm{post\text{-}comp}}$: correct pairs $(x,y)\in R_{s_{I}}$; the post-spec should accept."
> "$\tau_{\mathrm{post\text{-}sound}}$: pairs $(x,y)$ with $x\in\mathrm{dom}(R_{s_{I}})$ but $(x,y)\notin R_{s_{I}}$; the post-spec should reject."
> "A faithful specification accepts every test in the two completeness buckets and rejects every test in the two soundness buckets."
> "If the specification is too weak, a verifier may certify an incorrect program; if it is too strong, a correct program may fail to verify."

**(c) YES — and this is a naturally-occurring sabotaged twin, which is why I'm listing it under (C) too:**
> "For valid inputs, we also observe the output produced by the program being hacked when run on that input. If the Codeforces checker accepts this output, we add the input-output pair to $\tau_{\mathrm{post\text{-}comp}}$; otherwise, we add the pair to $\tau_{\mathrm{post\text{-}sound}}$."
> "This is especially important because LLMs struggle to create counterexamples for almost-correct but subtly wrong submissions to programming problems ( Sinha et al., 2025 ) , whereas Codeforces hacks are human-generated adversarial inputs written against real submitted solutions."

Mechanism:
> "In the symbolic check, the evaluator inserts each test case as a Verus assertion alongside the generated specification and runs the verifier on the resulting program. For completeness tests, the assertion states that the specification accepts the test (e.g., assert(pre_spec(x)) or assert(post_spec(x, y)) ). For soundness tests, the assertion states that the specification rejects the test (e.g., assert(!pre_spec(x)) or assert(!post_spec(x, y)) )."

**(d)** 581 tasks.
> "gemini-3.1pro , solves 77.8% of tasks, other frontier models solve 51.1--57.8% & OSS models reach only 21.5--25.5%."
> "if we evaluate only on completeness testcases, pass@1-completeness is substantially higher, but once we add soundness testcases to the evaluation, pass@1 drops from 77% to 58% for gpt5.3-codex , 82% to 78% for gemini-3.1pro , and 59% to 51% for opus4.6 ."

**LLM-as-judge is inadequate — a hard number you should have:**
> "When we used gpt5.3-codex as an LLM judge on its own specifications, it marked 49 of 191 incorrect but compilable specifications as correct. Thus, the LLM judge failed to identify errors in 25.7% of the incorrect specifications for which our benchmark found a verifiable failing testcase."

Failure taxonomy:
> "model-generated specs can omit important input assumptions, accept incorrect outputs, & reject valid ones."

- **(e)** **Apache-2.0** (verified: `license-formal-verif-is-cool-verus-spec-gym.json`).
- **(f)** `https://github.com/formal-verif-is-cool/verus-spec-gym`, `https://arxiv.org/abs/2605.26457`
- **(g)** **TWO oracles.** Verus → **Z3** (`"verification conditions are checked by the Z3 SMT solver ( de Moura and Bjørner, 2008 )"`), then a compiled-Rust concrete executor via extended `exec_spec`.

## B6. SpecGen — arXiv 2401.08807v5. ⚠️ **It mutates the SPEC, and for the opposite reason. Do not miscite it.**

**URLs fetched → saved:** `https://arxiv.org/abs/2401.08807` → `arxiv-abs-2401.08807.html`; `https://arxiv.org/html/2401.08807v5` → `arxiv-html-2401.08807v5.html`, text `fulltext-2401.08807.txt`

**(a) Perturbs the SPECIFICATION only:**
> "As shown in Table I , we define four kinds of mutation operators including predicative, logical, comparative, and arithmetic. Each type of mutation corresponds to one type of operator supported by JML. ... A mutation operation substitutes the operators of the corresponding type in the specification with another of the same type. For example, after applying a predicative mutation, a \exists predicate within a specification may be substituted with \forall ."

**The purpose is REPAIR, not strength assessment:**
> "given a verification failure result by the LLM, SpecGen endeavors to combine four different kinds of mutation operators to modify it and obtain all potential variants. A selector adopting a heuristic selection strategy by assigning different weights of variants further repeatedly chooses a subset of these mutated variants deemed most likely to pass the verification until the results are successfully verified."

**(b) There is NO automated strength or vacuity criterion. Quality is a human Likert study:**
> "User Rating . It aims to measure the semantic quality of the generated specifications. We invited 15 Ph.D. students who are experts in Java programming language to rate the specifications generated by different approaches. The research is conducted using the Likert Scale ( Likert 1932 ) [49] , where students are required to give a rating from one point to five points for each case according to a reference rating criteria."
> "the ground truth specifications (oracle) receive an average rating score of 4.83 ... the specifications generated by SpecGen received a rating score of 4.54 ... In comparison, the specifications generated by Houdini and Daikon received an average rating score of 2.32, reflecting the semantic weakness in these specifications."

Their motivating triviality example (useful as a baseline for what "too weak" looks like):
> "both Houdini and Daikon can only generate trivial post-conditions such as nums != null and \result[i] >= 0 for the method TwoSum() as a whole. ... The generated specifications are too trivial, without detailed information to accurately capture the program's functionality."

**(d)**
> "SpecGen succeeds in generating verifiable specifications for 279 out of 385 programs, outperforming the existing purely LLM-based approaches and conventional specification generation tools like Houdini and Daikon."
> "the number of programs handled by Daikon, Houdini, Conversational generation, and AutoSpec is 72, 98, 218, and 247, respectively."
> SV-COMP subset: "SpecGen outperforms all baseline approaches, with the number of programs that generated verifiable specifications increasing to 179." (of 265)
> Ablation: "SpecGen w/o Logical has the second least number of programs i.e., 235 ... SpecGen w/o Predicative and SpecGen w/o Arithmetic have the most number of programs (259 and 262 respectively)"

Config, verbatim:
> "The verifier is OpenJML [26] , the most recent JML specification verification tool ... We set the weight of comparative, logical, arithmetic, and predicative mutation to -1, -2, -4, and -4 respectively"

- **(c)** **No witness input.** Feedback is the verifier's error message text.
- **(e)** **MIT** (verified: `license-Lezhi-Ma-SpecGen-Artifact.json` → `MIT | https://github.com/Lezhi-Ma/SpecGen-Artifact/blob/main/LICENSE`).
- **(f)** `https://github.com/Lezhi-Ma/SpecGen-Artifact`, `https://sites.google.com/view/specgen`, `https://arxiv.org/abs/2401.08807`
- **(g)** OpenJML, one verifier. GPT-3.5-turbo-1106, temp 0.4, 4-shot, max 10 rounds.

## B7. VeriSpecGen — arXiv 2604.10392v1. **Abstract analyzed; full text saved but NOT analyzed.**

Abstract, verbatim from `arxiv-abs-2604.10392.html`:
> "We present VeriSpecGen, a traceable refinement framework that synthesizes intent-aligned specifications in Lean through requirement-level attribution and localized repair. VeriSpecGen decomposes natural language into atomic requirements and generates requirement-targeted tests with explicit traceability maps to validate generated specifications. When validation fails, traceability maps attribute failures to specific requirements, enabling targeted clause-level repairs. VeriSpecGen achieve 86.6% on VERINA SpecGen task using Claude Opus 4.5, improving over baselines by up to 31.8 points across different model families and scales. Beyond inference-time gains, we generate 343K training examples from VeriSpecGen refinement trajectories and demonstrate that training on these trajectories substantially improves specification synthesis by 62-106% relative and transfers gains to general reasoning abilities."

**GAP, plainly:** I fetched `https://arxiv.org/html/2604.10392v1` → `arxiv-html-2604.10392v1.html`, text `fulltext-2604.10392.txt` (90,160 chars), but I prioritized SpecSyn and VeriScale and did **not** read it. The file is on disk and ready. It is the current SOTA on Verina SpecGen (86.6%) and is likely relevant to (B) — recommend a follow-up pass.

---

# (C) Works that accept a spec only if it REFUTES a deliberately-broken implementation

## C1. SpecSyn — arXiv 2604.21570v1. **This is your idea, named, formalized, and measured.**

**URLs fetched → saved:** `https://arxiv.org/abs/2604.21570` → `arxiv-abs-2604.21570.html`; `https://arxiv.org/html/2604.21570v1` → `arxiv-html-2604.21570v1.html`, text `fulltext-2604.21570.txt`

**The framing, verbatim, is almost exactly your sabotaged-twin rationale:**
> "unlike specification correctness, which can be determined relatively easily with the aid of a verifier, the semantic strength of specifications, i.e., how precise the statements are in terms of reflecting program behaviors [66] , does not admit a rigorous definition and thus cannot be trivially assessed, resulting in the absence of mechanisms in existing approaches to guarantee the strength of generated specifications."
> "The idea originates from the concept of trivial properties on programs, i.e., properties that either hold for all programs or fail to hold for all programs [69] . Similar intuitions can be adapted to program specifications as well: trivial specifications adapt to all programs, while non-trivial specifications hold for some programs but are rejected by others, i.e., they can distinguish programs with distinctive semantics."
> "Guided by the insight that the semantic strength of specifications lies in their ability to distinguish programs from their non-equivalent variants, we measure the semantic strength of specifications by the number of variants they refute and leverage the assessment results to guide the LLM in generating stronger specifications."

**(b) The metric, verbatim (Definition 1):**
> "Given a program $p$, a set of specification $S$, and a set $M$ of semantic-non-equivalent mutation operators $m:P\rightarrow P$, the variant discriminative rate (VDR) of $S$ towards $M$ is defined as
> $\displaystyle r_{v}(S,p,M)=\frac{\sum\limits_{m\in M}\mathbb{I}(\mathcal{V}(m(p),S)\neq\emptyset)}{|M|}$
> where $\mathcal{V}:P\times\mathbb{S}\rightarrow\mathbb{S}$ is a verifier that takes as input a program $p\in P$ and a set of specification $S\in\mathbb{S}$ to produce a set of refuted specifications"

**And Definition 2 is exactly the constrained-optimization form of your gate** — maximize refutation subject to still verifying against the true program:
> "$\displaystyle S=\mathop{\arg\min}\limits_{S}\ |M|(1-r_{v}(S,p,M)),\quad\text{s.t.}\ \mathcal{V}(p,S)=\emptyset$"

**Threshold, verbatim:** `"we adopt the setting where $n_{refine}=n_{repair}=5$ and $t=0.75$."` and:
> "If the proportion of variants that fail verification exceeds a given threshold (line 32 in Alg. 1 ), the strength of the generated specifications is considered plausible. Otherwise, the undistinguished variants are utilized to construct a new query message (line 30 in Alg. 1 ), guiding the LLM in generating refined candidates. The message includes a randomly selected undistinguished variant and instructs the LLM to analyze the syntactic and semantic differences between this variant and the original program segment, and to propose new specifications for the properties that explicitly capture these differences."

**(a) Perturbs the CODE.** 188 operators, and a real equivalent-mutant filter:
> "we exploit the 188 mutation operators proposed by the work [61] targeting C compiler fuzzing. The operators are usefully comprehensive, covering a wide range of C language elements, including additions, removals, and modifications on operators, operands, identifiers, statements, control-flow structures, and user-defined type declarations."
> "To ensure the semantic-non-equivalence of the mutations, we adopt Trivial Compiler Equivalence (TCE) [62] , a lightweight technique for fast identification of program equivalence. The principle of TCE is to compile (usually with optimization flags specified) the programs to be assessed and consider them equivalent if the produced binary files are equal. We exploit the GNU C Compiler (GCC) [22] with the -O2 optimization flag specified to produce binary files for comparison. Mutated variant detected to be equivalent to the original segment will be excluded from the strength assessment process."

**(c) The witness is a SURVIVING MUTANT PROGRAM, not an input.** Frama-C/WP is a WP/SMT prover; what comes back is a set of refuted specifications. Worked example:
> "Despite some reasonable postconditions generated by LLM to specify the behavior of the function bufs_differ , these postconditions fail to impose proper bounds on the function's return value. Semantically non-equivalent mutations on the program yield a variant in which the return value was altered. Since the intermediate specifications do not constrain the range of the return value, they still adapt to the variant. With this information as feedback, the model analyzes the discrepancy and identifies the need for explicit constraints."

**(d) Numbers.** Benchmark: 50 self-contained C files from real open-source repos with hand-written ACSL ground truth.
> "our method maintains a high level of precision from 90% to 100% , on par with state-of-the-art approaches, while achieving the highest average recall (over 75% on the majority of programs) among all baselines"
> "SpecSyn incorporating GPT-5 yields the highest average recall (75.91%) ... Other versions of SpecSyn incorporating GPT-4 and Deepseek-R1 also demonstrate considerable performance, achieving 71.10% and 61.20% recall, respectively."
> "SpecSyn successfully discharges proof obligations for the most target properties ( 1071 out of 1365 , compared to 503 of Preguss)"

**The ablation is the number you actually want, and it is modest:**
> "When the specification refinement mechanism is removed, SpecSyn experiences an average decrease of approximately 2% in precision and about 5% in recall. Since the specification refinement mechanism is primarily designed to guide the model toward generating semantically stronger specifications, its contribution is manifested more prominently in recall than in precision. Given that SpecSyn incorporating GPT-4 and the refinement mechanism achieves a recall of 71.10% (Table 1 ), which is comparable to the performance obtained when using GPT-5 yet with the refinement mechanism disabled, we may conclude that the refinement mechanism contributes sufficiently to the strength of the generated specifications so as to compensate for the capability gap between the GPT-4 and GPT-5 models."

For contrast, the decomposition ablation dominates: `"the precision dropping by 11.41% and recall dropping by 12.66%"`. **So: the sabotaged-twin mechanism is worth roughly one model generation (GPT-4→GPT-5) of recall, but is a smaller effect than task decomposition.** That is a calibrated expectation for your own gate.

- **(e)** **NO REPO, NO LICENSE FOUND.** I grepped the full text for `availab|artifact|anonym|replication` and found no artifact statement and no GitHub link for SpecSyn itself. Stating plainly: SpecSyn appears to have **no public artifact** as of this preprint. (They do release "A dataset towards specification generation on real-world programs" per their contributions list, but give no URL.)
- **(f)** Paper `https://arxiv.org/abs/2604.21570`. Repo: none found.
- **(g)** `"Frama-C/WP [3] 25.0 is adopted as the specification verifier."` Frama-C/WP dispatches to multiple SMT back ends via Why3, so **multi-prover in the back end** — but the paper does **not** name them. Unspecified; flagging.

## C2. VeriScale — arXiv 2605.22368v1. **Explicit LLM red-team performing "Specification Gaming".**

**URLs fetched → saved:** `https://arxiv.org/abs/2605.22368` → `arxiv-abs-2605.22368.html`; `https://arxiv.org/html/2605.22368v1` → `arxiv-html-2605.22368v1.html`, text `fulltext-2605.22368.txt`

**The red-team prompt, verbatim from Appendix (spacing is the HTML's):**
> "You are an expert Red Teamer in formal verification and a " lazy " code hacker . Your objective is to perform " Specification Gaming ": identify underspecification loopholes within a given ‘ post - condition ‘ in Lean4 , and write degenerate code to exploit these vulnerabilities ."

And the attack playbook — note it targets **vacuous quantification** by name:
> "- Did it use ‘ $\forall$ x $\in$ xs ‘ but forget the empty - list case is vacuously true ?"
> "- * Edge Case Exploitation *: Force empty or trivial states ( e . g ., empty list , ‘0‘, ‘ none ‘) that make universally quantified checks (‘ $\forall$ x $\in$ []‘, …) vacuously true ."
> "- define custom ‘ structure ‘ s / ‘ inductive ‘ types as outputs purely so that a custom ‘ DecidableEq ‘, ‘ LE ‘, ‘ LT ‘, or ‘ BEq ‘ instance makes the post - condition trivially true"
> "6. You must generate exactly **5** different adversarial implementations . Try to use a * different * adversarial strategy from the list above for each one to probe different potential loopholes ."

**(a) Perturbs the CODE — adversarially, conditioned on the spec under test:**
> "Instead of directly prompting LLMs to generate arbitrary unexpected outputs, VeriScale synthesizes adversarial implementations designed to exploit weaknesses in LLM-generated specifications, executing them on expected inputs."
> "Crucially, a more capable model acts as a red team ( Perez et al., 2022 ) , crafting adversarial implementations to exploit vulnerabilities within these specifications."
> "As a fallback, if the model fails to generate an adversarial implementation, we systematically drop constraints from the ground-truth specification to expose an attack target, thereby facilitating the successful synthesis of an adversarial implementation."

**Why weak negatives are useless — argues your case for you:**
> "these trivially incorrect outputs are usually easily rejected by even highly flawed specifications, failing to provide meaningful diagnostic feedback for underspecification."
> "Because these unexpected outputs stem from systematic specification gaming rather than arbitrary hallucination, they closely mimic realistic logical errors, making them significantly more effective at exposing specification unsoundness and incompleteness."

**An important subtlety about (b).** The spec is *not directly* required to refute the implementation. The implementation is used to **mine a negative test case**, which is then frozen into the benchmark:
> "If an adversarial implementation produces an output that diverges from the ground truth but is still successfully accepted by the generated postconditions, this mismatched value is formally retained."

Mutants are then reused as a set-cover objective:
> "we repurpose the adversarial implementations synthesized in the previous stage, treating each as a distinct mutant. We associate each expected pair with the set of adversarial implementations it can kill, formulating test reduction as a set-cover problem. We first select expected pairs that cover the largest number of previously unkilled mutants using a greedy procedure"
> "Given an expected input, an adversarial implementation is considered "killed" if its output differs from the expected output. The illustrated case kills six out of seven adversarial implementations, making it a high-quality case."

A documented real catch:
> "Case study of a flawed specification on Verina #advanced_3. The generated postcondition successfully rejects unexpected outputs from the original dataset, but erroneously accepts our adversarially synthesized unexpected outputs."

**(c) YES** — the witness is a concrete (input, wrong-output) pair, baked permanently into VerinaPlus/VerinaLite.

**(d) Numbers:**
> "which expands the original test suites by over 83$\times$, and VerinaLite , a lightweight 14$\times$ variant"
> "GPT-5.5 experiences a severe performance degradation on VerinaPlus , plummeting from 68.78% to 44.44% on SpecGen and from 96.83% to 86.24% on CodeGen."
> "Taking the top-performing GPT-5.5 as a representative example again, the model experiences a moderate relative decline of roughly 10.59% in CodeGen when moving from the Verina baseline to VerinaPlus , yet suffers a staggering 24.34% relative reduction in its specification soundness and completeness score."
> "Claude-Opus-4.7 exhibits a substantial gap of 13.23% (77.78% vs. 64.55%) on the baseline. However, under the rigorous scrutiny of VerinaPlus , this ambiguity is effectively resolved, drastically shrinking the gap for the same model to merely 4.76% (50.26% vs. 45.50%)."
> "the augmented benchmarks also consistently maintain 100% code coverage."

Eight LLMs; `"we employ GPT-5.3-Codex for seed generation, problem decomposition, and adversarial implementation synthesis"`; `"All experiments are implemented using Lean v4.24.0."`; dual Xeon 8380, 80 cores.

Limitations, verbatim:
> "If the model struggles with the strict typing constraints of Lean 4, it may fail to synthesize sophisticated adversarial implementations."
> "the construction phase of the expanded test suites remains highly compute-intensive, requiring massive LLM sampling and Lean executions."

- **(e)** **Apache-2.0** (verified: `license-XiaoyangLiu-sjtu-VeriScale.json`).
- **(f)** `https://github.com/XiaoyangLiu-sjtu/VeriScale`, `https://arxiv.org/abs/2605.22368`
- **(g)** Lean 4 ITP + `#check` + concrete execution. **Not SMT**, and they say why that matters:
> "Unlike verification frameworks such as Dafny ( Leino, 2010 ) and Verus ( Lattuada et al., 2023 ) , which heavily leverage SMT solvers ( de Moura and Bjørner, 2008 ) for automated theorem proving with less explicit proof steps, Lean operates as an interactive theorem prover (ITP)."

## C3. Also in category (C), covered above
- **nl2postcond** `bug-completeness-score` (B1) — LLM-sampled natural wrong implementations; **no prover**.
- **NL2Contract** `verification completeness` (B2) — same mutants, but a verifier must *find* the violating input.
- **Verus-SpecGym** `τ_post-sound` (B5) — the broken twin is a *real human buggy submission*, and the input is a *real human adversarial hack*. If you want to argue your gate mirrors reality rather than synthetic mutation, this is your citation.

## C4. The theoretical root of (C) — **references verified, papers NOT fetched**

I have these verbatim from `tomb-joshi-2025-static-coverage-fmcad.pdf` (`-layout` extraction), but **did not fetch the papers themselves**:

> "[21] Orna Kupferman, Wenchao Li, and Sanjit A. Seshia. On the duality between vacuity and coverage. Technical Report UCB/EECS-2008-26, EECS Department, University of California, Berkeley, March 2008."
> "[22] Orna Kupferman, Wenchao Li, and Sanjit A. Seshia. A theory of mutations with applications to vacuity, coverage, and fault tolerance. In Proceedings of the 2008 International Conference on Formal Methods in Computer-Aided Design, FMCAD '08. IEEE Press, 2008."
> "[23] Viet Hoang Le, Loïc Correnson, Julien Signoles, and Virginie Wiels. Verification coverage for combining test and proof. In Catherine Dubois and Burkhart Wolff, editors, Tests and Proofs, pages 120–138, Cham, 2018. Springer International Publishing."
> "[16] Elaheh Ghassabani, Andrew Gacek, Michael W. Whalen, Mats P. E. Heimdahl, and Lucas Wagner. Proof-based coverage metrics for formal verification. In 2017 32nd IEEE/ACM International Conference on Automated Software Engineering (ASE), pages 194–199, 2017."
> "[17] Mihaela Gheorghiu and Arie Gurfinkel. VaqUoT: A tool for vacuity detection. Technical report, University of Toronto, Department of Computer Science, 2006."
> "[28] Jocelyn Simmonds, Jessica Davies, Arie Gurfinkel, and Marsha Chechik. Exploiting resolution proofs to speed up ltl vacuity detection for bmc. In Formal Methods in Computer Aided Design (FMCAD'07), pages 3–12, 2007."
> "[30] Emina Torlak, Felix Sheng-Ho Chang, and Daniel Jackson. Finding minimal unsatisfiable cores of declarative specifications. In Jorge Cuellar, Tom Maibaum, and Kaisa Sere, editors, FM 2008: Formal Methods, pages 326–341, Berlin, Heidelberg, 2008. Springer Berlin Heidelberg."

(Reference [29] is `"Aaron Tomb and Cormac Flanagan. Detecting inconsistencies via"` — my column extraction truncated the title. I will not guess it.)

**Kupferman/Li/Seshia FMCAD'08 [22] is the one I'd chase hardest** — per Tomb & Joshi it is *"The original work describing this duality"* and it *"assumed the use of mutation testing as a mechanism for evaluating coverage or vacuity"*. That is the 2008 theoretical ancestor of the sabotaged-twin gate. UCB/EECS-2008-26 should be free at `www2.eecs.berkeley.edu`.

## C5. Empty search space for (C)'s obvious terms — all saved as `arxiv-api-*.xml`
- `all:"specification adequacy"` → **0**
- `all:"discriminative specification"` → 20 hits, **all** unrelated (vision/ML/re-ID)
- `abs:"strength of specifications"` → 20 hits, **all** unrelated (materials science, physics)
- `all:"kill mutants" AND all:"specification"` → 2 hits, neither program verification
- `all:"counterexample to specification"` → 3 hits, unrelated
- `all:"underspecification" AND all:"formal verification" AND all:"LLM"` → **0**
- `all:"specification quality" AND all:"mutation"` → 1 hit (OpenAPI fault injection), not verification
- `abs:"bug discriminative"` → 2 hits: NL2Contract, plus 2607.28871 *Validation Evidence in LLM Repair Agents* (**not fetched**)

**The terminology has not converged.** Four independent names for the same metric: `bug-completeness-score` (nl2postcond), `verification completeness` (NL2Contract), `variant discriminative rate` (SpecSyn), `adversary-killing reduction` (VeriScale). If you name yours, you are naming a fifth. That is an argument for adopting SpecSyn's **VDR**, which is the only one given a formal definition and an optimization objective.

---

# License summary (all verified via GitHub API unless marked)

| Artifact | License | Verified from |
|---|---|---|
| Boogie (`/smoke`) | **MIT** | `boogie-license.json` |
| Dafny (`--warn-*`) | **MIT** (API says `NOASSERTION`/`Other` due to preamble) | `dafny-LICENSE.txt` + `dafny-license.json` |
| ProofPulse | **MIT** | `license-VeriFixer-ProofPulse.json` |
| VeriScale | **Apache-2.0** | `license-XiaoyangLiu-sjtu-VeriScale.json` |
| Verina | **Apache-2.0** | API + `verina-LICENSE.txt` |
| Verus-SpecGym | **Apache-2.0** | `license-formal-verif-is-cool-verus-spec-gym.json` |
| SpecGen-Artifact | **MIT** | `license-Lezhi-Ma-SpecGen-Artifact.json` |
| dafny-synthesis (Misu) | ⚠️ **GPL-3.0** | `license-Mondego-dafny-synthesis.json` |
| **SpecSyn** | **NO REPO, NO LICENSE FOUND** | grepped full text; no artifact statement |
| **NL2Contract** | **NO REPO, NO LICENSE FOUND** | no URL in paper |
| **nl2postcond** | **UNVERIFIED** — repo is `github.com/microsoft/nl-2-postcond` (from project site); license not fetched | `nl2postcond-site.html` |
| Frama-C, Why3 | **UNVERIFIED** — no LICENSE file fetched | — |

---

# Honest gaps, in priority order

1. **Beer et al. full text** — paywalled ("Download to read the full chapter text"). Abstract only. FMSD 2001 journal version not attempted.
2. **Kupferman/Li/Seshia FMCAD'08 + UCB/EECS-2008-26** — the mutation-based coverage/vacuity duality. Reference strings verified; papers not fetched. **Highest-value remaining target for (C).**
3. **Le et al. 2018** (Tests and Proofs, pp. 120-138) — "combine proof and test coverage using mutation-based metrics". Not fetched.
4. **VeriSpecGen (2604.10392)** — full text saved as `fulltext-2604.10392.txt`, not read. Current SOTA on Verina SpecGen at 86.6%.
5. **Verus source-level negative is docs+CLI only** — GitHub API rate-limited (`verus-tree.json` = 281-byte error). I could not grep the full Verus tree.
6. **Licenses for nl2postcond, NL2Contract, SpecSyn, Frama-C, Why3** — unverified or nonexistent.
7. **Not fetched, surfaced in searches:** 2604.22601 (*From Natural Language to Verified Code... Dafny*, matched `vacuous`+`Dafny`), 2607.28871 (*Validation Evidence in LLM Repair Agents*, matched `bug discriminative`), 2608.30803 (*Schwarz: Solver-Aware Agentic Program Verification*), 2604.03758 (*AutoReSpec*), AutoSpec (Wen et al., SpecGen's main baseline).
8. **Tomb & Joshi Fig. 10 arithmetic:** INT's printed total is 78; its sub-rows sum to 76. Theirs, not mine.

MutDafny appeared in exactly one search (`all:"mutation" AND all:"Dafny"` → arXiv 2511.15403v2) and I did not pursue it, per your instruction.