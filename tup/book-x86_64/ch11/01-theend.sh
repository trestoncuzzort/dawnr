# 11.1. The End
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter11/theend.html
# TUP_ACTION_PAGE

echo 12.4 > /etc/lfs-release

cat > /etc/lsb-release << "EOF"
DISTRIB_ID="Linux From Scratch"
DISTRIB_RELEASE="12.4"
DISTRIB_CODENAME="<your name here>"
DISTRIB_DESCRIPTION="Linux From Scratch"
EOF

cat > /etc/os-release << "EOF"
NAME="Linux From Scratch"
VERSION="12.4"
ID=lfs
PRETTY_NAME="Linux From Scratch 12.4"
VERSION_CODENAME="<your name here>"
HOME_URL="https://www.linuxfromscratch.org/lfs/"
RELEASE_TYPE="stable"
EOF
