"""Small programs in Python, judged by running them: a function written to a test that is given, a planted mistake
found behind a failing test (in one file or in two), a class completed to its test, an option or a subcommand added
to a script, a script that reads the file named on its command line, and a broken script repaired from its error.
Every expected value is computed here, from a reference written beside each catalogue entry."""
from __future__ import annotations

import re
import shlex
import textwrap

from dawnr_factory import PEOPLE, PLACES, STEMS, THINGS, family, say

GENERIC = ("helpers", "utils", "toolkit", "common", "misc", "shared", "basics", "mylib", "funcs", "extras")


def _f(spec: str, source: str, cases: list, bugs: list = ()) -> dict:
    """A catalogue function: what it does, a right source, a dozen calls it is checked on, wrong variants as (old, new)."""
    source = source.strip("\n") + "\n"
    return {"spec": spec, "source": source, "cases": cases, "bugs": list(bugs), "names": re.findall(r"^def (\w+)\(", source, re.M)}


def _space(source: str) -> dict:
    space: dict = {}
    exec(compile(source, "<reference>", "exec"), space)         # the catalogue's own code, written below
    return space


def _outcome(expr: str, space: dict) -> tuple:
    try:
        return True, eval(expr, space)
    except Exception as error:                                  # noqa: BLE001  (the error is what is checked)
        return False, type(error).__name__


def _assertion(expr: str, outcome: tuple) -> str:
    ok, value = outcome
    if ok:
        shown = f"({expr})" if re.search(r"==|!=|<|>|\bis\b|\bin\b|\bnot\b", expr) else expr      # no chained comparison
        return f"assert {shown} {'is' if value is None or isinstance(value, bool) else '=='} {value!r}, {expr}"
    return f"try:\n    {expr}\n    raise SystemExit({'no ' + value + ' from ' + expr!r})\nexcept {value}:\n    pass"


def _test(imports: list, body: list, checks: int) -> tuple:
    """A test file: the imports, the body, and a last line that is printed only when every check held."""
    token = f"all {checks} checks passed"
    head = "".join(f"from {module} import {', '.join(names)}\n" for module, names in imports)
    return head + "\n" + "\n".join(body) + f"\nprint({token!r})\n", token


def _module(pieces: list) -> str:
    """Functions as one module: their imports gathered at the top, each under a comment saying what it does."""
    imports, parts = [], []
    for spec, source in pieces:
        lines = source.strip("\n").split("\n")
        while lines and lines[0].startswith(("import ", "from ")):
            line = lines.pop(0)
            imports += [] if line in imports else [line]
        parts.append(textwrap.fill(spec, 110, initial_indent="# ", subsequent_indent="# ") + "\n" + "\n".join(lines).strip("\n"))
    return ("\n".join(imports) + "\n\n\n" if imports else "") + "\n\n\n".join(parts) + "\n"


def _checks(rng, entry: dict, bug: tuple | None = None, count: int = 0) -> list:
    """Assertions on an entry's cases: all of them, `count` of them, or (with a bug) some its wrong variant fails and
    some it passes."""
    right = _space(entry["source"])
    picked = list(range(len(entry["cases"])))
    if bug:
        wrong = _space(entry["source"].replace(*bug, 1))
        differ = [i for i in picked if _outcome(entry["cases"][i], right) != _outcome(entry["cases"][i], wrong)]
        same = [i for i in picked if i not in differ]
        picked = sorted(rng.sample(differ, min(len(differ), rng.randint(2, 3))) + rng.sample(same, min(len(same), rng.randint(2, 4))))
    elif count:
        picked = sorted(rng.sample(picked, count))
    return [_assertion(entry["cases"][i], _outcome(entry["cases"][i], right)) for i in picked]


FUNCS = [
    _f("slugify(text) returns the text in lower case with every run of characters that are not letters or digits replaced by one dash, and no dash at either end.", """
import re


def slugify(text):
    return re.sub('[^a-z0-9]+', '-', text.lower()).strip('-')
""", ["slugify('Hello World')", "slugify('  Hello,   World!  ')", "slugify('Already-a-slug')", "slugify('Python 3.10 Release')", "slugify('a__b')",
      "slugify('---')", "slugify('')", "slugify('MiXeD CaSe')", "slugify('end.')", "slugify('2026 Plan: Q3 & Q4')", "slugify('x')", "slugify('one/two|three')"],
       [(".strip('-')", ""), ("'[^a-z0-9]+'", "'[^a-z0-9]'"), ("text.lower()", "text")]),
    _f("rle_encode(text) writes each run of one repeated character as the length of the run followed by the character ('aaab' gives '3a1b'), and "
       "rle_decode(code) turns such a code back into the text (a length can have several digits; texts hold no digits).", """
def rle_encode(text):
    out, i = [], 0
    while i < len(text):
        j = i
        while j < len(text) and text[j] == text[i]:
            j += 1
        out.append(f'{j - i}{text[i]}')
        i = j
    return ''.join(out)


def rle_decode(code):
    out, count = [], ''
    for ch in code:
        if ch.isdigit():
            count += ch
        else:
            out.append(ch * int(count))
            count = ''
    return ''.join(out)
""", ["rle_encode('aaab')", "rle_encode('')", "rle_encode('abc')", "rle_encode('zzzzzzzzzzzz')", "rle_encode('aabbaa')", "rle_encode('  x')",
      "rle_encode('mississippi')", "rle_decode('3a1b')", "rle_decode('')", "rle_decode('12z')", "rle_decode('1a2b3c')", "rle_decode('2 1-3!')",
      "rle_decode(rle_encode('bookkeeper'))"],
       [("f'{j - i}{text[i]}'", "f'{text[i]}{j - i}'"), ("count += ch", "count = ch")]),
    _f("caesar(text, shift) moves every letter shift places along the alphabet, wrapping round from z to a and keeping upper and lower case; other "
       "characters stay as they are, and shift may be negative or larger than 26.", """
def caesar(text, shift):
    out = []
    for ch in text:
        if 'a' <= ch <= 'z':
            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
        elif 'A' <= ch <= 'Z':
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        else:
            out.append(ch)
    return ''.join(out)
""", ["caesar('abc', 1)", "caesar('xyz', 3)", "caesar('Hello, World!', 5)", "caesar('Hello, World!', -5)", "caesar('abc', 26)", "caesar('abc', 27)",
      "caesar('ABC', -1)", "caesar('', 4)", "caesar('Zebra 42', 2)", "caesar(caesar('Round trip', 11), -11)", "caesar('mixed CASE', 13)", "caesar('a-b_c', 52)"],
       [("% 26 + 97", "% 25 + 97"), ("% 26 + 65)", "% 26 + 97)"), ("ord(ch) - 97 + shift", "ord(ch) - 97 - shift")]),
    _f("is_anagram(a, b) is True when the two texts use the same letters the same number of times, ignoring upper and lower case and spaces, and False "
       "otherwise.", """
def is_anagram(a, b):
    def key(text):
        return sorted(text.replace(' ', '').lower())
    return key(a) == key(b)
""", ["is_anagram('listen', 'silent')", "is_anagram('Listen', 'Silent')", "is_anagram('dormitory', 'dirty room')", "is_anagram('abc', 'abd')",
      "is_anagram('aab', 'abb')", "is_anagram('', '')", "is_anagram('a', '')", "is_anagram('The eyes', 'They see')", "is_anagram('night', 'thing')",
      "is_anagram('abc', 'abcc')", "is_anagram('Astronomer', 'Moon starer')", "is_anagram('rat', 'car')"],
       [(".lower()", ""), ("sorted(", "set("), (".replace(' ', '')", "")]),
    _f("flatten(items) returns the values of a list that may hold lists inside lists, to any depth, as one flat list in their order; only lists are "
       "opened (a tuple or a string is one value).", """
def flatten(items):
    out = []
    for item in items:
        if isinstance(item, list):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out
""", ["flatten([1, 2, 3])", "flatten([1, [2, 3]])", "flatten([[1], [2, [3, [4]]]])", "flatten([])", "flatten([[], [[]]])", "flatten(['a', ['b', ['c']]])",
      "flatten([[1, 2], 3, [4, [5, 6]]])", "flatten([[[[7]]]])", "flatten([0, [None], [False]])", "flatten([(1, 2), [3]])", "flatten([[1, [2]], [], 3])",
      "flatten(['ab', ['cd']])"],
       [("out.extend(flatten(item))", "out.extend(item)"), ("isinstance(item, list)", "isinstance(item, (list, tuple))")]),
    _f("dedupe(items) returns the items without repeats, each kept at the place where it first appears.", """
def dedupe(items):
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
""", ["dedupe([1, 2, 1, 3, 2])", "dedupe([])", "dedupe(['b', 'a', 'b'])", "dedupe([3, 3, 3])", "dedupe([1, 2, 3])", "dedupe(['x', 'X', 'x'])",
      "dedupe([5, 4, 3, 4, 5])", "dedupe(['pen', 'cup', 'pen', 'lamp', 'cup'])", "dedupe([None, None])", "dedupe([1.5, 2, 1.5])", "dedupe(list('banana'))",
      "dedupe([10, 20, 10, 30, 20, 40])"],
       [("if item not in seen:", "if item not in out[-1:]:"), ("return out", "return sorted(seen)")]),
    _f("snake_to_camel(name) turns a snake_case name into camelCase: the underscores go, the letter after each one becomes a capital, and the first word "
       "stays as it is.", """
def snake_to_camel(name):
    first, *rest = name.split('_')
    return first + ''.join(word[:1].upper() + word[1:] for word in rest)
""", ["snake_to_camel('user_id')", "snake_to_camel('first_name')", "snake_to_camel('a')", "snake_to_camel('')", "snake_to_camel('total_amount_due')",
      "snake_to_camel('x_y_z')", "snake_to_camel('already')", "snake_to_camel('http_server_port')", "snake_to_camel('version_2_build')",
      "snake_to_camel('make_it_work')", "snake_to_camel('one_two')", "snake_to_camel('max_retry_count')"],
       [("return first + ", "return first.capitalize() + "), ("word[1:]", "word[2:]"), ("split('_')", "split('-')")]),
    _f("camel_to_snake(name) turns a camelCase name into snake_case: an underscore goes before each capital letter except at the very start, and every "
       "letter ends up in lower case.", """
def camel_to_snake(name):
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append('_')
        out.append(ch.lower())
    return ''.join(out)
""", ["camel_to_snake('userId')", "camel_to_snake('firstName')", "camel_to_snake('a')", "camel_to_snake('')", "camel_to_snake('totalAmountDue')",
      "camel_to_snake('X')", "camel_to_snake('already_snake')", "camel_to_snake('MaxValue')", "camel_to_snake('version2Build')", "camel_to_snake('aB')",
      "camel_to_snake('loadConfigFile')", "camel_to_snake('getX')"],
       [("if ch.isupper() and i > 0:", "if ch.isupper():"), ("out.append(ch.lower())", "out.append(ch)")]),
    _f("hex_to_rgb(code) turns a colour written as six hex digits, like '#ff8800' (the '#' may be missing and the letters may be in either case), into "
       "a tuple of three integers, here (255, 136, 0).", """
def hex_to_rgb(code):
    code = code.lstrip('#')
    return tuple(int(code[i:i + 2], 16) for i in (0, 2, 4))
""", ["hex_to_rgb('#ff8800')", "hex_to_rgb('ff8800')", "hex_to_rgb('#FFFFFF')", "hex_to_rgb('#000000')", "hex_to_rgb('#0a0b0c')", "hex_to_rgb('123456')",
      "hex_to_rgb('#AbCdEf')", "hex_to_rgb('#7f7f7f')", "hex_to_rgb('#ff0000')", "hex_to_rgb('00ff00')", "hex_to_rgb('#0000FF')", "hex_to_rgb('#c0ffee')"],
       [("(0, 2, 4)", "(0, 1, 2)"), ("code.lstrip('#')", "code[1:]"), ("int(code[i:i + 2], 16)", "int(code[i:i + 2], 10)")]),
    _f("rgb_to_hex(r, g, b) writes three integers from 0 to 255 as a colour '#rrggbb' in lower case with two hex digits each, and raises ValueError for "
       "a value outside 0 to 255.", """
def rgb_to_hex(r, g, b):
    for value in (r, g, b):
        if not 0 <= value <= 255:
            raise ValueError(value)
    return '#%02x%02x%02x' % (r, g, b)
""", ["rgb_to_hex(255, 136, 0)", "rgb_to_hex(0, 0, 0)", "rgb_to_hex(255, 255, 255)", "rgb_to_hex(10, 11, 12)", "rgb_to_hex(1, 2, 3)",
      "rgb_to_hex(127, 127, 127)", "rgb_to_hex(192, 255, 238)", "rgb_to_hex(16, 32, 48)", "rgb_to_hex(0, 128, 255)", "rgb_to_hex(256, 0, 0)",
      "rgb_to_hex(0, -1, 0)", "rgb_to_hex(15, 15, 15)"],
       [("'#%02x%02x%02x'", "'#%x%x%x'"), ("<= value <= 255", "<= value < 255"), ("% (r, g, b)", "% (r, b, g)")]),
    _f("balanced(text) is True when every (, [ and { in the text is closed by its matching bracket in the right order, and False otherwise; other "
       "characters do not matter.", """
def balanced(text):
    pairs, open_ = {')': '(', ']': '[', '}': '{'}, []
    for ch in text:
        if ch in '([{':
            open_.append(ch)
        elif ch in pairs:
            if not open_ or open_.pop() != pairs[ch]:
                return False
    return not open_
""", ["balanced('')", "balanced('()')", "balanced('([]{})')", "balanced('(]')", "balanced('((')", "balanced('))')", "balanced('a(b[c]d)e')",
      "balanced('{[}]')", "balanced('f(x) = [1, 2]')", "balanced(')(')", "balanced('{{[[(())]]}}')", "balanced('[(])')"],
       [("return not open_", "return True"), ("open_.pop() != pairs[ch]", "open_.pop() == ch"), ("if not open_ or open_.pop()", "if open_.pop()")]),
    _f("binary_search(xs, target) returns the index of target in xs, a sorted list of distinct values, or -1 when target is not in it.", """
def binary_search(xs, target):
    lo, hi = 0, len(xs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if xs[mid] == target:
            return mid
        if xs[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
""", ["binary_search([1, 3, 5, 7], 5)", "binary_search([1, 3, 5, 7], 1)", "binary_search([1, 3, 5, 7], 7)", "binary_search([1, 3, 5, 7], 4)",
      "binary_search([], 1)", "binary_search([9], 9)", "binary_search([9], 8)", "binary_search(list(range(0, 100, 3)), 99)",
      "binary_search(list(range(0, 100, 3)), 98)", "binary_search([-5, -2, 0, 4], -5)", "binary_search([2, 4, 6, 8, 10, 12], 12)",
      "binary_search([2, 4, 6, 8, 10, 12], 0)"],
       [("while lo <= hi:", "while lo < hi:"), ("len(xs) - 1", "len(xs) - 2"), ("return mid", "return xs[mid]")]),
    _f("merge_sorted(a, b) merges two lists that are each sorted into one sorted list, keeping repeated values.", """
def merge_sorted(a, b):
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i])
            i += 1
        else:
            out.append(b[j])
            j += 1
    return out + a[i:] + b[j:]
""", ["merge_sorted([1, 3, 5], [2, 4, 6])", "merge_sorted([], [])", "merge_sorted([1, 2], [])", "merge_sorted([], [3])", "merge_sorted([1, 1, 2], [1, 3])",
      "merge_sorted([5, 6], [1, 2])", "merge_sorted([1, 4, 9], [2, 3, 10, 11])", "merge_sorted(['a', 'c'], ['b'])", "merge_sorted([0], [0])",
      "merge_sorted([-3, 0, 7], [-5, 8])", "merge_sorted([2, 2, 2], [2])", "merge_sorted([1, 10, 100], [5, 50, 500])"],
       [("out + a[i:] + b[j:]", "out + a[i:]"), ("if a[i] <= b[j]:", "if a[i] >= b[j]:"), ("a[i:] + b[j:]", "a[i + 1:] + b[j:]")]),
    _f("rotate(xs, k) returns a new list with the items moved k places to the right, those falling off the end coming round to the front; a negative k "
       "moves them to the left, k may be larger than the list, and an empty list gives an empty list.", """
def rotate(xs, k):
    if not xs:
        return []
    k %= len(xs)
    return xs[-k:] + xs[:-k]
""", ["rotate([1, 2, 3, 4, 5], 1)", "rotate([1, 2, 3, 4, 5], 2)", "rotate([1, 2, 3, 4, 5], 0)", "rotate([1, 2, 3, 4, 5], 5)", "rotate([1, 2, 3, 4, 5], 7)",
      "rotate([1, 2, 3, 4, 5], -1)", "rotate([1, 2, 3, 4, 5], -6)", "rotate([], 3)", "rotate(['a'], 4)", "rotate(['a', 'b'], 1)", "rotate([1, 2, 3], -3)",
      "rotate([1, 2, 3, 4], 102)"],
       [("xs[-k:] + xs[:-k]", "xs[k:] + xs[:k]"), ("    k %= len(xs)\n", ""), ("    if not xs:\n        return []\n", "")]),
    _f("digit_sum(n) adds up the decimal digits of the integer n; a minus sign is ignored.", """
def digit_sum(n):
    return sum(int(d) for d in str(abs(n)))
""", ["digit_sum(0)", "digit_sum(7)", "digit_sum(10)", "digit_sum(123)", "digit_sum(999)", "digit_sum(-45)", "digit_sum(1000001)", "digit_sum(98765)",
      "digit_sum(-9)", "digit_sum(5050)", "digit_sum(11111)", "digit_sum(2026)"],
       [("str(abs(n))", "str(n)"), ("str(abs(n))", "str(abs(n))[1:]")]),
    _f("is_leap(year) is True for a leap year of the Gregorian calendar: a year divisible by 4, except a year divisible by 100 that is not divisible by "
       "400.", """
def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
""", ["is_leap(2024)", "is_leap(2023)", "is_leap(1900)", "is_leap(2000)", "is_leap(2100)", "is_leap(2400)", "is_leap(1996)", "is_leap(1999)",
      "is_leap(1600)", "is_leap(1700)", "is_leap(4)", "is_leap(2028)"],
       [("year % 400 == 0", "year % 400 != 0"), ("(year % 100 != 0 or year % 400 == 0)", "year % 100 != 0"), ("year % 4 == 0 and", "year % 4 == 0 or")]),
    _f("days_in_month(year, month) returns the number of days in a month (1 to 12) of a year, with 29 for February in a leap year (divisible by 4, "
       "except centuries not divisible by 400); any other month number raises ValueError.", """
def days_in_month(year, month):
    if not 1 <= month <= 12:
        raise ValueError(month)
    if month == 2:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    return 30 if month in (4, 6, 9, 11) else 31
""", ["days_in_month(2026, 1)", "days_in_month(2026, 2)", "days_in_month(2024, 2)", "days_in_month(1900, 2)", "days_in_month(2000, 2)",
      "days_in_month(2026, 4)", "days_in_month(2026, 6)", "days_in_month(2026, 7)", "days_in_month(2026, 9)", "days_in_month(2026, 12)",
      "days_in_month(2026, 11)", "days_in_month(2026, 13)", "days_in_month(2026, 0)"],
       [("(4, 6, 9, 11)", "(4, 6, 8, 11)"), ("year % 100 != 0 or year % 400 == 0", "year % 100 != 0"), ("<= month <= 12", "<= month <= 13")]),
    _f("word_freq(text) counts the words in a text, a word being a run of the letters a to z taken in lower case, and returns a dict from each word to "
       "its count.", """
import re


def word_freq(text):
    counts = {}
    for word in re.findall('[a-z]+', text.lower()):
        counts[word] = counts.get(word, 0) + 1
    return counts
""", ["word_freq('')", "word_freq('one')", "word_freq('a a b')", "word_freq('The the THE')", "word_freq('red, green; red!')", "word_freq(\"it's here\")",
      "word_freq('x1y2')", "word_freq('Apple apple pie')", "word_freq('  spaced   out  ')", "word_freq('to be or not to be')", "word_freq('one-two one')",
      "word_freq('Sun sun SUN moon')"],
       [("text.lower()", "text"), ("counts.get(word, 0) + 1", "1"), ("'[a-z]+'", "'[a-z]'")]),
    _f("transpose(matrix) swaps the rows and columns of a matrix given as a list of equal-length lists and returns a list of lists; an empty matrix "
       "gives an empty list.", """
def transpose(matrix):
    return [list(row) for row in zip(*matrix)]
""", ["transpose([[1, 2], [3, 4]])", "transpose([[1, 2, 3]])", "transpose([[1], [2], [3]])", "transpose([])", "transpose([[1, 2, 3], [4, 5, 6]])",
      "transpose([['a', 'b'], ['c', 'd'], ['e', 'f']])", "transpose([[0]])", "transpose([[1, 2], [3, 4], [5, 6]])", "transpose([[7, 8, 9], [1, 2, 3], [4, 5, 6]])",
      "transpose([[None, True]])", "transpose([[1, 1], [1, 1]])", "transpose([[2, 4, 6, 8]])"],
       [("zip(*matrix)", "zip(matrix)"), ("[list(row) for row in zip(*matrix)]", "list(zip(*matrix))")]),
    _f("running_sum(xs) returns a list whose item i is the sum of xs[0] up to and including xs[i].", """
def running_sum(xs):
    out, total = [], 0
    for x in xs:
        total += x
        out.append(total)
    return out
""", ["running_sum([])", "running_sum([5])", "running_sum([1, 2, 3])", "running_sum([1, 1, 1, 1])", "running_sum([3, -1, 4])", "running_sum([0, 0])",
      "running_sum([10, 20, 30, 40])", "running_sum([-5, 5, -5])", "running_sum([2.5, 2.5])", "running_sum([100])", "running_sum([1, 2, 3, 4, 5, 6])",
      "running_sum([7, 0, 7])"],
       [("        total += x\n        out.append(total)", "        out.append(total)\n        total += x"), ("total += x", "total = x")]),
    _f("c_to_f(c) turns degrees Celsius into Fahrenheit (F = C * 9 / 5 + 32) and f_to_c(f) does the opposite; both round the result to one decimal "
       "with round().", """
def c_to_f(c):
    return round(c * 9 / 5 + 32, 1)


def f_to_c(f):
    return round((f - 32) * 5 / 9, 1)
""", ["c_to_f(0)", "c_to_f(100)", "c_to_f(-40)", "c_to_f(37)", "c_to_f(21.5)", "c_to_f(-10)", "f_to_c(32)", "f_to_c(212)", "f_to_c(98.6)", "f_to_c(0)",
      "f_to_c(-40)", "f_to_c(100)", "f_to_c(50)"],
       [("(f - 32) * 5 / 9", "f - 32 * 5 / 9"), ("c * 9 / 5 + 32", "c * 5 / 9 + 32"), ("round((f - 32) * 5 / 9, 1)", "round((f - 32) * 5 / 9)")]),
]
FUNCS += [
    _f("title_case(text) gives every word a capital first letter and lower case for the rest, except the small words a, an, the, and, but, or, of, "
       "in, on, at, to and for, which are all lower case unless they are the first or the last word; words are separated by single spaces.", """
SMALL_WORDS = {'a', 'an', 'the', 'and', 'but', 'or', 'of', 'in', 'on', 'at', 'to', 'for'}


def title_case(text):
    words = text.split(' ')
    out = []
    for i, word in enumerate(words):
        low = word.lower()
        if low in SMALL_WORDS and 0 < i < len(words) - 1:
            out.append(low)
        else:
            out.append(low[:1].upper() + low[1:])
    return ' '.join(out)
""", ["title_case('the house on the hill')", "title_case('a walk in the park')", "title_case('BREAD AND SALT')", "title_case('out of the blue')",
      "title_case('')", "title_case('of')", "title_case('up to the top')", "title_case('the lamp in the tent')", "title_case('what it is for')",
      "title_case('an end')", "title_case('north by north')", "title_case('salt AND pepper')"],
       [("0 < i < len(words) - 1", "0 < i"), ("low[:1].upper() + low[1:]", "word[:1].upper() + word[1:]"), ("if low in SMALL_WORDS", "if word in SMALL_WORDS")]),
    _f("wrap(text, width) breaks a text into lines of at most width characters, putting as many whole words on each line as fit, with one space "
       "between words; a word longer than width gets a line of its own. It returns the list of lines.", """
def wrap(text, width):
    lines, line = [], ''
    for word in text.split():
        if not line:
            line = word
        elif len(line) + 1 + len(word) <= width:
            line += ' ' + word
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines
""", ["wrap('the quick brown fox', 10)", "wrap('', 5)", "wrap('word', 10)", "wrap('a b c d e', 3)", "wrap('extraordinary', 5)",
      "wrap('one two three four five six', 9)", "wrap('aa bb cc', 5)", "wrap('hello world', 11)", "wrap('hello world', 10)", "wrap('x x x x x', 1)",
      "wrap('pack my box with five dozen jugs', 12)", "wrap('a verylongword b', 4)"],
       [("len(line) + 1 + len(word) <= width", "len(line) + len(word) <= width"), ("len(line) + 1 + len(word) <= width", "len(line) + 1 + len(word) < width"),
        ("    if line:\n        lines.append(line)\n", "")]),
    _f("parse_kv(line) splits a line like 'name = value' at its first '=' and returns the pair (key, value) with the spaces round each taken off; a line "
       "without '=' or with an empty key raises ValueError.", """
def parse_kv(line):
    if '=' not in line:
        raise ValueError(line)
    key, value = line.split('=', 1)
    key, value = key.strip(), value.strip()
    if not key:
        raise ValueError(line)
    return key, value
""", ["parse_kv('a=1')", "parse_kv('name = Ana')", "parse_kv('  port=8080  ')", "parse_kv('url = x=y')", "parse_kv('empty =')",
      "parse_kv('k=  spaced value  ')", "parse_kv('path=/tmp/a b')", "parse_kv('x = =quoted')", "parse_kv('MiXeD = Case')", "parse_kv('novalue')",
      "parse_kv('= 5')", "parse_kv('')"],
       [("line.split('=', 1)", "line.split('=')"), ("key.strip(), value.strip()", "key.strip(), value"), ("if not key:", "if not value:")]),
    _f("compare_versions(a, b) compares two versions written as numbers and dots ('1.10.2'): it returns -1 when a is older, 1 when a is newer and 0 "
       "when they are the same; the parts compare as numbers, and a missing part counts as 0 ('1.0' is the same as '1').", """
def compare_versions(a, b):
    xs = [int(part) for part in a.split('.')]
    ys = [int(part) for part in b.split('.')]
    n = max(len(xs), len(ys))
    xs += [0] * (n - len(xs))
    ys += [0] * (n - len(ys))
    return (xs > ys) - (xs < ys)
""", ["compare_versions('1.0', '1.0')", "compare_versions('1.0', '1')", "compare_versions('1.2', '1.10')", "compare_versions('2.0', '1.99')",
      "compare_versions('1.0.1', '1.0')", "compare_versions('0.9', '1')", "compare_versions('3.4.5', '3.4.5')", "compare_versions('10.0', '9.9.9')",
      "compare_versions('1.01', '1.1')", "compare_versions('1.0.0.0', '1')", "compare_versions('2.1', '2.1.1')", "compare_versions('7', '7.0.0')"],
       [("    xs += [0] * (n - len(xs))\n", ""), ("(xs > ys) - (xs < ys)", "(xs < ys) - (xs > ys)"), ("[int(part) for part in a.split('.')]", "a.split('.')")]),
    _f("ordinal(n) writes a positive integer with its English ending: 1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st, 22nd, 101st, 111th, 112th and so on.", """
def ordinal(n):
    if 10 <= n % 100 <= 20:
        return f'{n}th'
    return str(n) + {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
""", ["ordinal(1)", "ordinal(2)", "ordinal(3)", "ordinal(4)", "ordinal(11)", "ordinal(12)", "ordinal(13)", "ordinal(21)", "ordinal(22)", "ordinal(23)",
      "ordinal(101)", "ordinal(111)", "ordinal(112)", "ordinal(1000)", "ordinal(1003)"],
       [("10 <= n % 100 <= 20", "10 <= n <= 20"), (".get(n % 10, 'th')", ".get(n, 'th')")]),
    _f("initials(name) returns the first letter of each part of a name as a capital, with no spaces or dots; parts are separated by spaces or hyphens.", """
def initials(name):
    return ''.join(word[0].upper() for word in name.replace('-', ' ').split())
""", ["initials('ana bo')", "initials('Kit')", "initials('')", "initials('  wren   yara  ')", "initials('lena-rosa quin')", "initials('uma vik sol')",
      "initials('Milo Oren Pia Tess')", "initials('x-y-z')", "initials('cy')", "initials('Hana  Ivo')", "initials('jun-kit')", "initials('bo uma-zed')"],
       [(".replace('-', ' ')", ""), ("word[0].upper()", "word[0]"), (".split())", ".split(' '))")]),
    _f("truncate(text, limit) returns the text unchanged when it has at most limit characters, and otherwise its first limit - 3 characters followed "
       "by '...', so that the result is exactly limit characters long.", """
def truncate(text, limit):
    if len(text) <= limit:
        return text
    return text[:limit - 3] + '...'
""", ["truncate('hello', 10)", "truncate('hello', 5)", "truncate('hello world', 8)", "truncate('abcdefghij', 9)", "truncate('', 3)", "truncate('abcd', 3)",
      "truncate('short', 6)", "truncate('a much longer sentence', 12)", "truncate('exact', 5)", "truncate('xyz', 4)", "truncate('1234567890', 7)",
      "truncate('two words', 8)"],
       [("text[:limit - 3]", "text[:limit]"), ("len(text) <= limit", "len(text) < limit")]),
    _f("second_largest(xs) returns the second largest distinct value in a list of numbers, and raises ValueError when there are fewer than two "
       "distinct values.", """
def second_largest(xs):
    values = sorted(set(xs))
    if len(values) < 2:
        raise ValueError('fewer than two distinct values')
    return values[-2]
""", ["second_largest([1, 2, 3])", "second_largest([3, 2, 1])", "second_largest([5, 5, 4])", "second_largest([10, 10, 10, 9])", "second_largest([-1, -2])",
      "second_largest([0, 100, 50, 100])", "second_largest([2.5, 1.5])", "second_largest([1, 9, 8, 9, 7])", "second_largest([3, 1, 3, 2])",
      "second_largest([7])", "second_largest([])", "second_largest([4, 4])"],
       [("sorted(set(xs))", "sorted(xs)"), ("values[-2]", "values[1]"), ("len(values) < 2", "len(values) < 1")]),
    _f("normalize_space(text) replaces every run of spaces, tabs and line breaks with a single space and removes them at both ends.", """
def normalize_space(text):
    return ' '.join(text.split())
""", ["normalize_space('a  b')", "normalize_space('  lead and trail  ')", "normalize_space('a\\tb')", "normalize_space('line one\\nline two')",
      "normalize_space('')", "normalize_space('   ')", "normalize_space('one')", "normalize_space('x \\t\\n y')", "normalize_space('many     spaces   here')",
      "normalize_space('\\ttabbed\\t')", "normalize_space('a b c')", "normalize_space('mixed \\n\\n gaps')"],
       [("text.split()", "text.split(' ')"), ("' '.join(text.split())", "text.strip()")]),
    _f("luhn_valid(number) checks a string of digits (spaces allowed and ignored) with the Luhn checksum: from the right, double every second digit, "
       "subtract 9 from a doubled digit over 9, and add everything up; it is valid when that sum ends in 0. Any other character, or fewer than two "
       "digits, makes it not valid.", """
def luhn_valid(number):
    digits = number.replace(' ', '')
    if len(digits) < 2 or not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0
""", ["luhn_valid('79927398713')", "luhn_valid('79927398710')", "luhn_valid('4539 3195 0343 6467')", "luhn_valid('8273 1232 7352 0569')",
      "luhn_valid('0')", "luhn_valid('00')", "luhn_valid('059')", "luhn_valid('12a4')", "luhn_valid('')", "luhn_valid('18')",
      "luhn_valid('4111 1111 1111 1111')", "luhn_valid('1234 5678 9012 3456')"],
       [("if i % 2 == 1:", "if i % 2 == 0:"), ("d -= 9", "d -= 10"), ("number.replace(' ', '')", "number")]),
    _f("is_valid_ipv4(text) is True for four decimal numbers from 0 to 255 joined by dots, with no signs, spaces or leading zeros (a single 0 is fine), "
       "and False for anything else.", """
def is_valid_ipv4(text):
    parts = text.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit() or (len(part) > 1 and part[0] == '0') or int(part) > 255:
            return False
    return True
""", ["is_valid_ipv4('10.20.30.40')", "is_valid_ipv4('0.0.0.0')", "is_valid_ipv4('255.255.255.255')", "is_valid_ipv4('256.1.1.1')", "is_valid_ipv4('1.2.3')",
      "is_valid_ipv4('1.2.3.4.5')", "is_valid_ipv4('01.2.3.4')", "is_valid_ipv4('1.2.3.a')", "is_valid_ipv4('')", "is_valid_ipv4('1..2.3')",
      "is_valid_ipv4('172.16.0.255')", "is_valid_ipv4(' 1.2.3.4')", "is_valid_ipv4('-1.2.3.4')"],
       [("int(part) > 255", "int(part) > 256"), ("(len(part) > 1 and part[0] == '0') or ", ""), ("len(parts) != 4", "len(parts) < 4")]),
    _f("common_prefix(words) returns the longest beginning that all the strings in the list share, and '' for an empty list.", """
def common_prefix(words):
    if not words:
        return ''
    prefix = words[0]
    for word in words[1:]:
        while not word.startswith(prefix):
            prefix = prefix[:-1]
    return prefix
""", ["common_prefix(['flower', 'flow', 'flight'])", "common_prefix(['dog', 'racecar'])", "common_prefix([])", "common_prefix(['alone'])",
      "common_prefix(['same', 'same'])", "common_prefix(['prefix', 'pre', 'presto'])", "common_prefix(['', 'a'])", "common_prefix(['abc', 'abd', 'abe'])",
      "common_prefix(['Case', 'case'])", "common_prefix(['interview', 'internet', 'interval'])", "common_prefix(['a', 'a', 'b'])",
      "common_prefix(['123', '1234', '12'])"],
       [("for word in words[1:]:", "for word in words[2:]:"), ("prefix = prefix[:-1]", "prefix = prefix[1:]"), ("    if not words:\n        return ''\n", "")]),
    _f("interleave(a, b) takes items from the two lists in turn, starting with a; when one list runs out, the rest of the other follows.", """
def interleave(a, b):
    out = []
    for i in range(max(len(a), len(b))):
        if i < len(a):
            out.append(a[i])
        if i < len(b):
            out.append(b[i])
    return out
""", ["interleave([1, 2], ['a', 'b'])", "interleave([], [])", "interleave([1, 2, 3], [])", "interleave([], [4])", "interleave([1], [2, 3, 4])",
      "interleave([1, 3, 5, 7], [2, 4])", "interleave(['x'], ['y'])", "interleave([0, 0], [1, 1])", "interleave(['a', 'b', 'c'], ['1', '2', '3'])",
      "interleave([None], [True, False])", "interleave([5, 6, 7], [8])", "interleave([1, 2], [3, 4, 5, 6])"],
       [("max(len(a), len(b))", "min(len(a), len(b))"), ("if i < len(a):", "if i <= len(a):")]),
    _f("find_duplicates(items) returns, in sorted order, each value that occurs more than once in the list, each of them once.", """
def find_duplicates(items):
    seen, dupes = set(), set()
    for item in items:
        if item in seen:
            dupes.add(item)
        seen.add(item)
    return sorted(dupes)
""", ["find_duplicates([1, 2, 3])", "find_duplicates([1, 2, 1])", "find_duplicates([])", "find_duplicates([3, 3, 3])", "find_duplicates([5, 4, 5, 4, 3])",
      "find_duplicates(['b', 'a', 'b', 'a'])", "find_duplicates([1, 2, 2, 3, 3, 3])", "find_duplicates([0, 0])", "find_duplicates(['x'])",
      "find_duplicates([9, 1, 9, 2, 1])", "find_duplicates([10, 2, 10, 2, 7, 7])", "find_duplicates(list('mississippi'))"],
       [("if item in seen:", "if item not in seen:"), ("\n        seen.add(item)", "\n            seen.add(item)")]),
    _f("pascal_row(n) returns row n of Pascal's triangle as a list, counting the top row [1] as row 0.", """
def pascal_row(n):
    row = [1]
    for _ in range(n):
        row = [1] + [row[i] + row[i + 1] for i in range(len(row) - 1)] + [1]
    return row
""", ["pascal_row(0)", "pascal_row(1)", "pascal_row(2)", "pascal_row(3)", "pascal_row(4)", "pascal_row(5)", "pascal_row(6)", "pascal_row(7)",
      "pascal_row(8)", "pascal_row(10)", "pascal_row(12)", "pascal_row(15)"],
       [("range(n)", "range(n - 1)"), ("row[i] + row[i + 1]", "row[i] * row[i + 1]")]),
    _f("collatz_steps(n) counts the steps from a positive integer n down to 1, where a step halves an even number and turns an odd number m into "
       "3 * m + 1 (so collatz_steps(1) is 0); n below 1 raises ValueError.", """
def collatz_steps(n):
    if n < 1:
        raise ValueError(n)
    steps = 0
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
    return steps
""", ["collatz_steps(1)", "collatz_steps(2)", "collatz_steps(3)", "collatz_steps(6)", "collatz_steps(7)", "collatz_steps(9)", "collatz_steps(12)",
      "collatz_steps(16)", "collatz_steps(27)", "collatz_steps(97)", "collatz_steps(0)", "collatz_steps(-5)"],
       [("while n != 1:", "while n > 2:"), ("steps = 0", "steps = 1")]),
    _f("to_base(n, base) writes a non-negative integer in a base from 2 to 16, using the digits 0-9 and then the lower-case letters a-f; to_base(0, "
       "base) is '0'.", """
BASE_DIGITS = '0123456789abcdef'


def to_base(n, base):
    if n == 0:
        return '0'
    out = ''
    while n > 0:
        out = BASE_DIGITS[n % base] + out
        n //= base
    return out
""", ["to_base(0, 2)", "to_base(5, 2)", "to_base(255, 16)", "to_base(255, 2)", "to_base(10, 10)", "to_base(8, 8)", "to_base(100, 7)", "to_base(4095, 16)",
      "to_base(1, 3)", "to_base(31, 16)", "to_base(6, 6)", "to_base(123456, 16)"],
       [("out = BASE_DIGITS[n % base] + out", "out = out + BASE_DIGITS[n % base]"), ("    if n == 0:\n        return '0'\n", ""),
        ("'0123456789abcdef'", "'0123456789ABCDEF'")]),
    _f("nested_get(data, path, default=None) follows a dotted path such as 'a.b.c' through nested dicts and returns the value at its end, or default "
       "when a key on the way is missing or a value on the way is not a dict.", """
def nested_get(data, path, default=None):
    for key in path.split('.'):
        if not isinstance(data, dict) or key not in data:
            return default
        data = data[key]
    return data
""", ["nested_get({'a': 1}, 'a')", "nested_get({'a': {'b': 2}}, 'a.b')", "nested_get({'a': {'b': {'c': 3}}}, 'a.b.c')", "nested_get({}, 'a')",
      "nested_get({'a': 1}, 'b', 0)", "nested_get({'a': {'b': 2}}, 'a.c', 'none')", "nested_get({'a': 1}, 'a.b')", "nested_get({'a': 1}, 'a.b', -1)",
      "nested_get({'x': {'y': [1, 2]}}, 'x.y')", "nested_get({'k': {'k': {'k': 'deep'}}}, 'k.k.k')", "nested_get({'a': {'b': 2}}, 'a')",
      "nested_get({'1': 'one'}, '1')"],
       [("if not isinstance(data, dict) or key not in data:", "if key not in data:"), ("return default", "return None")]),
    _f("invert_dict(d) returns a dict from each value of d to the sorted list of the keys that have that value.", """
def invert_dict(d):
    out = {}
    for key, value in d.items():
        out.setdefault(value, []).append(key)
    return {value: sorted(keys) for value, keys in out.items()}
""", ["invert_dict({})", "invert_dict({'a': 1})", "invert_dict({'a': 1, 'b': 1})", "invert_dict({'a': 1, 'b': 2})", "invert_dict({'x': 'k', 'y': 'k', 'z': 'm'})",
      "invert_dict({'b': 0, 'a': 0, 'c': 0})", "invert_dict({1: 'odd', 2: 'even', 3: 'odd'})", "invert_dict({'pen': 2, 'cup': 8, 'mug': 8})",
      "invert_dict({'only': None})", "invert_dict({'q': 5, 'r': 6, 's': 5, 't': 6})", "invert_dict({'a': 'x', 'b': 'y', 'c': 'z'})", "invert_dict({'z': 1, 'y': 1})"],
       [("sorted(keys)", "keys"), ("out.setdefault(value, []).append(key)", "out[value] = [key]")]),
    _f("bytes_to_human(n) writes a number of bytes for people: below 1024 as '512 B', otherwise divided by 1024 as many times as it takes to fall below "
       "1024 (KB, MB, GB, at most TB) and written with one decimal, as in '1.5 KB'.", """
def bytes_to_human(n):
    if n < 1024:
        return f'{n} B'
    size = float(n)
    for unit in ('KB', 'MB', 'GB', 'TB'):
        size /= 1024
        if size < 1024 or unit == 'TB':
            return f'{size:.1f} {unit}'
""", ["bytes_to_human(0)", "bytes_to_human(1)", "bytes_to_human(512)", "bytes_to_human(1023)", "bytes_to_human(1024)", "bytes_to_human(1536)",
      "bytes_to_human(1048576)", "bytes_to_human(5 * 1024 ** 2)", "bytes_to_human(1073741824)", "bytes_to_human(3 * 1024 ** 4)",
      "bytes_to_human(2048 * 1024 ** 4)", "bytes_to_human(123456789)"],
       [("if n < 1024:", "if n <= 1024:"), (":.1f}", ":.0f}"), ("size /= 1024", "size /= 1000")]),
    _f("reverse_words(text) returns the words of the text in reverse order, joined by single spaces (any run of spaces or tabs separates words).", """
def reverse_words(text):
    return ' '.join(reversed(text.split()))
""", ["reverse_words('hello world')", "reverse_words('one')", "reverse_words('')", "reverse_words('a b c')", "reverse_words('  padded   words  ')",
      "reverse_words('The quick brown fox')", "reverse_words('x y')", "reverse_words('keep punctuation, here!')", "reverse_words('1 2 3 4 5')",
      "reverse_words('same same')", "reverse_words('tab\\tsep')", "reverse_words('end.')"],
       [("text.split()", "text.split(' ')"), ("' '.join(reversed(text.split()))", "' '.join(word[::-1] for word in text.split())")]),
    _f("group_by_length(words) returns a dict from each word length to the list of the words of that length, in the order they came.", """
def group_by_length(words):
    out = {}
    for word in words:
        out.setdefault(len(word), []).append(word)
    return out
""", ["group_by_length([])", "group_by_length(['a'])", "group_by_length(['a', 'bb', 'c'])", "group_by_length(['cat', 'dog', 'emu', 'ox'])",
      "group_by_length(['', 'x'])", "group_by_length(['three', 'four', 'five', 'six'])", "group_by_length(['aa', 'aa'])",
      "group_by_length(['pen', 'lamp', 'cup', 'desk', 'mug'])", "group_by_length(['longest', 'short', 'tiny'])", "group_by_length(['q', 'w', 'e'])",
      "group_by_length(['ab', 'abc', 'abcd', 'abc'])", "group_by_length(['one', 'two', 'three', 'four'])"],
       [(".append(word)", ".insert(0, word)"), ("out.setdefault(len(word), []).append(word)", "out[len(word)] = [word]")]),
    _f("percent_change(old, new) returns the change from old to new as a percentage of old, rounded to one decimal with round(); an old value of 0 "
       "raises ValueError.", """
def percent_change(old, new):
    if old == 0:
        raise ValueError('old is 0')
    return round((new - old) / old * 100, 1)
""", ["percent_change(100, 110)", "percent_change(100, 90)", "percent_change(50, 75)", "percent_change(80, 80)", "percent_change(200, 50)",
      "percent_change(3, 4)", "percent_change(3, 2)", "percent_change(1, 3)", "percent_change(40, 41)", "percent_change(7, 10)", "percent_change(12.5, 25)",
      "percent_change(0, 5)"],
       [("(new - old) / old", "(new - old) / new"), ("if old == 0:", "if new == 0:")]),
]
BUGGY = [entry for entry in FUNCS if entry["bugs"]]


@family
def function_to_test(rng):
    """Write a function (or a pair) into a new module so that a test file that is given passes, the test unchanged."""
    entry = rng.choice(FUNCS)
    module = rng.choice((*entry["names"][:len(entry["names"]) == 1], *rng.sample(GENERIC, 2)))
    test, them, spec = f"test_{module}.py", " and ".join(entry["names"]), entry["spec"]
    lines = _checks(rng, entry)
    text, token = _test([(module, entry["names"])], lines, len(lines))
    return {"kind": "code", "files": {test: text},
            "request": say(rng, f"Write {module}.py so that `python3 {test}` prints '{token}'. It needs {them}: {spec} Do not change {test}.",
                           f"{test} tests code that is not written yet: {them} in {module}.py, where {spec} Write it so that the test passes as it is and "
                           f"prints '{token}'.",
                           f"Please implement {them} in a new file {module}.py: {spec} Check it with `python3 {test}`, which must print '{token}'; leave the "
                           "test file alone."),
            "expect": {"files": {f"{module}.py": [f"def {name}(" for name in entry["names"]], test: text}, "run": (f"python3 {test}", token)},
            "solution": {"answer": f"Wrote {them} in {module}.py; the test prints {token}.", "files": {f"{module}.py": _module([(spec, entry["source"])])}}}


def _buggy_module(rng, entry: dict, bug: tuple, extra: list) -> tuple:
    """A module holding entry with its bug and the extra functions, right and wrong, and the checks of its test."""
    group = [entry, *extra]
    rng.shuffle(group)
    right = _module([(e["spec"], e["source"]) for e in group])
    wrong = _module([(e["spec"], e["source"].replace(*bug, 1) if e is entry else e["source"]) for e in group])
    lines = [line for e in group for line in (_checks(rng, e, bug) if e is entry else _checks(rng, e, count=rng.randint(2, 3)))]
    return right, wrong, [name for e in group for name in e["names"]], lines


@family
def fix_planted_bug(rng):
    """A module of two or three functions, one with a planted mistake that its test shows: fix it, the test unchanged."""
    entry = rng.choice(BUGGY)
    extra = rng.sample([e for e in FUNCS if e is not entry], rng.randint(1, 2))
    module = rng.choice(GENERIC)
    test = f"test_{module}.py"
    right, wrong, names, lines = _buggy_module(rng, entry, rng.choice(entry["bugs"]), extra)
    text, token = _test([(module, names)], lines, len(lines))
    return {"kind": "code", "files": {f"{module}.py": wrong, test: text},
            "request": say(rng, f"`python3 {test}` fails. Find the mistake in {module}.py and correct it so that the test prints '{token}'. Do not edit the test.",
                           f"One of the functions in {module}.py has a bug that {test} catches. Fix the function; {test} itself stays as it is.",
                           f"{test} no longer passes. Read what it reports, repair {module}.py, and leave {test} unchanged; it should end by printing '{token}'."),
            "expect": {"files": {test: text}, "run": (f"python3 {test}", token), "may_change": [f"{module}.py"]},
            "solution": {"answer": f"Fixed {entry['names'][0]} in {module}.py.", "files": {f"{module}.py": right}}}


@family
def fix_two_files(rng):
    """One test over two modules, each with a planted mistake: both must be found and fixed, the test unchanged."""
    first, second = rng.sample(BUGGY, 2)
    rest = rng.sample([e for e in FUNCS if e is not first and e is not second], 2)
    a, b = rng.sample(GENERIC, 2)
    test = f"test_{rng.choice(('all', 'both', a + '_' + b, 'project', 'suite'))}.py"
    right_a, wrong_a, names_a, lines_a = _buggy_module(rng, first, rng.choice(first["bugs"]), rest[:1] if rng.random() < 0.6 else [])
    right_b, wrong_b, names_b, lines_b = _buggy_module(rng, second, rng.choice(second["bugs"]), rest[1:] if rng.random() < 0.6 else [])
    text, token = _test([(a, names_a), (b, names_b)], lines_a + lines_b, len(lines_a + lines_b))
    return {"kind": "multi", "files": {f"{a}.py": wrong_a, f"{b}.py": wrong_b, test: text},
            "request": say(rng, f"`python3 {test}` fails because of two mistakes, one in {a}.py and one in {b}.py. Fix both so that it prints '{token}'; do not "
                                "touch the test.",
                           f"There are two bugs behind the failures in {test}: one in {a}.py and another in {b}.py. Find and fix them, leaving the test as it is.",
                           f"Make `python3 {test}` print '{token}'. Something is wrong in {a}.py and something else in {b}.py; the test itself is right and must "
                           "not change."),
            "expect": {"files": {test: text}, "run": (f"python3 {test}", token), "may_change": [f"{a}.py", f"{b}.py"]},
            "solution": {"answer": f"Fixed {first['names'][0]} in {a}.py and {second['names'][0]} in {b}.py.", "files": {f"{a}.py": right_a, f"{b}.py": right_b}}}


def _c(cls: str, modules: tuple, spec: str, source: str, script: str, values) -> dict:
    """A catalogue class: what it does, a right source, and a test script whose lines are statements, `?expr` checked
    against what the right class gives, or `!Error:expr` that must raise; values(rng) fills the {NAMES} in it."""
    return {"cls": cls, "modules": modules, "spec": spec, "source": source.strip("\n") + "\n", "script": script.strip("\n").split("\n"), "values": values}


def _stub(source: str, cut: set) -> str:
    """The class with each method named in cut left as its def line, its docstring and `raise NotImplementedError`."""
    out, skip, pending = [], False, False
    for line in source.rstrip("\n").split("\n"):
        body = line.startswith("        ")
        if pending and not (body and line.strip().startswith('"""')):
            out.append("        raise NotImplementedError")
            pending = False
        if not body and line.strip():
            name = re.match(r"\s*def (\w+)\(", line)
            skip = pending = bool(name) and name.group(1) in cut
            out.append(line)
        elif not skip or not line.strip() or pending:
            out.append(line)
    if pending:
        out.append("        raise NotImplementedError")
    return "\n".join(out) + "\n"


def _script(rng, entry: dict) -> tuple:
    """The test body for a class and its number of checks, the expected values taken from the right class."""
    values = {key: repr(value) for key, value in entry["values"](rng).items()}
    space, body, checks = _space(entry["source"]), [], 0
    for raw in entry["script"]:
        line = raw.format(**values)
        if line[:1] in "?!":
            expr = line[1:].split(":", 1)[1] if line[0] == "!" else line[1:]
            got = _outcome(expr, space)
            assert got[0] == (line[0] == "?") and (got[0] or got[1] == line[1:].split(":")[0]), (entry["cls"], line, got)
            body.append(_assertion(expr, got))
            checks += 1
        else:
            exec(line, space)
            body.append(line)
    return body, checks


def _things(rng, n: int) -> dict:
    return dict(zip("ABCDEF", rng.sample(THINGS, n)))


CLASSES = [
    # (a first-in, first-out Queue stood here: push/pop/peek/is_empty/size with IndexError when empty is measuring task 70's
    # Stack, turned round)
    _c("Rect", ("shapes", "geometry", "rects"), "Rect(x, y, width, height) is a rectangle with its sides along the axes, given by its lower-left "
       "corner and its size and kept in .x, .y, .width and .height (a negative width or height raises ValueError); area() and perimeter() return "
       "those, contains(px, py) is True for a point inside it or on its edge, overlaps(other) is True when the two share some area (rectangles that "
       "only touch do not), and moved(dx, dy) returns a new Rect shifted by dx and dy.", '''
class Rect:
    """A rectangle with its sides along the axes: its lower-left corner and its size."""

    def __init__(self, x, y, width, height):
        if width < 0 or height < 0:
            raise ValueError('width and height must not be negative')
        self.x, self.y, self.width, self.height = x, y, width, height

    def area(self):
        """Width times height."""
        return self.width * self.height

    def perimeter(self):
        """Twice the width plus twice the height."""
        return 2 * (self.width + self.height)

    def contains(self, px, py):
        """True when the point lies inside or on the edge."""
        return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height

    def overlaps(self, other):
        """True when the two share some area; touching edges do not count."""
        return (self.x < other.x + other.width and other.x < self.x + self.width
                and self.y < other.y + other.height and other.y < self.y + self.height)

    def moved(self, dx, dy):
        """A new Rect shifted by dx and dy."""
        return Rect(self.x + dx, self.y + dy, self.width, self.height)
''', """
r = Rect({X}, {Y}, {W}, {H})
?r.area()
?r.perimeter()
?r.contains({X}, {Y})
?r.contains({X} + {W}, {Y} + {H})
?r.contains({X} - 1, {Y})
?r.contains({X} + {W} // 2, {Y} + {H} + 1)
s = r.moved({W}, 0)
?(s.x, s.y, s.width, s.height)
?r.overlaps(s)
t = r.moved(1, 1)
?r.overlaps(t)
?t.overlaps(r)
?(r.x, r.y)
?Rect(0, 0, 0, 5).area()
!ValueError:Rect(0, 0, -1, 2)
!ValueError:Rect(0, 0, 2, -3)
""", lambda rng: {"X": rng.randint(-5, 10), "Y": rng.randint(-5, 10), "W": rng.randint(2, 9), "H": rng.randint(2, 9)}),
    _c("Tally", ("tally", "counts", "tallies"), "Tally counts things: add(item, n=1) counts item n more times (n below 1 raises ValueError), count(item) "
       "says how many times it was counted (0 if never), total() adds all the counts up, top() returns the item counted most often (on a tie the first "
       "in alphabetical order, and None when nothing was counted) and items() returns (item, count) pairs sorted by item.", '''
class Tally:
    """Counts of things."""

    def __init__(self):
        self.counts = {}

    def add(self, item, n=1):
        """Count item n more times; n below 1 raises ValueError."""
        if n < 1:
            raise ValueError(n)
        self.counts[item] = self.counts.get(item, 0) + n

    def count(self, item):
        """How many times item was counted (0 if never)."""
        return self.counts.get(item, 0)

    def total(self):
        """All the counts added up."""
        return sum(self.counts.values())

    def top(self):
        """The item counted most often, the first alphabetically on a tie; None when empty."""
        if not self.counts:
            return None
        return min(self.counts, key=lambda item: (-self.counts[item], item))

    def items(self):
        """(item, count) pairs sorted by item."""
        return sorted(self.counts.items())
''', """
t = Tally()
?t.top()
?t.total()
t.add({A})
t.add({B}, {N})
t.add({A}, {M})
t.add({C})
?t.count({A})
?t.count({B})
?t.count({D})
?t.total()
?t.top()
?t.items()
!ValueError:t.add({A}, 0)
t.add({C}, {K})
?t.count({C})
?t.top()
?t.total()
""", lambda rng: dict(_things(rng, 4), N=rng.randint(2, 5), M=rng.randint(1, 4), K=rng.randint(2, 6))),
    _c("Matrix", ("matrix", "grid", "matrices"), "Matrix(rows) holds a matrix of numbers given as a list of rows of equal length (ValueError for no rows "
       "or rows of different lengths) and keeps them in .rows; shape() returns (rows, columns), get(i, j) the number in row i and column j (counted "
       "from 0), add(other) the sum and multiply(other) the matrix product, both as new Matrix objects and both raising ValueError when the shapes do "
       "not fit, and transpose() the transposed matrix as a new Matrix.", '''
class Matrix:
    """A matrix of numbers, as a list of rows of equal length."""

    def __init__(self, rows):
        if not rows or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError('rows must be given and of equal length')
        self.rows = [list(row) for row in rows]

    def shape(self):
        """(number of rows, number of columns)."""
        return len(self.rows), len(self.rows[0])

    def get(self, i, j):
        """The number in row i, column j, counted from 0."""
        return self.rows[i][j]

    def add(self, other):
        """The sum as a new Matrix; ValueError when the shapes differ."""
        if self.shape() != other.shape():
            raise ValueError('the shapes differ')
        return Matrix([[a + b for a, b in zip(r, s)] for r, s in zip(self.rows, other.rows)])

    def transpose(self):
        """Rows and columns swapped, as a new Matrix."""
        return Matrix([list(column) for column in zip(*self.rows)])

    def multiply(self, other):
        """The matrix product as a new Matrix; ValueError unless this one has as many columns as the other has rows."""
        if self.shape()[1] != other.shape()[0]:
            raise ValueError('the shapes do not fit')
        columns = list(zip(*other.rows))
        return Matrix([[sum(a * b for a, b in zip(row, column)) for column in columns] for row in self.rows])
''', """
m = Matrix({P})
n = Matrix({Q})
?m.shape()
?m.get(1, 2)
?m.get(0, 0)
?m.add(n).rows
?m.transpose().rows
?m.transpose().shape()
?m.multiply(n.transpose()).rows
?Matrix([[1, 0], [0, 1]]).multiply(Matrix({S})).rows
?m.rows
!ValueError:m.add(Matrix([[1]]))
!ValueError:m.multiply(n)
!ValueError:Matrix([[1, 2], [3]])
!ValueError:Matrix([])
""", lambda rng: {key: [[rng.randint(-3, 9) for _ in range(cols)] for _ in range(2)] for key, cols in (("P", 3), ("Q", 3), ("S", 2))}),
    _c("Inventory", ("inventory", "stockroom", "storeroom"), "Inventory keeps how many of each item are in stock: add(item, qty) adds a positive "
       "quantity (ValueError otherwise), remove(item, qty) takes some out (ValueError when there are fewer than qty; an item that reaches 0 is no "
       "longer listed), quantity(item) says how many there are (0 when none), items() returns the names of the items in stock, sorted, and total() "
       "the number of units altogether.", '''
class Inventory:
    """How many of each item are in stock."""

    def __init__(self):
        self.stock = {}

    def add(self, item, qty):
        """Add qty of item; qty must be positive (ValueError otherwise)."""
        if qty <= 0:
            raise ValueError(qty)
        self.stock[item] = self.stock.get(item, 0) + qty

    def remove(self, item, qty):
        """Take qty of item out; ValueError when there are fewer. An item that reaches 0 is no longer listed."""
        have = self.stock.get(item, 0)
        if qty <= 0 or qty > have:
            raise ValueError(f'cannot remove {qty} {item}')
        if qty == have:
            del self.stock[item]
        else:
            self.stock[item] = have - qty

    def quantity(self, item):
        """How many of item are in stock (0 when none)."""
        return self.stock.get(item, 0)

    def items(self):
        """The names of the items in stock, sorted."""
        return sorted(self.stock)

    def total(self):
        """How many units there are altogether."""
        return sum(self.stock.values())
''', """
inv = Inventory()
inv.add({A}, {N})
inv.add({B}, {M})
inv.add({A}, {K})
?inv.quantity({A})
?inv.quantity({C})
?inv.items()
?inv.total()
inv.remove({B}, {M})
?inv.items()
?inv.quantity({B})
!ValueError:inv.remove({A}, {N} + {K} + 1)
!ValueError:inv.remove({C}, 1)
!ValueError:inv.add({C}, 0)
inv.remove({A}, 1)
?inv.quantity({A})
inv.add({C}, {M})
?inv.items()
?inv.total()
""", lambda rng: dict(_things(rng, 3), N=rng.randint(2, 9), M=rng.randint(1, 9), K=rng.randint(1, 9))),
    _c("Timer", ("stopwatch", "laptimer", "timing"), "Timer measures laps from times that are given to it, in seconds: start(at) starts it (RuntimeError "
       "if it is already running), stop(at) stops it and keeps the lap, at minus the start (RuntimeError if it is not running), running() says "
       "whether it is running, the attribute laps holds the laps in order, elapsed() adds them up and longest() returns the longest (0 when there is "
       "none).", '''
class Timer:
    """Laps between start and stop, from times given in seconds."""

    def __init__(self):
        self.started = None
        self.laps = []

    def start(self, at):
        """Start at time at; RuntimeError if already running."""
        if self.started is not None:
            raise RuntimeError('already running')
        self.started = at

    def stop(self, at):
        """Stop at time at and keep the lap; RuntimeError if not running."""
        if self.started is None:
            raise RuntimeError('not running')
        self.laps.append(at - self.started)
        self.started = None

    def running(self):
        """True between a start and its stop."""
        return self.started is not None

    def elapsed(self):
        """The laps so far, added up."""
        return sum(self.laps)

    def longest(self):
        """The longest lap, or 0 when there is none."""
        return max(self.laps, default=0)
''', """
t = Timer()
?t.running()
?t.elapsed()
?t.longest()
t.start({S1})
?t.running()
!RuntimeError:t.start({S1} + 1)
t.stop({E1})
?t.running()
?t.elapsed()
t.start({S2})
t.stop({E2})
?t.laps
?t.elapsed()
?t.longest()
!RuntimeError:t.stop({E2} + 5)
t.start({S3})
t.stop({E3})
?t.elapsed()
?t.longest()
""", lambda rng: _laps(rng)),
    _c("Polynomial", ("poly", "polynomial", "algebra"), "Polynomial(coeffs) is a polynomial given by its coefficients, the constant first ([1, 0, 2] is "
       "1 + 2x^2), kept in .coeffs without trailing zeros (but at least [0]); degree() is the highest power with a coefficient that is not 0 (0 for "
       "a constant), calling it with a number x gives its value at x, add(other) returns the sum and derivative() the derivative, both as new "
       "Polynomial objects.", '''
class Polynomial:
    """A polynomial from its coefficients, the constant first."""

    def __init__(self, coeffs):
        coeffs = list(coeffs)
        while len(coeffs) > 1 and coeffs[-1] == 0:
            coeffs.pop()
        self.coeffs = coeffs or [0]

    def degree(self):
        """The highest power with a coefficient that is not 0 (0 for a constant)."""
        return len(self.coeffs) - 1

    def __call__(self, x):
        """The value at x."""
        return sum(c * x ** i for i, c in enumerate(self.coeffs))

    def add(self, other):
        """The sum as a new Polynomial."""
        n = max(len(self.coeffs), len(other.coeffs))
        a = self.coeffs + [0] * (n - len(self.coeffs))
        b = other.coeffs + [0] * (n - len(other.coeffs))
        return Polynomial([x + y for x, y in zip(a, b)])

    def derivative(self):
        """The derivative as a new Polynomial."""
        return Polynomial([i * c for i, c in enumerate(self.coeffs)][1:])
''', """
p = Polynomial({P})
q = Polynomial({Q})
?p.coeffs
?p.degree()
?p(0)
?p(2)
?p(-1)
?q(3)
?p.add(q).coeffs
?p.add(q).degree()
?p.derivative().coeffs
?q.derivative().derivative().coeffs
?Polynomial([1, 2, 0, 0]).coeffs
?Polynomial([0, 0]).degree()
?Polynomial([5]).derivative().coeffs
?p.add(Polynomial({NEG})).coeffs
""", lambda rng: _polys(rng)),
]


def _laps(rng) -> dict:
    times, at = {}, rng.randint(0, 10)
    for k in "123":
        times["S" + k] = at
        times["E" + k] = at = at + rng.randint(5, 90)
        at += rng.randint(0, 20)
    return times


def _polys(rng) -> dict:
    p = [rng.randint(-5, 5) for _ in range(rng.randint(2, 3))] + [rng.choice((-3, -2, -1, 1, 2, 3, 4))]
    q = [rng.randint(-5, 5) for _ in range(rng.randint(1, 2))] + [rng.choice((-2, -1, 1, 2, 3))]
    return {"P": p, "Q": q, "NEG": [-c for c in p]}


def _differ(rng, make, same) -> dict:
    """Values from make(rng), drawn again until same(values) is False."""
    values = make(rng)
    while same(values):
        values = make(rng)
    return values


CLASSES += [
    _c("Temperature", ("temperature", "temps", "weather"), "Temperature(celsius) holds a temperature in degrees Celsius in .celsius and raises "
       "ValueError below -273.15; Temperature.from_fahrenheit(f) makes one from degrees Fahrenheit (same rule); fahrenheit() and kelvin() return it "
       "in those units rounded to two decimals with round(), and warmer_than(other) is True when it is the higher of the two.", '''
class Temperature:
    """A temperature, kept in degrees Celsius."""

    def __init__(self, celsius):
        if celsius < -273.15:
            raise ValueError('below absolute zero')
        self.celsius = celsius

    @classmethod
    def from_fahrenheit(cls, f):
        """A Temperature from degrees Fahrenheit."""
        return cls((f - 32) * 5 / 9)

    def fahrenheit(self):
        """Degrees Fahrenheit, rounded to two decimals."""
        return round(self.celsius * 9 / 5 + 32, 2)

    def kelvin(self):
        """Kelvin, rounded to two decimals."""
        return round(self.celsius + 273.15, 2)

    def warmer_than(self, other):
        """True when this one is the higher of the two."""
        return self.celsius > other.celsius
''', """
t = Temperature({C})
?t.celsius
?t.fahrenheit()
?t.kelvin()
u = Temperature.from_fahrenheit({F})
?round(u.celsius, 2)
?u.fahrenheit()
?u.warmer_than(t)
?t.warmer_than(u)
?Temperature(-273.15).kelvin()
?Temperature(100).fahrenheit()
!ValueError:Temperature(-300)
!ValueError:Temperature.from_fahrenheit(-500)
?Temperature.from_fahrenheit(32).celsius
""", lambda rng: _differ(rng, lambda r: {"C": r.randint(-30, 45), "F": r.randint(-20, 110)}, lambda v: (v["F"] - 32) * 5 / 9 == v["C"])),
    _c("Playlist", ("playlist", "music", "songs"), "Playlist(name) keeps songs in order, each a title and a length in seconds: add(title, seconds) adds "
       "one at the end (ValueError if that title is already there), remove(title) removes it (ValueError if there is none), titles() returns the "
       "titles in order, move(title, position) moves a song so that it ends up at that position (0 is the first), total_seconds() adds the lengths "
       "up, and duration() gives that total as 'M:SS' (the minutes may pass 59).", '''
class Playlist:
    """Songs in order, each with a length in seconds."""

    def __init__(self, name):
        self.name = name
        self.songs = []

    def add(self, title, seconds):
        """Add a song at the end; ValueError if the title is already there."""
        if title in self.titles():
            raise ValueError(f'{title} is already in {self.name}')
        self.songs.append((title, seconds))

    def remove(self, title):
        """Remove the song with this title; ValueError if there is none."""
        for i, (name, _seconds) in enumerate(self.songs):
            if name == title:
                del self.songs[i]
                return
        raise ValueError(f'no song {title}')

    def titles(self):
        """The titles in order."""
        return [title for title, _seconds in self.songs]

    def move(self, title, position):
        """Move the song so that it ends up at this position, 0 being the first."""
        song = self.songs.pop(self.titles().index(title))
        self.songs.insert(position, song)

    def total_seconds(self):
        """The length of the whole list in seconds."""
        return sum(seconds for _title, seconds in self.songs)

    def duration(self):
        """The length of the whole list as 'M:SS'."""
        total = self.total_seconds()
        return f'{total // 60}:{total % 60:02d}'
''', """
p = Playlist({NAME})
?p.titles()
?p.duration()
p.add({T1}, {S1})
p.add({T2}, {S2})
p.add({T3}, {S3})
?p.titles()
?p.total_seconds()
?p.duration()
p.move({T3}, 0)
?p.titles()
p.move({T3}, 2)
?p.titles()
p.remove({T1})
?p.titles()
?p.duration()
!ValueError:p.remove({T1})
!ValueError:p.add({T2}, 100)
""", lambda rng: {"NAME": f"{rng.choice(PLACES)} {rng.choice(('mix', 'drive', 'evening', 'run'))}",
                  **{f"T{i}": f"{thing.title()} {rng.choice(('Song', 'Waltz', 'Blues', 'March', 'Dance'))}" for i, thing in enumerate(rng.sample(THINGS, 3), 1)},
                  **{f"S{i}": rng.randint(95, 400) for i in (1, 2, 3)}}),
    _c("Clock", ("clock", "wallclock", "timeofday"), "Clock(hours, minutes) is a time of day on a 24-hour clock, kept in .hours and .minutes, with "
       "minutes and hours that overflow carried round (Clock(25, 70) is 02:10 and Clock(0, -1) is 23:59); str() gives 'HH:MM', add(minutes) returns "
       "a new Clock that many minutes later (earlier when negative), minutes_until(other) counts the minutes forward to other (0 to 1439), and two "
       "clocks showing the same time are equal.", '''
class Clock:
    """A time of day, hours and minutes on a 24-hour clock."""

    def __init__(self, hours, minutes):
        self.hours, self.minutes = divmod((hours * 60 + minutes) % (24 * 60), 60)

    def __str__(self):
        """'HH:MM'."""
        return f'{self.hours:02d}:{self.minutes:02d}'

    def add(self, minutes):
        """A new Clock that many minutes later, or earlier when negative."""
        return Clock(self.hours, self.minutes + minutes)

    def minutes_until(self, other):
        """Minutes from this time forward to other, 0 to 1439."""
        return ((other.hours - self.hours) * 60 + other.minutes - self.minutes) % (24 * 60)

    def __eq__(self, other):
        """Equal when they show the same time."""
        return (self.hours, self.minutes) == (other.hours, other.minutes)
''', """
c = Clock({H}, {M})
?str(c)
?(c.hours, c.minutes)
?str(c.add({N}))
?str(c.add(-{K}))
?str(Clock(23, 59).add(1))
?str(Clock(25, 70))
?str(Clock(0, -1))
?c.minutes_until(Clock({H2}, {M2}))
?Clock({H2}, {M2}).minutes_until(c)
?c.minutes_until(c)
?Clock({H}, {M}) == c
?c.add(1440) == c
?c.add(1) == c
""", lambda rng: _differ(rng, lambda r: {"H": r.randint(0, 23), "M": r.randint(0, 59), "N": r.randint(30, 900), "K": r.randint(30, 900),
                                         "H2": r.randint(0, 23), "M2": r.randint(0, 59)}, lambda v: (v["H"], v["M"]) == (v["H2"], v["M2"]))),
    _c("Ratio", ("ratio", "rational", "fractional"), "Ratio(num, den=1) is a fraction kept in lowest terms in .num and .den, with the sign on the "
       "numerator (a denominator of 0 raises ZeroDivisionError); str() gives '3/4', or just '3' when the denominator is 1; + and * return new Ratio "
       "objects, two ratios with the same value are equal, and value() returns it as a float.", '''
from math import gcd


class Ratio:
    """A fraction in lowest terms, the sign on the numerator."""

    def __init__(self, num, den=1):
        if den == 0:
            raise ZeroDivisionError('the denominator is 0')
        if den < 0:
            num, den = -num, -den
        g = gcd(num, den)
        self.num, self.den = num // g, den // g

    def __str__(self):
        """'3/4', or just '3' when the denominator is 1."""
        return str(self.num) if self.den == 1 else f'{self.num}/{self.den}'

    def __add__(self, other):
        """The sum as a new Ratio."""
        return Ratio(self.num * other.den + other.num * self.den, self.den * other.den)

    def __mul__(self, other):
        """The product as a new Ratio."""
        return Ratio(self.num * other.num, self.den * other.den)

    def __eq__(self, other):
        """Equal when the values are."""
        return (self.num, self.den) == (other.num, other.den)

    def value(self):
        """The value as a float."""
        return self.num / self.den
''', """
a = Ratio({N1}, {D1})
b = Ratio({N2}, {D2})
?str(a)
?(a.num, a.den)
?str(a + b)
?str(a * b)
?str(b + b)
?str(Ratio(6, -8))
?str(Ratio(0, 5))
?str(Ratio(10, 5))
?Ratio(1, 2) == Ratio(2, 4)
?a == b
?a.value()
?str(Ratio(1, 3) + Ratio(2, 3))
!ZeroDivisionError:Ratio(1, 0)
""", lambda rng: _differ(rng, lambda r: {"N1": r.randint(1, 9), "D1": r.randint(2, 12), "N2": r.choice((-7, -5, -3, -1, 1, 2, 3, 5, 7)), "D2": r.randint(2, 12)},
                         lambda v: v["N1"] * v["D2"] == v["N2"] * v["D1"])),
    _c("RingBuffer", ("ring", "ringbuffer", "recent"), "RingBuffer(capacity) keeps the last capacity items (a capacity below 1 raises ValueError): "
       "append(item) adds one, dropping the oldest when it is full, to_list() returns the items oldest first, len() counts them, is_full() says "
       "whether it holds capacity items, and latest() returns the newest (IndexError when it is empty).", '''
class RingBuffer:
    """The last `capacity` items; adding to a full buffer drops the oldest."""

    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError(capacity)
        self.capacity = capacity
        self.items = []

    def append(self, item):
        """Add item, dropping the oldest when full."""
        self.items.append(item)
        if len(self.items) > self.capacity:
            self.items.pop(0)

    def to_list(self):
        """The items, oldest first."""
        return list(self.items)

    def __len__(self):
        """How many items it holds."""
        return len(self.items)

    def is_full(self):
        """True when it holds capacity items."""
        return len(self.items) == self.capacity

    def latest(self):
        """The newest item; IndexError when empty."""
        if not self.items:
            raise IndexError('the buffer is empty')
        return self.items[-1]
''', """
r = RingBuffer({CAP})
?len(r)
?r.is_full()
?r.to_list()
!IndexError:r.latest()
r.append({X1})
r.append({X2})
?r.to_list()
?r.latest()
r.append({X3})
r.append({X4})
r.append({X5})
?r.to_list()
?len(r)
?r.is_full()
?r.latest()
!ValueError:RingBuffer(0)
""", lambda rng: {"CAP": rng.choice((3, 4)), **{f"X{i}": x for i, x in enumerate(rng.sample(range(10, 100), 5), 1)}}),
    _c("Gradebook", ("grades", "gradebook", "marks"), "Gradebook keeps scores per student: add(student, score) records a score from 0 to 100 "
       "(ValueError otherwise), average(student) returns the student's mean score rounded to one decimal with round() (KeyError for a student with "
       "no scores), best() returns the student with the highest mean (the first in alphabetical order on a tie) and students() the students, sorted.", '''
class Gradebook:
    """Scores per student."""

    def __init__(self):
        self.scores = {}

    def add(self, student, score):
        """Record a score from 0 to 100; ValueError otherwise."""
        if not 0 <= score <= 100:
            raise ValueError(score)
        self.scores.setdefault(student, []).append(score)

    def average(self, student):
        """The student's mean score, rounded to one decimal; KeyError for an unknown student."""
        marks = self.scores[student]
        return round(sum(marks) / len(marks), 1)

    def best(self):
        """The student with the highest mean, the first alphabetically on a tie."""
        return min(self.scores, key=lambda s: (-sum(self.scores[s]) / len(self.scores[s]), s))

    def students(self):
        """The students, sorted."""
        return sorted(self.scores)
''', """
g = Gradebook()
g.add({A}, {S1})
g.add({B}, {S2})
g.add({A}, {S3})
g.add({C}, {S4})
g.add({B}, {S5})
?g.students()
?g.average({A})
?g.average({B})
?g.average({C})
?g.best()
!ValueError:g.add({A}, 101)
!ValueError:g.add({A}, -1)
!KeyError:g.average({D})
g.add({C}, {S6})
?g.average({C})
?g.best()
""", lambda rng: {**dict(zip("ABCD", rng.sample(PEOPLE, 4))), **{f"S{i}": rng.randint(40, 100) for i in range(1, 7)}}),
]


@family
def complete_class(rng):
    """A class with some methods still raising NotImplementedError, and its test: write them so the test passes, unchanged."""
    entry = rng.choice(CLASSES)
    module = rng.choice(entry["modules"])
    test, cls = f"test_{module}.py", entry["cls"]
    methods = [m for m in re.findall(r"    def (\w+)\(", entry["source"]) if m != "__init__"]
    cut = set(methods) if rng.random() < 0.4 else set(rng.sample(methods, rng.randint(2, len(methods) - 1)))
    body, checks = _script(rng, entry)
    text, token = _test([(module, [cls])], body, checks)
    spec = entry["spec"]
    return {"kind": "code", "files": {f"{module}.py": _stub(entry["source"], cut), test: text},
            "request": say(rng, f"{module}.py has a class {cls} that is only half written. Fill in the missing methods so that `python3 {test}` prints "
                                f"'{token}', without changing the test. What {cls} does: {spec}",
                           f"Finish the {cls} class in {module}.py. {spec} The methods that still raise NotImplementedError need writing; {test} must pass as "
                           "it is.",
                           f"Complete {cls} in {module}.py so that it passes {test} (do not edit the test). {spec}"),
            "expect": {"files": {f"{module}.py": [f"class {cls}"], test: text}, "run": (f"python3 {test}", token)},
            "solution": {"answer": f"Completed {cls}; the test prints {token}.", "files": {f"{module}.py": entry["source"]}}}


MARK = "=="


def _exact(pairs: list) -> tuple:
    """A run check that each command prints exactly its output, in turn: a marker line around each leaves no room for more."""
    command = "; ".join(f"echo {MARK}; {line}" for line, _out in pairs) + f"; echo {MARK}"
    return command, "".join(f"{MARK}\n{out}" for _line, out in pairs) + f"{MARK}\n"


def _sc(names, what, noun, positional, base, arguments, items, made, draw, options) -> dict:
    """A small script: what it prints now, its argparse lines and list of output items once options exist, the same
    items computed here from its arguments, a draw of arguments, and the options that suit it."""
    return {"names": names, "what": what, "noun": noun, "positional": positional, "base": base.strip("\n") + "\n", "arguments": arguments,
            "items": items, "made": made, "draw": draw, "options": options}


SCRIPTS = [
    _sc(("words.py", "echo_words.py", "say.py"), "prints the words given on its command line, one per line", "words", "the words", """
import sys

for word in sys.argv[1:]:
    print(word)
""", "parser.add_argument('words', nargs='+')\n", "args.words", lambda argv: list(argv), lambda rng: rng.sample(THINGS, rng.randint(3, 6)),
        ("reverse", "lines", "skip", "sep", "count")),
    _sc(("countdown.py", "launch.py"), "takes a number N and prints the numbers from N down to 1, one per line", "numbers", "the number", """
import sys

n = int(sys.argv[1])
for i in range(n, 0, -1):
    print(i)
""", "parser.add_argument('n', type=int)\n", "[str(i) for i in range(args.n, 0, -1)]", lambda argv: [str(i) for i in range(int(argv[0]), 0, -1)],
        lambda rng: [str(rng.randint(4, 9))], ("reverse", "lines", "skip", "sep")),
    _sc(("table.py", "times.py"), "takes a number N and prints its multiplication table from 1 to 10, one row per line such as `7 x 3 = 21`", "rows",
        "the number", """
import sys

n = int(sys.argv[1])
for i in range(1, 11):
    print(f'{n} x {i} = {n * i}')
""", "parser.add_argument('n', type=int)\n", "[f'{args.n} x {i} = {args.n * i}' for i in range(1, 11)]",
        lambda argv: [f"{argv[0]} x {i} = {int(argv[0]) * i}" for i in range(1, 11)], lambda rng: [str(rng.randint(2, 19))], ("reverse", "lines", "skip", "sep")),
    _sc(("letters.py", "spell.py"), "prints the letters of the word given on its command line, one per line", "letters", "the word", """
import sys

for letter in sys.argv[1]:
    print(letter)
""", "parser.add_argument('word')\n", "list(args.word)", lambda argv: list(argv[0]),
        lambda rng: [rng.choice([w for w in THINGS + STEMS if len(w) >= 4])], ("reverse", "lines", "skip", "sep", "count")),
    _sc(("seq.py", "span.py", "between.py"), "takes two numbers START and END and prints every whole number from START to END, one per line", "numbers",
        "the two numbers", """
import sys

start, end = int(sys.argv[1]), int(sys.argv[2])
for i in range(start, end + 1):
    print(i)
""", "parser.add_argument('start', type=int)\nparser.add_argument('end', type=int)\n", "[str(i) for i in range(args.start, args.end + 1)]",
        lambda argv: [str(i) for i in range(int(argv[0]), int(argv[1]) + 1)], lambda rng: (lambda s: [str(s), str(s + rng.randint(3, 8))])(rng.randint(1, 40)),
        ("reverse", "lines", "skip", "sep")),
    _sc(("squares.py", "powers.py"), "takes a number N and prints the squares of 1 to N, one per line", "squares", "the number", """
import sys

n = int(sys.argv[1])
for i in range(1, n + 1):
    print(i * i)
""", "parser.add_argument('n', type=int)\n", "[str(i * i) for i in range(1, args.n + 1)]", lambda argv: [str(i * i) for i in range(1, int(argv[0]) + 1)],
        lambda rng: [str(rng.randint(4, 9))], ("reverse", "lines", "skip", "sep")),
    _sc(("repeat.py", "echo_line.py"), "prints the text given on its command line", "lines", "the text", """
import sys

print(sys.argv[1])
""", "parser.add_argument('text')\n", "[args.text]", lambda argv: [argv[0]],
        lambda rng: [f"the {rng.choice(STEMS)} {rng.choice(('is ready', 'was sent', 'is late', 'needs a look', 'is on the desk'))}"], ("count",)),
]
OPTIONS = {   # usage, what it does (with the script's noun), code: the argparse line and what it does to `items`
    "reverse": ("--reverse", "prints the {noun} in reverse order", "parser.add_argument('--reverse', action='store_true')\n",
                "if args.reverse:\n    items = items[::-1]\n"),
    "lines": ("--lines N", "prints only the first N {noun}", "parser.add_argument('--lines', type=int)\n",
              "if args.lines is not None:\n    items = items[:args.lines]\n"),
    "skip": ("--skip N", "leaves out the first N {noun}", "parser.add_argument('--skip', type=int, default=0)\n", "items = items[args.skip:]\n"),
    "sep": ("--sep X", "prints the {noun} on one line, joined by X, instead of one per line", "parser.add_argument('--sep')\n", ""),
    "count": ("--count N", "prints the whole output N times, one copy after the other", "parser.add_argument('--count', type=int, default=1)\n", ""),
}


def _with_option(entry: dict, option: str) -> str:
    _usage, _what, argument, change = OPTIONS[option]
    show = "for item in items:\n    print(item)\n"
    if option == "sep":
        show = "if args.sep is not None:\n    print(args.sep.join(items))\nelse:\n    for item in items:\n        print(item)\n"
    elif option == "count":
        show = "for _ in range(args.count):\n    for item in items:\n        print(item)\n"
    return ("import argparse\n\nparser = argparse.ArgumentParser()\n" + entry["arguments"] + argument + "args = parser.parse_args()\n"
            + f"items = {entry['items']}\n" + change + show)


def _option_output(items: list, option: str | None, value) -> str:
    lines = {"reverse": lambda: items[::-1], "lines": lambda: items[:value], "skip": lambda: items[value:], "sep": lambda: [value.join(items)],
             "count": lambda: items * value}[option]() if option else items
    return "".join(line + "\n" for line in lines)


@family
def add_script_option(rng):
    """Add an option to a small command-line script; the run calls it without the option, and with it before and after its arguments."""
    entry = rng.choice(SCRIPTS)
    script, option = rng.choice(entry["names"]), rng.choice(entry["options"])
    usage, what = OPTIONS[option][0], OPTIONS[option][1].format(noun=entry["noun"])
    pairs = []
    for place in (None, "before", "after"):
        argv = entry["draw"](rng)
        items = entry["made"](argv)
        value = {"lines": lambda: rng.randint(1, len(items) - 1), "skip": lambda: rng.randint(1, len(items) - 1), "count": lambda: rng.randint(2, 4),
                 "sep": lambda: rng.choice((",", ";", " - ", "/", " | ", ":", "+", ", "))}.get(option, lambda: None)() if place else None
        flag = (usage.split()[0] + ("" if value is None else " " + shlex.quote(str(value)))) if place else ""
        words = " ".join(shlex.quote(a) for a in argv)
        line = f"python3 {script} " + {None: words, "before": f"{flag} {words}", "after": f"{words} {flag}"}[place]
        pairs.append((line, _option_output(items, option if place else None, value)))
    return {"kind": "code", "files": {script: entry["base"]},
            "request": say(rng, f"{script} {entry['what']}. Add an option {usage} that {what}. Without the option it must print exactly what it prints now, "
                                f"and the option must work whether it comes before or after {entry['positional']}.",
                           f"Extend {script}, which {entry['what']}, with an option {usage} that {what}. The option may come before or after "
                           f"{entry['positional']}, and without it the output stays the same.",
                           f"I'd like {script} to take {usage}: it {what}. Right now it {entry['what']}; keep that as it is when the option is missing, and "
                           f"accept the option both before and after {entry['positional']}."),
            "expect": {"run": _exact(pairs), "may_change": [script]},
            "solution": {"answer": f"Added {usage} to {script}.", "files": {script: _with_option(entry, option)}}}


PROLOGUE = """import json
import os
import sys

PATH = 'DATA'


def load():
    if not os.path.exists(PATH):
        return EMPTY
    with open(PATH) as f:
        return json.load(f)


def save(data):
    with open(PATH, 'w') as f:
        json.dump(data, f, indent=2)


command, args = sys.argv[1], sys.argv[2:]
data = load()
"""
FOODS = ("milk", "cheese", "yogurt", "eggs", "butter", "bread", "spinach", "tofu", "ham", "cream", "lettuce", "apples", "soup", "rice")


def _p(scripts, datas, empty, what, branches, commands, sim, setup) -> dict:
    """A small program keeping its data in a JSON file: what it does now and its branches, the commands that may be
    added ({name: (usage, what it does, branch, the checks to run: rng, state -> argv lists)}), a simulator
    sim(state, argv) -> output lines for every command, and setup(rng) -> the argv lists that fill it."""
    return {"scripts": scripts, "datas": datas, "empty": empty, "what": what, "branches": branches.strip("\n") + "\n", "commands": commands, "sim": sim,
            "setup": setup}


def _program(entry: dict, data: str, extra: str = "") -> str:
    return (PROLOGUE.replace("DATA", data).replace("EMPTY", entry["empty"]) + entry["branches"] + extra.strip("\n") + ("\n" if extra else "")
            + "else:\n    sys.exit('unknown command: ' + command)\n")


def _sim_notes(d, argv):
    command, args = argv[0], argv[1:]
    if command == "add":
        d.append(" ".join(args))
    elif command == "remove" and 1 <= int(args[0]) <= len(d):
        del d[int(args[0]) - 1]
    elif command == "remove":
        return [f"no note {args[0]}"]
    return {"list": lambda: [f"{n}. {t}" for n, t in enumerate(d, 1)], "count": lambda: [str(len(d))],
            "search": lambda: [f"{n}. {t}" for n, t in enumerate(d, 1) if args[0].lower() in t.lower()]}.get(command, list)()


def _sim_stock(d, argv):
    command, args = argv[0], argv[1:]
    if command == "add":
        d[args[0]] = d.get(args[0], 0) + int(args[1])
    elif command == "take" and d.get(args[0], 0) < int(args[1]):
        return [f"not enough {args[0]}"]
    elif command == "take":
        d[args[0]] -= int(args[1])
        d.pop(args[0]) if d[args[0]] == 0 else None
    return {"show": lambda: [f"{k} {d[k]}" for k in sorted(d)], "low": lambda: [f"{k} {d[k]}" for k in sorted(d) if d[k] < int(args[0])],
            "total": lambda: [str(sum(d.values()))]}.get(command, list)()


def _mean(xs) -> float:
    return sum(xs) / len(xs)


def _sim_scores(d, argv):
    command, args = argv[0], argv[1:]
    if command == "add":
        d.setdefault(args[0], []).append(int(args[1]))
        return []
    if command == "show":
        return [" ".join(map(str, d.get(args[0], [])))]
    if command == "average":
        return [f"{_mean(d[args[0]]):.1f}" if d.get(args[0]) else f"no scores for {args[0]}"]
    if command == "best":
        name = min(d, key=lambda p: (-_mean(d[p]), p))
        return [f"{name} {_mean(d[name]):.1f}"]
    return [f"{p} {len(d[p])}" for p in sorted(d)]


def _sim_marks(d, argv):
    command, args = argv[0], argv[1:]
    if command == "add":
        d[args[0]] = args[1]
    elif command in ("delete", "rename") and args[0] not in d:
        return [f"no bookmark {args[0]}"]
    elif command == "delete":
        del d[args[0]]
    elif command == "rename":
        d[args[1]] = d.pop(args[0])
    return {"list": lambda: [f"{k} {d[k]}" for k in sorted(d)], "find": lambda: [f"{k} {d[k]}" for k in sorted(d) if args[0] in k or args[0] in d[k]]}.get(command, list)()


def _sim_hours(d, argv):
    command, args = argv[0], argv[1:]
    if command == "log":
        d[args[0]] = d.get(args[0], 0) + float(args[1])
    elif command == "drop" and args[0] not in d:
        return [f"no project {args[0]}"]
    elif command == "drop":
        del d[args[0]]
    top = max(sorted(d), key=lambda k: d[k]) if d else None
    return {"show": lambda: [f"{k} {d[k]:.1f}" for k in sorted(d)], "total": lambda: [f"{sum(d.values()):.1f}"], "top": lambda: [f"{top} {d[top]:.1f}"]}.get(command, list)()


def _sim_pantry(d, argv):
    command, args = argv[0], argv[1:]
    order = sorted(d, key=lambda k: (d[k], k))
    if command == "add":
        d[args[0]] = args[1]
    elif command == "remove" and args[0] not in d:
        return [f"no {args[0]}"]
    elif command == "remove":
        del d[args[0]]
    return {"list": lambda: [f"{d[k]} {k}" for k in sorted(d, key=lambda k: (d[k], k))], "expired": lambda: [f"{d[k]} {k}" for k in order if d[k] < args[0]],
            "next": lambda: [f"{d[order[0]]} {order[0]}" if order else "empty"]}.get(command, list)()


def _notes_setup(rng):
    a, b, c = rng.sample(THINGS, 3)
    texts = [f"buy a {a}", f"{a.title()} needs a new part", f"call {rng.choice(PEOPLE)} about the {b}", f"take the {c} to {rng.choice(PLACES)}",
             f"fix the {b} before {rng.choice(('Monday', 'Friday', 'the weekend'))}"]
    rng.shuffle(texts)
    return [["add", *t.split()] for t in texts[:rng.randint(4, 5)]]


def _dated(rng, n: int) -> list:
    """n different dates in the autumn of 2026, in order."""
    import datetime
    return [str(datetime.date(2026, 9, 1) + datetime.timedelta(days=k)) for k in sorted(rng.sample(range(120), n))]


# The rules a command states are each run once: "on a tie, the first in alphabetical order" passed a plain max() while no
# check had a tie, and "`empty` when there is nothing" was never asked of an empty file (EvalPlus, arXiv:2305.01210:
# tests that leave a stated case out let wrong code through). A tie is made with a new name that sorts first, so that
# the order the names were added in gives the wrong one.

def _best_checks(rng, s) -> list:
    import copy
    first = ["add", rng.choice(sorted(s)), "100"]
    after = copy.deepcopy(s)
    _sim_scores(after, first)
    best = min(after, key=lambda p: (-_mean(after[p]), p))
    out = [["best"], first, ["best"]]
    free = [p for p in PEOPLE if p not in after]
    earlier = [p for p in free if p < best]
    if earlier:
        name = rng.choice(earlier)
        out += [["add", name, str(x)] for x in after[best]] + [["best"]]
    elif _mean(after[best]) < 100:                              # nothing sorts before the best: two new ones above it, the later
        a, b = sorted(rng.sample(free, 2))                     # in the alphabet added first
        out += [["add", b, "100"], ["add", a, "100"], ["best"]]
    return out


def _top_checks(rng, s) -> list:
    import copy
    first = ["log", min(s, key=s.get), "20"]
    after = copy.deepcopy(s)
    _sim_hours(after, first)
    top = min(after, key=lambda p: (-after[p], p))
    out = [["top"], first, ["top"]]
    free = [p for p in STEMS if p not in after]
    earlier = [p for p in free if p < top]
    if earlier:
        out += [["log", rng.choice(earlier), str(after[top])], ["top"]]
    else:                                                       # nothing sorts before the top: two new ones above it, the later
        a, b = sorted(rng.sample(free, 2))                     # in the alphabet logged first
        out += [["log", b, str(after[top] + 5)], ["log", a, str(after[top] + 5)], ["top"]]
    return out


def _next_checks(rng, s) -> list:
    new = sorted(rng.sample([f for f in FOODS if f not in s], 2))
    return [["next"], ["add", new[1], "2026-08-30"], ["next"], ["add", new[0], "2026-08-30"], ["next"], ["--fresh", "next"]]


PROGRAMS = [
    _p(("notes.py", "jot.py"), ("notes.json", "jottings.json"), "[]",
       "keeps short notes in {data}: `add TEXT` adds one, and `list` prints them numbered from 1 as `N. TEXT`", """
if command == 'add':
    data.append(' '.join(args))
    save(data)
elif command == 'list':
    for n, text in enumerate(data, 1):
        print(f'{n}. {text}')
""", {"count": ("count", "prints how many notes there are", "elif command == 'count':\n    print(len(data))\n",
                lambda rng, s: [["count"], ["add", "water", "the", "plants"], ["count"], ["list"]]),
      "remove": ("remove N", "deletes note number N, the later ones moving up a number, and prints `no note N` and changes nothing when there is no such "
                 "note", "elif command == 'remove':\n    n = int(args[0])\n    if 1 <= n <= len(data):\n        del data[n - 1]\n        save(data)\n"
                 "    else:\n        print(f'no note {n}')\n",
                 lambda rng, s: [["remove", str(rng.randint(1, len(s)))], ["remove", str(len(s) + rng.randint(2, 9))], ["list"]]),
      "search": ("search WORD", "prints the notes that contain WORD, in any mix of upper and lower case, as `N. TEXT` with their own numbers",
                 "elif command == 'search':\n    for n, text in enumerate(data, 1):\n        if args[0].lower() in text.lower():\n            print(f'{n}. {text}')\n",
                 lambda rng, s: [["search", rng.choice((str.upper, str.title))(max(THINGS, key=lambda w: sum(w in t.lower() for t in s)))], ["search", "zebra"]])},
       _sim_notes, _notes_setup),
    _p(("stock.py", "shed.py"), ("stock.json", "shed.json"), "{}",
       "counts things in {data}: `add ITEM N` adds N of an item, and `show` prints every item with its count as `ITEM N`, sorted by item", """
if command == 'add':
    data[args[0]] = data.get(args[0], 0) + int(args[1])
    save(data)
elif command == 'show':
    for item in sorted(data):
        print(item, data[item])
""", {"take": ("take ITEM N", "takes N of the item out; when there are fewer than N it prints `not enough ITEM` and changes nothing, and an item that "
                "reaches 0 is removed", "elif command == 'take':\n    item, n = args[0], int(args[1])\n    if data.get(item, 0) < n:\n"
                "        print(f'not enough {item}')\n    else:\n        data[item] -= n\n        if data[item] == 0:\n            del data[item]\n"
                "        save(data)\n",
                lambda rng, s: (lambda a, b, c: [["take", a, str(rng.randint(1, s[a] - 1))], ["take", b, str(s[b])], ["take", c, str(s[c] + rng.randint(1, 3))],
                                                 ["take", "zebra", "1"], ["show"]])(*rng.sample([k for k in sorted(s) if s[k] > 1], 3))),
      "low": ("low N", "prints the items with fewer than N in stock as `ITEM COUNT`, sorted by item",
              "elif command == 'low':\n    for item in sorted(data):\n        if data[item] < int(args[0]):\n            print(item, data[item])\n",
              lambda rng, s: [["low", str(sorted(s.values())[len(s) // 2])], ["low", "1"], ["show"]]),
      "total": ("total", "prints how many units there are of all the items together", "elif command == 'total':\n    print(sum(data.values()))\n",
                lambda rng, s: [["total"], ["add", rng.choice(sorted(s)), "3"], ["total"]])},
       _sim_stock, lambda rng: [["add", item, str(rng.randint(2, 12))] for item in rng.sample(THINGS, 5)]),
    _p(("scores.py", "league.py"), ("scores.json", "league.json"), "{}",
       "keeps players' scores in {data}: `add NAME SCORE` records a score, and `show NAME` prints that player's scores separated by spaces", """
if command == 'add':
    data.setdefault(args[0], []).append(int(args[1]))
    save(data)
elif command == 'show':
    print(' '.join(str(s) for s in data.get(args[0], [])))
""", {"average": ("average NAME", "prints the player's mean score with one decimal, or `no scores for NAME` when there are none",
                  "elif command == 'average':\n    scores = data.get(args[0], [])\n    if scores:\n        print(f'{sum(scores) / len(scores):.1f}')\n"
                  "    else:\n        print(f'no scores for {args[0]}')\n",
                  lambda rng, s: [["average", name] for name in sorted(s)] + [["average", rng.choice([p for p in PEOPLE if p not in s])]]),
      "best": ("best", "prints the player with the highest mean score and that mean with one decimal, as `NAME MEAN` (on a tie, the name first in "
               "alphabetical order)", "elif command == 'best':\n    name = min(data, key=lambda p: (-sum(data[p]) / len(data[p]), p))\n"
               "    print(f'{name} {sum(data[name]) / len(data[name]):.1f}')\n",
               lambda rng, s: _best_checks(rng, s)),
      "players": ("players", "prints every player with the number of scores they have, as `NAME COUNT`, sorted by name",
                  "elif command == 'players':\n    for name in sorted(data):\n        print(name, len(data[name]))\n",
                  lambda rng, s: [["players"], ["add", rng.choice([p for p in PEOPLE if p not in s]), "50"], ["players"]])},
       _sim_scores, lambda rng: [["add", name, str(rng.randint(40, 100))] for name in rng.sample(PEOPLE, 3) for _ in range(rng.randint(1, 2))]),
    _p(("marks.py", "bookmarks.py"), ("marks.json", "bookmarks.json"), "{}",
       "keeps bookmarks in {data}: `add NAME ADDRESS` saves one, and `list` prints them as `NAME ADDRESS`, sorted by name", """
if command == 'add':
    data[args[0]] = args[1]
    save(data)
elif command == 'list':
    for name in sorted(data):
        print(name, data[name])
""", {"delete": ("delete NAME", "removes that bookmark, or prints `no bookmark NAME` when there is none",
                 "elif command == 'delete':\n    if args[0] in data:\n        del data[args[0]]\n        save(data)\n    else:\n"
                 "        print(f'no bookmark {args[0]}')\n", lambda rng, s: [["delete", rng.choice(sorted(s))], ["delete", "zebra"], ["list"]]),
      "rename": ("rename OLD NEW", "gives the bookmark OLD the name NEW, keeping its address, or prints `no bookmark OLD` when there is none",
                 "elif command == 'rename':\n    old, new = args\n    if old in data:\n        data[new] = data.pop(old)\n        save(data)\n    else:\n"
                 "        print(f'no bookmark {old}')\n",
                 lambda rng, s: [["rename", rng.choice(sorted(s)), rng.choice([w for w in STEMS if w not in s])], ["rename", "zebra", "yak"], ["list"]]),
      "find": ("find TEXT", "prints the bookmarks whose name or address contains TEXT, as `NAME ADDRESS`, sorted by name",
               "elif command == 'find':\n    for name in sorted(data):\n        if args[0] in name or args[0] in data[name]:\n            print(name, data[name])\n",
               lambda rng, s: [["find", max(("docs", "shop", "news", "maps"), key=lambda h: sum(h in v for v in s.values()))], ["find", "zebra"]])},
       _sim_marks, lambda rng: [["add", name, f"https://{rng.choice(('docs', 'shop', 'news'))}.example.org/{rng.choice(THINGS)}"] for name in rng.sample(STEMS, 5)]),
    _p(("hours.py", "timesheet.py"), ("hours.json", "timesheet.json"), "{}",
       "adds up hours per project in {data}: `log PROJECT HOURS` adds hours to a project, and `show` prints every project with its hours to one decimal "
       "as `PROJECT HOURS`, sorted by project", """
if command == 'log':
    data[args[0]] = data.get(args[0], 0) + float(args[1])
    save(data)
elif command == 'show':
    for project in sorted(data):
        print(f'{project} {data[project]:.1f}')
""", {"total": ("total", "prints the hours of all the projects together, to one decimal", "elif command == 'total':\n    print(f'{sum(data.values()):.1f}')\n",
                lambda rng, s: [["total"], ["log", rng.choice(sorted(s)), "1.5"], ["total"]]),
      "top": ("top", "prints the project with the most hours and its hours to one decimal, as `PROJECT HOURS` (on a tie, the project first in alphabetical "
              "order)", "elif command == 'top':\n    project = min(data, key=lambda p: (-data[p], p))\n    print(f'{project} {data[project]:.1f}')\n",
              lambda rng, s: _top_checks(rng, s)),
      "drop": ("drop PROJECT", "removes the project, or prints `no project PROJECT` when there is none",
               "elif command == 'drop':\n    if args[0] in data:\n        del data[args[0]]\n        save(data)\n    else:\n"
               "        print(f'no project {args[0]}')\n", lambda rng, s: [["drop", rng.choice(sorted(s))], ["drop", "zebra"], ["show"]])},
       _sim_hours, lambda rng: [["log", project, rng.choice(("0.5", "1", "1.5", "2", "2.5", "3", "4"))] for project in rng.sample(STEMS, 4) for _ in range(rng.randint(1, 3))]),
    _p(("pantry.py", "fridge.py"), ("pantry.json", "fridge.json"), "{}",
       "tracks when food goes off, in {data}: `add ITEM DATE` stores an item with its date (YYYY-MM-DD), and `list` prints them as `DATE ITEM`, soonest "
       "first", """
if command == 'add':
    data[args[0]] = args[1]
    save(data)
elif command == 'list':
    for item in sorted(data, key=lambda i: (data[i], i)):
        print(data[item], item)
""", {"expired": ("expired DATE", "prints the items whose date is before DATE, as `DATE ITEM`, soonest first",
                  "elif command == 'expired':\n    for item in sorted(data, key=lambda i: (data[i], i)):\n        if data[item] < args[0]:\n"
                  "            print(data[item], item)\n", lambda rng, s: [["expired", sorted(s.values())[rng.randint(1, len(s) - 1)]], ["expired", "2026-01-01"]]),
      "next": ("next", "prints the item that goes off first, as `DATE ITEM` (on a tie, the item first in alphabetical order), or `empty` when there "
               "is nothing", "elif command == 'next':\n    if data:\n        item = min(data, key=lambda i: (data[i], i))\n        print(data[item], item)\n"
               "    else:\n        print('empty')\n", lambda rng, s: _next_checks(rng, s)),
      "remove": ("remove ITEM", "removes the item, or prints `no ITEM` when it is not there",
                 "elif command == 'remove':\n    if args[0] in data:\n        del data[args[0]]\n        save(data)\n    else:\n        print(f'no {args[0]}')\n",
                 lambda rng, s: [["remove", rng.choice(sorted(s))], ["remove", "zebra"], ["list"]])},
       _sim_pantry, lambda rng: [["add", food, day] for food, day in zip(rng.sample(FOODS, 5), rng.sample(_dated(rng, 5), 5))]),
]


@family
def add_json_command(rng):
    """Add a command to a small program that keeps its data in a JSON file; the run starts from no file and checks every line printed."""
    import copy
    import json
    entry = rng.choice(PROGRAMS)
    script, data = rng.choice(list(zip(entry["scripts"], entry["datas"])))
    name = rng.choice(sorted(entry["commands"]))
    usage, does, branch, checks = entry["commands"][name]
    setup, state = entry["setup"](rng), json.loads(entry["empty"])
    for argv in setup:
        entry["sim"](state, argv)
    files = {script: _program(entry, data), data: json.dumps(state, indent=2)}
    quoted = lambda argv: f"python3 {script} " + " ".join(shlex.quote(a) for a in argv)
    pairs, live = [], copy.deepcopy(state)
    for argv in checks(rng, copy.deepcopy(state)):
        line = quoted(argv)
        if argv[:1] == ["--fresh"]:                             # this one starts from no data file
            argv, live = argv[1:], json.loads(entry["empty"])
            line = f"rm -f {data}; " + quoted(argv)
        pairs.append((line, "".join(out + "\n" for out in entry["sim"](live, argv))))
    command, want = _exact(pairs)
    what = entry["what"].format(data=data)
    return {"kind": "code", "files": files,
            "request": say(rng, f"{script} {what}. Add a command `{usage}` that {does}. Keep the other commands working as they are.",
                           f"Teach {script} a new command, `{usage}`: it {does}. The rest stays as it is: {script} {what}.",
                           f"Please add a `{usage}` command to {script}; it {does}. Today the script {what}; leave that as it is."),
            "expect": {"run": (f"rm -f {data}; " + "; ".join(quoted(argv) + " > /dev/null" for argv in setup) + "; " + command, want),
                       "may_change": [script, data]},
            "solution": {"answer": f"Added `{usage}` to {script}.", "files": {script: _program(entry, data, branch)}}}


def _r(names, ext, spec, gen, compute, source, edge=None) -> dict:
    """A script that reads the file named on its command line: what it prints, a draw of such a file, the output computed
    here, and a right source; `edge` draws the second file so that a rule the spec states is met there (the `none`, the
    tie, the case), which the plain draw left out of three runs in four for `none`."""
    return {"names": names, "ext": ext, "spec": spec, "gen": gen, "compute": compute, "source": source.strip("\n") + "\n", "edge": edge}


def _numbers(rng, low, high, repeat=False) -> list:
    numbers = [rng.randint(low, high) for _ in range(rng.randint(6, 11))]
    if repeat:
        numbers += rng.sample(numbers, rng.randint(1, 3))
        rng.shuffle(numbers)
    return numbers


def _with_blanks(rng, lines: list) -> str:
    for _ in range(rng.randint(1, 2)):
        lines.insert(rng.randint(1, len(lines) - 1), "")
    return "\n".join(map(str, lines)) + "\n"


def _items_csv(rng) -> str:
    """name,qty,price rows whose qty times price (and price) are never tied at the top or with the average."""
    while True:
        rows = [(name, rng.randint(1, 20), rng.randint(50, 9999)) for name in rng.sample(THINGS, rng.randint(4, 7))]
        values, prices = [q * c for _n, q, c in rows], [c for _n, _q, c in rows]
        if values.count(max(values)) == 1 and all(c * len(prices) != sum(prices) for c in prices):
            return "name,qty,price\n" + "".join(f"{n},{q},{c / 100:.2f}\n" for n, q, c in rows)


def _rows(text: str) -> list:
    return [line.split(",") for line in text.splitlines()[1:]]


def _prose(rng) -> str:
    lines = []
    for _ in range(rng.randint(3, 5)):
        lines.append(" ".join(f"The {rng.choice(THINGS)} in {rng.choice(PLACES)} was {rng.choice(('moved', 'painted', 'mended', 'sold', 'counted', 'cleaned'))} "
                              f"by {rng.choice(PEOPLE)} {rng.choice(('today', 'on Monday', 'last week', 'before the storm', 'again', 'at noon'))}."
                              for _ in range(2)))
    return "\n".join(lines) + "\n"


def _scored(rng) -> str:
    while True:
        rows = [(name, rng.randint(0, 100)) for name in rng.sample(PEOPLE, rng.randint(4, 7))]
        scores = [s for _n, s in rows]
        tie = (sum(scores) * 100) % len(scores) == 0 and (sum(scores) * 100 // len(scores)) % 10 == 5
        if scores.count(max(scores)) == 1 and not tie:
            return "".join(f"{n} {s}\n" for n, s in rows)


def _temps(rng) -> str:
    while True:
        days = rng.sample(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"), rng.randint(4, 7))
        rows = [(d, low, low + rng.randint(1, 15)) for d, low in ((d, rng.randint(-5, 20)) for d in days)]
        gaps = [h - lo for _d, lo, h in rows]
        if gaps.count(max(gaps)) == 1:
            return "day,low,high\n" + "".join(f"{d},{lo},{h}\n" for d, lo, h in rows)


def _conf(rng) -> str:
    keys = rng.sample(("port", "name", "debug", "timeout", "retries", "theme", "language", "user", "level", "colour", "size", "mode"), rng.randint(4, 7))
    values = {"port": "8080", "name": "demo", "debug": "false", "timeout": "30", "retries": "3", "theme": "dark", "language": "en", "user": "guest",
              "level": "info", "colour": "blue", "size": "12", "mode": "fast"}
    lines = [rng.choice(("{k}={v}", "{k} = {v}", "  {k}= {v}", "{k} =  {v}")).format(k=k, v=values[k]) for k in keys]
    lines.insert(0, f"# settings for {rng.choice(STEMS)}")
    lines.insert(rng.randint(1, len(lines)), "# " + rng.choice(("network", "display", "limits")))
    return _with_blanks(rng, lines)


def _team_json(rng) -> str:
    import json
    teams = rng.sample(("red", "blue", "green", "gold", "north", "south"), rng.randint(2, 4))
    return json.dumps([{"name": name, "team": rng.choice(teams)} for name in rng.sample(PEOPLE, rng.randint(5, 10))], indent=1) + "\n"


def _with_digits(rng) -> str:
    lines = [rng.choice((f"room {rng.randint(1, 40)} is free", f"ask {rng.choice(PEOPLE)} about the {rng.choice(THINGS)}",
                         f"the {rng.choice(THINGS)} costs {rng.randint(2, 90)} today", f"meet in {rng.choice(PLACES)}", f"bring the {rng.choice(THINGS)}",
                         f"call back at {rng.randint(1, 12)}")) for _ in range(rng.randint(6, 10))]
    lines[0] = f"bring the {rng.choice(THINGS)}"
    lines[-1] = f"room {rng.randint(1, 40)} is booked"
    return "\n".join(lines) + "\n"


TIES = (("thermometer", "screwdriver"), ("wheelbarrow", "candlestick"), ("wastebasket", "loudspeaker"), ("typewriters", "calculators"),
        ("lampshades", "flowerpots"), ("tablecloth", "dishwasher"))


def _tie_line(rng) -> str:
    """A sentence holding two words longer than any other in the prose and of one length, the later in the alphabet
    first: the answer is the first in the file, not the last nor the first by spelling."""
    first, second = rng.choice(TIES)
    return f"{rng.choice(PEOPLE)} sold the {first} and the {second} {rng.choice(('today', 'on Monday', 'last week'))}.\n"


READERS = [
    _r(("minmax.py", "spread.py"), ".txt", "the smallest number, the largest and the difference between them, as `min A max B range C` (the file holds one "
       "whole number per line; blank lines are skipped)", lambda rng: _with_blanks(rng, _numbers(rng, -50, 500)),
       lambda t: (lambda ns: f"min {min(ns)} max {max(ns)} range {max(ns) - min(ns)}\n")([int(x) for x in t.split()]), """
import sys

with open(sys.argv[1]) as f:
    numbers = [int(line) for line in f if line.strip()]
print(f'min {min(numbers)} max {max(numbers)} range {max(numbers) - min(numbers)}')
"""),
    _r(("repeats.py", "dupes.py"), ".txt", "the numbers that occur more than once, in increasing order and separated by single spaces, or `none` when no "
       "number repeats (the file holds one whole number per line)", lambda rng: "\n".join(map(str, _numbers(rng, 1, 60, True))) + "\n",
       lambda t: (lambda ns: " ".join(str(n) for n in sorted(set(ns)) if ns.count(n) > 1) or "none")([int(x) for x in t.split()]) + "\n", """
import sys
from collections import Counter

with open(sys.argv[1]) as f:
    counts = Counter(int(line) for line in f if line.strip())
repeats = sorted(n for n, k in counts.items() if k > 1)
print(' '.join(map(str, repeats)) if repeats else 'none')
""", lambda rng: "\n".join(map(str, rng.sample(range(1, 61), rng.randint(6, 11)))) + "\n"),
    _r(("dearest.py", "top_item.py"), ".csv", "the name of the item whose qty times price is the largest, a space, and that amount with two decimals (the "
       "file is a CSV with the header name,qty,price)", _items_csv,
       lambda t: (lambda r: f"{r[0]} {int(r[1]) * round(float(r[2]) * 100) / 100:.2f}\n")(max(_rows(t), key=lambda r: int(r[1]) * round(float(r[2]) * 100))), """
import csv
import sys

with open(sys.argv[1]) as f:
    rows = list(csv.DictReader(f))
best = max(rows, key=lambda row: int(row['qty']) * float(row['price']))
print(f"{best['name']} {int(best['qty']) * float(best['price']):.2f}")
"""),
    _r(("pricey.py", "above_average.py"), ".csv", "the names of the items whose price is above the average price, one per line, in the order of the file "
       "(the file is a CSV with the header name,qty,price)", _items_csv,
       lambda t: (lambda rs: "".join(r[0] + "\n" for r in rs if round(float(r[2]) * 100) * len(rs) > sum(round(float(x[2]) * 100) for x in rs)))(_rows(t)), """
import csv
import sys

with open(sys.argv[1]) as f:
    rows = list(csv.DictReader(f))
average = sum(float(row['price']) for row in rows) / len(rows)
for row in rows:
    if float(row['price']) > average:
        print(row['name'])
"""),
    _r(("longest.py", "longword.py"), ".txt", "the longest word and its length, as `WORD LENGTH`, where a word is a run of letters; on a tie the word that "
       "comes first in the file wins", _prose, lambda t: (lambda w: f"{w} {len(w)}\n")(max(re.findall("[A-Za-z]+", t), key=len)), """
import re
import sys

with open(sys.argv[1]) as f:
    words = re.findall('[A-Za-z]+', f.read())
longest = max(words, key=len)
print(longest, len(longest))
""", lambda rng: _prose(rng) + _tie_line(rng)),
    _r(("vocab.py", "distinct.py"), ".txt", "the number of different words in the file, compared in lower case, where a word is a run of letters", _prose,
       lambda t: f"{len({w.lower() for w in re.findall('[A-Za-z]+', t)})}\n", """
import re
import sys

with open(sys.argv[1]) as f:
    words = re.findall('[A-Za-z]+', f.read())
print(len({word.lower() for word in words}))
""", lambda rng: _prose(rng) + f"The {rng.choice(THINGS)} in {rng.choice(PLACES)} was moved by {rng.choice(PEOPLE)} before the storm.\n"),
    _r(("digits.py", "numbered.py"), ".txt", "every line that contains a digit, with its line number counted from 1, as `N: LINE`", _with_digits,
       lambda t: "".join(f"{n}: {line}\n" for n, line in enumerate(t.splitlines(), 1) if re.search("[0-9]", line)), """
import sys

with open(sys.argv[1]) as f:
    for n, line in enumerate(f, 1):
        if any(ch.isdigit() for ch in line):
            print(f'{n}: {line.rstrip()}')
"""),
    _r(("settings.py", "showconf.py"), ".conf", "the settings in the file sorted by key, one per line as `key = value` with one space on each side of the equals sign; "
       "lines that are empty or start with # are skipped, and the spaces around keys and values are dropped", _conf,
       lambda t: "".join(f"{k} = {v}\n" for k, v in sorted(tuple(p.strip() for p in line.split("=", 1)) for line in t.splitlines()
                                                          if line.strip() and not line.startswith("#"))), """
import sys

settings = {}
with open(sys.argv[1]) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            key, value = line.split('=', 1)
            settings[key.strip()] = value.strip()
for key in sorted(settings):
    print(f'{key} = {settings[key]}')
"""),
    _r(("best.py", "winner.py"), ".txt", "the name with the highest score and the average of all the scores to one decimal, as `best NAME average X` "
       "(each line of the file is a name and a whole-number score, separated by a space)", _scored,
       lambda t: (lambda rs: f"best {max(rs, key=lambda r: int(r[1]))[0]} average {sum(int(r[1]) for r in rs) / len(rs):.1f}\n")([l.split() for l in t.splitlines()]), """
import sys

with open(sys.argv[1]) as f:
    rows = [line.split() for line in f if line.strip()]
best = max(rows, key=lambda row: int(row[1]))
average = sum(int(score) for _name, score in rows) / len(rows)
print(f'best {best[0]} average {average:.1f}')
"""),
    _r(("widest.py", "swing.py"), ".csv", "the day with the largest difference between its high and its low, and that difference, as `DAY N` (the file "
       "is a CSV with the header day,low,high, in whole numbers)", _temps,
       lambda t: (lambda r: f"{r[0]} {int(r[2]) - int(r[1])}\n")(max(_rows(t), key=lambda r: int(r[2]) - int(r[1]))), """
import csv
import sys

with open(sys.argv[1]) as f:
    rows = list(csv.DictReader(f))
widest = max(rows, key=lambda row: int(row['high']) - int(row['low']))
print(widest['day'], int(widest['high']) - int(widest['low']))
"""),
    _r(("teams.py", "headcount.py"), ".json", "each team with the number of people in it, as `TEAM N`, sorted by team name (the file is a JSON list of "
       "objects with the keys name and team)", _team_json,
       lambda t: (lambda ts: "".join(f"{k} {ts.count(k)}\n" for k in sorted(set(ts))))([p["team"] for p in __import__("json").loads(t)]), """
import json
import sys

with open(sys.argv[1]) as f:
    people = json.load(f)
counts = {}
for person in people:
    counts[person['team']] = counts.get(person['team'], 0) + 1
for team in sorted(counts):
    print(team, counts[team])
"""),
]


@family
def file_report_script(rng):
    """Write a script that reads the file named on its command line and prints a stated result; the run checks its exact output on two files."""
    entry = rng.choice(READERS)
    script = rng.choice(entry["names"])
    a, b = (stem + entry["ext"] for stem in rng.sample(STEMS, 2))
    texts = {a: entry["gen"](rng), b: (entry["edge"] or entry["gen"])(rng)}
    spec = entry["spec"]
    return {"kind": "code", "files": dict(texts),
            "request": say(rng, f"Write {script}: it reads the file named on its command line and prints {spec}. For example `python3 {script} {a}`; it should "
                                f"work just as well for {b} and any other file like them.",
                           f"I need a script {script} that takes a file name as its argument and prints {spec}. Try it on {a} and {b}.",
                           f"Create {script}, to be run as `python3 {script} FILE`, which prints {spec}. {a} and {b} here are examples of such files."),
            "expect": {"files": {script: [], **texts}, "run": _exact([(f"python3 {script} {name}", entry["compute"](texts[name])) for name in (a, b)])},
            "solution": {"answer": f"Wrote {script}.", "files": {script: entry["source"]}}}


def _b(names, datas, gen, source, errors, compute, answer) -> dict:
    """A script that reads DATA and prints a result its first line describes: a draw of DATA, the right source, the
    mistakes that can be planted in it as (old, new) (a wrong import, a misspelt name, an index or slice one off), and
    what it prints and what the answer must hold, both computed here from the data."""
    return {"names": names, "datas": datas, "gen": gen, "source": source.strip("\n") + "\n", "errors": errors, "compute": compute, "answer": answer}


def _value_parts(text: str) -> tuple:
    rows = [(n, int(q) * round(float(p) * 100)) for n, q, p in _rows(text)]
    best = max(rows, key=lambda r: r[1])
    return sum(v for _n, v in rows) / 100, best[0], best[1] / 100


def _grade_parts(text: str) -> tuple:
    import statistics
    scores = {line.split()[0]: int(line.split()[1]) for line in text.splitlines()[1:]}
    return f"{statistics.mean(scores.values()):.1f}", max(scores, key=scores.get)


def _gap_parts(text: str) -> tuple:
    day = max(_rows(text), key=lambda r: int(r[2]) - int(r[1]))
    return day[0], int(day[2]) - int(day[1])


def _date_parts(text: str) -> tuple:
    import datetime
    entries = sorted(line.split(" ", 1) for line in text.splitlines() if line.strip())
    return (datetime.date.fromisoformat(entries[-1][0]) - datetime.date.fromisoformat(entries[0][0])).days, entries[-1][1]


def _events(rng) -> str:
    whats = [f"{verb} the {thing}" for verb, thing in zip(rng.sample(("fix", "paint", "sell", "clean", "move", "check", "return"), 6), rng.sample(THINGS, 6))]
    lines = [f"{day} {what}" for day, what in zip(_dated(rng, rng.randint(4, 6)), whats)]
    rng.shuffle(lines)
    return "\n".join(lines) + "\n"


def _sizes(rng) -> str:
    while True:
        rows = [(f"{stem}{rng.choice(('.pdf', '.txt', '.png', '.zip'))}", rng.randint(100, 5_000_000)) for stem in rng.sample(STEMS, rng.randint(4, 7))]
        if [b for _n, b in rows].count(max(b for _n, b in rows)) == 1:
            return "name,bytes\n" + "".join(f"{n},{b}\n" for n, b in rows)


def _size_parts(text: str) -> tuple:
    rows = _rows(text)
    return f"{sum(int(b) for _n, b in rows) / 1024:.1f}", max(rows, key=lambda r: int(r[1]))[0]


BROKEN = [
    _b(("value.py", "stock_value.py", "worth.py"), ("items.csv", "stock.csv", "goods.csv"), _items_csv, '''
"""Prints the total value of the stock in DATA (qty times price over every row) and the item worth the most."""
import csv

with open('DATA') as f:
    rows = list(csv.reader(f))[1:]
total, best, best_value = 0.0, '', -1.0
for name, qty, price in rows:
    value = int(qty) * float(price)
    total += value
    if value > best_value:
        best, best_value = name, value
print(f'total {total:.2f}')
print(f'most {best} {best_value:.2f}')
''', [("import csv", "import cvs"), ("csv.reader(f))[1:]", "csv.reader(f))[0:]"), ("    total += value", "    totl += value")],
       lambda t: (lambda total, name, value: f"total {total:.2f}\nmost {name} {value:.2f}\n")(*_value_parts(t)),
       lambda t: (lambda total, name, _value: [f"{total:.2f}", name])(*_value_parts(t))),
    _b(("grades.py", "class_report.py", "marks.py"), ("grades.txt", "marks.txt", "results.txt"), lambda rng: "name score\n" + _scored(rng), '''
"""Prints the class average of the scores in DATA to one decimal, and who scored highest."""
from statistics import mean

with open('DATA') as f:
    lines = f.read().splitlines()[1:]
scores = {}
for line in lines:
    name, score = line.split()
    scores[name] = int(score)
print(f'average {mean(scores.values()):.1f}')
print(f'top {max(scores, key=scores.get)}')
''', [("from statistics import mean", "from statistics import average"), ("splitlines()[1:]", "splitlines()[0:]"),
      ("    scores[name] = int(score)", "    score[name] = int(score)")],
       lambda t: (lambda average, top: f"average {average}\ntop {top}\n")(*_grade_parts(t)), lambda t: list(_grade_parts(t))),
    _b(("gaps.py", "swing_day.py", "range_day.py"), ("temps.csv", "weather.csv", "week.csv"), _temps, '''
"""Prints the day in DATA with the biggest gap between its low and its high, and the size of that gap."""
import csv

with open('DATA') as f:
    rows = list(csv.DictReader(f))
gaps = {row['day']: int(row['high']) - int(row['low']) for row in rows}
day = max(gaps, key=gaps.get)
print(f'{day} {gaps[day]}')
''', [("import csv", "import csvs"), ("row['high']", "row['hihg']"), ("{gaps[day]}", "{gap[day]}")],
       lambda t: (lambda day, gap: f"{day} {gap}\n")(*_gap_parts(t)), lambda t: [str(x) for x in _gap_parts(t)]),
    _b(("timeline.py", "first_last.py", "between.py"), ("events.txt", "diary.txt", "plan.txt"), _events, '''
"""Prints how many days lie between the first and the last date in DATA, and what happens on the last date."""
from datetime import date

with open('DATA') as f:
    entries = sorted(line.split(' ', 1) for line in f.read().splitlines() if line.strip())
first, last = date.fromisoformat(entries[0][0]), date.fromisoformat(entries[-1][0])
print(f'{(last - first).days} days')
print(f'last: {entries[-1][1]}')
''', [("from datetime import date", "from datetime import Date"), ("entries[-1][1]", "entries[-1][2]"),
      ("date.fromisoformat(entries[0][0])", "date.fromisoformat(entry[0][0])")],
       lambda t: (lambda days, what: f"{days} days\nlast: {what}\n")(*_date_parts(t)), lambda t: [str(x) for x in _date_parts(t)]),
    _b(("sizes.py", "disk_use.py", "folder_size.py"), ("sizes.csv", "files.csv", "listing.csv"), _sizes, '''
"""Prints the total size of the files listed in DATA in kilobytes (1024 bytes, one decimal) and the largest of them."""
with open('DATA') as f:
    rows = [line.split(',') for line in f.read().splitlines()[1:]]
total = sum(int(size) for _name, size in rows)
largest = max(rows, key=lambda row: int(row[1]))[0]
print(f'total {total / 1024:.1f} KB')
print(f'largest {largest}')
''', [("splitlines()[1:]", "splitlines()[:]"), ("{largest}')", "{larges}')"), ("for _name, size in rows)", "for _name, size in row)")],
       lambda t: (lambda kb, name: f"total {kb} KB\nlargest {name}\n")(*_size_parts(t)), lambda t: list(_size_parts(t))),
    _b(("wordstats.py", "story_stats.py", "textinfo.py"), ("story.txt", "chapter.txt", "essay.txt"), _prose, '''
"""Prints how many words DATA has and its longest word (a word is a run of letters; the first one wins a tie)."""
import re

with open('DATA') as f:
    words = re.findall('[A-Za-z]+', f.read())
longest = max(words, key=len)
print(f'{len(words)} words')
print(f'longest: {longest}')
''', [("import re", "import rex"), ("{longest}')", "{longset}')"), ("re.findall(", "re.find_all(")],
       lambda t: (lambda ws: f"{len(ws)} words\nlongest: {max(ws, key=len)}\n")(re.findall("[A-Za-z]+", t)),
       lambda t: (lambda ws: [str(len(ws)), max(ws, key=len)])(re.findall("[A-Za-z]+", t))),
]


@family
def fix_from_traceback(rng):
    """A script that crashes on a wrong import, a misspelt name or an index one off: fix it from its error and say what it then prints."""
    entry = rng.choice(BROKEN)
    script, data = rng.choice(entry["names"]), rng.choice(entry["datas"])
    text, right = entry["gen"](rng), entry["source"].replace("DATA", data)
    output = entry["compute"](text)
    return {"kind": "code", "files": {script: right.replace(*rng.choice(entry["errors"]), 1), data: text},
            "request": say(rng, f"`python3 {script}` stops with an error. Read the error, fix {script} so that it does what its first line says, and tell me what "
                                "it prints.",
                           f"{script} is broken: running it ends in a traceback. Fix it and tell me its output.",
                           f"Get {script} working again (`python3 {script}` fails at the moment). Once it runs, what does it print?",
                           f"Something in {script} makes it crash. Find it from the error message, correct it, and report what the script prints."),
            "expect": {"answer": entry["answer"](text), "files": {data: text}, "run": _exact([(f"python3 {script}", output)]), "may_change": [script]},
            "solution": {"answer": f"Fixed {script}. It prints:\n{output}", "files": {script: right}}}
