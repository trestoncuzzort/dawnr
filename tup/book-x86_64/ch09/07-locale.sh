# 9.7. Configuring the System Locale
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter09/locale.html
# TUP_ACTION_PAGE

locale -a

LC_ALL=<locale name> locale charmap

LC_ALL=<locale name> locale language
LC_ALL=<locale name> locale charmap
LC_ALL=<locale name> locale int_curr_symbol
LC_ALL=<locale name> locale int_prefix

cat > /etc/profile << "EOF"
# Begin /etc/profile

for i in $(locale); do
  unset ${i%=*}
done

if [[ "$TERM" = linux ]]; then
  export LANG=C.UTF-8
else
  export LANG=<ll>_<CC>.<charmap><@modifiers>
fi

# End /etc/profile
EOF
