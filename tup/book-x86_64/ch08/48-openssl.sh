# 8.48. OpenSSL-3.5.2
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/openssl.html
# TUP_TARBALL=openssl-3.5.2.tar.gz

./config --prefix=/usr         \
         --openssldir=/etc/ssl \
         --libdir=lib          \
         shared                \
         zlib-dynamic

make

if tup_tests_enabled "openssl"; then
HARNESS_JOBS=$(nproc) make test
else tup_receipt_skip_tests "openssl"; fi

sed -i '/INSTALL_LIBS/s/libcrypto.a libssl.a//' Makefile
make MANSUFFIX=ssl install

mv -v /usr/share/doc/openssl /usr/share/doc/openssl-3.5.2

cp -vfr doc/* /usr/share/doc/openssl-3.5.2
