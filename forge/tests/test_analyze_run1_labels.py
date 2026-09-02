"""tests/test_analyze_run1_labels.py — the greedy-provenance label, and the
numeric tie it used to read as an absence.

analyze_run1.py reports which construction produced each arm's BANKED aggregate:
greedy-free (the sampled draws only), or greedy-anchored (the temp-0 greedy draw
counted as one more draw). The label is DERIVED -- both constructions are
recomputed and compared against the stored number -- so it cannot drift off the
data. But when the two come out equal the stored number cannot say which one
produced it, and the label answered that tie with "greedy-free (no greedy draw
was banked)". The parenthetical is a claim about what is IN the row, and no
comparison of two equal numbers can support it.

THE WITNESS, executed: one row with greedy=True, sampled=[1, 1], aggregate 1.0.
Greedy-free that is (1+1)/2 = 1.0; greedy-anchored it is (1+1+1)/3 = 1.0. The
row plainly banks a greedy draw, and the old label said none was banked.

Presence is a fact about the ROW SHAPE, so it is read from the row shape
(has_greedy_draw). On a tie the stored value is reported as greedy-ANCHORED
whenever a greedy draw exists -- the anchored reading is then true of the number
-- and the claim of absence is made only when no row carries one.

The broken twin is kept here verbatim (test_stats_core.py idiom) and asserted to
STILL mislabel the witness, so a test that stops discriminating is itself a
failure rather than a silent pass.

NOTHING HERE CHANGES A PUBLISHED NUMBER, and the last two tests say why against
the retained bytes rather than asserting it: the two compared arms bank no
greedy draw at all, so their label was true and is now checked; the base arm
banks one on every entry but its aggregate matches only the anchored
construction, so it is discriminated numerically and never reaches the tie.

AND THE SAME SHAPE ONE LEVEL UP: THE TWO ARMS, AGAINST EACH OTHER
-----------------------------------------------------------------
The label fix above is per-arm, and so was the verifier fix before it
(single_key). Neither says anything about the two arms MATCHING, and the
primary Welch is a comparison BETWEEN them:

  - two arms each internally one verifier key, with the keys differing from
    EACH OTHER, both cleared single_key() and were compared -- one Welch
    across two instruments, reported as an effect of training;
  - a greedy-free trained arm against a greedy-anchored null arm printed
    "UNRECOGNISED (matches neither construction)" on the metric line and
    then reported a difference, a CI and a p-value underneath it.

Three instances of one shape counting the original pooling finding, so
analyze_run1.require_commensurable() is a PRECONDITION rather than a third
patch: what two arms must share is derived from the row structure (see its
comment block, steps 1-3) and it raises. The tests below carry both reds,
a dimension the mechanical derivation covers that neither red names, and
the cry-wolf side -- per-replicate fields, one-row arms, and the two
retained arms Table 1 is computed from, which pass it silently.

Run: python tests/test_analyze_run1_labels.py   (self-executing; the runner at
the bottom is the same one every other file in tests/ carries)
"""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import analyze_run1 as A                                          # noqa: E402
from analyze_run1 import BASE, NULL, TRAINED                      # noqa: E402
from stats_core import DegenerateInput, welch                     # noqa: E402


def _row(greedy, sampled, aggregate, tid="t1"):
    return {"model": "fixture", "aggregate": aggregate,
            "per_task": [{"tid": tid, "greedy": greedy, "sampled": sampled}]}


# 1.0 greedy-free and 1.0 greedy-anchored: the two constructions cannot be told
# apart on this row, and it HAS a banked greedy draw.
WITNESS = [_row(True, [1, 1], 1.0)]
# The same three numbers with no greedy draw -- the one shape for which "no
# greedy draw was banked" is a true thing to say.
NO_GREEDY = [_row(None, [1, 1], 1.0)]


def _stored_construction_numeric_only(rows):
    """The bug, verbatim: the tie answered by asserting the absence."""
    if not rows:
        return "no rows"
    free = all(v is not None and abs(A.rate(r) - v) <= A._TOL
               for r, v in ((r, A.greedy_free_rate(r)) for r in rows))
    anch = all(v is not None and abs(A.rate(r) - v) <= A._TOL
               for r, v in ((r, A.greedy_anchored_rate(r)) for r in rows))
    if free and not anch:
        return "greedy-free"
    if anch and not free:
        return "greedy-ANCHORED"
    if free and anch:
        return "greedy-free (no greedy draw was banked)"
    return "UNRECOGNISED (matches neither construction)"


def test_the_two_constructions_really_do_tie_on_the_witness():
    """The precondition every test below rests on. If these three numbers ever
    stop being equal, the witness has stopped being a witness."""
    r = WITNESS[0]
    assert A.greedy_free_rate(r) == 1.0, A.greedy_free_rate(r)
    assert A.greedy_anchored_rate(r) == 1.0, A.greedy_anchored_rate(r)
    assert A.rate(r) == 1.0, A.rate(r)


def test_a_banked_greedy_draw_is_never_labelled_absent():
    label = A.stored_construction(WITNESS)
    assert "no greedy draw was banked" not in label, label
    assert label.startswith("greedy-ANCHORED"), label
    # The twin must still lie, or this test has stopped testing anything.
    assert _stored_construction_numeric_only(WITNESS) == \
        "greedy-free (no greedy draw was banked)", "twin lost its bug"


def test_presence_is_read_from_the_row_shape_not_from_the_numbers():
    """Identical stored numbers, opposite row shapes. Only something that looks
    at the row can tell these apart, and the twin -- which looks only at the
    numbers -- gives them one answer."""
    assert A.has_greedy_draw(WITNESS) is True
    assert A.has_greedy_draw(NO_GREEDY) is False
    assert A.stored_construction(WITNESS) != A.stored_construction(NO_GREEDY)
    assert _stored_construction_numeric_only(WITNESS) == \
        _stored_construction_numeric_only(NO_GREEDY), "twin lost its bug"


def test_the_absence_claim_survives_where_it_is_true():
    """The fix must not answer the lie by refusing to say anything: where no
    row carries a greedy draw, the label still says so."""
    assert A.stored_construction(NO_GREEDY) == \
        "greedy-free (no greedy draw was banked)"


def test_a_numerically_discriminating_aggregate_still_reads_greedy_free():
    """greedy=False, sampled=[1, 1], aggregate 1.0: free is 1.0, anchored is
    2/3, and the stored number matches only free. Here the number itself says
    the greedy draw was left OUT of the aggregate, so the plain greedy-free
    label stands even though a greedy draw exists -- that label makes no claim
    about presence. Labelling this one ANCHORED would be a new false statement,
    not a fix."""
    rows = [_row(False, [1, 1], 1.0)]
    assert abs(A.greedy_anchored_rate(rows[0]) - 2 / 3) < 1e-12
    assert A.has_greedy_draw(rows) is True
    assert A.stored_construction(rows) == "greedy-free"


def test_a_genuinely_anchored_arm_is_still_labelled_anchored():
    rows = [_row(True, [1, 0], 2 / 3)]
    assert A.stored_construction(rows) == "greedy-ANCHORED"


def test_an_aggregate_matching_neither_construction_is_still_unrecognised():
    rows = [_row(True, [1, 1], 0.25)]
    assert A.stored_construction(rows).startswith("UNRECOGNISED"), \
        A.stored_construction(rows)


def test_the_compared_arms_bank_no_greedy_draw_in_the_retained_data():
    """Why no published number moves: the label on the two compared arms was
    TRUE all along -- it just was not checked. Now it is."""
    by = A.load()
    rows = by[TRAINED] + by[NULL]
    assert len(rows) == 80, len(rows)
    assert A.has_greedy_draw(rows) is False
    assert A.stored_construction(rows) == \
        "greedy-free (no greedy draw was banked)"


def test_the_base_arm_never_reaches_the_tie_branch():
    """It banks a greedy draw on every entry, and its stored aggregate matches
    only the anchored construction -- discriminated by the numbers, so its
    printed label is untouched by this fix."""
    rows = A.load()[BASE]
    assert A.has_greedy_draw(rows) is True
    assert A.stored_construction(rows) == "greedy-ANCHORED"


# --- the two arms, against each other -------------------------------------
PIN = {"version": "3.11.9", "platform": "win32",
       "executable": "/x/.venv-train/bin/python"}
OTHER = {"version": "3.12.10", "platform": "linux",
         "executable": "/x/.venv-train/bin/python"}

# Four replicates whose rates DIFFER: welch() refuses two constant arms
# (stats_core), and a fixture that cannot reach welch cannot witness a
# p-value being printed over it.
_PATTERNS = ([[1, 1, 0, 0, 0], [1, 0, 0, 0, 0]],
             [[1, 1, 1, 0, 0], [1, 0, 0, 0, 0]],
             [[1, 0, 0, 0, 0], [1, 1, 0, 0, 0]],
             [[1, 1, 0, 0, 0], [1, 1, 1, 0, 0]])


def _free(es):
    return sum(sum(e["sampled"]) / len(e["sampled"]) for e in es) / len(es)


def _anchored(es):
    v = []
    for e in es:
        s = list(e["sampled"])
        if e.get("greedy") is not None:
            s = [float(bool(e["greedy"]))] + s
        v.append(sum(s) / len(s))
    return sum(v) / len(v)


def _arm(model, verifier, greedy=None, banked=_free, flip=False, **over):
    """One arm of four replicates, in the shape the banked rows carry.

    `sampler` is held identical whatever `greedy` is, so a fixture that
    varies the construction varies ONLY the construction; the point of each
    red below is which single dimension the refusal names.
    """
    rows = []
    for i, pats in enumerate(_PATTERNS):
        es = [{"tid": f"t{j}", "greedy": greedy,
               "sampled": list(reversed(p)) if flip else list(p)}
              for j, p in enumerate(pats)]
        row = {"model": model, "verifier": verifier,
               "aggregate": {"pass@1": round(banked(es), 4)},
               "per_task": es, "task_set": "ruler_v2_null",
               "n_samples": 5, "temp": 0.8, "n_tasks": len(es),
               "gen_errors_total": 0,
               "coverage": {"pass@1": {"tasks_scored": len(es),
                                       "tasks_total": len(es)}},
               "sampler": {"draws_per_task": 5, "greedy_anchor": False,
                           "temperature": 0.8},
               "ts": f"2026-08-02T0{i}:00:00", "replicate": i + 1}
        row.update(over)
        rows.append(row)
    return rows


def _noise_file(rows):
    d = pathlib.Path(tempfile.mkdtemp(prefix="test_commensurable_"))
    p = d / "ruler_noise.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return p


def _the_old_primary(tr_rows, nu_rows):
    """The comparison exactly as it ran before the precondition: single_key()
    on each arm, the metric label over the two together, then Welch. Kept so
    a test that has stopped discriminating fails instead of passing."""
    A.single_key(TRAINED, tr_rows)
    A.single_key(NULL, nu_rows)
    return (A.stored_construction(tr_rows + nu_rows),
            welch([A.rate(r) for r in tr_rows],
                  [A.rate(r) for r in nu_rows]))


# Resolved TOLERANTLY, on purpose. Against bytes that carry no
# precondition at all these give None, so each red below fails saying
# what RAN -- with the p-value it produced -- instead of saying that a
# name is missing. "No such attribute" is not a witness to a defect.
_REQUIRE = getattr(A, "require_commensurable", None)
_INCOMMENSURABLE = getattr(A, "Incommensurable", ())


def _refusal(tr_rows, nu_rows, a_name=TRAINED, b_name=NULL):
    """The refusal message, or None if the comparison is allowed to run."""
    if _REQUIRE is None:
        return None
    try:
        _REQUIRE(a_name, tr_rows, b_name, nu_rows)
        return None
    except _INCOMMENSURABLE as e:
        return str(e)


def test_two_arms_on_different_verifiers_are_refused():
    """THE FIRST RED. Each arm is internally ONE verifier key, so single_key()
    clears both; the keys differ from each other, so the primary Welch is one
    t-test across two instruments -- the same pooling defect the first fix
    closed, moved from inside an arm to between the arms."""
    tr, nu = _arm(TRAINED, PIN), _arm(NULL, OTHER, flip=True)
    # THE TWIN, run FIRST so its result can be quoted into the failure:
    # the pre-existing fence clears both arms, and the comparison it used
    # to run still produces a p-value over them. What the fix changes is
    # that the comparison is no longer reached.
    assert len(A.partition(tr)) == 1 and len(A.partition(nu)) == 1, \
        "twin lost its bug: single_key() would have caught this by itself"
    _, w = _the_old_primary(tr, nu)
    msg = _refusal(tr, nu)
    assert msg is not None, (
        "two instruments were compared and nothing in the analysis said "
        f"so: the comparison that ran reports p = {w['p']:.4f} across "
        f"verifier keys 3.11.9/win32 and 3.12.10/linux")
    assert "verifier key" in msg, msg
    assert "3.11.9/win32" in msg and "3.12.10/linux" in msg, msg


def test_arms_whose_aggregates_were_built_differently_are_refused():
    """THE SECOND RED. Trained banks the greedy-free construction, null banks
    the greedy-anchored one. stored_construction() over the two TOGETHER is
    UNRECOGNISED, and that string used to be printed on the metric line with
    a difference, a CI and a p-value reported underneath it."""
    tr = _arm(TRAINED, PIN, greedy=False, banked=_free)
    nu = _arm(NULL, PIN, greedy=True, banked=_anchored, flip=True)
    # THE TWIN, run FIRST: the label the old metric line printed, and the
    # p-value printed underneath that label. Both are quoted into the
    # failure message below, so a red here reads as the report that
    # shipped rather than as a missing name.
    label, w = _the_old_primary(tr, nu)
    assert label == "UNRECOGNISED (matches neither construction)", label
    msg = _refusal(tr, nu)
    assert msg is not None, (
        f"the metric line reads {label!r} and the comparison underneath "
        f"it still reports p = {w['p']:.4f}")
    assert "stored aggregate construction" in msg, msg
    assert "greedy-free" in msg and "greedy-ANCHORED" in msg, msg


def test_an_arm_whose_own_aggregate_is_unrecognised_is_refused_by_name():
    """An arm matching NEITHER construction has no construction to share, so
    it is refused before the dimensions are compared at all -- otherwise two
    arms both labelled UNRECOGNISED would agree with each other and pass."""
    tr = _arm(TRAINED, PIN, greedy=True,
              banked=lambda es: round(_free(es) * 0.5, 4))
    nu = _arm(NULL, PIN, greedy=True, banked=_anchored, flip=True)
    assert A.stored_construction(tr).startswith("UNRECOGNISED")
    msg = _refusal(tr, nu)
    assert msg is not None, (
        "an arm matching neither construction was compared anyway, at "
        f"p = {_the_old_primary(tr, nu)[1]['p']:.4f}")
    assert "UNRECOGNISED" in msg and TRAINED in msg, msg
    # ...and both arms UNRECOGNISED is still a refusal, not an agreement.
    other = _arm(NULL, PIN, greedy=True,
                 banked=lambda es: round(_free(es) * 0.5, 4), flip=True)
    assert A.shape_dimensions(tr)["stored aggregate construction"] == \
        A.shape_dimensions(other)["stored aggregate construction"]
    assert _refusal(tr, other) is not None


def test_a_run_field_neither_red_names_is_covered_too():
    """Why the set is DERIVED and not patched from the two findings: the draw
    count and the sampling temperature are in neither, and both are covered
    because the rows carry them and each arm holds them constant."""
    tr = _arm(TRAINED, PIN)
    nu = _arm(NULL, PIN, flip=True, n_samples=4, temp=0.2)
    msg = _refusal(tr, nu)
    assert msg is not None, (
        "a 4-draw arm sampled at temp 0.2 was compared against a 5-draw "
        f"arm at temp 0.8, at p = {_the_old_primary(tr, nu)[1]['p']:.4f}")
    assert "row field 'n_samples'" in msg, msg
    assert "row field 'temp'" in msg, msg


def test_per_replicate_fields_are_not_dimensions():
    """The cry-wolf side of step 2. ts and replicate differ on every row of
    both arms, so neither arm HAS a value on them to compare. Treating them
    as configuration would refuse every comparison ever made."""
    tr, nu = _arm(TRAINED, PIN), _arm(NULL, PIN, flip=True)
    keys = ({k for r in tr + nu for k in r}
            - set(A._READ_BY_NAME) - set(A._DERIVED_INSTEAD))
    ctx = A.context_dimensions(tr, keys)
    assert ctx["ts"] == A._VARIES and ctx["replicate"] == A._VARIES, ctx
    assert _refusal(tr, nu) is None, _refusal(tr, nu)


def test_a_field_varying_in_both_arms_is_not_a_dimension():
    """The retained arms carry per-run diagnostics taking 39 distinct values
    in one arm and 38 in the other. Both arms agree the field is not run
    configuration; recording the COUNT alongside the marker would turn that
    agreement into a refusal, so the marker deliberately carries none."""
    tr, nu = _arm(TRAINED, PIN), _arm(NULL, PIN, flip=True)
    for i, r in enumerate(tr):
        r["diagnostic"] = i          # four distinct values
    for i, r in enumerate(nu):
        r["diagnostic"] = i % 2      # two distinct values
    assert _refusal(tr, nu) is None, _refusal(tr, nu)
    # ...but constant in ONE arm and varying in the other is a real
    # difference: the two arms disagree about what their configuration is.
    for r in tr:
        r["diagnostic"] = 7
    assert "row field 'diagnostic'" in (_refusal(tr, nu) or ""), (
        "one arm holds `diagnostic` at a single value and the other does "
        "not, and the comparison ran anyway: " + str(_refusal(tr, nu)))


def test_a_one_row_arm_is_left_to_welch_rather_than_misclassified():
    """With one row every key is trivially constant, ts included, so step 2
    declines to classify rather than refuse for a false reason. Nothing
    escapes: welch() rejects a one-row arm itself, so no p-value is printed
    over one either way."""
    tr, nu = _arm(TRAINED, PIN)[:1], _arm(NULL, PIN, flip=True)[:1]
    assert A.context_dimensions(tr, {"ts"}) is None
    assert _refusal(tr, nu) is None, _refusal(tr, nu)
    try:
        welch([A.rate(r) for r in tr], [A.rate(r) for r in nu])
        raise AssertionError("welch answered a one-row arm")
    except DegenerateInput as e:
        assert "at least 2 observations" in str(e), e


def test_main_refuses_before_it_prints_anything():
    """End to end at the compare site, asserted on STDOUT, because the
    defect this closes was a printed number and not a wrong return value.
    Two arms on different verifiers: main() must stop on the way in, and
    the whole report -- p-value included -- is quoted back when it does
    not."""
    path = _noise_file(_arm(TRAINED, PIN) + _arm(NULL, OTHER, flip=True))
    saved, A.NOISE = A.NOISE, path
    buf, raised = io.StringIO(), None
    try:
        with contextlib.redirect_stdout(buf):
            try:
                A.main()
            except BaseException as e:                    # noqa: BLE001
                raised = e
    finally:
        A.NOISE = saved
    out = buf.getvalue()
    assert "p = " not in out, (
        "main() printed a p-value over two arms scored on different "
        "verifiers:\n" + out)
    assert out == "", out
    assert type(raised).__name__ == "Incommensurable", (raised, out)
    assert "verifier key" in str(raised), raised


def test_the_retained_compared_arms_are_commensurable():
    """THE HARD INVARIANT, checked rather than asserted. The two arms Table 1
    is computed from pass this precondition on every dimension, so it prints
    nothing and moves no published number."""
    by = A.load()
    tr = A.single_key(TRAINED, by[TRAINED])
    nu = A.single_key(NULL, by[NULL])
    assert len(tr) == 40 and len(nu) == 40, (len(tr), len(nu))
    assert A.require_commensurable(TRAINED, tr, NULL, nu) is None
    assert A.shape_dimensions(tr) == A.shape_dimensions(nu), (
        A.shape_dimensions(tr), A.shape_dimensions(nu))
    keys = ({k for r in tr + nu for k in r}
            - set(A._READ_BY_NAME) - set(A._DERIVED_INSTEAD))
    assert A.context_dimensions(tr, keys) == A.context_dimensions(nu, keys)


def test_the_base_arm_is_not_commensurable_with_the_trained_arm():
    """Stated on the RETAINED bytes, because it is the reason the base arm is
    labelled reference-only rather than a third comparison: it banks four
    sampled draws where the compared arms bank five, and its aggregate is
    greedy-anchored where theirs is greedy-free."""
    by = A.load()
    tr = A.single_key(TRAINED, by[TRAINED])
    base = [r for r in by[BASE] if A.verifier_key(r)[0] != A.UNPINNED]
    msg = _refusal(tr, base, b_name=BASE)
    assert msg is not None, "the base arm read as commensurable"
    assert "sampled draws behind each per-task rate" in msg, msg
    assert "stored aggregate construction" in msg, msg


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as e:
                fails.append(name); print(f"FAIL {name}: {e}")
            except Exception as e:                                # noqa: BLE001
                fails.append(name)
                print(f"FAIL {name}: raised {type(e).__name__}: {e}")
    print(f"\n{len(fails)} failed")
    raise SystemExit(1 if fails else 0)
