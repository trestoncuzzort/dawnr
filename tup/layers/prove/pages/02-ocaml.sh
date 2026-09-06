# prove 2: OCaml 4.14.2 from source, the compiler Rocq is built with.
# TUP_TARBALL=ocaml-4.14.2.tar.gz
./configure --prefix=/usr --disable-ocamldoc
make -j$(nproc) world.opt
make install
ocaml -version
