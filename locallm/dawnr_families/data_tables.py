"""Tables and records: rows of CSV, JSON and JSON lines filtered, totalled, joined, converted, ranked, counted by
month or hour, checked against a rule and merged. Everything the judge expects (a file to the byte, a JSON value, a
number in the answer) is computed here from the rows the seed draws, and each request names every detail the judge
checks: the file, the header, the order of the rows, the number of decimals."""
from __future__ import annotations

import datetime as dt
import json
import re
from fractions import Fraction

from dawnr_factory import PEOPLE, PLACES, STEMS, THINGS, family, say

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
CATEGORIES = ("food", "travel", "books", "tools", "fuel", "phone", "garden", "gifts", "music", "repairs")
GENRES = ("mystery", "poetry", "history", "travel", "cooking", "science", "fantasy", "drama")
ROOMS = ("attic", "cellar", "garage", "porch", "kitchen", "shed", "hall", "studio")
DEPARTMENTS = ("sales", "support", "design", "finance", "legal", "ops", "research")
PROJECTS = ("atlas", "beacon", "cobalt", "delta", "ember", "falcon", "garnet", "harbor")
STATUSES = ("paid", "shipped", "cancelled", "pending", "returned")
CLUBS = ("chess", "rowing", "choir", "hiking", "pottery", "film", "cycling", "drawing")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
TRADES = ("Hardware", "Paper", "Supply", "Goods", "Trading", "Works")
CHORES = ("fix", "paint", "clean", "order", "move", "check", "label", "return")
FEATURES = ("search", "export", "import", "sharing", "comments", "tags", "backup", "reports", "calendar", "maps")
DECIMALS = {0: "a whole number", 1: "one decimal", 2: "two decimals"}


# ------------------------------------------------------------------ tables --

class Table:
    """Rows of text under named columns, and what each column is for: `groups` to group or match on, `adds` numbers
    that add up, `levels` numbers that only average, `nums` the decimals of every number column, `label` a column
    that names a row, `key` an id column, `when` its date or time."""

    def __init__(self, stem, noun, cols, rows, nums, groups=(), adds=(), levels=(), label=None, key=None, when=None, ids=None):
        self.stem, self.noun, self.cols, self.rows, self.nums = stem, noun, cols, rows, nums
        self.groups, self.adds, self.levels, self.label, self.key, self.when, self.ids = groups, adds, levels, label, key, when, ids

    @property
    def numbers(self) -> tuple:
        return self.adds + tuple(c for c in self.levels if c not in self.adds)

    def csv(self, rows=None, cols=None) -> str:
        cols = cols or self.cols
        return ",".join(cols) + "\n" + "".join(",".join(r.get(c, "") for c in cols) + "\n" for r in (self.rows if rows is None else rows))

    def typed(self, row, cols=None) -> dict:
        """The row with its numbers as numbers."""
        return {c: (row[c] if c not in self.nums else int(row[c]) if self.nums[c] == 0 else float(row[c])) for c in (cols or self.cols)}

    def jsonl(self) -> str:
        return "".join(json.dumps(self.typed(r)) + "\n" for r in self.rows)

    def shown(self, row, col, form) -> str:
        """A value as the file shows it: the CSV's text, or the number JSON writes."""
        return row[col] if form == "csv" or col not in self.nums else json.dumps(self.typed(row, [col])[col])


def _day(rng, year, first, months) -> str:
    m = first + rng.randrange(months)
    return f"{year + (m - 1) // 12}-{(m - 1) % 12 + 1:02d}-{rng.randint(1, 28):02d}"


def _times(rng, n, start, days, weights=None) -> list:
    """n different minutes within `days` days from `start`, in order, written 2026-03-14 09:12."""
    picks: set = set()
    while len(picks) < n:
        picks.add((rng.randrange(days), rng.choices(range(24), weights)[0] if weights else rng.randrange(24), rng.randrange(60)))
    return [(start + dt.timedelta(days=d, hours=h, minutes=m)).strftime("%Y-%m-%d %H:%M") for d, h, m in sorted(picks)]


def expenses(rng, n, span=3):
    cats, who = rng.sample(CATEGORIES, rng.randint(3, 5)), rng.sample(PEOPLE, rng.randint(2, 4))
    year, first = rng.choice((2025, 2026)), rng.randint(1, 12)
    rows = sorted(({"date": _day(rng, year, first, span), "category": rng.choice(cats), "amount": f"{rng.randint(150, 32000) / 100:.2f}",
                    "paid_by": rng.choice(who)} for _ in range(n)), key=lambda r: r["date"])
    return Table(rng.choice(("expenses", "spending", "costs")), ("expense", "expenses"), ["date", "category", "amount", "paid_by"], rows,
                 {"amount": 2}, groups=("category", "paid_by"), adds=("amount",), when="date")


def books(rng, n, span=0):
    n = min(n, 40)
    titles = rng.sample([f"The {t.title()} of {p}" for t in THINGS for p in PLACES], n)
    who, kinds = rng.sample(PEOPLE, rng.randint(4, 7)), rng.sample(GENRES, rng.randint(3, 5))
    rows = [{"id": f"B{101 + i}", "title": titles[i], "author": rng.choice(who), "genre": rng.choice(kinds), "year": str(rng.randint(1958, 2025)),
             "pages": str(rng.randint(90, 980)), "price": f"{rng.randint(4, 48)}.{rng.choice(('25', '50', '75', '95', '99'))}"} for i in range(n)]
    return Table(rng.choice(("books", "library", "bookshelf")), ("book", "books"), ["id", "title", "author", "genre", "year", "pages", "price"], rows,
                 {"year": 0, "pages": 0, "price": 2}, groups=("genre", "author"), adds=("pages", "price"), levels=("year",), label="title", key="id")


def readings(rng, n, span=0):
    where = rng.sample(ROOMS, rng.randint(3, 5))
    start = dt.datetime(rng.choice((2025, 2026)), rng.randint(1, 12), 1)
    rows = [{"sensor": rng.choice(where), "time": t, "celsius": f"{rng.randint(-60, 340) / 10:.1f}", "humidity": str(rng.randint(25, 95))}
            for t in _times(rng, n, start, span or rng.choice((3, 20, 75)))]
    return Table(rng.choice(("readings", "climate", "temperatures")), ("reading", "readings"), ["sensor", "time", "celsius", "humidity"], rows,
                 {"celsius": 1, "humidity": 0}, groups=("sensor",), levels=("celsius", "humidity"), when="time")


def orders(rng, n, span=4):
    who, what, states = rng.sample(PEOPLE, rng.randint(4, 8)), rng.sample(THINGS, rng.randint(4, 8)), rng.sample(STATUSES, rng.randint(3, 4))
    year, first, number = rng.choice((2025, 2026)), rng.randint(1, 12), rng.randint(1001, 8000)
    rows = [{"order_id": str(number + i), "date": d, "customer": rng.choice(who), "item": rng.choice(what), "qty": str(rng.randint(1, 12)),
             "status": rng.choice(states)} for i, d in enumerate(sorted(_day(rng, year, first, span) for _ in range(n)))]
    return Table("orders", ("order", "orders"), ["order_id", "date", "customer", "item", "qty", "status"], rows, {"order_id": 0, "qty": 0},
                 groups=("customer", "item", "status"), adds=("qty",), key="order_id", when="date")


def staff(rng, n, span=0):
    n = min(n, 20)
    names, depts, ids = rng.sample(PEOPLE, n), rng.sample(DEPARTMENTS, rng.randint(3, 5)), sorted(rng.sample(range(100, 1000), n))
    rows = [{"id": f"E{ids[i]}", "name": names[i], "department": rng.choice(depts), "salary": str(rng.randint(560, 1920) * 50),
             "started": _day(rng, rng.randint(2014, 2025), 1, 12)} for i in range(n)]
    return Table(rng.choice(("staff", "employees", "team")), ("employee", "employees"), ["id", "name", "department", "salary", "started"], rows,
                 {"salary": 0}, groups=("department",), adds=("salary",), label="name", key="id", when="started")


def stock(rng, n, span=0):
    n = min(n, 30)
    what, shelves, skus = rng.sample(THINGS, n), rng.sample([r + c for r in "ABCD" for c in "1234"], rng.randint(3, 6)), rng.sample(range(1000, 10000), n)
    rows = [{"sku": f"SK-{skus[i]}", "item": what[i], "shelf": rng.choice(shelves), "count": str(rng.randint(0, 240)),
             "unit_price": f"{rng.randint(100, 9000) / 100:.2f}"} for i in range(n)]
    return Table(rng.choice(("stock", "inventory", "storeroom")), ("item", "items"), ["sku", "item", "shelf", "count", "unit_price"], rows,
                 {"count": 0, "unit_price": 2}, groups=("shelf",), adds=("count",), levels=("unit_price",), label="item", key="sku")


def runs(rng, n, span=3):
    who, year, first = rng.sample(PEOPLE, rng.randint(3, 6)), rng.choice((2025, 2026)), rng.randint(1, 12)
    rows = []
    for d in sorted(_day(rng, year, first, span) for _ in range(n)):
        km = rng.randint(20, 300)
        rows.append({"date": d, "runner": rng.choice(who), "km": f"{km / 10:.1f}", "minutes": str(round(km / 10 * rng.uniform(4.4, 7.6)))})
    return Table(rng.choice(("runs", "training", "running")), ("run", "runs"), ["date", "runner", "km", "minutes"], rows, {"km": 1, "minutes": 0},
                 groups=("runner",), adds=("km", "minutes"), when="date")


def weather(rng, n, span=3):
    cities, year, first = rng.sample(PLACES, rng.randint(3, 5)), rng.choice((2025, 2026)), rng.randint(1, 12)
    seen: dict = {}
    while len(seen) < n:
        seen.setdefault((_day(rng, year, first, span), rng.choice(cities)), (rng.choice((0, 0, 0, rng.randint(1, 420))), rng.randint(-50, 360)))
    rows = [{"date": d, "city": c, "rain_mm": f"{rain / 10:.1f}", "max_c": f"{top / 10:.1f}"} for (d, c), (rain, top) in sorted(seen.items())]
    return Table(rng.choice(("weather", "rainfall", "stations")), ("record", "records"), ["date", "city", "rain_mm", "max_c"], rows,
                 {"rain_mm": 1, "max_c": 1}, groups=("city",), adds=("rain_mm",), levels=("max_c",), when="date")


def hours(rng, n, span=3):
    who, work = rng.sample(PEOPLE, rng.randint(2, 5)), rng.sample(PROJECTS, rng.randint(3, 5))
    year, first = rng.choice((2025, 2026)), rng.randint(1, 12)
    rows = sorted(({"date": _day(rng, year, first, span), "person": rng.choice(who), "project": rng.choice(work), "hours": f"{rng.randint(1, 16) / 2:.1f}"}
                   for _ in range(n)), key=lambda r: r["date"])
    return Table(rng.choice(("hours", "timesheet", "worklog")), ("entry", "entries"), ["date", "person", "project", "hours"], rows, {"hours": 1},
                 groups=("person", "project"), adds=("hours",), when="date")


def visits(rng, n, span=4):
    """Rows whose id comes back again and again: for distinct counts and the most frequent."""
    stem, noun, col, prefix, place, value, places = rng.choice((("deliveries", ("delivery", "deliveries"), "customer", "C-", "depot", "kg", 1),
                                                                ("loans", ("loan", "loans"), "card", "L-", "branch", "days", 0),
                                                                ("gym", ("visit", "visits"), "member", "M-", "site", "minutes", 0)))
    ids = [f"{prefix}{x}" for x in rng.sample(range(1000, 10000), rng.randint(max(6, n // 5), max(8, n // 2)))]
    weight, sites = [rng.random() ** 3 + 0.02 for _ in ids], rng.sample(PLACES, rng.randint(2, 4))
    year, first = rng.choice((2025, 2026)), rng.randint(1, 12)
    rows = sorted(({"date": _day(rng, year, first, span), col: rng.choices(ids, weight)[0], place: rng.choice(sites),
                    value: f"{rng.randint(2, 250) / 10:.1f}" if places else str(rng.randint(5, 120))} for _ in range(n)), key=lambda r: r["date"])
    return Table(stem, noun, ["date", col, place, value], rows, {value: places}, groups=(place,), adds=(value,), when="date", ids=col)


TABLES = (expenses, books, readings, orders, staff, stock, runs, weather, hours, visits)
DATED = (expenses, orders, runs, weather, hours, visits)
PLAIN = tuple(m for m in TABLES if m is not orders)       # an order_id is digits: "numbers as numbers" would not say what it is


# ------------------------------------------------------------------ helpers --

OPS = {">": ("more than {}", "greater than {}"), ">=": ("at least {}", "{} or more"), "<": ("less than {}", "lower than {}"), "<=": ("at most {}", "{} or less")}
TESTS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}


def _condition(rng, t, kinds=("number", "group", "month", "both"), least=2):
    """(words, test, tag): a condition on t's rows that at least `least` rows meet and at least two do not; None when
    none is found. The threshold of a number is a value of the file, so that a row on the edge is there to get right."""
    kinds = [k for k in kinds if {"number": t.numbers, "group": t.groups, "month": t.when, "both": t.groups and t.numbers}[k]]
    for _ in range(30):
        if not kinds:
            return None
        kind, parts, tests, tag = rng.choice(kinds), [], [], ""
        if kind in ("group", "both"):
            col = rng.choice(t.groups)
            value, negate = rng.choice(t.rows)[col], kind == "group" and rng.random() < 0.25
            parts.append(f"whose {col} is {'not ' if negate else ''}{value}")
            tests.append(lambda r, col=col, value=value, negate=negate: (r[col] == value) != negate)
            tag = ("not-" if negate else "") + value.lower()
        if kind in ("number", "both"):
            col, op = rng.choice(t.numbers), rng.choice(tuple(OPS))
            pivot = rng.choice(t.rows)[col]
            parts.append(f"whose `{col}` is " + rng.choice(OPS[op]).format(pivot))
            tests.append(lambda r, col=col, op=op, pivot=Fraction(pivot): TESTS[op](Fraction(r[col]), pivot))
        if kind == "month" and t.when == "started":
            year = rng.choice(t.rows)["started"][:4]
            parts.append(f"whose started date is in {year}")
            tests.append(lambda r, year=year: r["started"][:4] == year)
            tag = year
        elif kind == "month":
            month = rng.choice(t.rows)[t.when][:7]
            parts.append(f"dated in {MONTHS[int(month[5:]) - 1]} {month[:4]}")
            tests.append(lambda r, col=t.when, month=month: r[col][:7] == month)
            tag = month
        test = lambda r, tests=tuple(tests): all(f(r) for f in tests)
        if least <= sum(map(test, t.rows)) <= len(t.rows) - 2:
            return " and ".join(parts), test, tag
    return None


def _fixed(value, places: int, plain: bool = False) -> str | None:
    """A Fraction written with `places` decimals, rounded half up. None when it lies so near a rounding tie that float
    code could round it the other way, or (plain) when it ends in a 0 an answer might leave off."""
    scaled = Fraction(value) * 10 ** places
    if abs(scaled - scaled.numerator // scaled.denominator - Fraction(1, 2)) < Fraction(1, 1000):
        return None
    whole = int((scaled + Fraction(1, 2)) // 1)
    text = ("-" if whole < 0 else "") + str(abs(whole) // 10 ** places) + (f".{abs(whole) % 10 ** places:0{places}d}" if places else "")
    return None if plain and places and text.endswith("0") else text


def _num_re(text: str) -> str:
    """A pattern for the number `text` standing on its own: 1475 also as 1,475 and 12.50 also as 12.5, but not inside
    21475, 1475.5, 2026-03-14 or 09:14; "7,12,19" is a list, so 12 is found in it."""
    sign, whole, digits = re.fullmatch(r"(-?)(\d+)(?:\.(\d+))?", text).groups()
    cut = len(whole) % 3 or 3
    body = whole[:cut] + "".join(rf"[,\u202f\u00a0 ]?{whole[i:i + 3]}" for i in range(cut, len(whole), 3))
    core = (digits or "").rstrip("0")
    tail = (rf"\.{core}0*" if core else r"(?:\.0+)?") if digits else ""
    before = r"(?<![\d.:])" + (r"(?<!\d[,\u202f\u00a0 ])" if len(whole) == 3 else "") + ("" if sign else r"(?<!-)")
    return before + re.escape(sign) + body + tail + r"(?!\d|[.:-]\d|[,\u202f\u00a0 ]\d{3}(?!\d))"


def _id_re(text: str) -> str:
    """A pattern for an id such as E107, SK-1234 or 1043 standing on its own."""
    return _num_re(text) if text.isdigit() else r"(?<![\w-])" + re.escape(text) + r"(?!\d)"


LIST_SEP = r"\s*(?:,\s*and\b|,|;|\band\b)\s*"


def _list_re(items) -> str:
    """A pattern for exactly these ids or numbers as one list, in this order, with nothing listed before or after them:
    "2, 9, 12 and 19" passes for [2, 9, 12, 19], and so does "lines 2,9,12,19."; "2, 9, 12, 19, 21" does not."""
    body = LIST_SEP.join(f"(?:{_id_re(x)})" for x in items)
    return r"(?<!\w,)(?<!\w, )(?<!\w;)(?<!\w; )(?<!\w and )" + body + rf"(?!{LIST_SEP}(?:\d|[A-Za-z]+-?\d))"


def _lines_re(rows) -> str:
    """A pattern for these rows of fields in this order, each row's fields side by side with , : ; | - = ( or spaces between
    them (bold marks, bullets and other words around are fine): a name is checked together with its own figure."""
    sep = r"\**[ \t]*(?:[,:;|=(\u2013\u2014-]|[ \t])[ \t]*\**"
    field = lambda x: _num_re(x) if re.fullmatch(r"-?\d+(\.\d+)?", x) else r"(?<![\w-])" + re.escape(x)
    return "(?s)" + ".*?".join(sep.join(field(x) for x in row) for row in rows)


def _total(rows, col) -> Fraction:
    return sum((Fraction(r[col]) for r in rows), Fraction(0))


def _mean(rows, col) -> Fraction:
    return _total(rows, col) / len(rows)


def _cell(value) -> str:
    return "" if value is None else str(value)


def _dump(value) -> str:
    return json.dumps(value, indent=2) + "\n"


def _words(items) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ------------------------------------------------------------------ families --

@family
def csv_filter(rng):
    """The rows of a CSV that meet a condition, unchanged under the same header: copied to a new file, deleted from the
    file, or moved out of it into a new one."""
    cond = None
    while cond is None:
        t = rng.choice(TABLES)(rng, rng.randint(10, 24))
        cond = _condition(rng, t)
    words, test, tag = cond
    src, rows = f"{t.stem}.csv", t.noun[1]
    hit, rest = [r for r in t.rows if test(r)], [r for r in t.rows if not test(r)]
    out = rng.choice((f"{t.stem}-{tag}.csv", f"{tag}.csv", "selected.csv")) if tag else rng.choice(("selected.csv", "filtered.csv", f"{t.stem}-subset.csv"))
    mode = rng.choice(("copy", "copy", "delete", "move"))
    if mode == "copy":
        request = say(rng, f"Copy the rows of {src} {words} into a new file {out}, with the same header line. Keep those rows exactly as they are and in their original order, and leave {src} unchanged.",
                      f"Make {out} from {src}: its header line, then only the {rows} {words}, unchanged and in the order they appear. {src} itself stays as it is.",
                      f"I only need the {rows} {words}. Put them in {out} under the same header as {src}, each row copied as it is, in the same order; don't touch {src}.")
        want = {out: t.csv(hit), src: t.csv()}
    elif mode == "delete":
        request = say(rng, f"Delete every row of {src} {words}. Keep the header and all the other rows exactly as they are, in the same order.",
                      f"Remove the {rows} {words} from {src}; the header and the remaining rows stay unchanged and in order.",
                      f"{src} has {rows} I don't want: the ones {words}. Take them out of the file and leave everything else in it as it is.")
        want = {src: t.csv(rest)}
    else:
        request = say(rng, f"Move the rows of {src} {words} into {out} (with the same header line), and leave the other rows in {src}. Don't change the rows themselves or their order.",
                      f"Split {src} in two: the {rows} {words} go to a new file {out} under the same header, the others stay in {src}. Rows unchanged, original order in both files.")
        want = {out: t.csv(hit), src: t.csv(rest)}
    return {"kind": "data", "files": {src: t.csv()}, "request": request, "expect": {"files": want},
            "solution": {"answer": "Done.", "files": {k: v for k, v in want.items() if k != src or mode != "copy"}}}


@family
def csv_group_totals(rng):
    """Totals per group of a CSV (or counts and totals, or averages) into a new CSV, in a stated order and number format,
    sometimes over only the rows that meet a condition."""
    while True:
        mode = rng.choice(("total", "total", "count", "average"))
        t = rng.choice(TABLES if mode == "average" else tuple(m for m in TABLES if m is not readings))(rng, rng.randint(14, 40))
        group, value = rng.choice(t.groups), rng.choice(t.numbers if mode == "average" else t.adds)
        only, rows = "", t.rows
        if rng.random() < 0.35:                              # over some rows only, and every group still has some
            cond = _condition(rng, t, ("month", "group"), least=4)
            if cond is None or group in cond[0].split():
                continue
            only, rows = f", counting only the {t.noun[1]} {cond[0]}", [r for r in t.rows if cond[1](r)]
            if {r[group] for r in rows} != {r[group] for r in t.rows}:
                continue
        names = sorted({r[group] for r in rows})
        places = 2 if mode == "average" or t.nums[value] == 2 else 0 if t.nums[value] == 0 else rng.choice((1, 2))
        stat = {g: (_mean if mode == "average" else _total)([r for r in rows if r[group] == g], value) for g in names}
        shown = {g: _fixed(stat[g], places) for g in names}
        order = rng.choice(("desc", "asc", "alpha"))
        if len(names) >= 2 and None not in shown.values() and (order == "alpha" or len(set(shown.values())) == len(names)):
            break
    count = {g: sum(1 for r in rows if r[group] == g) for g in names}
    key = "average" if mode == "average" else rng.choice(("total", f"total_{value}"))
    header = f"{group},count,{key}" if mode == "count" else f"{group},{key}"
    names.sort(key=lambda g: g if order == "alpha" else (stat[g] if order == "asc" else -stat[g]))
    text = header + "\n" + "".join(f"{g},{count[g]},{shown[g]}\n" if mode == "count" else f"{g},{shown[g]}\n" for g in names)
    src, out = f"{t.stem}.csv", rng.choice((f"{group}-{'averages' if mode == 'average' else 'totals'}.csv", f"{t.stem}-by-{group}.csv", f"by-{group}.csv"))
    what = {"total": f"the total {value} of the rows with that {group}", "count": f"the number of rows with that {group} and their total {value}",
            "average": f"the average {value} of the rows with that {group}"}[mode]
    number = {0: "as a whole number", 1: "with one decimal", 2: "with two decimals (7.50, not 7.5)"}[places]
    big = "average" if mode == "average" else "total"
    ordered = {"desc": f"from the largest {big} to the smallest", "asc": f"from the smallest {big} to the largest", "alpha": f"in alphabetical order of {group}"}[order]
    request = say(rng, f"Write {out} with the header `{header}` and one row per {group} in {src}{only}: {what}, {number}. Order the rows {ordered}.",
                  f"From {src}{only}, make a small table {out}: the header line `{header}`, then for each {group} {what}, {number}, {ordered}.",
                  f"For every {group} in {src}{only}, I'd like {what}. Save it as {out} with the header `{header}`, the numbers {number}, rows {ordered}.")
    return {"kind": "data", "files": {src: t.csv()}, "request": request, "expect": {"files": {out: text, src: t.csv()}},
            "solution": {"answer": f"Wrote {out}.", "files": {out: text}}}


def _pair(rng):
    """Two tables that share a key, as (left, right, key, columns the report may take from each side, the noun of a
    left row); the first of the left columns names a row and is what the report may be sorted by."""
    kind, start = rng.choice(("staff", "books", "readings", "stock", "members", "tasks")), dt.datetime(2026, rng.randint(1, 12), rng.randint(1, 20))
    names = rng.sample(PEOPLE, rng.randint(7, 12))
    if kind == "staff":
        depts = rng.sample(DEPARTMENTS, rng.randint(4, 6))
        right = [{"dept": d[:3].upper(), "department": d, "floor": str(rng.randint(1, 6))} for d in depts[1:]]
        left = [{"id": f"E{101 + i}", "name": n, "dept": rng.choice(right)["dept"], "started": _day(rng, rng.randint(2014, 2025), 1, 12)} for i, n in enumerate(names)]
        spec = ("staff", "departments", "dept", depts[0][:3].upper(), ("name", "started"), ("department", "floor"), ("employee", "employees"))
    elif kind == "books":
        right = [{"author_id": f"A{i + 1}", "author": a, "city": rng.choice(PLACES)} for i, a in enumerate(rng.sample(PEOPLE, rng.randint(3, 5)))]
        titles = rng.sample([f"The {t.title()} of {p}" for t in THINGS for p in PLACES], len(names))
        left = [{"book_id": str(201 + i), "title": ti, "author_id": rng.choice(right)["author_id"], "year": str(rng.randint(1960, 2025))} for i, ti in enumerate(titles)]
        spec = ("books", "authors", "author_id", f"A{len(right) + 1}", ("title", "year"), ("author", "city"), ("book", "books"))
    elif kind == "readings":
        right = [{"sensor_id": f"S{i + 1}", "room": r, "floor": str(rng.randint(0, 3))} for i, r in enumerate(rng.sample(ROOMS, rng.randint(3, 5)))]
        left = sorted(({"sensor_id": rng.choice(right)["sensor_id"], "time": t, "celsius": f"{rng.randint(-50, 300) / 10:.1f}"}
                       for t in _times(rng, len(names), start, 2)), key=lambda r: r["sensor_id"])
        spec = ("readings", "sensors", "sensor_id", f"S{len(right) + 1}", ("time", "celsius"), ("room", "floor"), ("reading", "readings"))
    elif kind == "stock":
        right = [{"supplier_id": f"V{10 + i}", "supplier": f"{town} {rng.choice(TRADES)}", "lead_days": str(rng.randint(1, 14))}
                 for i, town in enumerate(rng.sample(PLACES, rng.randint(3, 5)))]
        left = [{"sku": f"SK-{sku}", "item": it, "supplier_id": rng.choice(right)["supplier_id"], "count": str(rng.randint(0, 200))}
                for it, sku in zip(rng.sample(THINGS, len(names)), rng.sample(range(1000, 10000), len(names)))]
        spec = ("stock", "suppliers", "supplier_id", f"V{10 + len(right)}", ("item", "sku", "count"), ("supplier", "lead_days"), ("item", "items"))
    elif kind == "members":
        right = [{"club_id": f"K{i + 1}", "club": c, "meets": rng.choice(WEEKDAYS)} for i, c in enumerate(rng.sample(CLUBS, rng.randint(3, 5)))]
        left = [{"member_id": str(301 + i), "name": n, "club_id": rng.choice(right)["club_id"], "joined": _day(rng, rng.randint(2019, 2026), 1, 12)} for i, n in enumerate(names)]
        spec = ("members", "clubs", "club_id", f"K{len(right) + 1}", ("name", "joined"), ("club", "meets"), ("member", "members"))
    else:
        right = [{"owner_id": f"P{i + 1}", "owner": o, "team": rng.choice(("north", "south", "web", "data", "field"))} for i, o in enumerate(rng.sample(PEOPLE, rng.randint(3, 5)))]
        titles = rng.sample([f"{c} the {t}" for c in CHORES for t in THINGS], len(names))
        left = [{"task_id": str(401 + i), "title": ti, "owner_id": rng.choice(right)["owner_id"], "due": _day(rng, 2026, rng.randint(1, 10), 3)} for i, ti in enumerate(titles)]
        spec = ("tasks", "owners", "owner_id", f"P{len(right) + 1}", ("title", "due"), ("owner", "team"), ("task", "tasks"))
    for r in rng.sample(left, rng.randint(1, 2)):          # a key the other file does not have
        r[spec[2]] = spec[3]
    return left, right, spec


@family
def csv_join(rng):
    """Two CSVs joined on a key into a report with the columns asked for; a row whose key the other file lacks is left
    out or kept with empty cells, as the request says."""
    left, right, (L, R, key, spare, lout, rout, noun) = _pair(rng)
    lcols, rcols = list(left[0]), list(right[0])
    cols = [lout[0]] + rng.sample(list(lout[1:]) + list(rout), rng.randint(2, min(3, len(lout) - 1 + len(rout))))
    if not set(cols) & set(rout):
        cols[-1] = rng.choice(rout)
    keep, order, found = rng.random() < 0.5, rng.choice(("file", "sorted")), {r[key]: r for r in right}
    pairs = [(r, found.get(r[key])) for r in left if keep or r[key] in found]
    if order == "sorted":
        pairs.sort(key=lambda p: p[0][lout[0]])
    header, taken = ",".join(cols), [c for c in cols if c in rout]
    text = header + "\n" + "".join(",".join(a[c] if c in lout else (b[c] if b else "") for c in cols) + "\n" for a, b in pairs)
    Lf, Rf = f"{L}.csv", f"{R}.csv"
    out = rng.choice(("report.csv", f"{L}-{R}.csv", f"{L}-report.csv"))
    ordered = f"in the same order as in {Lf}" if order == "file" else (f"sorted by {lout[0]}, earliest first" if lout[0] == "time" else f"sorted by {lout[0]} alphabetically")
    missing = (f"Leave out any {noun[0]} whose {key} is not in {Rf}." if not keep else
               f"{'An' if noun[0][0] in 'aeiou' else 'A'} {noun[0]} whose {key} is not in {Rf} still gets its row, with {_words(taken)} left empty.")
    request = say(rng, f"Join {Lf} with {Rf} on {key} and write {out} with the header `{header}`, one row per {noun[0]}, {ordered}. {missing}",
                  f"For every {noun[0]} in {Lf}, look up the {key} in {Rf}, and write {out} with the columns {header} (that header line first), {ordered}. {missing}",
                  f"Make {out} from {Lf} and {Rf}, matched on {key}: header `{header}`, rows {ordered}. {missing}")
    files = {Lf: ",".join(lcols) + "\n" + "".join(",".join(r[c] for c in lcols) + "\n" for r in left),
             Rf: ",".join(rcols) + "\n" + "".join(",".join(r[c] for c in rcols) + "\n" for r in right)}
    return {"kind": "data", "files": files, "request": request, "expect": {"files": {out: text, **files}},
            "solution": {"answer": f"Wrote {out}.", "files": {out: text}}}


@family
def records_aggregate(rng):
    """A number only a short program gets right from many rows of CSV or JSON lines: a mean or a total over the rows
    that meet a condition, the largest or smallest under a condition with its row, how many distinct values, or how
    many rows lie above the mean."""
    form, ask = rng.choice(("csv", "csv", "jsonl")), rng.choice(("mean", "total", "extreme", "distinct", "above"))
    expect: dict = {}
    while True:
        t = (visits if ask == "distinct" else rng.choice(TABLES if ask != "above" else (expenses, readings, orders, runs, weather, hours, visits)))(rng, rng.randint(40, 160))
        cond = _condition(rng, t, ("group", "month", "both"), least=3)
        if cond is None or (ask == "total" and not t.adds):
            continue
        words, test, _tag = cond
        hit, col = [r for r in t.rows if test(r)], rng.choice(t.adds if ask == "total" else t.numbers)
        file, rows = f"{t.stem}.{form}", t.noun[1]
        if ask in ("mean", "total"):
            places = rng.choice((1, 2)) if ask == "mean" else t.nums[col]
            figure = _mean if ask == "mean" else _total
            right, wrong = _fixed(figure(hit, col), places, plain=True), _fixed(figure(t.rows, col), places)
            if not right or wrong == right:
                continue
            request = (say(rng, f"What is the mean `{col}` of the {rows} {words} in {file}? Give it to {DECIMALS[places]}.",
                           f"In {file}, take the {rows} {words} and work out their average `{col}`, rounded to {DECIMALS[places]}.",
                           f"I need the average of `{col}` over the {rows} {words} in {file} ({DECIMALS[places]}, please).") if ask == "mean" else
                       say(rng, f"What is the total of `{col}` over the {rows} {words} in {file}?",
                           f"Add up the `{col}` values of all the {rows} {words} in {file}. What do you get?",
                           f"In {file}, what does `{col}` come to altogether for the {rows} {words}?"))
            expect, answer = {"says": [_num_re(right)]}, f"It is {right}."
            if wrong:                                         # the figure over every row, the condition forgotten
                expect["lacks_re"] = [_num_re(wrong)]
        elif ask == "extreme":
            most = rng.choice(("highest", "lowest"))
            ranked = sorted(hit, key=lambda r: Fraction(r[col]), reverse=most == "highest")
            overall = sorted(t.rows, key=lambda r: Fraction(r[col]), reverse=most == "highest")[0]
            if Fraction(ranked[0][col]) == Fraction(ranked[1][col]):
                continue
            best = ranked[0]
            names = [t.label] if t.label else [t.when] + ([g for g in t.groups if g not in words.split()][:1])
            value = t.shown(best, col, form)
            request = say(rng, f"Among the {rows} {words} in {file}, which one has the {most} `{col}`? Give its {_words(names + ['the ' + col])}, as they are written in the file.",
                          f"In {file}, find the {t.noun[0]} with the {most} `{col}` among those {words}, and tell me its {_words(names + ['that ' + col])} (as written in the file).")
            parts = [p for n in names for p in best[n].split(" ")] if t.when in names else [best[n] for n in names]
            expect = {"answer": parts, "says": [_num_re(value)]}
            expect["lacks_re"] = [_num_re(t.shown(ranked[1], col, form))]      # the runner-up, or a list of candidates
            if Fraction(overall[col]) != Fraction(best[col]):                     # the extreme of every row, the condition forgotten
                expect["lacks_re"].append(_num_re(t.shown(overall, col, form)))
            answer = f"{', '.join(best[n] for n in names)}: {col} {value}."
        elif ask == "distinct":
            many = len({r[t.ids] for r in hit})
            if many < 8 or many == len({r[t.ids] for r in t.rows}):
                continue
            request = say(rng, f"How many different {t.ids}s appear among the {rows} {words} in {file}?",
                          f"In {file}, count the distinct {t.ids} values over the {rows} {words}. How many are there?",
                          f"Looking only at the {rows} {words} in {file}, how many separate {t.ids}s are there?")
            expect, answer = {"says": [_num_re(str(many))]}, f"There are {many}."
        else:
            mean = _mean(t.rows, col)
            many = sum(1 for r in t.rows if Fraction(r[col]) > mean)
            if mean in {Fraction(r[col]) for r in t.rows}:
                continue
            request = say(rng, f"How many {rows} in {file} have a `{col}` value above the average `{col}` of all the {rows} in the file?",
                          f"Work out the mean of `{col}` over every row of {file}, then tell me how many {rows} have a `{col}` above it.")
            expect, answer = {"says": [_num_re(str(many))]}, f"{many} of them."
        break
    return {"kind": "data", "files": {file: t.csv() if form == "csv" else t.jsonl()}, "request": request, "expect": expect, "solution": {"answer": answer}}


ENV = (("APP_NAME", lambda rng: rng.choice(STEMS)), ("APP_PORT", lambda rng: str(rng.choice((3000, 5000, 8000, 8080, 9090)))),
       ("APP_TITLE", lambda rng: f"{rng.choice(PLACES)} {rng.choice(THINGS)} club"), ("APP_WORKERS", lambda rng: str(rng.randint(2, 16))),
       ("DB_NAME", lambda rng: rng.choice(STEMS) + "_db"), ("DB_PORT", lambda rng: str(rng.choice((5432, 3306, 27017)))), ("DB_POOL", lambda rng: str(rng.randint(2, 20))),
       ("LOG_LEVEL", lambda rng: rng.choice(("info", "debug", "warning"))), ("LOG_DIR", lambda rng: f"/var/log/{rng.choice(STEMS)}"),
       ("LOG_KEEP_DAYS", lambda rng: str(rng.choice((7, 14, 30, 90)))), ("CACHE_DIR", lambda rng: f"/var/cache/{rng.choice(STEMS)}"),
       ("CACHE_TTL", lambda rng: str(rng.choice((60, 300, 900, 3600)))), ("GREETING", lambda rng: f"Hello from {rng.choice(PLACES)}"),
       ("TIME_ZONE", lambda rng: rng.choice(("Europe/Oslo", "Asia/Tokyo", "Africa/Dakar", "America/Lima"))), ("FEATURE_EXPORT", lambda rng: rng.choice(("true", "false"))),
       ("MAX_UPLOAD_MB", lambda rng: str(rng.choice((5, 10, 25, 50)))), ("REPORT_DAY", lambda rng: rng.choice(WEEKDAYS)))
PREFIXES = ("APP_", "DB_", "LOG_", "CACHE_")


@family
def records_convert(rng):
    """Records from one format into another: CSV to a JSON list or object (numbers as numbers) or to JSON lines, JSON or
    JSON lines to CSV in a stated column order, an env file to JSON, a flat JSON object to an env file."""
    way = rng.choice(("csv-json", "csv-json", "json-csv", "csv-jsonl", "env-json", "json-env"))
    if way in ("csv-json", "csv-jsonl"):
        t = rng.choice(PLAIN)(rng, rng.randint(4, 9))
        src = f"{t.stem}.csv"
        shape = rng.choice(("list", "some", "keyed" if t.label or t.key else "list")) if way == "csv-json" else "lines"
        cols = sorted(rng.sample(t.cols, 3), key=t.cols.index) if shape == "some" else t.cols
        if shape == "keyed":
            by = t.key or t.label
            want = {r[by]: t.typed(r, [c for c in t.cols if c != by]) for r in t.rows}
            shaped = f"one JSON object whose keys are the {by} values, each mapped to an object of that row's other columns"
        else:
            want = [t.typed(r, cols) for r in t.rows]
            shaped = (f"a JSON list with one object per row, holding only the columns {_words(cols)}" if shape == "some" else
                      "one JSON object per line, one line per row in the same order, with the header's names as keys" if shape == "lines" else
                      "a JSON list with one object per row, in the same order, with the header's names as keys")
        out = f"{t.stem}.jsonl" if shape == "lines" else f"{t.stem}.json"
        request = say(rng, f"Convert {src} to {out}: {shaped}. Numbers must be JSON numbers, everything else stays text.",
                      f"I need the data of {src} as {out}, written as {shaped}; numeric values as numbers, not strings.",
                      f"Make {out} out of {src} ({shaped}). Keep numbers as numbers and the rest as strings, and leave {src} alone.")
        expect = {"files": {src: t.csv()}}
        if shape == "lines":
            def lines(work, out=out, want=want):
                try:
                    got = [json.loads(line) for line in (work / out).read_text().splitlines() if line.strip()]
                except (OSError, ValueError):
                    return [f"{out} is missing or is not one JSON object per line"]
                return [] if got == want else [f"{out} does not hold the rows of {src} as asked"]
            expect.update(fn=lines, may_change=[out])
            made = "".join(json.dumps(x) + "\n" for x in want)
        else:
            expect["json"], made = {out: want}, _dump(want)
        return {"kind": "data", "files": {src: t.csv()}, "request": request, "expect": expect, "solution": {"answer": f"Wrote {out}.", "files": {out: made}}}
    if way == "json-csv":
        t = rng.choice(PLAIN)(rng, rng.randint(4, 9))
        records = [dict(rng.sample(list(t.typed(r).items()), len(t.cols))) for r in t.rows]
        cols, by = rng.sample(t.cols, rng.randint(3, len(t.cols))), t.label or t.key or t.when
        gap = rng.choice([c for c in cols if c not in (t.key, t.label, by)])
        for rec in rng.sample(records, rng.randint(1, 2)):
            del rec[gap]
        form = rng.choice(("json", "jsonl"))
        src, out = f"{t.stem}.{form}", f"{t.stem}.csv"
        order = rng.choice(("file", "sorted")) if by in cols and len({rec[by] for rec in records}) == len(records) else "file"
        records_out = sorted(records, key=lambda rec: rec[by]) if order == "sorted" else records
        text = ",".join(cols) + "\n" + "".join(",".join(_cell(rec.get(c)) for c in cols) + "\n" for rec in records_out)
        ordered = f"in the order of {src}" if order == "file" else f"sorted by {by}" + (", earliest first" if by == t.when else " alphabetically")
        request = say(rng, f"Turn {src} into {out}: a CSV with the header `{','.join(cols)}` (columns in exactly that order) and one row per record, {ordered}. Where a record has no {gap}, leave that cell empty. Numbers are written as they are in {src}.",
                      f"Write {out} from the records in {src}, with the columns {','.join(cols)} in that order as the header line, rows {ordered}; a missing {gap} becomes an empty cell, and numbers stay as {src} writes them.")
        source = _dump(records) if form == "json" else "".join(json.dumps(rec) + "\n" for rec in records)
        return {"kind": "data", "files": {src: source}, "request": request, "expect": {"files": {out: text, src: source}}, "solution": {"answer": f"Wrote {out}.", "files": {out: text}}}
    if way == "env-json":
        chosen, lines = rng.sample(ENV, rng.randint(6, 10)), [f"# settings for the {rng.choice(STEMS)} service"]
        found = {}
        for name, make_value in chosen:
            value = make_value(rng) if rng.random() > 0.1 else ""
            style = rng.choice(('"', "'", "") if " " not in value else ('"', "'"))
            lines += ([""] if rng.random() < 0.2 else []) + ([f"# {name.lower().replace('_', ' ')}"] if rng.random() < 0.2 else [])
            lines.append(("export " if rng.random() < 0.25 else "") + f"{name}={style}{value}{style}")
            found[name] = value
        shared = [p for p in PREFIXES if sum(name.startswith(p) for name in found) >= 2]
        rule = rng.choice(("same", "lower", "prefix") if shared else ("same", "lower"))
        prefix = rng.choice(shared) if rule == "prefix" else ""
        want = {"same": dict(found), "lower": {k.lower(): v for k, v in found.items()},
                "prefix": {k[len(prefix):]: v for k, v in found.items() if k.startswith(prefix)}}[rule]
        src, out = rng.choice(("app.env", "server.env", "worker.env", "local.env")), rng.choice(("env.json", "settings.json", "config.json"))
        text = "\n".join(lines) + "\n"
        keys = {"same": "the same keys", "lower": "every key in lower case",
                "prefix": f"only the variables whose name starts with {prefix}, with that prefix taken off the key"}[rule]
        request = say(rng, f"Turn {src} into {out}: one JSON object with {keys}, and every value as a string. Skip blank lines and comment lines (starting with #), drop a leading `export `, and take the quotes off a quoted value.",
                      f"Read the variables in {src} (KEY=value lines; ignore blank lines and lines starting with #, strip any `export ` in front and the quotes around quoted values) and write them to {out} as a JSON object with {keys}. All values stay strings.")
        return {"kind": "data", "files": {src: text}, "request": request, "expect": {"json": {out: want}, "files": {src: text}}, "solution": {"answer": f"Wrote {out}.", "files": {out: _dump(want)}}}
    chosen = rng.sample(ENV, rng.randint(5, 8))
    data = {}
    for name, make_value in chosen:
        value = make_value(rng)
        data[name.lower()] = int(value) if value.isdigit() else (value == "true") if value in ("true", "false") else value
    src, out = rng.choice(("config.json", "settings.json", "service.json")), rng.choice(("app.env", "service.env", "deploy.env"))
    shown = {True: "true", False: "false"}
    text = "".join(f"{k.upper()}=" + (f'"{v}"' if isinstance(v, str) and " " in v else shown.get(v, v) if isinstance(v, bool) else str(v)) + "\n" for k, v in data.items())
    request = say(rng, f"Write {out} from {src}: one line KEY=value per key, in the order of {src}, the key in capital letters, true and false in lower case, numbers as they are, and double quotes around a value only when it contains a space.",
                  f"I need the settings in {src} as an env file, {out}: a KEY=value line for each key in the same order, keys upper-cased, booleans written true or false, numbers unchanged, and a value with a space in it wrapped in double quotes (no quotes otherwise).")
    return {"kind": "data", "files": {src: _dump(data)}, "request": request, "expect": {"files": {out: text, src: _dump(data)}}, "solution": {"answer": f"Wrote {out}.", "files": {out: text}}}


@family
def records_top_k(rng):
    """The k largest, smallest or most frequent in a table of records (CSV or JSON lines), written as lines in a stated
    format or given as the answer."""
    k, form, how = rng.choice((3, 4, 5)), rng.choice(("csv", "csv", "jsonl")), rng.choice(("largest", "largest", "frequent"))
    while True:
        if how == "largest":
            t = rng.choice((books, staff, stock, readings, runs, weather, expenses))(rng, rng.randint(15, 60))
            col, most = rng.choice(t.numbers), rng.choice(("highest", "lowest"))
            ranked = sorted(t.rows, key=lambda r: Fraction(r[col]), reverse=most == "highest")
            if len({Fraction(r[col]) for r in ranked[:k + 1]}) < k + 1:
                continue
            names = [t.label] if t.label else [t.when, t.groups[0]]
            sep = rng.choice((": ", ",")) if len(names) == 1 else rng.choice((",", " "))
            template = sep.join(names + [col]) if sep != ": " else f"{names[0]}: {col}"
            lines = [sep.join([r[n] for n in names] + [t.shown(r, col, form)]) for r in ranked[:k]]
            file, rows = f"{t.stem}.{form}", t.noun[1]
            ask = say(rng, f"which {k} {rows} in {file} have the {most} {col}", f"the {k} {rows} with the {most} {col} in {file}")
            order, figure = f"{most} first", f"its {col}"
            parts = [[r[n] for n in names] + [t.shown(r, col, form)] for r in ranked[:k]]
            beyond = _num_re(t.shown(ranked[k], col, form))
            break
        t = rng.choice((visits, visits, orders, expenses))(rng, rng.randint(40, 140))
        col = t.ids or rng.choice(t.groups)
        tally: dict = {}
        for r in t.rows:
            tally[r[col]] = tally.get(r[col], 0) + 1
        ranked = sorted(sorted(tally), key=lambda v: -tally[v])
        if len(ranked) <= k or len({tally[v] for v in ranked[:k + 1]}) < k + 1:
            continue
        sep = rng.choice((" ", ",", ": "))
        template, lines = f"{col}{sep}count", [f"{v}{sep}{tally[v]}" for v in ranked[:k]]
        file, rows, order, figure = f"{t.stem}.{form}", t.noun[1], "most frequent first", "the number of rows it has"
        ask = say(rng, f"which {k} {col} values occur in the most rows of {file}", f"the {k} {col} values that appear most often in {file} (counting rows)")
        parts = [[v, str(tally[v])] for v in ranked[:k]]
        beyond = r"(?<![\w-])" + re.escape(ranked[k]) + r"(?![\w-])"
        break
    source = t.csv() if form == "csv" else t.jsonl()
    if rng.random() < 0.3:
        request = say(rng, f"Tell me {ask}, each with {figure}: one line apiece as `{template}`, {order}.",
                      f"Please list {ask}, {order}, one per line in the form `{template}`.")
        request = request[0].upper() + request[1:]
        return {"kind": "data", "files": {file: source}, "request": request, "expect": {"says": [_lines_re(parts)], "lacks_re": [beyond]},
                "solution": {"answer": "\n".join(lines)}}
    out = rng.choice((f"top{k}.txt", f"top-{col}.txt", "top.txt"))
    text = "\n".join(lines) + "\n"
    request = say(rng, f"Find {ask} and write them to {out}, {order}, one per line as `{template}` (values as the file writes them).",
                  f"Write {out} listing {ask}: {k} lines, {order}, each in the form `{template}` with the values as they appear in the file.")
    return {"kind": "data", "files": {file: source}, "request": request, "expect": {"files": {out: text, file: source}}, "solution": {"answer": f"Wrote {out}.", "files": {out: text}}}


LOGS = (("door.log", ("front-door", "back-door", "garage-door"), ("opened", "closed")), ("pump.log", ("pump-1", "pump-2"), ("started", "stopped")),
        ("printer.log", ("printer-a", "printer-b"), ("printed", "jammed")), ("alarm.log", ("zone-1", "zone-2", "zone-3"), ("armed", "disarmed", "triggered")))


@family
def records_per_period(rng):
    """How many records, or how much, per month or per hour of the day (all days together) from the timestamps of a CSV,
    a JSON lines file or a log, written as a small CSV table."""
    unit, every = rng.choice(("month", "month", "hour")), rng.random() < 0.4
    if unit == "month":
        while True:
            t = rng.choice(DATED)(rng, rng.randint(25, 90), span=rng.randint(4, 7))
            months = sorted({r[t.when][:7] for r in t.rows})
            if len(months) < 3:
                continue
            if every:                                         # a month in the middle with nothing in it
                gone = rng.choice(months[1:-1])
                t.rows = [r for r in t.rows if r[t.when][:7] != gone]
            y, m = int(months[0][:4]), int(months[0][5:])
            span = []
            while f"{y}-{m:02d}" <= months[-1]:
                span.append(f"{y}-{m:02d}")
                y, m = (y + 1, 1) if m == 12 else (y, m + 1)
            keep = span if every else sorted({r[t.when][:7] for r in t.rows})
            col = rng.choice(t.adds) if rng.random() < 0.35 else None
            places = (2 if t.nums[col] else 0) if col else 0
            in_month = {k: [r for r in t.rows if r[t.when][:7] == k] for k in keep}
            figure = {k: _fixed(_total(in_month[k], col), places) if col else str(len(in_month[k])) for k in keep}
            if None not in figure.values():
                break
        form = rng.choice(("csv", "csv", "jsonl"))
        file, rows = f"{t.stem}.{form}", t.noun[1]
        out, header = rng.choice(("per-month.csv", "monthly.csv", f"{t.stem}-by-month.csv")), "month,total" if col else "month,count"
        what = f"the total `{col}` of the {rows} in each month" if col else f"the number of {rows} in each month"
        amount = (" (totals as whole numbers)" if places == 0 else " (totals with two decimals, like 7.50)") if col else ""
        nothing = _fixed(Fraction(0), places) if col else "0"
        zeros = f"Include every month from {span[0]} to {span[-1]}, with {nothing} for a month that has none." if every else f"Only the months that have {rows}."
        request = say(rng, f"From {file}, write {out} with the header `{header}`: {what}{amount}, the month written like {span[0]}, oldest month first. {zeros}",
                      f"Put {what} of {file} into {out}{amount}: header `{header}`, one row per month (YYYY-MM), in calendar order. {zeros}")
        source = t.csv() if form == "csv" else t.jsonl()
        text = header + "\n" + "".join(f"{k},{figure[k]}\n" for k in keep)
        return {"kind": "data", "files": {file: source}, "request": request, "expect": {"files": {out: text, file: source}}, "solution": {"answer": f"Wrote {out}.", "files": {out: text}}}
    weights = [rng.random() ** 2 * (3 if 7 <= h <= 19 else 1) for h in range(24)]
    start, n = dt.datetime(rng.choice((2025, 2026)), rng.randint(1, 12), rng.randint(1, 20)), rng.randint(40, 160)
    source_kind = rng.choice(("readings", "log", "jsonl"))
    if source_kind == "readings":
        t = readings(rng, n, span=rng.randint(2, 9))
        stamps = [r["time"] for r in t.rows]
        file, what, source = f"{t.stem}.csv", "readings", t.csv()
    else:
        stamps = _times(rng, n, start, rng.randint(2, 12), weights)
        seconds = [rng.randrange(60) for _ in stamps]
        if source_kind == "log":
            file, devices, events = rng.choice(LOGS)
            pairs = [(s, rng.choice(events)) for s in stamps]
            source = "".join(f"{s}:{sec:02d} {rng.choice(devices)} {e}\n" for (s, e), sec in zip(pairs, seconds))
        else:
            file, events = rng.choice((("events.jsonl", ("login", "logout")), ("app-events.jsonl", ("upload", "download", "delete"))))
            pairs = [(s, rng.choice(events)) for s in stamps]
            source = "".join(json.dumps({"at": s.replace(" ", "T") + f":{sec:02d}", "user": rng.choice(PEOPLE).lower(), "event": e}) + "\n"
                             for (s, e), sec in zip(pairs, seconds))
        event = rng.choice(events)
        stamps = [s for s, e in pairs if e == event]
        what = f'lines whose event is "{event}"' if source_kind == "log" else f'records whose "event" is "{event}"'
    tally = {f"{h:02d}": sum(1 for s in stamps if s[11:13] == f"{h:02d}") for h in range(24)}
    keep = list(tally) if every else [h for h in tally if tally[h]]
    out = rng.choice(("per-hour.csv", "hourly.csv", "by-hour.csv"))
    zeros = "List all 24 hours, with 0 where there are none." if every else "Leave out the hours that have none."
    request = say(rng, f"Count the {what} in {file} per hour of the day, over all the days together, and write {out} with the header `hour,count`: the hour as two digits (00 to 23), in order. {zeros}",
                  f"For each hour of the day (00 to 23, all days added together), how many {what} are in {file}? Save the counts as {out}, header `hour,count`, hours as two digits, earliest hour first. {zeros}")
    text = "hour,count\n" + "".join(f"{h},{tally[h]}\n" for h in keep)
    return {"kind": "data", "files": {file: source}, "request": request, "expect": {"files": {out: text, file: source}}, "solution": {"answer": f"Wrote {out}.", "files": {out: text}}}


def _shift(day: str, days: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=days)).isoformat()


@family
def records_validate(rng):
    """The rows of a table that break a stated rule (a field left empty, a value that is not a number or lies outside a
    range, a date that is not a real date or falls outside a range), found and written out or named; in a JSON lines
    file, the lines that are not valid JSON or lack a number."""
    if rng.random() < 0.25:
        return _validate_jsonl(rng)
    while True:
        t = rng.choice((expenses, orders, runs, staff, books, stock, hours, weather))(rng, rng.randint(14, 30))
        rules = rng.sample([r for r in ("number", "empty", "date", "range") if r != "date" or t.when], rng.randint(1, 2))
        col = rng.choice(t.numbers)
        values = sorted(Fraction(r[col]) for r in t.rows)
        lo, hi = values[1], values[-2]
        if lo < hi:
            break
    rows = [dict(r) for r in t.rows]
    bad_at = sorted(rng.sample(range(len(rows)), rng.randint(2, 4)))
    edge_at = rng.sample([i for i in range(len(rows)) if i not in bad_at], rng.randint(1, 2))
    if t.when:
        days = sorted(r[t.when] for r in rows)
        first, last = days[0][:8] + "01", days[-1]
    said = []
    for rule in rules:
        if rule == "number":
            said.append(f"its {col} is not a number")
        elif rule == "empty":
            said.append("any of its fields is empty")
        elif rule == "date":
            said.append(f"its {t.when} is not a real date from {first} to {last} (both included) written as YYYY-MM-DD")
        else:
            said.append(f"its {col} is not between {lo} and {hi} (both included)" if t.nums[col] == 0 else
                        f"its {col} is not between {_fixed(lo, t.nums[col])} and {_fixed(hi, t.nums[col])} (both included)")
    lo_text, hi_text = (str(lo), str(hi)) if t.nums[col] == 0 else (_fixed(lo, t.nums[col]), _fixed(hi, t.nums[col]))
    for i in bad_at:
        rule = rng.choice(rules)
        if rule == "number":
            rows[i][col] = rng.choice(("n/a", "TBD", "?", "abc", "12.5.0", "1O5", "--"))
        elif rule == "empty":
            rows[i][rng.choice([c for c in t.cols if c != t.key])] = ""
        elif rule == "date":
            rows[i][t.when] = rng.choice((_shift(first, -rng.randint(1, 40)), _shift(last, rng.randint(1, 40)), first[:5] + "02-30", first[:5] + "13-02",
                                          first.replace("-", "/"), f"{first[8:]}.{first[5:7]}.{first[:4]}"))
        else:
            step = Fraction(1, 10 ** t.nums[col]) * rng.randint(1, 50)
            rows[i][col] = _fixed(lo - step, t.nums[col]) if rng.random() < 0.5 else _fixed(hi + step, t.nums[col])
            if t.nums[col] == 0:
                rows[i][col] = str(int(Fraction(rows[i][col])))
    for i in edge_at:                                        # right on the edge of a rule, and good
        rule = rng.choice(rules)
        if rule == "number":
            rows[i][col] = "0" if t.nums[col] == 0 else _fixed(Fraction(0), t.nums[col])
            if "range" in rules and not lo <= 0 <= hi:
                rows[i][col] = lo_text
        elif rule == "date":
            rows[i][t.when] = rng.choice((first, last))
        elif rule == "range":
            rows[i][col] = rng.choice((lo_text, hi_text))
    def broken(r):
        for rule in rules:
            if rule == "number" and not re.fullmatch(r"-?\d+(\.\d+)?", r[col]):
                return True
            if rule == "empty" and any(r[c] == "" for c in t.cols):
                return True
            if rule == "date":
                try:
                    if not (re.fullmatch(r"\d{4}-\d\d-\d\d", r[t.when]) and first <= dt.date.fromisoformat(r[t.when]).isoformat() <= last):
                        return True
                except ValueError:
                    return True
            if rule == "range" and re.fullmatch(r"-?\d+(\.\d+)?", r[col]) and not lo <= Fraction(r[col]) <= hi:
                return True
        return False
    bad = [i for i, r in enumerate(rows) if broken(r)]
    t.rows = rows
    src = f"{t.stem}.csv"
    rule_text = "A row is bad when " + " or when ".join(said) + "."
    how = rng.choice(("rejects", "split", "lines", "answer"))
    if how == "answer" and t.key:
        request = say(rng, f"Check {src} against this rule and tell me the {t.key} of every bad row, in the order of the file, separated by commas. {rule_text}",
                      f"{rule_text} Which rows of {src} are bad? Answer with their {t.key} values as one comma-separated list, in file order.")
        ids = [rows[i][t.key] for i in bad]
        return {"kind": "data", "files": {src: t.csv()}, "request": request, "expect": {"says": [_list_re(ids)]}, "solution": {"answer": "Bad rows: " + ", ".join(ids) + "."}}
    if how in ("lines", "answer"):
        numbers = [str(i + 2) for i in bad]
        if how == "answer":
            request = say(rng, f"{rule_text} Which lines of {src} hold a bad row? Count the header as line 1, and answer with the line numbers in order, separated by commas.",
                          f"Go through {src} and give me the line numbers of the bad rows (the header is line 1) as one comma-separated list, smallest first. {rule_text}")
            return {"kind": "data", "files": {src: t.csv()}, "request": request, "expect": {"says": [_list_re(numbers)]},
                    "solution": {"answer": "Lines " + ", ".join(numbers) + "."}}
        out = rng.choice(("bad-lines.txt", "problems.txt", "invalid-lines.txt"))
        request = say(rng, f"{rule_text} Write the line numbers of the bad rows of {src} to {out}, one number per line, smallest first, counting the header as line 1.",
                      f"Find the rows of {src} that break this rule and put their line numbers in {out} (one per line, in order; the header is line 1). {rule_text}")
        text = "\n".join(numbers) + "\n"
        return {"kind": "data", "files": {src: t.csv()}, "request": request, "expect": {"files": {out: text, src: t.csv()}}, "solution": {"answer": f"Wrote {out}.", "files": {out: text}}}
    out = rng.choice(("rejects.csv", "bad-rows.csv", "invalid.csv"))
    wrong, right = [rows[i] for i in bad], [r for i, r in enumerate(rows) if i not in bad]
    if how == "rejects":
        request = say(rng, f"{rule_text} Copy the bad rows of {src} into {out}, under the same header, unchanged and in their original order. Leave {src} as it is.",
                      f"Check every row of {src}: {rule_text[0].lower() + rule_text[1:]} Put the bad ones in {out} with the same header line, rows as they are, same order; don't change {src}.")
        want = {out: t.csv(wrong), src: t.csv()}
    else:
        request = say(rng, f"{rule_text} Move the bad rows of {src} into {out} (same header line, rows unchanged, original order) so that {src} keeps only the good ones.",
                      f"Clean up {src}: {rule_text[0].lower() + rule_text[1:]} Take the bad rows out of it and put them, as they are and in order, into {out} under the same header.")
        want = {out: t.csv(wrong), src: t.csv(right)}
    return {"kind": "data", "files": {src: t.csv()}, "request": request, "expect": {"files": want},
            "solution": {"answer": "Done.", "files": {k: v for k, v in want.items() if k != src or how != "rejects"}}}


def _validate_jsonl(rng):
    t = rng.choice((expenses, runs, readings, orders, hours, weather))(rng, rng.randint(14, 30))
    col = rng.choice(t.numbers)
    lines = [json.dumps(t.typed(r)) for r in t.rows]
    bad = sorted(rng.sample(range(len(lines)), rng.randint(2, 4)))
    for i in bad:
        rec = t.typed(t.rows[i])
        kind = rng.choice(("cut", "quotes", "missing", "text", "null"))
        if kind == "cut":
            lines[i] = lines[i][:-1]
        elif kind == "quotes":
            lines[i] = lines[i].replace('"', "'")
        elif kind == "missing":
            del rec[col]
            lines[i] = json.dumps(rec)
        else:
            rec[col] = str(rec[col]) if kind == "text" else None
            lines[i] = json.dumps(rec)
    for i in rng.sample([i for i in range(len(lines)) if i not in bad], 1):    # good, if odd: a zero, the keys in another order
        rec = t.typed(t.rows[i])
        rec[col] = 0
        lines[i] = json.dumps(dict(reversed(list(rec.items()))))
    src = f"{t.stem}.jsonl"
    source = "\n".join(lines) + "\n"
    numbers = [str(i + 1) for i in bad]
    rule = f"A line is bad when it is not valid JSON, when it has no \"{col}\", or when its {col} is not a JSON number (a quoted \"12\" is text, and null is not a number)."
    if rng.random() < 0.5:
        out = rng.choice(("bad-lines.txt", "broken.txt"))
        request = say(rng, f"{rule} Write the line numbers of the bad lines of {src} to {out}, one per line, in order, counting the first line as 1.",
                      f"Some lines of {src} are broken. {rule} List their line numbers (the first line is 1) in {out}, one per line, smallest first.")
        text = "\n".join(numbers) + "\n"
        return {"kind": "data", "files": {src: source}, "request": request, "expect": {"files": {out: text, src: source}}, "solution": {"answer": f"Wrote {out}.", "files": {out: text}}}
    request = say(rng, f"{rule} Which lines of {src} are bad? Give their line numbers, the first line being 1, as one comma-separated list in order.",
                  f"Check {src} line by line and tell me which line numbers are bad (counting from 1), smallest first and separated by commas. {rule}")
    return {"kind": "data", "files": {src: source}, "request": request, "expect": {"says": [_list_re(numbers)]}, "solution": {"answer": "Lines " + ", ".join(numbers) + "."}}


def _merged(a: dict, b: dict, lists: str) -> dict:
    """b over a: objects merged key by key (not at all for "top"), lists joined without repeats ("join") or replaced."""
    out = dict(a)
    for k, v in b.items():
        if lists != "top" and isinstance(a.get(k), dict) and isinstance(v, dict):
            out[k] = _merged(a[k], v, lists)
        elif lists == "join" and isinstance(a.get(k), list) and isinstance(v, list):
            out[k] = a[k] + [x for x in v if x not in a[k]]
        else:
            out[k] = v
    return out


@family
def json_merge(rng):
    """Two JSON files merged by a stated rule: the second's values win with objects merged key by key and lists joined
    without repeats (or replaced), a top-level merge, records matched by id, or a folder of JSON parts made one file."""
    way = rng.choice(("join", "join", "replace", "top", "records", "parts"))
    if way in ("join", "replace", "top"):
        name = rng.choice(STEMS)
        first = {"name": name, "port": rng.choice((3000, 5000, 8000, 8080)), "debug": False,
                 "log": {"level": rng.choice(("info", "warning")), "file": f"{name}.log", "keep_days": rng.choice((7, 14, 30))},
                 "paths": {"data": f"/srv/{name}/data", "cache": f"/var/cache/{name}"}, "features": rng.sample(FEATURES, 3), "admins": sorted(rng.sample(PEOPLE, 2))}
        second = {"log": {"level": "debug", "format": rng.choice(("json", "text"))},
                  "features": [rng.choice(first["features"])] + rng.sample([f for f in FEATURES if f not in first["features"]], 2)}
        if rng.random() < 0.6:
            second["port"] = rng.choice([p for p in (3001, 5050, 8081, 9000) if p != first["port"]])
        if rng.random() < 0.5:
            second["admins"] = [rng.choice(first["admins"]), rng.choice([p for p in PEOPLE if p not in first["admins"]])]
        if rng.random() < 0.5:
            second["mail"] = {"from": f"{name}@example.org", "every_hours": rng.choice((6, 12, 24))}
        if rng.random() < 0.4:
            second["debug"] = True
        second = dict(rng.sample(list(second.items()), len(second)))
        a, b = rng.choice((("defaults.json", "local.json"), ("base.json", "override.json"), ("team.json", "mine.json"), ("shared.json", "custom.json")))
        out = rng.choice(("merged.json", "effective.json", "combined.json"))
        want = _merged(first, second, way)
        rule = {"join": f"where both files set the same key, {b} wins; an object found in both is merged key by key the same way; a list found in both becomes "
                        f"{a}'s items followed by those of {b}'s items that are not already in it; keys found in only one file are kept",
                "replace": f"where both files set the same key, {b} wins; an object found in both is merged key by key the same way, but a list in {b} replaces "
                           f"{a}'s list whole; keys found in only one file are kept",
                "top": f"only the top level counts, so each top-level key of {b} replaces the same key of {a} completely, with no merging inside it; keys "
                       f"only in {a} stay as they are"}[way]
        request = say(rng, f"Merge {a} and {b} into {out}: {rule}. Don't change the two files.",
                      f"Combine {a} with {b} and save the result as {out}. The rule: {rule}.")
        files = {a: _dump(first), b: _dump(second)}
    elif way == "records":
        stem = rng.choice(("plants", "tools", "rooms", "parts"))
        ids = rng.sample(range(1, 80), rng.randint(9, 14))
        olds, news = sorted(ids[:-3]), ids[-3:]
        first = [{"id": i, "name": rng.choice(THINGS), "count": rng.randint(0, 40), "place": rng.choice(PLACES)} for i in olds]
        changed = rng.sample(olds, rng.randint(2, 3))
        whole = rng.random() < 0.5
        second = [({"id": i, "name": rng.choice(THINGS), "count": rng.randint(0, 40), "place": rng.choice(PLACES)} if whole else
                   {"id": i, "count": rng.randint(41, 90)}) for i in changed]
        second += [{"id": i, "name": rng.choice(THINGS), "count": rng.randint(0, 40), "place": rng.choice(PLACES)} for i in news]
        rng.shuffle(second)
        a, b, out = f"{stem}.json", rng.choice(("updates.json", "changes.json", f"{stem}-new.json")), rng.choice((f"{stem}-merged.json", "merged.json"))
        by_id = {r["id"]: r for r in second}
        sort = rng.random() < 0.5
        want = [((by_id[r["id"]] if whole else {**r, **by_id[r["id"]]}) if r["id"] in by_id else r) for r in first]
        want += [r for r in second if r["id"] not in {x["id"] for x in first}]
        if sort:
            want.sort(key=lambda r: r["id"])
        replace = ("a record of {b} replaces the record with the same id in {a} whole" if whole else
                   "the fields of a record in {b} overwrite those of the record with the same id in {a}, and the fields it does not have keep their old values").format(a=a, b=b)
        order = "sorted by id" if sort else f"{a}'s records in their order, then {b}'s new records in the order they appear there"
        request = say(rng, f"Merge the records of {b} into those of {a} and write the result to {out}: {replace}; records whose id is in only one file are kept. The list is {order}.",
                      f"Write {out}: the records of {a} updated from {b} by id ({replace}), plus the records of {b} with a new id, {order}. Leave {a} and {b} as they are.")
        files = {a: _dump(first), b: _dump(second)}
    else:
        folder = rng.choice(("parts", "daily", "exports"))
        names = sorted(rng.sample([f"{p.lower()}" for p in PLACES], rng.randint(3, 5)))
        parts = {n: [{"item": rng.choice(THINGS), "qty": rng.randint(1, 20)} for _ in range(rng.randint(1, 4))] for n in names}
        files = {f"{folder}/{n}.json": _dump(parts[n]) for n in names}
        out = rng.choice(("all.json", "combined.json"))
        if rng.random() < 0.5:
            want = [x for n in names for x in parts[n]]
            request = say(rng, f"Combine the JSON files in {folder}/ into {out}: one list holding every record of every file, the files taken in alphabetical order of their names, the records of each in their own order.",
                          f"Each file in {folder}/ is a JSON list. Join them into one list in {out}, file by file in alphabetical order of the file names, keeping each file's records in order.")
        else:
            want = {n: parts[n] for n in names}
            request = say(rng, f"Put the JSON files of {folder}/ together into {out}: one object whose keys are the file names without .json, each mapped to that file's content.",
                          f"Make {out} from the files in {folder}/: a JSON object with one key per file (its name, minus .json) and the file's list as the value.")
    return {"kind": "data", "files": files, "request": request, "expect": {"json": {out: want}, "files": dict(files)}, "solution": {"answer": f"Wrote {out}.", "files": {out: _dump(want)}}}
