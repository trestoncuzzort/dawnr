# 8.53. Packaging-25.0
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/packaging.html
# TUP_TARBALL=packaging-25.0.tar.gz

pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD

pip3 install --no-index --find-links dist packaging
