# 8.55. Setuptools-80.9.0
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/setuptools.html
# TUP_TARBALL=setuptools-80.9.0.tar.gz

pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD

pip3 install --no-index --find-links dist setuptools
