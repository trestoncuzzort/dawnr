#!/bin/bash
# chain56.sh: chapters 5 and 6 as the lfs user, the way the book has it:
# a shell with nothing in its environment but what 4.4's .bashrc sets.
#
# `su - lfs` is not usable unattended: the book's .bash_profile execs a
# fresh bash, which discards any -c command. runuser plus env -i plus an
# explicit source of .bashrc reaches the same environment (measured: the
# variables the book lists, nothing else, hashing off) without the exec.
# Runs as root; writes CHAIN56 COMPLETE, which chain7.sh waits for.
set -u
export LFS=/mnt/lfs
LOG=$LFS/sources/log
run_ch() {
  runuser -u lfs -- env -i HOME=/home/lfs TERM="${TERM:-xterm}" TUP_ARCH="${TUP_ARCH:-}" /bin/bash -c \
    '. /home/lfs/.bashrc && exec /bin/bash /home/lfs/driver.sh /home/lfs/book/'"$1"
}
run_ch ch05 && run_ch ch06 \
  && echo "CHAIN56 COMPLETE" || echo "CHAIN56 FAILED"
