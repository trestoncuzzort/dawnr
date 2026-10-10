# T81: reproduce flight verification on a fresh Linux account

Registered before deploying the engine or its proof tools to a fresh Ubuntu
24.04 account. Existing project targets are the PX4 source correspondence,
machine-width proofs, and repeatable use from a clean checkout. The next
measurement uses those existing suites, without introducing a demonstration
application or substituting synthetic results for flight-code evidence.

Install under the account's own tool directories from the pinned archives in
the repository's installation record. Check archive digests before extraction.
Use the documented Why3 driver for Alt-Ergo-free 2.4.3. Keep toolchain changes
separate from source changes. GPU and system-container access are unavailable
to this account; neither is needed by the proof kernels.

Bars: all seven adapters identify the installed versions; abs, gcd and reverse
produce verified/refuted with three agreeing runs per side. Then run the full
committed corpus and the existing flight suites from the same clean revision,
retaining separate tables and producer identities. Run the compiled PX4
correspondence checks at their recorded source revisions. A named abstention,
timeout, tool error or disagreement remains a finding, never a successful cell.

The host is shared. Start with five cells in flight (up to thirty kernel calls)
and one SPARK job per call, the regime already measured in run_par.py. Parallel
tool builds may use sixteen compiler jobs when the host is idle. Limit memory,
retain logs and make all jobs attributable to this account so they can stop
without disturbing other users. Increased concurrency needs measured stable
verdicts rather than an inference from the processor count.

Prior work: AGENTS.md, NORTH-STAR.md, Dockerfile, t/RUN-ON-LINUX.md,
t/flight/README.md, t/flight/px4_diff.py, t/flight/px4_stmt.py, run_par.py's
contention findings, and the official installation instructions at
https://opam.ocaml.org/doc/Install.html.

Results pending.
