#!/bin/bash
# OVERRIDE ch08/bash: same exec-to-login pattern as ch07 createfiles.
set -e
PAGE="$TUP_PAGE"
sed 's|^exec /usr/bin/bash --login$|: # exec-to-login skipped under the driver|' "$PAGE" | bash -e
