# 8.54. Wheel-0.46.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/wheel.html
# TUP_TARBALL=wheel-0.46.1.tar.gz

pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD

pip3 install --no-index --find-links dist wheel
