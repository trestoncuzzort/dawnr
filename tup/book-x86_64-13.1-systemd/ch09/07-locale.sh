#!/bin/bash
# 9.7. Configuring the System Locale
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/locale.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment,replaceable-parameter
printf '%s\n' 'ch09/07-locale.sh: named override required: native-policy-review, book-alternatives-or-judgment, replaceable-parameter' >&2
exit 97
: <<'TUP_UNSELECTED_db69672e3ccc41dbf157e24ed0f796dd31cdfc3bfa92cd60c9488e3ba766cf0c'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
locale -a
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
LC_ALL=<locale name> locale charmap
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
LC_ALL=<locale name> locale language
LC_ALL=<locale name> locale charmap
LC_ALL=<locale name> locale int_curr_symbol
LC_ALL=<locale name> locale int_prefix
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
cat > /etc/locale.conf << "EOF"
LANG=<ll>_<CC>.<charmap><@modifiers>
EOF
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
cat > /etc/profile << "EOF"
# Begin /etc/profile

for i in $(locale); do
  unset ${i%=*}
done

if [[ "$TERM" = linux ]]; then
  export LANG=C.UTF-8
else
  source /etc/locale.conf

  for i in $(locale); do
    key=${i%=*}
    if [[ -v $key ]]; then
      export $key
    fi
  done
fi

# End /etc/profile
EOF
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
localectl set-locale LANG="<ll>_<CC>.<charmap><@modifiers>"
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
localectl set-locale LANG="en_US.UTF-8" LC_CTYPE="en_US"
# TUP_BLOCK_END=007
TUP_UNSELECTED_db69672e3ccc41dbf157e24ed0f796dd31cdfc3bfa92cd60c9488e3ba766cf0c
