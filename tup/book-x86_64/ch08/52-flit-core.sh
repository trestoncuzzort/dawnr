# 8.52. Flit-Core-3.12.0
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/flit-core.html
# TUP_TARBALL=flit_core-3.12.0.tar.gz

pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD

pip3 install --no-index --find-links dist flit_core
