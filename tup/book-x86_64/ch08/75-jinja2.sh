# 8.75. Jinja2-3.1.6
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/jinja2.html
# TUP_TARBALL=jinja2-3.1.6.tar.gz

pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD

pip3 install --no-index --find-links dist Jinja2
