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

Windows, reached from Ubuntu under WSL (2026-10-05): Windows's programs are called by their .exe names and take
Windows paths (Microsoft Learn, "Working across file systems": interop). Each line is from Microsoft's own pages:
explorer.exe opening a path (the same page); LockWorkStation (winuser.h) behind `rundll32.exe user32.dll`;
`Clear-RecycleBin -Force` (PowerShell 5.1); the volume keys as virtual-key codes 173, 174 and 175 (Winuser.h), sent
with WScript.Shell's SendKeys; `shutdown /s /r /h /l /a /t`. Receipt f69fc63e80f2. Not here, because no documented
line does it: dark mode (a registry value apps read only when told it changed) and a volume set to a number
(Windows has no command for it; the keys move it two percent a press).
"""
from __future__ import annotations

import re
import shutil

# (job, where, program, line). `where`: "" any machine; "session" any desktop session; "systemd"; a desktop's name as
# XDG_CURRENT_DESKTOP gives it; or two of these joined by +. For one job the lines are in order of preference and the
# first that fits is given.
RECIPES = [
    # a Windows desktop under WSL: first, so that they win where both a Windows program and a Linux one are found
    ("open a file, a folder or a web page", "WINDOWS", "explorer.exe", 'explorer.exe "$(wslpath -w PATH)"',
     'a web page: explorer.exe "https://..."; it reports exit 1 even when it opened the item'),
    ("start a program", "WINDOWS", "powershell.exe", "powershell.exe -NoProfile -Command 'Start-Process notepad'", ""),
    ("close a program", "WINDOWS", "taskkill.exe", "taskkill.exe /IM notepad.exe", "what is running: tasklist.exe"),
    ("copy text to the clipboard", "WINDOWS", "clip.exe", "printf %s 'TEXT' | clip.exe", ""),
    ("lock the screen", "WINDOWS", "rundll32.exe", "rundll32.exe user32.dll,LockWorkStation", ""),
    ("a desktop notification", "WINDOWS", "powershell.exe",
     "powershell.exe -NoProfile -Command 'Add-Type -AssemblyName System.Windows.Forms; $n = New-Object System.Windows.Forms.NotifyIcon; "
     "$n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; $n.ShowBalloonTip(5000, \"dawnr\", \"TEXT\", \"Info\"); "
     "Start-Sleep 6; $n.Dispose()'", ""),
    ("mute", "WINDOWS", "powershell.exe", "powershell.exe -NoProfile -Command '(New-Object -ComObject WScript.Shell).SendKeys([char]173)'",
     "the mute key: it toggles"),
    ("sound volume", "WINDOWS", "powershell.exe",
     "powershell.exe -NoProfile -Command '$k = New-Object -ComObject WScript.Shell; 1..50 | ForEach-Object { $k.SendKeys([char]174) }; "
     "1..20 | ForEach-Object { $k.SendKeys([char]175) }'", "the volume keys, two percent a press: all the way down, then up to 40%"),
    ("empty the trash", "WINDOWS", "powershell.exe", "powershell.exe -NoProfile -Command 'Clear-RecycleBin -Force'", ""),
    ("Wi-Fi off", "WINDOWS", "netsh.exe", "netsh.exe wlan disconnect",
     'turning the adapter off takes an administrator\'s prompt: netsh interface set interface name="Wi-Fi" admin=disabled'),
    ("shut down in N minutes", "WINDOWS", "shutdown.exe", "shutdown.exe /s /t SECONDS", "shutdown.exe /a cancels; /r restarts; /h hibernates"),
    ("sign out", "WINDOWS", "shutdown.exe", "shutdown.exe /l", ""),
    # ... and what to call to find out (the 4B asked a Windows machine for its battery with `acpi` and `tput lines`,
    # its free space with `wmic`, which Windows 11 no longer has, and its name with Get-ComputerInfo, which takes a minute)
    ("battery left", "WINDOWS", "powershell.exe", 'powershell.exe -NoProfile -Command "Get-CimInstance Win32_Battery | Select-Object -ExpandProperty EstimatedChargeRemaining"', "a percentage"),
    ("the Windows version", "WINDOWS", "powershell.exe", 'powershell.exe -NoProfile -Command "Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version"', ""),
    ("the programs running", "WINDOWS", "tasklist.exe", "tasklist.exe", 'one of them: tasklist.exe /FI "IMAGENAME eq notepad.exe"'),
    ("the Wi-Fi network", "WINDOWS", "netsh.exe", "netsh.exe wlan show interfaces", ""),
    ("free space on a drive", "WINDOWS", "powershell.exe", 'powershell.exe -NoProfile -Command "Get-PSDrive C | Select-Object Used, Free"', "bytes"),
    ("the computer's name", "WINDOWS", "hostname.exe", "hostname.exe", ""),
    ("the time zone", "WINDOWS", "tzutil.exe", "tzutil.exe /g", ""),
    ("whether dark mode is on", "WINDOWS", "reg.exe", 'reg.exe query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v AppsUseLightTheme', "0x0 is dark, 0x1 light"),
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
    for job, where, program, line, *note in RECIPES:            # a note of its own, or the line's trailing parenthesis
        if job not in given and all(fits.get(w, w.upper() in desktop) for w in where.split("+")) and has(program):
            given[job] = (line, note[0]) if note else (line.split(" (")[0], line.split(" (", 1)[1].rstrip(")") if " (" in line else "")
    return ("Lines that work on this computer, to use rather than guess: " + "; ".join(f"{job}: `{line}`" + (f" ({note})" if note else "")
            for job, (line, note) in given.items()) + ".") if given else ""
