#!/bin/bash
# Run inside the selected Python source tree before configure. No Python needed.
set -euo pipefail
profile=/tup-build/native/profiles/lfs-13.1-systemd
printf '%s\n' \
  '527e714523264093910a0a0b1a55c6583f952835c89061537fc40ad98c347056  Lib/poplib.py' \
  '584cf309bc2048fed5909a6fe5ea96582a0da41cbddd285feea422c700bf0d7d  Python/fileutils.c' | sha256sum --check --strict
patch --batch --forward --fuzz=0 -Np1 -i "$profile/python-3.14.10-security-backports.patch"
printf '%s\n' \
  'a6ffff188814b56d95b043c31d9e0dfee51ac6d6e92afe74ab070cb6136b076f  Lib/poplib.py' \
  '219f7bb3883bbdecccdbe611b112ff34e241eae46f496fa2a2606d0884b727d2  Python/fileutils.c' | sha256sum --check --strict
