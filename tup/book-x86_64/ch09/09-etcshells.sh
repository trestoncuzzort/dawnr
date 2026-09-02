# 9.9. Creating the /etc/shells File
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter09/etcshells.html
# TUP_ACTION_PAGE

cat > /etc/shells << "EOF"
# Begin /etc/shells

/bin/sh
/bin/bash

# End /etc/shells
EOF
