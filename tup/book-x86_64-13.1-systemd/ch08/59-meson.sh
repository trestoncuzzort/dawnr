#!/bin/bash
# 8.59. Meson-1.12.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/meson.html
# TUP_TARBALL=meson-1.12.0.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/59-meson.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_104edb43428842e05da03e86a5bef69c130309399354e3de06fbc058bb73eef6'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
pip3 install --no-index --find-links dist meson
install -vDm644 data/shell-completions/bash/meson /usr/share/bash-completion/completions/meson
install -vDm644 data/shell-completions/zsh/_meson /usr/share/zsh/site-functions/_meson
# TUP_BLOCK_END=002
TUP_UNSELECTED_104edb43428842e05da03e86a5bef69c130309399354e3de06fbc058bb73eef6
