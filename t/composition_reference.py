"""Independent closed-form oracle for the composition curriculum.

Works from stage descriptors alone: it never imports `interp`, never walks a
t AST and never reads the generated source. Agreement with the traced
interpreter is therefore a cross-check between two implementations, not
evidence that either is right, and never a proof obligation discharged.
"""

KINDS = ("affine", "cap", "shift", "tri")


def statement_count(kind):
    """Top-level statements a stage contributes, which fixes its AST paths."""
    if kind not in KINDS:
        raise ValueError(f"unknown stage kind {kind!r}")
    return 4 if kind == "tri" else 1


def apply_stage(stage, value):
    kind = stage[0]
    if kind == "affine":
        _, a, b = stage
        return a * value + b
    if kind == "cap":
        _, c = stage
        return c if value > c else value
    if kind == "shift":
        _, c = stage
        return c - value if value < 0 else value + c
    if kind == "tri":
        _, c = stage
        n = value if value > 0 else 0
        return c + n * (n - 1) // 2
    raise ValueError(f"unknown stage kind {kind!r}")


def final_value(stages, x):
    value = x
    for stage in stages:
        value = apply_stage(stage, value)
    return value


def loop_trips(stages, x):
    """Total loop iterations, for bounding trace length before generation."""
    value, trips = x, 0
    for stage in stages:
        if stage[0] == "tri":
            trips += value if value > 0 else 0
        value = apply_stage(stage, value)
    return trips


def _typed(value):
    return {"type": "unassigned"} if value is None else {"type": "int", "value": value}


def expected_events(stages, x):
    """The exact event stream `t/execution_trace.collect` must produce."""
    env = {"x": x, "r": None}
    events = []

    def emit(kind, path, **details):
        events.append(dict(kind=kind, path=list(path),
                           state={k: _typed(v) for k, v in sorted(env.items())}, **details))

    emit("enter", [0])
    env["r"] = x
    emit("exit", [0], returned=False)
    index = 1
    for position, stage in enumerate(stages, start=1):
        kind = stage[0]
        if kind == "affine":
            emit("enter", [index])
            env["r"] = apply_stage(stage, env["r"])
            emit("exit", [index], returned=False)
        elif kind in ("cap", "shift"):
            c = stage[1]
            emit("enter", [index])
            taken = ("then" if env["r"] > c else "else") if kind == "cap" else (
                "then" if env["r"] < 0 else "else")
            emit("guard", [index], taken=taken)
            if kind == "cap" and taken == "else":
                pass       # the capped branch is the only statement; else is empty
            else:
                emit("enter", [index, taken, 0])
                env["r"] = apply_stage(stage, env["r"])
                emit("exit", [index, taken, 0], returned=False)
            emit("exit", [index], returned=False)
        elif kind == "tri":
            c = stage[1]
            bound, counter = f"n{position}", f"i{position}"
            entry = env["r"]
            emit("enter", [index])
            env[bound] = entry
            emit("exit", [index], returned=False)
            index += 1
            emit("enter", [index])
            env[counter] = 0
            emit("exit", [index], returned=False)
            index += 1
            emit("enter", [index])
            env["r"] = c
            emit("exit", [index], returned=False)
            index += 1
            emit("enter", [index])
            for iteration in range(entry if entry > 0 else 0):
                emit("guard", [index], taken=True, iteration=iteration)
                emit("enter", [index, "body", 0])
                env["r"] = env["r"] + env[counter]
                emit("exit", [index, "body", 0], returned=False)
                emit("enter", [index, "body", 1])
                env[counter] = env[counter] + 1
                emit("exit", [index, "body", 1], returned=False)
            emit("guard", [index], taken=False, iteration=entry if entry > 0 else 0)
            emit("exit", [index], returned=False)
        else:
            raise ValueError(f"unknown stage kind {kind!r}")
        index += 1
    return events
