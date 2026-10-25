#!/usr/bin/env bash
# The old desktop-to-laptop release driver is retired by the release plan's execution policy.
# Export with v6_export.py on the approved GPU host, then use release_arms.sh with explicit D and L.
set -eu
printf '%s\n' 'The local release driver is retired.' \
  'Run v6_export.py on the approved GPU host, then release_arms.sh with D and L set.' \
  'Use spec33.sh LABEL GGUF ask for the private specification answers; GitHub performs grading.' >&2
exit 2
