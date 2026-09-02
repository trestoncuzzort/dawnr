# 8.85. Cleaning Up
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/cleanup.html
# TUP_ACTION_PAGE

rm -rf /tmp/{*,.*}

find /usr/lib /usr/libexec -name \*.la -delete

find /usr -depth -name $(uname -m)-lfs-linux-gnu\* | xargs rm -rf

userdel -r tester
