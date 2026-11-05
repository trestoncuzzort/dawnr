# Supplementary targets for the reviewed native13 Python pages. Read it after
# CPython's own generated Makefile, from the package build directory:
#
#   make -f Makefile -f /tup-build/native/profiles/lfs-13.1-systemd/python-built.mk <target>
#
# A shared-library interpreter cannot find its libpython before installation,
# and once an earlier Python is installed a bare ./python silently loads that
# older installed library instead of the one just built. CPython's own build
# commands avoid both by running "$(RUNSHARED) $(PYTHON_FOR_BUILD) <script>";
# see checksharedmods and TESTPYTHON in Makefile.pre.in of the selected
# Python-3.14.10 archive. Reuse exactly those generated variables: no library
# path is defined here.
# https://github.com/python/cpython/blob/v3.14.10/Makefile.pre.in
TUP_NATIVE13 = /tup-build/native/profiles/lfs-13.1-systemd

.PHONY: tup-built-library tup-backport-regressions tup-suite-results

# Both reviewed pages configure --enable-shared. An empty RUNSHARED would let
# the dynamic loader choose a library that this build did not produce.
tup-built-library:
	@test -n "$(strip $(RUNSHARED))" || { echo 'RUNSHARED is empty: refusing to run an interpreter against an unidentified libpython' >&2; exit 1; }

tup-backport-regressions: tup-built-library
	$(RUNSHARED) $(PYTHON_FOR_BUILD) $(TUP_NATIVE13)/python-backport-tests.py --output native-python-backports.trs

tup-suite-results: tup-built-library
	$(RUNSHARED) $(PYTHON_FOR_BUILD) $(TUP_NATIVE13)/python-suite-results.py native-python.xml native-python-full.trs
