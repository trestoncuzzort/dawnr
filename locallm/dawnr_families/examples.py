"""Five families written first, as the pattern for the rest: files whose order matters, a planted mistake behind a
test, and a described machine asked about and acted on."""
from __future__ import annotations

import re

from dawnr_factory import PEOPLE, SERVICES, STEMS, SYSTEM_SERVICES, THINGS, Machine, family, say


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
    # ten more, each in a module of its own name: five bugs drew only 14 different tasks in 40 seeds
    ("seqtools", "last_n", "def last_n(xs, n):\n    return xs[-n:] if n > 0 else []\n", "def last_n(xs, n):\n    return xs[-n:]\n",
     ["assert last_n([1, 2, 3], 2) == [2, 3], last_n([1, 2, 3], 2)", "assert last_n([1, 2, 3], 0) == [], last_n([1, 2, 3], 0)"]),
    ("pathutil", "extension", "def extension(name):\n    return name.rsplit('.', 1)[1] if '.' in name else ''\n",
     "def extension(name):\n    return name.split('.')[1] if '.' in name else ''\n",
     ["assert extension('notes.txt') == 'txt', extension('notes.txt')", "assert extension('backup.tar.gz') == 'gz', extension('backup.tar.gz')",
      "assert extension('README') == '', extension('README')"]),
    ("pricing", "with_tax", "def with_tax(price, rate):\n    return round(price * (1 + rate / 100), 2)\n", "def with_tax(price, rate):\n    return round(price * rate / 100, 2)\n",
     ["assert with_tax(100, 20) == 120.0, with_tax(100, 20)", "assert with_tax(19.99, 0) == 19.99, with_tax(19.99, 0)"]),
    ("signs", "sign", "def sign(x):\n    return (x > 0) - (x < 0)\n", "def sign(x):\n    return 1 if x >= 0 else -1\n",
     ["assert sign(7) == 1, sign(7)", "assert sign(-3) == -1, sign(-3)", "assert sign(0) == 0, sign(0)"]),
    ("pairtools", "pairs", "def pairs(xs):\n    return list(zip(xs, xs[1:]))\n", "def pairs(xs):\n    return list(zip(xs, xs[2:]))\n",
     ["assert pairs([1, 2, 3]) == [(1, 2), (2, 3)], pairs([1, 2, 3])", "assert pairs([5]) == [], pairs([5])"]),
    ("prefixes", "strip_prefix", "def strip_prefix(text, prefix):\n    return text[len(prefix):] if text.startswith(prefix) else text\n",
     "def strip_prefix(text, prefix):\n    return text.lstrip(prefix)\n",
     ["assert strip_prefix('v1.2', 'v') == '1.2', strip_prefix('v1.2', 'v')", "assert strip_prefix('aab', 'a') == 'ab', strip_prefix('aab', 'a')",
      "assert strip_prefix('main', 'x') == 'main'"]),
    ("blanks", "is_blank", "def is_blank(text):\n    return not text.strip()\n", "def is_blank(text):\n    return not text\n",
     ["assert is_blank('')", "assert is_blank('   ')", "assert not is_blank(' x ')"]),
    ("ratios", "percent", "def percent(part, whole):\n    return round(part / whole * 100, 1)\n", "def percent(part, whole):\n    return round(part // whole * 100, 1)\n",
     ["assert percent(1, 4) == 25.0, percent(1, 4)", "assert percent(3, 3) == 100.0, percent(3, 3)"]),
    ("weekdays", "is_weekend", "def is_weekend(day):\n    return day.lower() in ('saturday', 'sunday')\n", "def is_weekend(day):\n    return day in ('saturday', 'sunday')\n",
     ["assert is_weekend('Sunday')", "assert is_weekend('saturday')", "assert not is_weekend('Monday')"]),
    ("wording", "plural", "def plural(word, n):\n    return word if n == 1 else word + 's'\n", "def plural(word, n):\n    return word if n <= 1 else word + 's'\n",
     ["assert plural('cup', 1) == 'cup', plural('cup', 1)", "assert plural('cup', 3) == 'cups', plural('cup', 3)", "assert plural('cup', 0) == 'cups', plural('cup', 0)"]),
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
                           f"Make `python3 {test}` print OK by correcting {function} in {module}.py, without touching {test}.",
                           f"{function} in {module}.py has a mistake that `python3 {test}` shows. Correct the function so that the test prints OK, and keep {test} as it is."),
            "expect": {"run": (f"python3 {test}", "OK"), "may_change": [f"{module}.py"]},
            "solution": {"answer": f"Fixed {function}.", "files": {f"{module}.py": right}}}


def _num(n) -> str:
    """The number on its own (4 is not the 4 of 64 or 24, which a substring check let through), 16.0 for 16 too."""
    return rf"(?<![\w.,-]){re.escape(str(n))}(?:\.0+)?(?![\d-]|[.,]\d)"


def _running(name: str) -> dict:
    """The judge of "is it running?" when it is: a yes, and nothing that says this service is not (a bare substring
    check let "isn't active" through, as "active" is inside it)."""
    n = re.escape(name)
    return {"says": [r"(?i)\byes\b|\b(?:is|it's|it is) (?:running|active|up)\b|\bactive \(running\)"],
            "lacks_re": [rf"(?i)^\W*no\b|\b{n}(?: service)? (?:is not|isn't|is inactive)\b|\bit(?: is not|'s not| isn't) (?:running|active)\b"]}


def _stopped(name: str) -> dict:
    """The judge of "is it running?" when it is not: a no as a word ("no" is inside "now", "normally", "gnome"), and
    no saying that this service, or "it", is running."""
    n = re.escape(name)
    return {"says": [r"(?i)\bno\b|\bnot\b|n't\b|\binactive\b|\bdead\b|\bstopped\b"],
            "lacks_re": [rf"(?i)^\W*yes\b|\b{n}(?: service)? is (?:running|active)\b|\bit(?: is|'s) (?:running|active)\b"]}


@family
def machine_question(rng):
    """One question about a described computer, answered from what its commands print."""
    m = Machine(rng)
    pid, top, _cpu, _mem = m.top_process
    # a service of the five that is not running; when all five are, any other that is not (seed 290 had all five)
    stopped = sorted(set(("nginx", "cups", "docker", "cron", "postgresql")) - m.active) or sorted(set(SYSTEM_SERVICES) - m.active)
    on, off = sorted(m.active)[0], stopped[0]
    have = sorted(m.installed)[0]
    free = m.disk_gib * (1 - m.disk_used)
    # no wording is a measuring request (106 asks the time zone, 108 the hostname, both of this very computer)
    asked = rng.choice([
        (say(rng, "How many processor threads does this computer have?", "How many logical CPUs are there on this machine?", "How many CPU threads can this machine run at once?"),
         {"says": [_num(m.cpus)]}, f"It has {m.cpus}."),
        (say(rng, "Which kernel version is this computer running?", "What kernel release is running here?", "Tell me the kernel release of this machine."),
         {"answer": [m.kernel]}, f"It runs {m.kernel}."),
        (say(rng, "How much memory does this computer have in total?", "How many gigabytes of RAM are installed here?", "What is the total RAM of this machine?"),
         {"says": [_num(m.memory_gib)]}, f"{m.memory_gib} GiB."),
        (say(rng, "What host name does this machine have?", "What is this machine called on the network?", "Which name does this computer go by on the network?"), {"answer": [m.host]}, f"It is {m.host}."),
        (say(rng, "Which process is using the most memory right now, and what is its process id?", "What is taking the most memory at the moment? Give the program and its pid.",
             "Which program holds the most RAM at the moment, and under which pid?"),
         {"answer": [top], "says": [_num(pid)]}, f"{top}, pid {pid}."),
        (say(rng, f"Is the {on} service running?", f"Is {on} active on this machine?", f"Is {on} up at the moment?"), _running(on), f"Yes, {on} is active."),
        (say(rng, f"Is the {off} service running?", f"Is {off} active right now?", f"Is {off} up at the moment?"), _stopped(off), f"No, {off} is not running."),
        (say(rng, f"Is {have} installed, and which version?", f"Which version of {have} is on this computer?"), {"answer": [m.installed[have]]}, f"{have} {m.installed[have]} is installed."),
        (say(rng, "How much disk space is free on the root file system?", "How many gigabytes are left on the main disk?", "How much room is left on the disk that holds /?"), {"says": [_num(f"{free:.0f}")]}, f"{free:.0f}G are free."),
        (say(rng, "Which time zone is this machine set to?", "Which time zone does this machine use?", "In which time zone does this computer keep its clock?"), {"answer": [m.timezone.split("/")[-1]]}, f"{m.timezone}."),
        (say(rng, "Which distribution is this computer running?", "What Linux distribution is this?", "Which Linux distribution does this machine have?"),
         {"answer": [m.distro.split()[0]]}, f"{m.distro} {m.version}".strip() + "."),
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
    # no wording is a measuring request, names and numbers aside (115, 116, 117, 120, 121, 123 and 114/140 were, and the
    # gate refused 8 of 40 seeds)
    acts = [
        (say(rng, f"Put the sound volume at {level}%.", f"Turn the volume to {level} percent."), rf"wpctl set-volume \S+ ({level}%|0\.{level:02d}0?)(\s|$)", f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {level}%"),
        (say(rng, "Mute the speakers.", "Switch the sound off for now."), r"wpctl set-mute \S+ (1|toggle)", "wpctl set-mute @DEFAULT_AUDIO_SINK@ 1"),
        (say(rng, "Lock the screen now; I am stepping away.", "Lock this session."), r"loginctl lock-session", "loginctl lock-session"),
        (say(rng, f"Switch the computer off in {minutes} minutes.", f"Power off in {minutes} minutes from now."), rf"shutdown (-h |-P )?\+{minutes}(\s|$)", f"shutdown +{minutes}"),
        (say(rng, f"Please start my {service} user service.", f"Start {service}, which runs as a service of mine."), rf"systemctl --user (start|restart) {re.escape(service)}", f"systemctl --user start {service}"),
        (say(rng, f"Send a desktop notification that says: {text}", f"Pop up a notification with the text: {text}"), rf"notify-send .*{re.escape(text)}", f'notify-send "{text}"'),
        (say(rng, "Turn the Wi-Fi off.", "Switch the Wi-Fi radio off."), r"nmcli r(adio)? wifi off|rfkill block (wifi|wlan)", "nmcli radio wifi off"),
    ]
    if m.desktop in ("GNOME", "KDE"):
        acts.append((say(rng, "Switch dark mode on.", "Switch the desktop to its dark colours."), re.escape(dark.rsplit(" ", 1)[0]) + r" ['\"]?" + re.escape(dark.rsplit(" ", 1)[1]), dark))
    request, pattern, line = rng.choice(acts)
    return {"kind": "act", "files": {}, "request": request, "expect": {"pc": pattern}, "machine": m, "solution": {"answer": "Done.", "acted": [line]}}
