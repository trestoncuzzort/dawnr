# 8.57. Meson-1.8.3
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/meson.html
# TUP_TARBALL=meson-1.8.3.tar.gz

pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD

pip3 install --no-index --find-links dist meson
install -vDm644 data/shell-completions/bash/meson /usr/share/bash-completion/completions/meson
install -vDm644 data/shell-completions/zsh/_meson /usr/share/zsh/site-functions/_meson
