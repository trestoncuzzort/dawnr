"""baselines.py — what a DUMB model scores on the same text, so "it learned" is a
claim you can check rather than a number you have to trust.

WHY THIS EXISTS. The studio's headline said the model had come "99% of the way
from guessing to certainty". Both ends of that sentence were real; the *start*
was not a fair opponent. "Guessing" meant a uniform draw over the alphabet — 83
equally-likely characters — and essentially anything beats it. Measured on the
20MB stories corpus, on the exact split the trainer used:

    uniform over the alphabet          6.375 bits/char    83.00 choices
    letter frequency alone             4.446 bits/char    21.80 choices
    bigram   (previous 1 character)    3.317 bits/char     9.97 choices
    trigram  (previous 2 characters)   2.436 bits/char     5.41 choices
    the trained 3.18M model            1.111 bits/char     2.16 choices

A trigram is a lookup table. It has no parameters to train, no gradient, no GPU,
and it already covers most of the distance from 83 to 1. Against uniform the
model looks 99% of the way there; against the trigram it is about 74% of the
remaining distance. Both numbers are true and only the second one is useful.

The failure this prevents is not a small one. On a corpus with heavy repetition
or a skewed alphabet, a model can post an excellent loss having learned almost
nothing a lookup table did not already know — and with uniform as the only
reference, the report would congratulate it. The gap between the model and the
n-gram is the part that required learning; that gap is what this file measures.

WHAT THIS IS NOT. These are deliberately weak models, and a stronger baseline
would only make the comparison harsher. Add-1 smoothing is the simplest thing
that works, not the best (Kneser-Ney would score better and so would a longer
context). That direction is safe: understating the baseline is the failure mode
to avoid, because it flatters the model. If someone replaces these with better
n-grams and the model's advantage shrinks, the new number is the honest one.

AND THE ELIGIBILITY RULE RIDES ALONG. A baseline is only meaningful on the same
held-out text the model was scored on. If that split cannot support a validation
claim — data.split_verdict() returns anything but None, or the leakage scan is
not CLEAN — then the comparison is as meaningless as the model's own val loss,
and callers must not present it as evidence. compare() therefore takes the
already-split text rather than re-splitting, so it cannot silently score a
different split than the one that trained (the F-02 trap, in miniature).

AND IT IS ENFORCED OVER A WHOLE PAYLOAD, not over one field. holdout_eligibility
answers whether a holdout can carry a claim; withhold_claims takes an
experiment's result payload and nulls every claim in it when the answer is no,
deriving the set of claims by walking the payload rather than from a list
someone maintains by hand beside it. See its docstring for what was published
the two times only one field was nulled.
"""
from __future__ import annotations

import math
from collections import Counter

LN2 = math.log(2)

# Add-1 (Laplace). Chosen for inspectability: one number, no tuning, and a reader
# can verify the arithmetic by hand. See the module docstring on why a weak
# smoother is the safe direction.
ALPHA = 1.0

# The n-gram order reported alongside the frequency model. 3 is the strongest of
# the cheap references measured above (bigram 3.317 bits, trigram 2.436) while
# still fitting in a table of ~11k cells on a 20MB corpus. Reporting the hardest
# cheap opponent to beat is the point; reporting an easy one would repeat the
# mistake this file exists to fix.
NGRAM_ORDER = 3


def _mean_nats(logprobs_sum: float, n: int) -> float:
    """Cross-entropy in nats per character. Same unit train.py reports, so the
    numbers can be compared without converting anything."""
    return -logprobs_sum / max(n, 1)


def uniform_nats(vocab_size: int) -> float:
    """Every character equally likely — the reference the studio used to call
    'pure guessing'. Included so the old headline number stays visible next to
    the ones that mean something."""
    return math.log(max(vocab_size, 1))


def frequency_nats(train: str, val: str, vocab_size: int) -> float:
    """The DoR's 'trivial character-frequency model': how well you predict the
    next character knowing only how common each character is, and nothing else."""
    counts = Counter(train)
    total = sum(counts.values())
    denom = total + ALPHA * vocab_size
    s = sum(math.log((counts.get(c, 0) + ALPHA) / denom) for c in val)
    return _mean_nats(s, len(val))


def ngram_nats(train: str, val: str, vocab_size: int,
               order: int = NGRAM_ORDER) -> float:
    """The DoR's 'smoothed character n-gram': predict the next character from the
    previous `order - 1`.

    Counted with zip-slices over the string rather than a dict-of-Counters: it is
    one pass, and on the 20MB corpus it builds in 1.8s into ~11k cells. That cost
    is why this can run on every claim-bearing run instead of being opt-in.

    The context table is FOLDED OUT OF the n-gram table rather than counted from
    the string a second time, and that is a correctness point before it is a
    speed one. Counting (k-1)-grams over the string walks one position further
    than counting k-grams does, so the FINAL (k-1)-gram gets counted as a
    context that never had a following character. Any context equal to that one
    then divides by a denominator one too large and its conditional
    distribution sums to less than 1: measured on an 8,708-character corpus,
    0.99953 at order 2, 0.99762 at order 3 and 0.99160 at order 4. Summing the
    k-gram counts instead makes sum_c (n + 1) / (d + V) equal (d + V) / (d + V)
    by construction, at every order, for every context.

    An unseen context falls back to add-1 over the whole alphabet, which is the
    same floor `uniform_nats` reports — a context the model has never seen is a
    context this baseline cannot help with, and pretending otherwise would
    understate the baseline.
    """
    k = max(order, 1)
    if len(train) <= k or not val:
        return uniform_nats(vocab_size)

    # counts[ctx][nxt] via two flat Counters: the full n-gram, and its context.
    # The context table is the n-gram table with the last character dropped, so
    # the two can never disagree about how many positions were counted. See the
    # docstring: counting it from the string instead walked one position further
    # and left the last context with a successor it never had.
    full = Counter(zip(*(train[i:] for i in range(k))))
    ctx = None
    if k > 1:
        ctx = Counter()
        for gram, n in full.items():
            ctx[gram[:-1]] += n

    hist = tuple(train[-(k - 1):]) if k > 1 else ()
    s = 0.0
    for c in val:
        if k == 1:
            n, d = full.get((c,), 0), sum(full.values())
        else:
            n = full.get(hist + (c,), 0)
            d = ctx.get(hist, 0)
        s += math.log((n + ALPHA) / (d + ALPHA * vocab_size))
        if k > 1:
            hist = (hist + (c,))[-(k - 1):]
    return _mean_nats(s, len(val))


def holdout_eligibility(text: str, train_text: str | None, val_text: str | None,
                        val_frac: float = 0.1, seed: int = 1337, *,
                        doc_aligned: bool) -> str | None:
    """Why this holdout cannot carry a baseline comparison, or None if it can.

    THE RULE IN THIS MODULE'S DOCSTRING, MADE CALLABLE. It was prose here and
    an inline check in studio.py, and the two experiments had neither: they
    published closed_fraction on any corpus at all. Measured, before this
    existed, with training stubbed so only the analysis ran:

      one document holding 99% of the corpus   split_verdict "corpus",
                                               closed_fraction 0.0221 published
      near-duplicate documents on both sides   leakage CONTAMINATED,
                                               closed_fraction -0.3258 published
      one character, no holdout at all         ZeroDivisionError

    Every one of those numbers is the model and the baseline being wrong in the
    same direction on the same unusable holdout, printed as a percentage with a
    "vs table" column heading over it.

    The split arm and the leakage arm are both required, and they catch
    different things: a corpus can split perfectly and still have the same
    passages on both sides, and a corpus with no overlap at all can still fail
    to yield a holdout worth the name.

    doc_aligned IS KEYWORD-ONLY AND HAS NO DEFAULT, deliberately. It is passed
    straight to leakage.scan, whose document arm counts byte-identical
    documents against a tight 0.10 bar and is meaningful only on a split that
    cut between documents; on a positional cut those "documents" are fragments.
    This function used to call scan() with no flag at all and inherit its
    default of True, which reads fragment counts against the document bar.
    Measured on a 18,249-character corpus of 100 blocks, every fifth one an
    identical separator, cut positionally at 90%: documents 2/10 = 20.0%,
    lines 5.9%, content 0.0%, and the eligibility answer came back "the leakage
    scan reads CONTAMINATED: 20.0% of validation documents are byte-identical
    to a training one" -- while the same report prints "documents n/a, the
    split cut through a document, so document counts are not meaningful". With
    doc_aligned=False the same holdout reads CLEAN. A default would let the
    next caller inherit the same wrong answer silently; a required keyword
    makes it state what it split, and a caller that does not know gets a
    TypeError rather than a verdict.

    A LIMIT THIS DOES NOT FIX, named rather than left for the next reader to
    find: the split arm below asks group_split's question. split_health()
    re-splits `text` by document whatever the caller's split was, so on a
    positional caller it reports on a holdout that caller is not using, and the
    "splitter" remedy it can return ("another seed probably would") is
    grouped-only advice -- a positional cut does not have a seed. The leakage
    arm is now honest about the split it was handed; the split arm is not yet.

    Imports are local so that importing baselines stays free for callers that
    only want the arithmetic, and so this module never has to be ordered
    against leakage.py at import time.
    """
    from data import split_health, split_verdict
    from leakage import scan

    if train_text is None or not val_text:
        return ("no held-out text was produced, so there is nothing to score a "
                "baseline on")
    v = split_verdict(split_health(text, val_frac, seed))
    if v is not None:
        return {
            "empty": "nothing was held back at all, so there is no holdout",
            "corpus": ("this corpus cannot support the requested split: no "
                       "whole-document split of it gets near the request"),
            "splitter": ("this split fell short of the requested holdout, "
                         "though the corpus could support it -- another seed "
                         "probably would"),
        }[v]
    rep = scan(train_text, val_text, doc_aligned=doc_aligned)
    if not rep.trustworthy:
        return f"the leakage scan reads {rep.verdict}: {rep.reason}"
    return None


def closed_fraction(ngram_choices: float, model_choices: float,
                    ineligible: str | None = None) -> tuple[float | None, str | None]:
    """Of the distance the lookup table left on the table, how much the model
    closed -- or None, and the sentence that says why there is no number.

    Two ways there is no number. The holdout may be ineligible, in which case
    the caller already knows why and passes it through. Or the lookup table may
    already be at 1.0 choices, which leaves the fraction without a denominator:
    both experiments divided by (ngram_choices - 1.0) unguarded and died with
    ZeroDivisionError on a single-character corpus, where the n-gram falls back
    to uniform_nats(1) == 0 and exp(0) is exactly 1.0.

    NOT USED BY compare() BELOW, deliberately and not happily: compare()
    answers the same question with 0.0 in the no-denominator case, which reads
    as "the model closed none of the distance" when the truth is "there was no
    distance". Changing it moves what train.py and studio.py print, so it wants
    its own change and its own witness rather than a ride on this one.
    """
    if ineligible:
        return None, ineligible
    if ngram_choices <= 1.0:
        return None, (f"the lookup table already scores {ngram_choices:.4f} "
                      f"choices, so there is no distance left to close and the "
                      f"fraction has no denominator")
    return (ngram_choices - model_choices) / (ngram_choices - 1.0), None


# The three fields the gate below writes for itself. They are the ANSWER to the
# eligibility question rather than a reading of the run, so no caller declares
# them and no caller sets them: a payload that wrote its own holdout_eligible
# could disagree with the gate that suppressed it.
GATE_FIELDS = ("holdout_eligible", "ineligible_reason", "claims_withheld")


def _leaf_paths(node, prefix: tuple = ()):
    """Every leaf path of a payload, as tuples of key names.

    A LIST IS A LEAF. A list of comparisons is one claim the run makes, not one
    claim per element, and nothing here needs to null the third element of a
    list while keeping the second.
    """
    if isinstance(node, dict) and node:
        for k, v in node.items():
            yield from _leaf_paths(v, prefix + (str(k),))
    else:
        yield prefix


def _declared(path: tuple, data) -> bool:
    """Whether one leaf path is declared a measurement.

    `*` matches exactly ONE segment, so "arms.*.mean" covers every arm without
    naming them. A pattern never matches a PREFIX of a path: declaring
    "baseline" would not silently adopt whatever a later change adds inside it,
    and that is the direction this has to fail in.
    """
    for pattern in data:
        segs = pattern.split(".")
        if len(segs) == len(path) and all(s in ("*", p)
                                          for s, p in zip(segs, path)):
            return True
    return False


def _null_claims(node, data, prefix: tuple = ()):
    """`node` with every undeclared leaf replaced by None. Builds a new object;
    the caller's payload is not modified."""
    if isinstance(node, dict) and node:
        return {k: _null_claims(v, data, prefix + (str(k),))
                for k, v in node.items()}
    return node if _declared(prefix, data) else None


def claims_in(payload: dict, data) -> list[str]:
    """The claim-bearing paths of `payload`, DERIVED by walking `payload`.

    The set is computed from the object that is about to be published, not
    typed out beside it. A caller declares what it MEASURED; everything else in
    the structure is an assertion built on the holdout, including a field added
    to the payload next year by someone who never read this module. A list of
    fields to null would have to be edited in step with the payload and would
    fail open when it was not; this fails closed, and the cost is that a new
    measurement has to be declared before it survives.
    """
    return sorted(".".join(p) for p in _leaf_paths(payload)
                  if p and p[0] not in GATE_FIELDS and not _declared(p, data))


def withhold_claims(payload: dict, ineligible: str | None, data) -> dict:
    """Null every claim in `payload` when the holdout cannot carry one.

    ELIGIBILITY GATES THE WHOLE VERDICT SURFACE, NOT ONE FIELD. This is the
    third time the same failure has been found: a run that has already printed
    why it cannot be trusted goes on to publish the ordinary affirmative
    result. First closed_fraction was published on an ineligible corpus; then
    closed_fraction alone was nulled and everything beside it survived.
    Measured on the bytes before this function existed, with training stubbed
    so only the analysis ran and a corpus one document of which holds 99% of
    it, exp_steps_vs_quality printed

        NOT ELIGIBLE for a baseline comparison: this corpus cannot support the
        requested split: no whole-document split of it gets near the request

    and, at the end of the same run,

        VERDICT: longer training measurably helps

    while the result file carried that verdict plus two comparisons marked
    beats_noise true, and runs.jsonl recorded
    {"verdict": "longer training measurably helps", ...} with no eligibility
    field anywhere on the row. Every one of those is an affirmative claim about
    unseen text, made about a holdout the same run had just called unusable.

    WHAT SURVIVES, AND WHY IT IS NOT A LOOPHOLE. The measurements do. A per-seed
    validation loss is the number the model scored on the text that was actually
    held back; it is what happened, and recording it is how a later reader can
    re-derive anything if the split is ever shown to be sound after all. What
    ineligibility destroys is the INTERPRETATION -- that those numbers say
    anything about text the model has not seen -- so every difference between
    arms, every comparison against noise and every verdict string goes, and the
    readings stay beside the sentence that says why they cannot be read. A
    caller that declares a comparison as a measurement is lying to this
    function; nothing here can stop it, and the declaration is in its file
    where a reader can check it.

    Returns a new payload. The original is not modified.
    """
    withheld = claims_in(payload, data)
    if ineligible:
        out = _null_claims(payload, data)
    else:
        out = dict(payload)
    out["holdout_eligible"] = ineligible is None
    out["ineligible_reason"] = ineligible
    out["claims_withheld"] = [] if ineligible is None else withheld
    return out


def compare(train: str, val: str, vocab_size: int,
            model_val_nats: float | None = None) -> dict:
    """Score every baseline on this split, plus the model if you have its loss.

    Returns nats/char, bits/char and 'choices' (exp of the loss — the same
    quantity the studio plots) for each, so a caller can present whichever unit
    suits its reader. `closed_fraction` answers the question the old headline was
    reaching for, but against the n-gram instead of against uniform: of the
    distance the n-gram left on the table, how much did the model close?
    """
    out: dict[str, dict] = {}

    def row(name: str, nats: float) -> None:
        out[name] = {"nats_per_char": nats,
                     "bits_per_char": nats / LN2,
                     "choices": math.exp(nats)}

    row("uniform", uniform_nats(vocab_size))
    row("frequency", frequency_nats(train, val, vocab_size))
    row(f"ngram_{NGRAM_ORDER}", ngram_nats(train, val, vocab_size))

    if model_val_nats is not None:
        row("model", model_val_nats)
        ng = out[f"ngram_{NGRAM_ORDER}"]["choices"]
        md = out["model"]["choices"]
        # How much of the n-gram's remaining distance to perfect the model closed.
        # Negative means the model is WORSE than the lookup table, which is the
        # single most useful thing this file can tell you.
        out["closed_fraction"] = (ng - md) / (ng - 1.0) if ng > 1.0 else 0.0
    return out


def summary_lines(cmp: dict) -> list[str]:
    """Plain-language rendering. Deliberately states what beating uniform is
    worth, because that is the sentence the old headline left out."""
    order_key = f"ngram_{NGRAM_ORDER}"
    label = {"uniform": "pure guessing (every character equally likely)",
             "frequency": "knowing only which letters are common",
             order_key: f"a lookup table on the previous {NGRAM_ORDER - 1} characters",
             "model": "YOUR MODEL"}
    lines = []
    for key in ("uniform", "frequency", order_key, "model"):
        if key not in cmp:
            continue
        r = cmp[key]
        lines.append(f"  {label[key]:<52} {r['bits_per_char']:5.3f} bits/char"
                     f"   {r['choices']:6.2f} choices")
    if "closed_fraction" in cmp:
        pct = cmp["closed_fraction"] * 100
        if pct < 0:
            lines.append(f"  Your model is WORSE than the lookup table "
                         f"({-pct:.0f}% behind it). More training, more text, or a "
                         f"bigger model — but right now it has not earned its cost.")
        else:
            lines.append(f"  Beating pure guessing is easy — the lookup table above "
                         f"does most of it for free.")
            lines.append(f"  Of what the lookup table could NOT do, your model did "
                         f"{pct:.0f}%. That part needed learning.")
    return lines
