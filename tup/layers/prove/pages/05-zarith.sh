# prove 5: zarith 1.13, arbitrary-precision integers over tup's own gmp.
# TUP_TARBALL=zarith-1.13.tar.gz
./configure
make -j$(nproc)
make install
