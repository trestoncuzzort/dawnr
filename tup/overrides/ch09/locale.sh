#!/bin/bash
# OVERRIDE ch09/locale: the page's first blocks are INTERACTIVE PROBES
# (`locale -a`, `LC_ALL=<locale name> locale charmap`) for a human choosing a
# locale; the placeholder form fails. tup's choice is made here instead:
# en_US.UTF-8, the locale glibc was built with support for.
set -e
cat > /etc/profile << "PROFEOF"
# Begin /etc/profile

for i in $(locale); do
  unset ${i%=*}
done

export LANG=en_US.UTF-8

# End /etc/profile
PROFEOF
