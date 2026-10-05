"""dawnr_agent/recipes.py: the line for a common job on this desktop, read from a table and not recalled
(2026-10-05).

A 4B asked to turn a KDE desktop dark wrote `qdbus org.kde.plasma-desktop ... setDarkMode true`, a call that does
not exist, twice with two spellings; asked to empty the trash it looked up a MIME type. It knows that such commands
exist and not which, and the machine's own manual does not say (`apropos trash`: "nothing appropriate"). So the
lines are given: for each job the first line whose program this machine has and whose desktop is this one, as one
sentence added to what the model is told about the computer (dawnr_cli.py). The person still sees every line before
it runs; this only decides what the line is likely to be.

Every line here was read from the program itself, on the machine this was written on (Ubuntu 26.04, GNOME 50,
PipeWire: `gsettings range`, `wpctl --help`, `loginctl --help`, `gio help trash`, `shutdown --help`) or, for the two
Plasma programs, from their source (invent.kde.org: plasma-workspace/kcms/colors/plasma-apply-colorscheme.cpp, a
positional scheme name; kio/src/kioworkers/trash/ktrash.cpp, `--empty`). Research receipt 2549b0a8f435. A line
that could not be read that way is not in the table.
"""
from __future__ import annotations

import re
import shutil

# (job, where, program, line). `where`: "" any machine; "session" any desktop session; "systemd"; a desktop's name as
# XDG_CURRENT_DESKTOP gives it; or two of these joined by +. For one job the lines are in order of preference and the
# first that fits is given.
RECIPES = [
    ("open a file, a folder or a web page", "session", "xdg-open", "xdg-open PATH"),
    ("dark mode", "GNOME", "gsettings", "gsettings set org.gnome.desktop.interface color-scheme prefer-dark (light again: default)"),
    ("dark mode", "KDE", "plasma-apply-colorscheme", "plasma-apply-colorscheme BreezeDark (light again: BreezeLight)"),
    ("night light", "GNOME", "gsettings", "gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled true"),
    ("larger text", "GNOME", "gsettings", "gsettings set org.gnome.desktop.interface text-scaling-factor 1.25"),
    ("do not disturb", "GNOME", "gsettings", "gsettings set org.gnome.desktop.notifications show-banners false"),
    ("sound volume", "session", "wpctl", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 40%"),
    ("sound volume", "session", "pactl", "pactl set-sink-volume @DEFAULT_SINK@ 40%"),
    ("sound volume", "session", "amixer", "amixer set Master 40%"),
    ("mute", "session", "wpctl", "wpctl set-mute @DEFAULT_AUDIO_SINK@ 1 (0 unmutes)"),
    ("mute", "session", "pactl", "pactl set-sink-mute @DEFAULT_SINK@ 1 (0 unmutes)"),
    ("mute", "session", "amixer", "amixer set Master mute (unmute)"),
    ("screen brightness", "session", "brightnessctl", "brightnessctl set 50%"),
    ("lock the screen", "session+systemd", "loginctl", "loginctl lock-session"),
    ("empty the trash", "KDE", "ktrash6", "ktrash6 --empty"),
    ("empty the trash", "KDE", "ktrash5", "ktrash5 --empty"),
    ("empty the trash", "session", "gio", "gio trash --empty"),
    ("Wi-Fi off", "", "nmcli", "nmcli radio wifi off (on)"),
    ("Wi-Fi off", "", "rfkill", "rfkill block wifi (unblock)"),
    ("Bluetooth off", "", "rfkill", "rfkill block bluetooth (unblock)"),
    ("Bluetooth off", "", "bluetoothctl", "bluetoothctl power off (on)"),
    ("a service of the person's own", "systemd", "systemctl", "systemctl --user start NAME (stop, restart; a system service takes sudo, which the person runs)"),
    ("shut down in N minutes", "", "shutdown", "shutdown +N (shutdown -c cancels)"),
    ("suspend", "systemd", "systemctl", "systemctl suspend"),
]


def recipes(machine: str, has=shutil.which) -> str:
    """The sentence of jobs and their lines for the machine that `machine` describes (system.facts' sentence: its
    desktop and whether it has systemd are read from it), with only programs `has` finds. "" when none fits."""
    found = None if "no desktop session" in machine else re.search(r"desktop (.+?)(?: on (?:wayland|x11))?\.", machine)
    desktop = found.group(1).upper().split() if found else []
    fits = {"": True, "session": bool(desktop), "systemd": "systemd" in machine}
    given: dict = {}
    for job, where, program, line in RECIPES:
        if job not in given and all(fits.get(w, w.upper() in desktop) for w in where.split("+")) and has(program):
            given[job] = line
    return ("Lines that work on this computer, to use rather than guess: " + "; ".join(f"{job}: `{line.split(' (')[0]}`"
            + (" (" + line.split(" (", 1)[1] if " (" in line else "") for job, line in given.items()) + ".") if given else ""
