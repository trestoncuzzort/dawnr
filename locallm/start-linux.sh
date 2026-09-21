#!/bin/sh
# Starts locallm on Linux.
#
# Run it from a terminal with ./start-linux.sh, or double-click it if your file
# manager is set to run scripts rather than open them. It installs nothing and
# downloads nothing: it finds a Python, checks the one piece that is often
# missing, and opens the window.
#
# If the terminal says "Permission denied", the file lost its executable bit on
# the way here. Fix it once with: chmod +x start-linux.sh

# WHERE THIS FILE IS, which is not where you are standing. A file manager
# starts a script in your home folder, so asking for "home.py" would look in
# the wrong place and report that it does not exist. ${0%/*} cuts the file name
# off this script's own path; cd and pwd turn what is left into a full path
# that nothing later can misread (mywiki.wooledge.org/BashFAQ/028, which also
# explains the CDPATH= in front: a cd can otherwise be sent somewhere else
# entirely by a CDPATH set in your shell). Everything is in quotes so a stick
# mounted at /media/you/My Drive works like any other folder.
case "$0" in
    */*) folder="${0%/*}" ;;
    *)   folder="." ;;
esac
here=$(CDPATH= cd -- "$folder" && pwd) || exit 1

# A window opened by a double-click closes the moment this script ends, taking
# the reason with it. Everything that gives up below waits here first.
wait_for_reader() {
    printf '\n  Press Enter to close this window. '
    read -r discarded_line
}

# python3 first, then python. Which name works is not something to assume: on
# some systems "python" is still Python 2, on others there is no "python" at
# all. Each candidate has to answer this before it is accepted, because a
# Python 2 accepted here would fail at the next check with a message about
# tkinter, sending you off to install a package you do not need.
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
        '  No Python 3.10 or newer was found on this computer.' \
        '' \
        '  Most Linux systems already have one. If yours does not, your package' \
        '  manager has it -- on Debian, Ubuntu and Mint that is:' \
        '' \
        '      sudo apt install python3' \
        '' \
        '  Otherwise get it from python.org/downloads. Then run this again.'
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
# (docs.python.org/3/library/tkinter.html). On Debian and Ubuntu it is a
# separate package that a stock python3 does not pull in
# (packages.debian.org/stable/python3-tk). Asking costs 13 ms, measured here.
# Not asking costs a page of traceback ending in ImportError, which says
# nothing about which of the hundred things on this computer to change.
if ! "$PY" -c 'import tkinter' >/dev/null 2>&1; then
    printf '%s\n' \
        '' \
        '  Python is here, but the part that draws windows is not.' \
        '' \
        '      Debian, Ubuntu, Mint:  sudo apt install python3-tk' \
        '      Fedora:                sudo dnf install python3-tkinter' \
        '      anything else:         search your package manager for tkinter' \
        '' \
        '  This is normal and it is not something you did. Python treats this' \
        '  part as optional, so it is left out of many Linux installs. Install' \
        '  it and run this again. START-HERE.md in this folder has the rest,' \
        '  including what still works while you have no window.'
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
