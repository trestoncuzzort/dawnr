# Reviewed required-suite exceptions

The required-suite gate stops a build on any result that is not a pass. A file
`<package>.allow` here is the only way a named non-pass result can be accepted,
and only for the three suites whose harness writes every non-pass result as
its own named line: `glibc` (`tests.sum`), `binutils` and `gcc` (DejaGnu
`.sum`). Automake `.trs`, Autotest, Tcl and JUnit suites cannot use a list;
their known failures need a fix or an explicit, recorded deselection in the
audited recipe instead.

## What a list is

- Lines starting with `#` are the review record. A list must say, per group of
  entries, **`# Basis:`** why the result is expected for this exact package
  version in this build environment (the LFS book's statement for this
  version, an upstream bug, or a traced cause), and **`# Observed:`** in which
  real run the exact lines were seen. A failure that was never observed in a
  real run of this profile is not listed.
- Exactly one **`@min-pass N`** line sets the smallest acceptable number of
  passes for the whole suite. It is taken from the observed run, so an
  exception cannot excuse a suite that largely did not run.
- Every other non-empty line is one complete result line, byte for byte as the
  harness writes it, for example `FAIL: io/tst-lchmod`. There are no patterns,
  wildcards or counts.

## What the judge does with it

[`required-suite.sh`](../required-suite.sh) accepts a suite with non-pass
results only if every such line is in the list, the DejaGnu totals
(`# of unexpected failures` and the like) equal the number of named lines, the
pass floor is met, and each required component summary still reports passes.
A listed result that does not occur is fine: several documented failures are
intermittent or depend on the processor. Anything unlisted refuses with the
unexplained lines retained in the suite's evidence directory.

A non-zero exit status of the suite command is accepted only when at least one
reviewed exception was observed and nothing is unexplained. The receipt then
records the command's real status, the number of exceptions and the digest of
the list; [`build.py`](../../../build.py) refuses a receipt whose digest or
count differs from the list staged with that build.

## Changing a list

A list is a build input: changing it changes the build identity, so a completed
build cannot be re-judged with a different list. Review new results against
the retained evidence of the run that produced them, add the basis, and start
a fresh build. Remove entries when a package update makes them pass. Never add
an entry to make a build finish; an unexplained failure is a finding.
