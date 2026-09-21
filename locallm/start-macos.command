#!/bin/sh
# Starts locallm on a Mac. Double-click it in the Finder.
#
# The .command ending is what makes that work: the Finder opens a Terminal
# window and runs the file. Python's own macOS installer ships one the same
# way, "Install Certificates.command" (docs.python.org/3/using/mac.html). The
# file must be executable or the Finder refuses to run it at all.
#
# If macOS says it cannot check this file for malicious software, that is
# Gatekeeper, and it says the same about every script downloaded from
# anywhere. Open System Settings, go to Privacy & Security, scroll down, and
# click the "Open Anyway" button (support.apple.com/en-us/102445). It asks
# once, and only for a copy that arrived over the network.
#
# It installs nothing and downloads nothing: it finds a Python, checks the one
# piece that is often missing, and opens the window.

# WHERE THIS FILE IS, which is not where the Terminal starts. A double-click
# gives you a shell sitting in your home folder, not in this folder, so asking
# for "home.py" would look in the wrong place and report that it does not
# exist. That is the whole bug this line exists to prevent. ${0%/*} cuts the
# file name off this script's own path; cd and pwd turn what is left into a
# full path (mywiki.wooledge.org/BashFAQ/028, which also explains the CDPATH=
# in front: a cd can otherwise be sent somewhere else by a CDPATH set in your
# shell). Everything is in quotes so a stick mounted at /Volumes/My Drive works
# like any other folder.
case "$0" in
    */*) folder="${0%/*}" ;;
    *)   folder="." ;;
esac
here=$(CDPATH= cd -- "$folder" && pwd) || exit 1

# The Terminal window closes the moment this script ends, taking the reason
# with it. Everything that gives up below waits here first.
wait_for_reader() {
    printf '\n  Press Enter to close this window. '
    read -r discarded_line
}

# python3 first, then python. Which name works is not something to assume: a
# Mac may have Python from python.org, from Homebrew, from Xcode's command line
# tools, or none at all. Each candidate has to answer this before it is
# accepted, because an old Python accepted here would fail later with a message
# about something else entirely.
version_check='import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'

PY=
for candidate in python3 python; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    "$candidate" -c "$version_check" >/dev/null 2>&1 || continue
    PY="$candidate"
    break
done

if [ -z "$PY" ]; then
    printf '%s\n' \
        '' \
        '  No Python 3.10 or newer was found on this Mac.' \
        '' \
        '  Get the installer from python.org/downloads. Take the ordinary one' \
        '  for macOS; it includes everything this needs. Then double-click this' \
        '  file again.'
    wait_for_reader
    exit 1
fi

if [ ! -f "$here/home.py" ]; then
    printf '%s\n' \
        '' \
        '  The program is not in this folder:' \
        '' \
        "      $here" \
        '' \
        '  This file only starts locallm; it is not locallm. Keep it together' \
        '  with the rest of the folder it arrived in, or unpack that folder' \
        '  again and start from there.'
    wait_for_reader
    exit 1
fi

# THE CHECK THAT TURNS A TRACEBACK INTO A SENTENCE. tkinter is what draws the
# window, and Python's own documentation calls it an optional module that can
# be missing from a working copy of Python
# (docs.python.org/3/library/tkinter.html), at a cost of 13 ms to ask. The
# installer from python.org includes it -- "A macOS-native version of Tk is
# included with the installer" (docs.python.org/3/using/mac.html) -- but
# Homebrew keeps it in a second formula, one per Python version, so a Homebrew
# Python usually cannot import it. Without this check the first thing you see
# is a page of traceback ending in ImportError, which names nothing you can
# act on.
if ! "$PY" -c 'import tkinter' >/dev/null 2>&1; then
    printf '%s\n' \
        '' \
        '  Python is here, but the part that draws windows is not.' \
        '' \
        '  If this Python came from Homebrew, Tk is a separate formula and its' \
        '  name carries the version. Ask which version you have, then install' \
        '  the matching one:' \
        '' \
        "      $PY --version" \
        '      brew install python-tk@3.13      <- use your own version here' \
        '' \
        '  (formulae.brew.sh/formula/python-tk@3.13)' \
        '' \
        '  If you would rather not, the installer from python.org includes Tk' \
        '  already. START-HERE.md in this folder has the rest, including what' \
        '  still works while you have no window.'
    wait_for_reader
    exit 1
fi

"$PY" "$here/home.py" "$@"
status=$?
if [ "$status" -ne 0 ]; then
    printf '%s\n' \
        '' \
        "  locallm stopped with an error (code $status)." \
        '' \
        '  Whatever is printed above this line is what Python said. It is the' \
        '  useful part if you ask anyone about it, so copy it before closing.'
    wait_for_reader
fi
exit "$status"
