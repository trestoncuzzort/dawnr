"""assistant_rows.py: what dawnr_teach.py kept, made into rows: the turns that were sent back are taken out, and
the loss falls only on what the model wrote. A stand-in for the chat template; no tokenizer, no model."""
import json

from locallm import assistant_rows as rows


def call(name, **arguments):
    return {"role": "assistant", "content": "", "tool_calls": [{"id": "c", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}


def render(messages, generate):
    """An assistant turn inside a task is the generation prompt followed by the turn, as in the Qwen3.5 template."""
    out = ""
    for m in messages:
        if m["role"] == "assistant":
            said = (m.get("content") or "") + "".join(f"<call {c['function']['name']} {sorted(c['function']['arguments'].items())}>" for c in m.get("tool_calls") or [])
            out += "<a><think></think>" + said + "</a>\n"
        else:
            out += f"<{m['role']}>{m.get('content')}</{m['role']}>\n"
    return out + ("<a><think></think>" if generate else "")


START = [{"role": "system", "content": "S"}, {"role": "user", "content": "Shift the files up by one."}, call("fs_list", path="here"), {"role": "tool", "content": "here: 3 entries"}]


def test_a_turn_that_was_sent_back_and_the_sending_back_are_taken_out_and_a_refusal_stays():
    wrong, right = call("sh", command="for i in 2 3; do mv $i $((i+1)); done"), call("sh", command="mv 3 4 && mv 2 3")
    kept = START + [wrong, {"role": "tool", "content": rows.SENT_BACK + " After this, what here/3 holds now would be in no file. Nothing has run."},
                    right, {"role": "tool", "content": "exit 0\nApplied 3 changes"},
                    {"role": "assistant", "content": "Shifted."}, {"role": "user", "content": "You changed here/x.py and have not run anything since. Run it."},
                    call("sh", command="python3 x.py"), {"role": "tool", "content": "exit 0\nOK"}, {"role": "assistant", "content": "Shifted, and x.py prints OK."}]
    cleaned = rows.clean(kept)
    assert [rows.calls_of(m)[0][1] if m.get("tool_calls") else m["content"] for m in cleaned if m["role"] == "assistant"] == [
        '{"path": "here"}', '{"command": "mv 3 4 && mv 2 3"}', '{"command": "python3 x.py"}', "Shifted, and x.py prints OK."]
    refused = START + [call("pc", command="sudo apt install x"), {"role": "tool", "content": "refused: pc: it asks for administrator rights"}, {"role": "assistant", "content": "Run it yourself."}]
    assert rows.clean(refused) == refused                          # a tool's own refusal is how a refusal is learned
    last = START + [wrong, {"role": "tool", "content": rows.SENT_BACK + " Not run."}]
    assert rows.clean(last) == last                                # nothing follows: nothing to put in its place


def test_the_loss_falls_on_what_the_model_wrote_and_not_on_the_listing_the_front_door_made():
    kept = START + [call("sh", command="mv 3 4 && mv 2 3"), {"role": "tool", "content": "exit 0"}, {"role": "assistant", "content": "Shifted."}]
    units = rows.pieces(kept, [], render)
    assert len(units) == 1 and "".join(text for text, _t in units[0]) == render(rows.for_template(kept), False).rstrip("\n")
    trained = [text for text, t in units[0] if t]
    assert trained == ["<call sh [('command', 'mv 3 4 && mv 2 3')]></a>", "Shifted.</a>"]
    assert not any("fs_list" in text for text in trained) and any("fs_list" in text for text, t in units[0] if not t)
    only_listing = START + [{"role": "assistant", "content": "Three files."}]
    assert [t for _x, t in rows.pieces(only_listing, [], render)[0]].count(True) == 1


def test_a_template_that_renders_history_differently_gets_a_row_a_turn():
    def shifting(messages, generate):                           # past turns lose their thinking block once a later user turn exists
        text = render(messages, generate)
        return text.replace("<think></think>", "", text.count("<think></think>") - 1) if any(m["role"] == "user" and m["content"] == "again" for m in messages) else text
    kept = START + [{"role": "assistant", "content": "First."}, {"role": "user", "content": "again"}, {"role": "assistant", "content": "Second."}]
    units = rows.pieces(kept, [], shifting)
    assert len(units) == 2 and [[t for _x, t in unit] for unit in units] == [[False, True], [False, True]]
    assert units[0][1][0] == "First.</a>" and units[1][1][0] == "Second.</a>" and units[1][0][0].endswith("<a><think></think>")
