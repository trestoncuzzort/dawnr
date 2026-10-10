# T78: extend the runnable kernel coverage

Registered before installing the remaining release archives or running their
proof controls. T75/T76 exercised Dafny and Lean; T77 added the pinned SPARK
release. Verus, F*, Rocq and Frama-C were absent, so previous collected tests
and partial matrices do not establish their current behavior on this host.

Use the versions recorded in `t/RUN-ON-LINUX.md` where available. Fetch release
metadata from the publishers, check archive digests, install below the user
tool directory and retain a small provenance receipt. Do not change system
security policy or overwrite a working toolchain. Rust, if required by Verus,
gets the release's recorded toolchain with the minimal profile.

Bars: each installed adapter identifies its real tool; `abs`, `gcd` and
`reverse` each produce verified/refuted with three agreeing runs per side in
that adapter. A missing dependency or a proof timeout is recorded as such.
After installation controls, run the committed corpus from a clean checkout
and compare with the recorded matrix. Named abstentions and measured solver
limits remain limitations; they are not converted to successful cells. Only
a complete clean seven-kernel matrix could replace `t/AGREEMENT.md`.

Prior work: the repository's Linux installation record, `verifiers/discover.py`,
adapter version and budget definitions, and publisher release metadata at
https://github.com/verus-lang/verus/releases,
https://github.com/FStarLang/FStar/releases and
https://github.com/alire-project/GNAT-FSF-builds/releases.

GNATprove FSF 16.1.0, Verus 0.2026.08.30.b432e82 and F* 2026.08.30 were
installed from checksum-verified publisher archives. Verus uses Rust 1.97.1;
the new Rust installation did not modify shell startup files. Alongside the
existing Dafny/Lean installations, all five kernels passed the three-task smoke
matrix from clean engine checkout `21528a1`: 15 verified/refuted cells, three
agreeing runs per side. The table and archive identities are under
`t/evidence/2026-10-10-kernel-install/`.

Opam 2.5.2 was installed from its checksum-verified release binary and built
OCaml 4.14.4 locally. Rocq 9.2.0, its pinned standard library, Frama-C 33.0 and
Alt-Ergo-free 2.4.3 are being installed. The five-kernel committed-corpus run is
also in progress from clean checkout `edc1027`; neither pending activity is
counted as completed evidence.

The first opam transaction built Rocq, its standard library, Frama-C and
Alt-Ergo-free, but exited nonzero because `dot` was missing for conf-graphviz.
Graphviz 16.1.0 was built from its checksum-verified official source archive;
`dot -V`, an actual SVG render and the opam dependency check then passed.

Rocq passed all three smoke tasks. Frama-C passed abs/gcd but returned
TOOL_ERROR on reverse. Its emitted polymorphic SMT-LIB query failed to parse in
Alt-Ergo-free 2.4.3, and Why3 1.8.2 reports that version as unrecognized. This is
not recorded as a refutation or a successful installation control. Next use
Alt-Ergo 2.6.1, a version recognized by this Why3 and already used by the pinned
SPARK distribution, and repeat all three Frama-C controls. No specification,
lowering or verification budget is changed for this dependency repair.
