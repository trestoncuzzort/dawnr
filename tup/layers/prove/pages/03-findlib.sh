# prove 3: findlib 1.9.6, ocamlfind, which zarith's build requires.
# TUP_TARBALL=findlib-1.9.6.tar.gz
./configure
make all
make opt
make install
ocamlfind printconf destdir
