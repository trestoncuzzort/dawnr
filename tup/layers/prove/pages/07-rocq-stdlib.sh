# prove 7: the Rocq STANDARD LIBRARY, a separate package since Rocq 9.
# Found the honest way: rocq-core built and installed clean, and then
# `Require Import ZArith` failed inside tup and the max task came back
# MALFORMED. The kernel without its stdlib can check proofs but cannot talk
# about arithmetic the way t's lowering speaks it (ZArith, lia).
# TUP_TARBALL=rocq-stdlib-9.2.0.tar.gz
# The rocq binary locates its own OCaml packages (rocq-runtime, the lia
# plugin) through findlib AT RUNTIME, and dune installed their METAs under
# /usr/lib/<pkg>/, a directory findlib does not search. The stdlib build
# died on Fl_package_base.No_such_package("rocq-runtime") to prove it.
# Fix findlib's own config, not this page's env: every later consumer of
# the kernel (page 08's coqc included) needs the same resolution.
FLCONF=$(ocamlfind printconf conf)
grep -q '"/usr/lib"' "$FLCONF" ||   sed -i 's|^path="|path="/usr/lib:|' "$FLCONF"
ocamlfind list | grep -q "^rocq-runtime" || { echo "findlib still blind to rocq-runtime"; exit 1; }
export OCAMLPATH=$(ocamlfind printconf destdir)
dune build -p rocq-stdlib -j $(nproc)
dune install -p rocq-stdlib --prefix /usr
# the probe that failed before this page existed, now a gate:
printf 'Require Import ZArith Lia.\nOpen Scope Z_scope.\nGoal forall a b : Z, a <= b -> a <= b + 1. intros. lia. Qed.\n' > /tmp/stdlib_probe.v
coqc /tmp/stdlib_probe.v
rm -f /tmp/stdlib_probe.* 
echo "stdlib probe: ZArith + lia discharge a goal"
