#!/bin/bash
# OVERRIDE ch08/pkgmgt: 8.2 "Package Management" is an ADVISORY ESSAY. Its
# code blocks are illustrations of package-management approaches (a bare
# ./configure among them), not build steps; running them fails instantly.
# tup ships no package manager by design at 0.1; the receipt records why.
echo "ch08/02-pkgmgt: advisory essay, no build steps, skipped by override"
