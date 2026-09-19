"""Bounded concrete telemetry for research data; never a proof certificate.

Callers supply an already parsed task and type-correct interpreter inputs.
Independent reference validation and train/evaluation split checks are separate
requirements before a record is eligible for training.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import interp


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def typed(value):
    # Preserve bool/int and pair/sequence distinctions in exported states.
    if value is None:
        return {"type": "unassigned"}
    if type(value) is bool:
        return {"type": "bool", "value": value}
    if type(value) is int:
        return {"type": "int", "value": value}
    if isinstance(value, list):
        return {"type": "seq", "value": [typed(x) for x in value]}
    # Refuse unsupported values rather than silently changing their t type.
    raise TypeError(f"trace export does not support {type(value).__name__}")


def state(env):
    return {k: typed(v) for k, v in sorted(env.items())}


def collect(task, inputs, *, max_events=10000):
    if max_events < 1:
        raise ValueError("max_events must be positive")
    task = deepcopy(task)
    env = deepcopy(inputs)
    record = {
        "schema": 1, "evidence": "bounded_concrete_execution",
        "task_sha256": digest(task),
        "contract_sha256": digest({k: task.get(k) for k in
                                  ("params", "returns", "requires", "ensures", "spec_funs")}),
        "producer_sha256": {
            name: sha256(Path(path).read_bytes()).hexdigest()
            for name, path in (("interpreter", interp.__file__), ("exporter", __file__))},
        "inputs": state(inputs), "events": [],
        "independently_validated": False,
        "training_eligible": False,
        "scope": "body_statements_function_expressions_opaque",
    }

    def capture(event):
        if len(record["events"]) >= max_events:
            raise interp.Budget("trace event cap")
        record["events"].append({**event, "state": state(event["state"])})

    funs = interp.funs_of(task, task["body"])
    st = interp.St()
    phase = "requires"
    try:
        if not all(interp.ev(e, env, funs, st) for e in task.get("requires", [])):
            record["status"] = "outside_precondition"
            return record
        for ret in task["returns"]:
            env[ret["name"]] = None
        phase = "body"
        interp.exec_body(task["body"], env, funs, st, trace=capture)
        if any(env[r["name"]] is None for r in task["returns"]):
            record["status"] = "unassigned_return"
        else:
            phase = "ensures"
            record["status"] = ("executed_no_postcondition" if not task.get("ensures") else
                "ensures_true_at_input" if all(
                interp.ev(e, env, funs, st) for e in task.get("ensures", []))
                else "ensures_false_at_input")
    except interp.Undef:
        record["status"] = "undefined"
        record["phase"] = phase
    except (interp.Budget, RecursionError):
        record["status"] = "unknown_budget"
        record["phase"] = phase
    record["final_state"] = state(env)
    record["steps"] = st.n
    return record
