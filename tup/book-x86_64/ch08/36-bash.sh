# 8.36. Bash-5.3
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/bash.html
# TUP_TARBALL=bash-5.3.tar.gz

./configure --prefix=/usr             \
            --without-bash-malloc     \
            --with-installed-readline \
            --docdir=/usr/share/doc/bash-5.3

make

chown -R tester .

LC_ALL=C.UTF-8 su -s /usr/bin/expect tester << "EOF"
set timeout -1
spawn make tests
expect eof
lassign [wait] _ _ _ value
exit $value
EOF

make install

exec /usr/bin/bash --login
