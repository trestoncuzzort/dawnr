# prove 4: dune 3.21.0, Rocq's build system, bootstrapped by ocaml itself.
# 3.21 and not 3.16: rocq-stdlib's dune-project declares (lang dune 3.21),
# and dune refuses forward. rocq-core is content with either.
# TUP_TARBALL=dune-3.21.0.tar.gz
make release
make install PREFIX=/usr
dune --version
