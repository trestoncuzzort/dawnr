# 8.74. MarkupSafe-3.0.2
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/markupsafe.html
# TUP_TARBALL=markupsafe-3.0.2.tar.gz

pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD

pip3 install --no-index --find-links dist Markupsafe
