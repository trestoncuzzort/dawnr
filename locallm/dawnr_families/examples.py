"""Five families written first, as the pattern for the rest: files whose order matters, a planted mistake behind a
test, and a described machine asked about and acted on."""
from __future__ import annotations

import re

from dawnr_factory import PEOPLE, SERVICES, STEMS, THINGS, Machine, family, say


@family
def rename_numbered(rng):
    """Number the files of one kind in alphabetical order (01-name.ext, 02-name.ext, ...); the rest stay."""
    ext = rng.choice((".txt", ".md", ".csv"))
    stems = rng.sample(STEMS, rng.randint(3, 6))
    files = {s + ext: f"{s} of {rng.choice(PEOPLE)}\n" for s in stems}
    other = rng.choice(STEMS) + rng.choice((".json", ".log"))
    files[other] = "{}\n"
    width = rng.choice((2, 3))
    want = {f"{i:0{width}d}-{s}{ext}": files[s + ext] for i, s in enumerate(sorted(stems), 1)}
    first = f"{1:0{width}d}-{sorted(stems)[0]}{ext}"
    return {"kind": "chain", "files": files,
            "request": say(rng, f"Number the {ext} files here in alphabetical order by putting a {width}-digit number and a dash in front of each name ({first} for the first). Leave the other files as they are.",
                           f"Put a running number in front of every {ext} file, alphabetically: the first becomes {first}, and so on. Nothing else changes."),
            "expect": {"files": {**{s + ext: None for s in stems}, **want, other: files[other]}},
            "solution": {"answer": "Numbered.", "files": {**{s + ext: None for s in stems}, **want}}}


@family
def shift_numbered(rng):
    """Make room in a numbered series by moving every file from number K up by one: the order of the moves matters."""
    stem, ext = rng.choice(("chapter", "part", "scene", "step", "lesson")), rng.choice((".txt", ".md"))
    n, k = rng.randint(4, 7), rng.randint(2, 3)
    name = lambda i: f"{stem}-{i:02d}{ext}"
    files = {name(i): f"{stem} {i}: {rng.choice(THINGS)} and {rng.choice(THINGS)}\n" for i in range(1, n + 1)}
    want = {name(i): files[name(i)] for i in range(1, k)}
    want.update({name(i + 1): files[name(i)] for i in range(k, n + 1)})
    return {"kind": "chain", "files": files,
            "request": say(rng, f"A new {stem} {k} is coming. Make room for it: rename {name(k)} and every later one so that each number goes up by one. Do not create the new file.",
                           f"Shift the {stem} files from {name(k)} onwards up by one number, so that there is no {name(k)} any more and the last one is {name(n + 1)}."),
            "expect": {"files": {**want, name(k): None}},
            "solution": {"answer": "Shifted.", "files": {**want, name(k): None}}}


BUGS = [   # (module, function, right source, wrong source, test lines)
    ("textutil", "count_vowels", "def count_vowels(text):\n    return sum(1 for ch in text.lower() if ch in 'aeiou')\n",
     "def count_vowels(text):\n    return sum(1 for ch in text if ch in 'aeiou')\n", ["assert count_vowels('Audio') == 4, count_vowels('Audio')", "assert count_vowels('xyz') == 0"]),
    ("numutil", "clamp", "def clamp(x, low, high):\n    return max(low, min(high, x))\n",
     "def clamp(x, low, high):\n    return max(high, min(low, x))\n", ["assert clamp(5, 0, 3) == 3, clamp(5, 0, 3)", "assert clamp(-2, 0, 3) == 0", "assert clamp(2, 0, 3) == 2"]),
    ("listutil", "chunks", "def chunks(xs, n):\n    return [xs[i:i + n] for i in range(0, len(xs), n)]\n",
     "def chunks(xs, n):\n    return [xs[i:i + n] for i in range(0, len(xs) - 1, n)]\n", ["assert chunks([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]], chunks([1, 2, 3, 4, 5], 2)", "assert chunks([], 3) == []"]),
    ("mathutil", "gcd", "def gcd(a, b):\n    while b:\n        a, b = b, a % b\n    return a\n",
     "def gcd(a, b):\n    while b:\n        a, b = b, a // b\n    return a\n", ["assert gcd(12, 18) == 6, gcd(12, 18)", "assert gcd(7, 5) == 1", "assert gcd(9, 0) == 9"]),
    ("strutil", "is_palindrome", "def is_palindrome(text):\n    letters = [ch.lower() for ch in text if ch.isalnum()]\n    return letters == letters[::-1]\n",
     "def is_palindrome(text):\n    letters = [ch for ch in text if ch.isalnum()]\n    return letters == letters[::-1]\n",
     ["assert is_palindrome('Never odd or even')", "assert not is_palindrome('dawnr')", "assert is_palindrome('')"]),
]


@family
def fix_function_bug(rng):
    """One function with a planted mistake and a test that shows it; the test must pass and stay as it is."""
    module, function, right, wrong, lines = rng.choice(BUGS)
    test = f"test_{module}.py"
    files = {f"{module}.py": wrong, test: f"from {module} import {function}\n\n" + "\n".join(lines) + "\nprint('OK')\n"}
    return {"kind": "code", "files": files,
            "request": say(rng, f"`python3 {test}` fails. Fix {module}.py so that it prints OK. Do not change the test.",
                           f"The test in {test} does not pass. Find the mistake in {module}.py and fix it; leave the test alone.",
                           f"Make `python3 {test}` print OK by correcting {function} in {module}.py, without touching {test}."),
            "expect": {"run": (f"python3 {test}", "OK"), "may_change": [f"{module}.py"]},
            "solution": {"answer": f"Fixed {function}.", "files": {f"{module}.py": right}}}


@family
def machine_question(rng):
    """One question about a described computer, answered from what its commands print."""
    m = Machine(rng)
    pid, top, _cpu, _mem = m.top_process
    on, off = sorted(m.active)[0], sorted(set(("nginx", "cups", "docker", "cron", "postgresql")) - m.active)[0]
    have = sorted(m.installed)[0]
    free = m.disk_gib * (1 - m.disk_used)
    asked = rng.choice([
        (say(rng, "How many processor threads does this computer have?", "How many logical CPUs are there on this machine?"), {"answer": [str(m.cpus)]}, f"It has {m.cpus}."),
        (say(rng, "Which kernel version is this computer running?", "What kernel release is running here?"), {"answer": [m.kernel]}, f"It runs {m.kernel}."),
        (say(rng, "How much memory does this computer have in total?", "How many gigabytes of RAM are installed here?"), {"answer": [str(m.memory_gib)]}, f"{m.memory_gib} GiB."),
        (say(rng, "What is this computer's hostname?", "What is this machine called on the network?"), {"answer": [m.host]}, f"It is {m.host}."),
        (say(rng, "Which process is using the most memory right now, and what is its process id?", "What is taking the most memory at the moment? Give the program and its pid."),
         {"answer": [top, str(pid)]}, f"{top}, pid {pid}."),
        (say(rng, f"Is the {on} service running?", f"Is {on} active on this machine?"), {"any": [["yes", "active", "is running"]], "lacks": ["not running", "inactive", "not active"]}, f"Yes, {on} is active."),
        (say(rng, f"Is the {off} service running?", f"Is {off} active right now?"), {"any": [["no", "not", "inactive"]]}, f"No, {off} is not running."),
        (say(rng, f"Is {have} installed, and which version?", f"Which version of {have} is on this computer?"), {"answer": [m.installed[have]]}, f"{have} {m.installed[have]} is installed."),
        (say(rng, "How much disk space is free on the root file system?", "How many gigabytes are left on the main disk?"), {"answer": [f"{free:.0f}"]}, f"{free:.0f}G are free."),
        (say(rng, "What time zone is this computer set to?", "Which time zone does this machine use?"), {"answer": [m.timezone.split("/")[-1]]}, f"{m.timezone}."),
        (say(rng, "Which distribution is this computer running?", "What Linux distribution is this?"), {"answer": [m.distro.split()[0]]}, f"{m.distro} {m.version}".strip() + "."),
    ])
    return {"kind": "state", "files": {}, "request": asked[0], "expect": asked[1], "machine": m, "solution": {"answer": asked[2]}}


@family
def machine_act(rng):
    """One thing done on a described computer by one command, which is shown and recorded and never run."""
    m = Machine(rng)
    while not m.desktop:
        m = Machine(rng)
    level, minutes, service, text = rng.choice((20, 30, 45, 60, 75)), rng.choice((10, 15, 45, 90)), rng.choice(SERVICES), f"{rng.choice(STEMS)} ready"
    dark = "plasma-apply-colorscheme BreezeDark" if m.desktop == "KDE" else "gsettings set org.gnome.desktop.interface color-scheme prefer-dark"
    acts = [
        (say(rng, f"Set the sound volume to {level}%.", f"Turn the volume to {level} percent."), rf"wpctl set-volume \S+ ({level}%|0\.{level:02d}0?)(\s|$)", f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {level}%"),
        (say(rng, "Mute the sound.", "Switch the sound off for now."), r"wpctl set-mute \S+ (1|toggle)", "wpctl set-mute @DEFAULT_AUDIO_SINK@ 1"),
        (say(rng, "Lock the screen.", "Lock this session."), r"loginctl lock-session", "loginctl lock-session"),
        (say(rng, f"Shut the computer down in {minutes} minutes.", f"Power off in {minutes} minutes from now."), rf"shutdown (-h |-P )?\+{minutes}(\s|$)", f"shutdown +{minutes}"),
        (say(rng, f"Start my user service called {service}.", f"Start {service}, which runs as a service of mine."), rf"systemctl --user (start|restart) {re.escape(service)}", f"systemctl --user start {service}"),
        (say(rng, f"Send a desktop notification that says: {text}", f"Pop up a notification with the text: {text}"), rf"notify-send .*{re.escape(text)}", f'notify-send "{text}"'),
        (say(rng, "Turn off Wi-Fi.", "Switch the Wi-Fi radio off."), r"nmcli r(adio)? wifi off|rfkill block (wifi|wlan)", "nmcli radio wifi off"),
    ]
    if m.desktop in ("GNOME", "KDE"):
        acts.append((say(rng, "Turn on dark mode.", "Switch the desktop to its dark colours."), re.escape(dark.rsplit(" ", 1)[0]) + r" ['\"]?" + re.escape(dark.rsplit(" ", 1)[1]), dark))
    request, pattern, line = rng.choice(acts)
    return {"kind": "act", "files": {}, "request": request, "expect": {"pc": pattern}, "machine": m, "solution": {"answer": "Done.", "acted": [line]}}
