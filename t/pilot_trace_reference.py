"""Independent closed-form telemetry oracle for the three development templates.

Does not interpret t ASTs or call interp. Not a general program verifier.
"""


def expected_events(family, offset, x):
    events = []

    def event(kind, path, r=None, i=None, **details):
        snapshot = {"x": {"type": "int", "value": x},
                    "r": {"type": "unassigned"} if r is None else
                    {"type": "int", "value": r}}
        if i is not None:
            snapshot["i"] = {"type": "int", "value": i}
        if kind == "exit":
            details["returned"] = False
        events.append(dict(kind=kind, path=path, state=snapshot, **details))

    event("enter", [0])
    if family == "affine":
        event("exit", [0], 3 * x + offset)
    elif family == "absolute_offset":
        branch = "then" if x < 0 else "else"
        event("guard", [0], taken=branch)
        event("enter", [0, branch, 0])
        event("exit", [0, branch, 0], abs(x) + offset)
        event("exit", [0], abs(x) + offset)
    elif family == "triangular":
        event("exit", [0], offset)
        event("enter", [1], offset)
        event("exit", [1], offset, 0)
        event("enter", [2], offset, 0)
        for i in range(max(x, 0)):
            before = offset + i * (i - 1) // 2
            after = offset + i * (i + 1) // 2
            event("guard", [2], before, i, taken=True, iteration=i)
            event("enter", [2, "body", 0], before, i)
            event("exit", [2, "body", 0], after, i)
            event("enter", [2, "body", 1], after, i)
            event("exit", [2, "body", 1], after, i + 1)
        n = max(x, 0)
        result = offset + n * (n - 1) // 2
        event("guard", [2], result, n, taken=False, iteration=n)
        event("exit", [2], result, n)
    else:
        raise ValueError("unknown development family")
    return events
