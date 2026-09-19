"""Typed hygienic expansion of acyclic `inline fun` expression definitions.

The result is the existing checked task AST. Helpers are expression templates:
their meaning is substitution, including the core's short-circuit definedness.
No contracts, backend assumptions, or new verifier nodes are introduced.
"""
from __future__ import annotations

import check_wf


class ExpansionError(ValueError):
    def __init__(self, message, node, rule="inline-fun"):
        super().__init__(message)
        self.node = node
        self.rule = rule


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _typed_empty(expr, expected):
    # An empty nested sequence loses its contextual type when substituted into
    # e.g. len/at/concat. Existing fill(0, []) preserves both its type and value.
    if expected == {"seq": "seq"} and expr == {"op": "seq", "args": []}:
        return {"op": "fill", "args": [{"int": 0}, {"op": "seq", "args": []}]}
    if "ite" in expr:
        branch = expr["ite"]
        return {"ite": dict(branch, **{
            "then": _typed_empty(branch["then"], expected),
            "else": _typed_empty(branch["else"], expected)})}
    return expr


class Expander:
    def __init__(self, task, helpers, positions, max_nodes):
        self.helpers = {}
        self.positions = positions
        self.used = set(_strings(task)) | set(_strings(helpers))
        self.serial = 0
        self.nodes = 0
        self.max_nodes = max_nodes

    def mark(self, source, result):
        self.nodes += 1
        if self.nodes > self.max_nodes:
            raise ExpansionError("inline expansion exceeds the node budget", source,
                                 "inline-expansion-budget")
        if self.positions is not None and isinstance(result, dict):
            position = self.positions.get(id(source))
            if position is not None:
                self.positions[id(result)] = position
        return result

    def fresh(self):
        while True:
            name = f"inlineVar{self.serial}"
            self.serial += 1
            if name not in self.used:
                self.used.add(name)
                return name

    def clone(self, value):
        if isinstance(value, dict):
            return self.mark(value, {k: self.clone(v) for k, v in value.items()})
        if isinstance(value, list):
            return [self.clone(v) for v in value]
        return value

    def substitute(self, value, arguments, bound=None):
        bound = bound or {}
        if isinstance(value, list):
            return [self.substitute(v, arguments, bound) for v in value]
        if not isinstance(value, dict):
            return value
        if set(value) == {"var"}:
            name = value["var"]
            if name in bound:
                return self.mark(value, {"var": bound[name]})
            if name in arguments:
                return self.clone(arguments[name])
        for quantifier in ("forall", "exists"):
            if quantifier in value:
                q = value[quantifier]
                fresh = self.fresh()
                scope = dict(bound, **{q["var"]: fresh})
                return self.mark(value, {quantifier: {
                    "var": fresh,
                    "lo": self.substitute(q["lo"], arguments, bound),
                    "hi": self.substitute(q["hi"], arguments, bound),
                    "body": self.substitute(q["body"], arguments, scope)}})
        return self.mark(value, {k: self.substitute(v, arguments, bound) for k, v in value.items()})

    def expand(self, value):
        if isinstance(value, list):
            return [self.expand(v) for v in value]
        if not isinstance(value, dict):
            return value
        if "call" in value and value["call"]["fun"] in self.helpers:
            call = value["call"]
            helper = self.helpers[call["fun"]]
            arguments = {p["name"]: _typed_empty(self.expand(arg), p["type"])
                         for p, arg in zip(helper["params"], call["args"])}
            expanded = self.substitute(helper["body"], arguments)
            return self.mark(value, expanded)
        return self.mark(value, {k: self.expand(v) for k, v in value.items()})


def expand_task(task, helpers, positions=None, file="<string>", max_nodes=100_000):
    """Check every source helper/call, expand, then check the resulting core task."""
    if not helpers:
        return task
    if task["t"] != 1:
        raise ExpansionError("inline functions require t 1", helpers[0], "inline-version")
    reserved = {task["name"]} | {f["name"] for f in task.get("spec_funs", [])}
    signatures = {}
    expander = Expander(task, helpers, positions, max_nodes)
    for helper in helpers:
        name = helper["name"]
        if name in reserved or name in signatures:
            raise ExpansionError(f"duplicate or conflicting inline function {name}", helper,
                                 "inline-name")
        names = [p["name"] for p in helper["params"]]
        if len(set(names)) != len(names):
            raise ExpansionError(f"duplicate parameter in inline function {name}", helper,
                                 "inline-params")
        types = [p["type"] for p in helper["params"]] + [helper["result"]]
        if not all(check_wf._valid_type(ty) for ty in types):
            raise ExpansionError(f"invalid type in inline function {name}", helper,
                                 "inline-type")
        env = {p["name"]: p["type"] for p in helper["params"]}
        result, errors = check_wf.expression_type(
            helper["body"], env, signatures, helper["result"], positions, file)
        if errors:
            raise ExpansionError(f"inline function {name}: {errors[0]}", helper,
                                 "inline-definition")
        if result != helper["result"]:
            raise ExpansionError(f"inline function {name}: body type differs from declared result",
                                 helper, "inline-result")
        signatures[name] = helper
        expanded = expander.expand(_typed_empty(helper["body"], helper["result"]))
        expander.helpers[name] = dict(helper, body=expanded)

    # This checks the original calls, so even an unused parameter's argument
    # must have its declared type and respect scope before substitution removes it.
    errors = check_wf.check_wf(task, positions, file, expression_funs=signatures)
    if errors:
        raise ExpansionError(str(errors[0]), task, "inline-call")
    expanded = expander.expand(task)
    errors = check_wf.check_wf(expanded, positions, file)
    if errors:
        raise ExpansionError(str(errors[0]), task, "inline-expanded")
    return expanded
