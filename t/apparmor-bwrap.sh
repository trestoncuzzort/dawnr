#!/bin/bash
# Lets bubblewrap create its namespaces on Ubuntu 23.10 and later, which restrict unprivileged user namespaces with
# AppArmor and grant them per program through a profile with `userns,`
# (ubuntu.com/blog/ubuntu-23-10-restricted-unprivileged-user-namespaces). dawnr runs model-written Python only inside
# bubblewrap (t/py_sandbox.py). Run once, as root: sudo bash t/apparmor-bwrap.sh
# Ubuntu's own bwrap profile is used where the apparmor package ships it (enabled by default from 26.04); otherwise
# a profile that adds `userns,` for /usr/bin/bwrap alone, in the form of Ubuntu's example.
set -eu
[ "$(id -u)" = 0 ] || { echo "run as root: sudo bash $0" >&2; exit 1; }
if [ -e /etc/apparmor.d/bwrap-userns-restrict ]; then
  echo "Ubuntu's bwrap profile is already in /etc/apparmor.d"
elif [ -e /usr/share/apparmor/extra-profiles/bwrap-userns-restrict ]; then
  cp /usr/share/apparmor/extra-profiles/bwrap-userns-restrict /etc/apparmor.d/
  apparmor_parser -r /etc/apparmor.d/bwrap-userns-restrict
  echo "enabled Ubuntu's bwrap profile (bwrap-userns-restrict)"
else
  cat > /etc/apparmor.d/bwrap <<'PROFILE'
abi <abi/4.0>,
include <tunables/global>

profile bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
  include if exists <local/bwrap>
}
PROFILE
  apparmor_parser -r /etc/apparmor.d/bwrap
  echo "added /etc/apparmor.d/bwrap (userns for /usr/bin/bwrap)"
fi
