# 7.2. Changing Ownership
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter07/changingowner.html
# TUP_ACTION_PAGE

chown --from lfs -R root:root $LFS/{usr,var,etc,tools}
case $(uname -m) in
  x86_64) chown --from lfs -R root:root $LFS/lib64 ;;
esac
