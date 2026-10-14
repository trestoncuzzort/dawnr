#!/usr/bin/env python3
"""ONE admission + interpretation policy for the E1 paired gate, imported IDENTICALLY by resume, run
completeness and the authoritative aggregator, so a single row can never be counted two different ways.

Policy:
  * STABILITY is a refusal: a graded observation counts only if BOTH flake-agreement flags are True.
  * VACUOUS, TIMEOUT, UNPROVED, MALFORMED, TOOL_ERROR are NOT verify/refute verdicts -- they are
    unverifiable observations (carried with their reason). Only a stable VERIFIED or REFUTED is a verdict.
  * A graded Result is reused on resume ONLY if its eff_config_id matches, its bound input-identity hashes
    match the frozen manifest, and each Result's own source_sha256 matches the bound lowered source (and is
    not the 64-zero placeholder). Typed outcomes (parse/lower/backend-unavailable/input-drift) are NEVER
    reused from a checkpoint -- they are recomputed fresh each run from the current validated input, so a
    stale drift/parse/lower record can never poison a later valid resume.
  * Only worker-level failures (no Result produced) are transient and retried. A kernel TIMEOUT is a
    produced, budget-limited OBSERVATION: reused like any graded Result, and interpreted as unverifiable
    (not a verdict). This is the one consistent timeout policy.
"""
VERIFIED, REFUTED, VACUOUS = "verified", "refuted", "vacuous"
ZERO_SHA = "0" * 64
IDENT3 = ("program_sha256", "twin_sha256", "witness_sha256")
# typed states that are DETERMINISTIC for the frozen input+config -> a resolved (complete) observation
RESOLVED_TYPED = ("unverified:parse-error", "unverified:lower-error", "unverified:backend-unavailable")
# typed states that are NOT resolved -> the cell is incomplete until re-run
INCOMPLETE_TYPED = ("unverified:input-drift", "unverified:worker-error", "unverified:worker-timeout")


def interpret(d):
    """Canonical cell interpretation. graded -> real/twin in {verified,refuted} (stable) else unverifiable:*."""
    st = d.get("state", "graded")
    if st != "graded" and "real_outcome" not in d:
        return {"kind": "typed", "state": st}
    ra, ta = d.get("real_agreed"), d.get("twin_agreed")

    def side(o, ag):
        return o if (o in (VERIFIED, REFUTED) and ag is True) else f"unverifiable:{o}|agreed={ag}"
    return {"kind": "graded", "state": "graded", "stable": ra is True and ta is True,
            "real": side(d.get("real_outcome"), ra), "twin": side(d.get("twin_outcome"), ta)}


def graded_admissible(d, eff_cfg=None, pair_ident=None, bound_src=None, strict=True):
    """True iff d is a trustworthy, reusable graded OBSERVATION for its cell. strict=False (preserved v1 raw,
    no identity binding) keeps only the stability refusal; strict=True enforces config + identity + source."""
    if d.get("state") != "graded":
        return False                                   # typed rows are never reused (recomputed fresh)
    if not (d.get("real_agreed") is True and d.get("twin_agreed") is True):
        return False                                   # stability is a refusal
    # integrity checks that hold in BOTH modes: a graded verdict must retain both Result objects, each from
    # THIS cell's kernel, and the top-level outcome must equal the retained Result's outcome (no contradiction)
    rr, tr = d.get("real_result") or {}, d.get("twin_result") or {}
    if not rr or not tr:
        return False
    kern = d.get("kernel")
    if rr.get("backend") != kern or tr.get("backend") != kern:
        return False
    if d.get("real_outcome") != rr.get("outcome") or d.get("twin_outcome") != tr.get("outcome"):
        return False
    if not strict:
        return True
    if d.get("eff_config_id") != eff_cfg:
        return False
    if pair_ident is None:                             # strict (v2) cannot validate without a frozen pair
        return False
    for k in IDENT3:                                   # identity REQUIRED present AND matching (fail-closed)
        if d.get(k) != pair_ident.get(k):
            return False
    rr, tr = d.get("real_result") or {}, d.get("twin_result") or {}
    if rr.get("source_sha256") in (None, ZERO_SHA) or tr.get("source_sha256") in (None, ZERO_SHA):
        return False                                   # a Result must carry the real bytes it graded
    if bound_src is None:
        return False
    return (rr.get("source_sha256") == bound_src.get("real_src_sha256")
            and tr.get("source_sha256") == bound_src.get("twin_src_sha256"))


def interp_key(d):
    """Hashable interpretation for conflict detection (two admissible rows that disagree -> quarantine)."""
    it = interpret(d)
    return (it["kind"], it.get("state"), it.get("real"), it.get("twin"))
