"""Development-only execution corpus; not a sealed evaluation or SFT dataset."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from execution_trace import collect, digest
from pilot_trace_reference import expected_events
import surface


def integer(x):
    return {"int": x}


def variable(x):
    return {"var": x}


def operator(name, *args):
    return {"op": name, "args": list(args)}


def pilot_rows():
    for family in ("affine", "absolute_offset", "triangular"):
        for offset in range(5):
            source = (f"t 1 gate recursion task dev_{family}_{offset}(x: int) "
                      "returns (r: int) ensures r == x { r := x; }")
            task = surface.parse(source)
            # These are execution examples; no fabricated proof obligations.
            task["ensures"] = []
            if family == "affine":
                task["body"] = [{"assign": ["r", operator("+", operator(
                    "*", variable("x"), integer(3)), integer(offset))]}]
                reference = lambda x: 3 * x + offset
            elif family == "absolute_offset":
                task["body"] = [{"if": {
                    "cond": operator("<", variable("x"), integer(0)),
                    "then": [{"assign": ["r", operator("-", integer(offset), variable("x"))]}],
                    "else": [{"assign": ["r", operator("+", variable("x"), integer(offset))]}]}}]
                reference = lambda x: abs(x) + offset
            else:
                task["body"] = [
                    {"assign": ["r", integer(offset)]},
                    {"var": {"name": "i", "type": "int", "init": integer(0)}},
                    {"while": {"cond": operator("<", variable("i"), variable("x")),
                               "body": [
                                   {"assign": ["r", operator("+", variable("r"), variable("i"))]},
                                   {"assign": ["i", operator("+", variable("i"), integer(1))]}]}}]
                reference = lambda x: offset + max(x, 0) * (max(x, 0) - 1) // 2
            for x in range(-16, 33):
                row = collect(task, {"x": x})
                if row["events"] != expected_events(family, offset, x):
                    raise AssertionError((family, offset, x, "trace mismatch"))
                expected = reference(x)
                if row["status"] != "executed_no_postcondition" or row["final_state"]["r"] != {
                        "type": "int", "value": expected}:
                    raise AssertionError((family, offset, x, row))
                if family == "triangular":
                    for event in row["events"]:
                        if event["kind"] == "guard":
                            i = event["iteration"]
                            if event["state"]["r"]["value"] != offset + i * (i - 1) // 2:
                                raise AssertionError("loop state mismatch")
                row.update(family=family, split="development_only", task=task,
                           sample_id=digest([task, x]),
                           reference_check={"final_value": expected,
                                            "method": "independent_python_formula",
                                            "scope": "final_value_and_loop_header_sum" if family == "triangular"
                                            else "final_value"})
                row["reference_check"].update(scope="all_body_events_and_final_value",
                    trace_oracle_sha256=sha256(Path(__file__).with_name(
                        "pilot_trace_reference.py").read_bytes()).hexdigest())
                row["independently_validated"] = True
                # Development-only records still lack a training/evaluation split.
                yield row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    counts, seen = {}, set()
    output = args.out / "traces.jsonl"
    with output.open("w") as stream:
        for row in pilot_rows():
            if row["sample_id"] in seen:
                raise AssertionError("duplicate sample")
            seen.add(row["sample_id"])
            counts[row["family"]] = counts.get(row["family"], 0) + 1
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    card = {"purpose": "development telemetry validation only", "counts": counts,
            "rows": len(seen), "data_sha256": sha256(output.read_bytes()).hexdigest(),
            "generator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "provenance": "deterministic handwritten AST templates; no model-generated labels",
            "training_ready": False, "formal_proof": False,
            "limitations": ["three families only", "no held-out evaluation split",
                            "no corpus tokenizer or loss-mask audit"]}
    (args.out / "card.json").write_text(json.dumps(card, indent=2) + "\n")
    print(json.dumps(card))


if __name__ == "__main__":
    main()
