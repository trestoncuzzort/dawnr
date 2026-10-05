"""tool_check.py: a tool call is released only when what it passes was said; otherwise the person is asked for the
value by the parameter's name (2026-10-05).

    python3 locallm/tool_check.py --host 127.0.0.1:8712 --tools tools.json "Get the current weather for me."

A model given tools fills every required parameter of the call it writes, whether or not the person gave a value
for it. When2Call (Ross, Mahabaleshwarkar and Suhara, arXiv:2504.18851) removes one required value from each of
1,062 requests and counts how often a model calls anyway. "Calibration is the Bottleneck" (arXiv:2609.00949) finds
tool-trained models passing placeholders such as 'my_token' and '1234567890' in that situation, and the benchmark's
grader passing them. The runtimes that serve small models hold a call to the tool's schema (llama.cpp builds a
grammar from it), which makes the call well formed and says nothing about where its values came from; some stacks
add a second language model to judge the call. Here the check is not a model, and the model is not changed.

The rule is the one schema-guided dialogue systems used for slots (Rastogi et al., arXiv:1909.05855): the value of
a free-text or numeric parameter has to come from the conversation, and the value of a categorical one from the
schema's own list. A value is accounted for when it is

  - the parameter's `default`, or a boolean, or null;
  - one of the parameter's `enum` (passed on spelled as the schema spells it) that the conversation picks: its
    words or their stems were said, or it is the only one (`--any-enum` releases a choice nobody made);
  - a number the conversation states (as digits, as a word, or as a percentage of it);
  - words, other than the parameter's own name, of which at least half are in the conversation, compared without
    case, accents or punctuation, with
    numbers, month names and afternoon hours read as numbers (`2026-03-05` is in "March 5th, 2026", `23:00` in
    "11PM") and a run of words also by its initials (`San Francisco` is in "SF");
  - a list or an object that is not empty and whose every part is accounted for.

Then, for each call the model wrote:

  - a tool that was not declared: the call is refused;
  - a required parameter that is missing, or whose value is not accounted for, or is not one of its `enum`: the
    call is not released, and the person is asked for that parameter, with the value the model proposed shown as
    a proposal;
  - an optional parameter whose value is not accounted for, or a parameter the tool does not declare: left out of
    the call, and that is said.

The conversation is what the person, the system prompt and earlier tool results said. The model's own earlier
turns do not count: a value it proposed and the person accepted with a bare "yes" is asked about once more.

What this does not check: that a value is the right one for its parameter. A call that passes a word of the
request to the wrong parameter is released; so is an identifier put together from the request's own words
(`roar-katy-perry`), and a truth value nobody stated. How often the check stops a call that should have been a
question, and how many right calls it turns into questions, is measured on When2Call
(locallm/PREDICT-2026-10-05-tool-check.md). Research receipt 0a4596ca86e5.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import rag_rgb  # noqa: E402

STOP = frozenset("a an and are as at be by for from i in is it me my of on or our that the this to us we with you your".split())
RUN = re.compile(r"[^\W_]+")
NUMBER = re.compile(r"(?<![\w.])(-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(\s*(?:%|percent\b))?")
WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
         "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000, "million": 1000000,
         "once": 1, "twice": 2, "single": 1, "couple": 2, "pair": 2, "dozen": 12, "half": Fraction(1, 2)}
MONTHS = {m: n for n, names in enumerate(("january jan", "february feb", "march mar", "april apr", "may", "june jun",
                                           "july jul", "august aug", "september sep sept", "october oct",
                                           "november nov", "december dec"), 1) for m in names.split()}
HALF = Fraction(1, 2)
SHARE = HALF                   # of a text value's words, the share that must be in the conversation


def fold(text: str) -> str:
    """Lower case, accents and compatibility forms removed: `Hà Nội` and `ha noi` are one string."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold()


def words(text: str) -> list[str]:
    """A text's words as written, folded: runs of letters and digits, so `card123` is one word and not `card`."""
    return RUN.findall(fold(text))


def number_of(word: str) -> str | None:
    """The whole number a word starts with, without leading zeros: `05`, `5`, `5th` and `5pm` all give `5`."""
    m = re.match(r"\d+", word)
    return str(int(m.group(0))) if m else None


def said_words(text: str) -> frozenset[str]:
    """Everything a value's word may match in the conversation: each word as written; the number a word starts
    with (`15th` gives 15); a number word or a month as its number (`five`, of a date `May`); an hour before `pm`
    also as the 24-hour one (`11PM` gives 23)."""
    out, raw = set(), words(text)
    for i, w in enumerate(raw):
        out.add(w)
        n = number_of(w)
        if n is not None:
            out.add(n)
            rest = w[len(re.match(r"\d+", w).group(0)):] or next((q for q in raw[i + 1:i + 3] if not q[0].isdigit()), "")
            if rest in ("pm", "p") and 1 <= int(n) < 12:
                out.add(str(int(n) + 12))
            elif rest in ("am", "a") and int(n) == 12:
                out.add("0")
        elif w in WORDS and WORDS[w] != HALF:
            out.add(str(WORDS[w]))
        elif w in MONTHS:
            out.add(str(MONTHS[w]))
    return frozenset(out)


def value_words(text: str) -> list[str]:
    """A value's words, the ones that say something: stop words dropped, a number without its leading zeros."""
    return [str(int(w)) if w.isdigit() else w for w in words(text) if w not in STOP]


def numbers(text: str) -> set[Fraction]:
    """The numbers a text states: each numeral, a percentage also as its fraction, and the number words."""
    out: set[Fraction] = set()
    for m in NUMBER.finditer(text):
        x = Fraction(m.group(1).replace(",", ""))
        out |= {x, abs(x)} | ({x / 100} if m.group(2) else set())
    seen = re.findall(r"\d+(?:\.\d+)?|[^\W\d_]+", fold(text))
    for i, w in enumerate(seen):
        if w not in WORDS:
            continue
        x = Fraction(WORDS[w])
        out.add(x)
        before = seen[i - 1] if i else ""
        if x in (100, 1000, 1000000) and (before in WORDS or before[:1].isdigit()):      # two hundred, 5 thousand
            out.add(x * (Fraction(WORDS[before]) if before in WORDS else Fraction(before)))
        elif 20 <= x <= 90 and x % 10 == 0 and i + 1 < len(seen) and 1 <= WORDS.get(seen[i + 1], 0) <= 9:
            out.add(x + WORDS[seen[i + 1]])                                               # twenty-five
    return out


def spec(tool) -> dict:
    """A declared tool as {"name", "description", "properties", "required"}, from OpenAI's shape
    ({"type": "function", "function": {...}}), the bare one, or either as a JSON string."""
    if isinstance(tool, str):
        tool = json.loads(tool)
    f = tool.get("function", tool)
    params = f.get("parameters") or {}
    return {"name": f.get("name", ""), "description": f.get("description", ""),
            "properties": params.get("properties") or {}, "required": list(params.get("required") or f.get("required") or [])}


def said(messages: list[dict]) -> str:
    """What a value may come from: the person's turns, the system prompt and tool results; not the model's turns."""
    out = []
    for m in messages:
        if m.get("role") in ("user", "system", "tool"):
            c = m.get("content")
            out.append(c if isinstance(c, str) else " ".join(p.get("text", "") for p in c or [] if isinstance(p, dict)))
    return "\n".join(out)


class Said:
    """The conversation, read once: its words and its numbers."""

    def __init__(self, text: str):
        self.words, self.numbers = said_words(text), numbers(text)

    def has(self, word: str) -> bool:
        """A value's word is in the conversation as written, or (a word that starts with a number, `5th`) by its number."""
        return word in self.words or (word[0].isdigit() and number_of(word) in self.words and not word.isdigit() and
                                      re.fullmatch(r"\d+(st|nd|rd|th|am|pm|h|hr|hrs|m|min|mins|s|sec|secs|kg|km|cm|mm|g|lb|lbs|k|x)", word) is not None)

    def chose(self, member: str) -> bool:
        """Whether the conversation picks this member of an enum: at least half of its words are said, where a word
        is also said by its stem (`Music` in "a musical performance", `Sci-fi` in "scientific fiction"). The choice
        is among values the schema itself lists, so the match may be looser than for a value written freely."""
        mine = value_words(member)
        if not mine:
            return False

        def said(w: str) -> bool:
            if self.has(w):
                return True
            return any((len(w) >= 3 and c.startswith(w)) or (len(c) >= 4 and w.startswith(c)) for c in self.words if c not in STOP)
        return 2 * sum(1 for w in mine if said(w)) >= len(mine)


def in_enum(value, enum: list) -> tuple[bool, object]:
    """(whether the value is one of the enum, the value as it is passed on): compared as folded text, and a string
    is passed on spelled as the schema spells it (`Plus` for an enum of `plus`)."""
    for member in enum:
        if member == value or fold(str(member)).strip() == fold(str(value)).strip():
            return True, member if isinstance(value, str) and isinstance(member, str) else value
    return False, value


def same_text(a, b) -> bool:
    return a == b or fold(str(a)).strip() == fold(str(b)).strip()


def accounted(value, prop: dict, conversation: Said, strict_enum: bool = True, name: str = "") -> tuple[bool, object, str]:
    """(whether the value is accounted for, the value as it is passed on, why not). `prop` is the parameter's schema
    and `name` its name: a value made of the parameter's own name (`Project Name` for `project_name`) says nothing."""
    prop = prop if isinstance(prop, dict) else {}
    if value is None or isinstance(value, bool):
        return True, value, ""
    if isinstance(value, (list, dict)) and not value:
        return False, value, "it is empty"
    is_default = prop.get("default") not in (None, "") and not isinstance(value, (list, dict)) and same_text(value, prop["default"])
    if isinstance(prop.get("enum"), list) and prop["enum"] and not isinstance(value, (list, dict)):
        ok, member = in_enum(value, prop["enum"])
        if not ok:
            return False, value, "it is not one of " + ", ".join(str(m) for m in prop["enum"])
        if is_default or not strict_enum or len(prop["enum"]) == 1 or conversation.chose(str(member)):
            return True, member, ""
        return False, member, "which of " + ", ".join(str(m) for m in prop["enum"]) + " was not said"
    if is_default:
        return True, value, ""
    if isinstance(value, list):
        items, parts = prop.get("items") if isinstance(prop.get("items"), dict) else {}, []
        for v in value:
            ok, v2, why = accounted(v, items, conversation, strict_enum, name)
            if not ok:
                return False, value, f"{show(v)}: {why}"
            parts.append(v2)
        return True, parts, ""
    if isinstance(value, dict):
        inner, parts = prop.get("properties") if isinstance(prop.get("properties"), dict) else {}, {}
        for k, v in value.items():
            ok, v2, why = accounted(v, inner.get(k, {}), conversation, strict_enum, k)
            if not ok:
                return False, value, f"{k} = {show(v)}: {why}"
            parts[k] = v2
        return True, parts, ""
    if isinstance(value, (int, float)):
        try:
            x = Fraction(str(value))
        except ValueError:
            return False, value, "it is not a number"
        return (True, value, "") if x in conversation.numbers else (False, value, "that number was not said")
    text = str(value)
    own = set(words(name.replace("_", " ")))
    content = [w for w in value_words(text) if w not in own] if own else value_words(text)
    if not content:
        return False, value, "it is empty" if not text.strip() else "it says nothing of its own"
    found = [conversation.has(w) for w in content]
    for i in range(len(content)):                               # `SF` said for San Francisco, `GB` for Great Britain
        for j in range(i + 2, min(len(content), i + 4) + 1):
            if all(w[0].isalpha() for w in content[i:j]) and "".join(w[0] for w in content[i:j]) in conversation.words:
                found[i:j] = [True] * (j - i)
    return (True, value, "") if sum(found) >= SHARE * len(content) else (False, value, "those words were not said")


def show(value) -> str:
    return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else f"'{value}'"


def read_call(call) -> tuple[str, dict | None]:
    """(name, arguments) of a call in OpenAI's shape ({"function": {"name", "arguments": "<json>"}}) or the bare
    one; arguments None when they are not one JSON object."""
    f = call.get("function", call) if isinstance(call, dict) else {}
    args = f.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except ValueError:
            return f.get("name", ""), None
    return f.get("name", ""), args if isinstance(args, dict) else None


def check(tools: list, messages: list[dict], call, strict_enum: bool = True) -> dict:
    """One call judged against the tools declared and the conversation so far:

    {"action": "call", "name", "arguments", "left_out": [...]}      released, perhaps without some optional values
    {"action": "ask", "name", "ask": [{"parameter", "description", "proposed"?, "why"}], "left_out": [...]}
    {"action": "refuse", "name", "why"}
    """
    name, args = read_call(call)
    declared = {s["name"]: s for s in map(spec, tools)}
    if name not in declared:
        return {"action": "refuse", "name": name, "why": f"no tool named {name} was declared" if name else "the call names no tool"}
    if args is None:
        return {"action": "refuse", "name": name, "why": "the arguments are not one JSON object"}
    tool, conversation = declared[name], Said(said(messages))
    kept, ask, left_out = {}, [], []
    for key, value in args.items():
        prop = tool["properties"].get(key)
        if prop is None and tool["properties"]:
            left_out.append({"parameter": key, "value": value, "why": f"{name} declares no such parameter"})
            continue
        ok, passed, why = accounted(value, prop or {}, conversation, strict_enum, key)
        if ok:
            kept[key] = passed
        elif key in tool["required"]:
            ask.append({"parameter": key, "description": (prop or {}).get("description", ""), "proposed": value, "why": why})
        else:
            left_out.append({"parameter": key, "value": value, "why": why})
    for key in tool["required"]:
        if key not in args:
            ask.append({"parameter": key, "description": (tool["properties"].get(key) or {}).get("description", ""),
                        "why": "the call gives no value for it"})
    if ask:
        return {"action": "ask", "name": name, "ask": ask, "left_out": left_out}
    return {"action": "call", "name": name, "arguments": kept, "left_out": left_out}


def check_all(tools: list, messages: list[dict], calls: list, strict_enum: bool = True) -> dict:
    """A turn's calls together: {"action": "call", "calls": [...]} only when every one is released; one that has to
    be asked about makes the turn a question, and one to an undeclared tool makes it a refusal."""
    verdicts = [check(tools, messages, c, strict_enum) for c in calls]
    for action in ("refuse", "ask"):
        if any(v["action"] == action for v in verdicts):
            return {"action": action, "verdicts": verdicts}
    return {"action": "call", "calls": [{"name": v["name"], "arguments": v["arguments"]} for v in verdicts], "verdicts": verdicts}


def question(verdict: dict) -> str:
    """What the person is shown in place of a call that was not released."""
    lines = []
    for v in verdict.get("verdicts", [verdict]):
        if v["action"] == "refuse":
            lines.append(f"NOT CALLED: {v['why']}.")
        elif v["action"] == "ask":
            for a in v["ask"]:
                about = f" ({a['description'].rstrip('.')})" if a.get("description") else ""
                proposed = f" The model proposed {show(a['proposed'])}; {a['why']}." if "proposed" in a else ""
                lines.append(f"To call {v['name']} I need `{a['parameter']}`{about}. What should it be?{proposed}")
        for x in v.get("left_out", []):
            lines.append(f"Left out of {v['name']}: {x['parameter']} = {show(x['value'])} ({x['why']}).")
    return "\n".join(lines)


def ask_model(host: str, tools: list, messages: list[dict], post=rag_rgb._post, max_tokens: int = 400) -> dict:
    """The model's own turn with the tools offered natively: its message ({"content", "tool_calls"})."""
    body = {"messages": messages, "tools": tools, "temperature": 0, "max_tokens": max_tokens}
    return post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", required=True, help="host:port of a llama-server holding the base model")
    ap.add_argument("--tools", required=True, type=Path, help="a JSON file: the list of tools, in OpenAI's shape")
    ap.add_argument("--any-enum", action="store_true", help="release a choice among a parameter's enum that nobody made")
    ap.add_argument("--json", type=Path, help="write the verdict here as JSON")
    ap.add_argument("request")
    a = ap.parse_args(argv)
    try:
        tools = json.loads(a.tools.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"tool_check: {a.tools}: {error}", file=sys.stderr)
        return 2
    messages = [{"role": "user", "content": a.request}]
    reply = ask_model(a.host, tools, messages)
    calls = reply.get("tool_calls") or []
    if not calls:
        print((reply.get("content") or "").strip() or "(the model wrote nothing)")
        return 0
    verdict = check_all(tools, messages, calls, not a.any_enum)
    if verdict["action"] == "call":
        for c in verdict["calls"]:
            print(f"CALL {c['name']}({json.dumps(c['arguments'], ensure_ascii=False)})")
    notes = question(verdict)
    if notes:
        print(notes)
    if a.json:
        a.json.write_text(json.dumps(verdict, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if verdict["action"] == "call" else 1


if __name__ == "__main__":
    raise SystemExit(main())
