#!/bin/bash
# OVERRIDE ch08/groff: fill the book's <paper_size> placeholder.
#
# The page reads `PAGE=<paper_size> ./configure --prefix=/usr`, where
# <paper_size> is a literal instruction to the reader, not shell. Under the
# driver bash tries to run a file called `paper_size` and the page dies in
# under a second. tup uses `letter`, which is the correct default for where
# this is built; groff's setting affects man-page rendering only, and
# /etc/papersize can override it at any time.
set -e
PAGE_SRC="$TUP_PAGE"
[ -s "$PAGE_SRC" ] || { echo "override: cannot find the groff page"; exit 1; }
sed 's@^PAGE=<paper_size> @PAGE=letter @' "$PAGE_SRC" > /tmp/groff-paper.sh
grep -q "PAGE=letter" /tmp/groff-paper.sh || { echo "override: substitution missed"; exit 1; }
grep -q "<paper_size>" /tmp/groff-paper.sh && { echo "override: placeholder survived"; exit 1; }
. /tmp/groff-paper.sh
