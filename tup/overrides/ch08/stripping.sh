#!/bin/bash
# OVERRIDE ch08/stripping: OPTIONAL in the book (saves disk space only) and
# version-fragile — it names exact sonames (libstdc++.so.6.0.34 etc.) that
# fail the moment a version moves. tup 0.1 keeps its debug symbols: 120G of
# disk is not scarce, and a system that can be debugged is worth more here
# than a smaller one. Recorded as a deliberate skip, not an omission.
echo "$TUP_PAGE_ID: optional, skipped by policy (debug symbols kept)"
