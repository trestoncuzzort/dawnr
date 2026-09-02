"""leakage.py — find training text hiding in your validation set.

This is the check almost no training tool performs, and it is the most common
way a good-looking number turns out to be fake. If validation text also appears
in training, the model has already seen the answers, val loss drops, and you
conclude your change helped when it did nothing.

    python leakage.py --data corpus.txt

It measures three things, cheapest first:

  document overlap  whole documents that appear on both sides of the split
  line overlap      validation lines that appear verbatim in training
  content overlap   winnowing fingerprints of validation text found in training

ALL THREE DECIDE THE VERDICT, each against its own bar, and the verdict is the
worst call any of them makes. This file used to print all three and decide on
content alone, which is not merely untidy: content overlap cannot see a copied
run shorter than 50 characters at all, so a holdout made entirely of verbatim
copies of short training documents scored 0.0% and read CLEAN. See Report.

TWO OF THE THREE CAN BE n/a, and an arm that is n/a says so rather than voting
CLEAN: documents on a split that cut mid-document, lines on a holdout with too
few of them for a fraction to be a measurement. A CLEAN verdict is only ever as
strong as the arms that could actually be read, and the report names them.

BUT n/a IS FOR A FRACTION THAT CANNOT BE READ, NEVER FOR ONE THAT IS TOO LARGE
TO ARGUE WITH. The line arm's small-holdout floor was written as a gate on the
whole arm, which turned a denominator into a blind spot: 19 validation lines,
every one of them a verbatim training line in a new order, read n/a on lines,
0.0% on content, and CLEAN overall. A floor that quiets the borderline band must
still let overwhelming overlap through, and this one now does. See
LINE_DECISIVE.

Content overlap is the finest-grained of the three, WITHIN a scope worth stating
up front: this is an exact-substring scanner, not a near-duplicate scanner.
Measured recall on this project's own documents, by clone type:

    verbatim copy                          100%
    reformatted (whitespace re-rendered)    90%
    every identifier renamed                 0%
    renamed + 10% of statements edited       0%

Renaming identifiers costs almost nothing; replacing the string literals is what
destroys detection. On this codebase roughly 7% of the text is prose inside the
code, and that 7% carries nearly all the surviving signal. So a CLEAN verdict
means no one copied and pasted. It does not mean validation is independent.

Nothing here is a model. It is string matching, and it runs in under a second.
"""
from __future__ import annotations

import argparse
import sys
import hashlib
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import runlog
from data import documents, group_split, split_health, split_verdict

SHINGLE = 50          # characters per k-gram
WINDOW = 25           # winnowing window, in k-grams. Guarantees that any shared
                      # run of >= WINDOW + SHINGLE - 1 = 74 characters is caught,
                      # regardless of where it starts. See shingles().
DOC_MARKER = "\n\n# file: "

# Above this fraction of validation shingles found in training, a val number is
# not worth reporting. Below the lower bound, incidental overlap is expected in
# any corpus with shared vocabulary and is not a finding.
CONTAMINATED = 0.20
SUSPECT = 0.05

# The other two signals get their own bars, because they are not the same kind
# of evidence. Justified against measurement in Report._calls().
DOC_CONTAMINATED = 0.10
DOC_SUSPECT = 0.01
LINE_CONTAMINATED = 0.90
LINE_SUSPECT = 0.50

# The line arm needs a denominator before its fraction means anything. At n
# validation lines, ONE honestly recurring line -- a licence header, a repeated
# heading -- is worth 1/n, so at n = 2 a single shared line reads 50.0% and
# trips the SUSPECT bar on its own. Measured on 110 genuinely clean grouped
# splits of this project's own text (its Python sources, and its markdown; 5
# seeds x 11 requested val fractions), three of them read SUSPECT on the line
# arm with nothing copied anywhere: two 2-line holdouts at 50.0% and one
# 12-line holdout at 50.0%. Above 20 lines, none of the 56 splits measured
# reached the bar and the worst clean reading was 39.1%.
#
# 20 is that measured floor and it is also where the arithmetic stops being a
# coin flip: one recurring line is worth 5 points, so reaching 0.50 takes ten
# shared lines rather than one. Below it the SUSPECT band reads n/a and says so,
# the same way the document arm is gated by doc_aligned -- an unreadable signal
# is not a clean one, and the report must not let it look like either.
LINE_MIN_VAL_LINES = 20

# THE FLOOR SUPPRESSES BORDERLINE EVIDENCE. IT MUST NOT SUPPRESS OVERWHELMING
# EVIDENCE, and as first written it did: it gated the whole arm, so it was a
# blind spot with a denominator's justification. Measured on the bytes before
# this change, a 19-line holdout every line of which is a verbatim training line
# in a different order:
#
#     lines 19 / 19 (100.0%)   content 0.0%   documents n/a
#     VERDICT CLEAN   trustworthy True
#
# One line under the floor, nothing in the holdout unseen, and the scan called
# it clean. At 20 lines the identical fixture reads CONTAMINATED.
#
# The floor's own justification is what separates the two cases. It exists
# because ONE honestly recurring line is worth 1/n, so at small n the SUSPECT
# band is noise; it says nothing whatever about a holdout that IS its training
# set. So the floor keeps the SUSPECT band, and the arm still escalates below it
# when the overlap is decisive: LINE_DECISIVE of the lines shared, on at least
# LINE_DECISIVE_MIN_LINES of them.
#
# 0.90 is LINE_CONTAMINATED, the bar this arm already calls contamination at,
# and below the floor it is a demanding one rather than a loose one. Integer
# counts: reaching 0.90 takes EVERY line up to n = 9 (8/9 is 88.9%), then 9 of
# 10, 14 of 15, 18 of 19. That is not a licence header recurring, it is the
# holdout.
#
# 3 is the smallest denominator at which "all of it" is more than the corpus's
# own boilerplate. Two of the three false SUSPECTs the floor was built for are
# 2-line holdouts, one shared line each; a 2-line holdout whose BOTH lines are
# boilerplate is the same shape one line further along, and a 1-line holdout is
# a single line. From 3 up, "all of it" needs three independent lines to recur
# together.
#
# The amended rule owes the evidence the floor was justified with, so it was
# re-measured on the same calibration: the two corpora of commit 98be925,
# rebuilt byte-exactly (non-test Python sources 255,237 chars sha1 a35d7d4ce43c;
# markdown 89,349 chars sha1 b364c23b1ec5, both at commit 38f5866), 5 seeds x 11
# requested val fractions x 2 corpora = 110 genuinely clean grouped splits, plus
# a 320-split superset over 32 val fractions, because that commit records only 3
# of its 11 fractions and the other 8 are not recoverable from it. The three
# known false SUSPECTs reproduce exactly (2 lines at 50.0% on seeds 7 and
# 20260901, 12 lines at 50.0% on seed 4242, all at val_frac 0.0002/0.002 on the
# Python corpus), and the decisive rule fires on NONE of either set. The worst
# clean line_frac measured below the floor is 50.0% over the 110 and 66.7% over
# the 320 -- twenty-three points of room at the tighter of the two. Above the
# floor: 33.3% and 39.1%. Zero of 110 and zero of 320. See the commit message.
LINE_DECISIVE = LINE_CONTAMINATED
LINE_DECISIVE_MIN_LINES = 3

_RANK = {"CLEAN": 0, "SUSPECT": 1, "CONTAMINATED": 2}


def _call(frac: float, contaminated: float, suspect: float) -> str:
    """One signal's own verdict against its own two bars."""
    if frac >= contaminated:
        return "CONTAMINATED"
    return "SUSPECT" if frac >= suspect else "CLEAN"


def _h(chunk: bytes) -> int:
    """64-bit hash of one k-gram.

    Width matters here in a way it would not for an ordinary hash table, because
    winnowing keeps the MINIMUM hash in each window. Minima are drawn from the
    bottom of the range, so the effective space is far smaller than the nominal
    one and collisions inflate accordingly. Measured with 32-bit crc32: selected
    fingerprints averaged 0.056 of the range against 0.502 for all hashes, a 9x
    concentration, and two independently generated, genuinely CLEAN corpora
    showed false overlap rising with size (0.0065% at 200KB to 0.0293% at 2MB).
    Extrapolated, a large clean corpus would eventually trip the contamination
    threshold on collisions alone. 64 bits removes the effect entirely at every
    size measured, for the same fingerprint count and no measurable cost.
    """
    return int.from_bytes(hashlib.blake2b(chunk, digest_size=8).digest(), "big")


def shingles(text: str, k: int = SHINGLE, window: int = WINDOW) -> set[int]:
    """Winnowing fingerprints (Schleimer, Wilkerson & Aiken 2003).

    The obvious approach, keeping every k-th window at a fixed stride, is
    PHASE-DEPENDENT and quietly broken: two identical passages are only compared
    when both happen to start on the same stride phase. Measured on this
    project's own corpus, a document copied verbatim into training was detected
    at 1 of 10 byte offsets. A detector that misses nine tenths of the exact
    case it exists to catch is worse than none, because it reads CLEAN.

    Winnowing instead selects windows by CONTENT: hash every k-gram, then in
    each sliding window of `window` hashes keep the smallest. Which hashes get
    kept therefore depends on the text, not on where the text starts, so the
    same passage yields the same fingerprints wherever it appears.

    IT IS A TRADE, NOT A FREE WIN, and the trade is measured rather than
    asserted. Detection against the length of the shared run, 20 trials each,
    winnowing versus the old sampler:

        100 chars   100%  vs   90%
         74 chars   100%  vs  100%     <- the documented guarantee, window+k-1
         73 chars   100%  vs   90%
         60 chars    40%  vs   80%     <- old sampler is BETTER here
         50 chars    10%  vs   80%     <- and much better here
         40 chars     0%  vs    0%

    So winnowing buys phase-invariance above the guarantee length and gives up
    short-run sensitivity below it. For finding duplicated documents, passages
    and functions, that is the right trade. For finding copied fragments shorter
    than ~60 characters it is the wrong one, and this returns fewer of them than
    the code it replaced.

    The 74-character guarantee is checked by test_detectors.py, which asserts
    the documented number rather than a hopeful one. Per this file's own rule:
    a docstring that says "guarantee" names the test that checks it.
    """
    if len(text) < k:
        return {_h(text.encode("utf-8", "ignore"))} if text.strip() else set()

    b = text.encode("utf-8", "ignore")
    hashes = [_h(b[i:i + k]) for i in range(len(b) - k + 1)]
    if len(hashes) < window:
        return set(hashes)

    # Sliding-window minimum. Popping on >= keeps the RIGHTMOST minimal hash,
    # which is the tie-break the paper specifies: consecutive windows then tend
    # to re-select the same fingerprint instead of two adjacent ones.
    selected: set[int] = set()
    dq: deque[int] = deque()
    prev = -1
    for i, h in enumerate(hashes):
        while dq and hashes[dq[-1]] >= h:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - window:
            dq.popleft()
        if i >= window - 1:
            j = dq[0]
            if j != prev:
                selected.add(hashes[j])
                prev = j
    return selected


@dataclass
class Report:
    train_chars: int
    val_chars: int
    val_docs: int
    val_docs_in_train: int
    doc_aligned: bool          # False when the split cut through a document
    val_lines: int
    val_lines_in_train: int
    val_shingles: int
    val_shingles_in_train: int

    @property
    def doc_frac(self) -> float:
        return self.val_docs_in_train / max(self.val_docs, 1)

    @property
    def line_frac(self) -> float:
        return self.val_lines_in_train / max(self.val_lines, 1)

    @property
    def shingle_frac(self) -> float:
        return self.val_shingles_in_train / max(self.val_shingles, 1)

    @property
    def lines_readable(self) -> bool:
        """Whether the holdout has enough lines for line_frac to be a
        measurement across its whole range, SUSPECT band included. See
        LINE_MIN_VAL_LINES."""
        return self.val_lines >= LINE_MIN_VAL_LINES

    @property
    def lines_decisive(self) -> bool:
        """Whether the overlap is too large for the floor to be about it.

        The floor is a statement about the BORDERLINE band: at small n one
        recurring line moves the fraction too far for 0.50 to mean anything.
        Nothing about that argument reaches 100% of a 19-line holdout, which is
        19 lines of training text with nothing unseen among them however small
        the denominator. See LINE_DECISIVE.
        """
        return (self.val_lines >= LINE_DECISIVE_MIN_LINES
                and self.line_frac >= LINE_DECISIVE)

    @property
    def lines_read(self) -> bool:
        """Whether the line arm gets a vote at all: a readable denominator, or
        an overlap decisive enough not to need one."""
        return self.lines_readable or self.lines_decisive

    def _signals(self) -> list[dict]:
        """Every arm: its fraction, its call, whether it is read, and why not.

        ONE TABLE, BECAUSE THREE CONSUMERS READ IT and they must not be able to
        disagree. The verdict is the worst call among the arms that are read,
        the reason quotes the arms that produced that call, and record() -- the
        row a writer persists -- carries all of them. Before this table the row
        was assembled by hand at three call sites and consisted of the verdict
        and the CONTENT fraction: measured on
        test_detectors.short_document_fixture, a holdout 100% of which is
        byte-identical to a training document, train.py:104 and studio.py:522
        persisted {"verdict": "CONTAMINATED", "content_frac": 0.0} and runlog's
        summary printed

            CONTAMINATED  content 0.00%

        which is a verdict beside the one number that did not cause it. The
        deciding arms were documents 100.0% and lines 100.0%, and neither was
        written down anywhere.

        THREE MEASUREMENTS, THREE BARS, AND THE VERDICT IS THE WORST OF THEM.
        This used to read shingle_frac alone while printing all three, which is
        precisely the failure test_detectors.py's docstring names — a human
        reads the healthy number — except that here the blind spot is
        structural rather than incidental. Winnowing cannot fingerprint a
        shared run shorter than SHINGLE = 50 characters, so a holdout built
        ENTIRELY of byte-identical copies of short training documents scores no
        content overlap whatsoever. Measured: 40 copied documents of 30-35
        characters, 100% of the holdout duplicated, content overlap 0.0%, old
        verdict CLEAN and trustworthy True.

        The three bars differ because the three signals do:

          content   0.20 / 0.05, unchanged. A shared 74-character run can be
                    coincidence in a corpus with shared vocabulary and
                    boilerplate, so it needs room before it means anything.

          documents 0.10 / 0.01, TIGHTER, because a byte-identical document has
                    no innocent explanation: two independently written
                    documents are not byte-identical. Measured 0.000% across
                    six clean grouped splits (this project's own sources and
                    its markdown, seeds 1337/7/99). Read only when the split is
                    document-aligned; on a positional cut the counts describe
                    fragments and the report already prints n/a for them.
                    Expect 0 on the grouped path — group_split de-duplicates
                    before it splits — so this arm exists for the callers that
                    bring their own split, which is what scan() invites.

          lines     0.90 / 0.50, MUCH LOOSER, because short lines legitimately
                    recur: `}`, `    return`, a repeated heading. Measured on
                    this project's own sources as a corpus, grouped split, with
                    nothing copied anywhere: 11.1%, 18.4% and 26.7% of
                    validation lines at seeds 99, 7 and 1337. A 0.20 bar here
                    would cry wolf on every code corpus in existence. At 0.90
                    the holdout is a re-arrangement of training lines and there
                    is nothing unseen left in it. The SUSPECT band is read only
                    above LINE_MIN_VAL_LINES, because a bar is only half of a
                    signal: below 20 lines one recurring line is worth 5 points
                    or more and the fraction is noise with a percent sign on it.
                    The CONTAMINATED bar still fires below the floor, from
                    LINE_DECISIVE_MIN_LINES lines up, because that argument is
                    about a borderline fraction and does not reach a holdout
                    that is 90% training text. See LINE_DECISIVE.
        """
        # A line call made below the floor says so in the same breath. The
        # reader of that sentence has been told elsewhere that under 20 lines
        # the arm reads n/a, and a verdict that contradicts that without
        # explaining itself is the contradiction the floor was added to remove,
        # arriving from the other side.
        below = ("" if self.lines_readable else
                 f", decisive on {self.val_lines} lines even under the "
                 f"{LINE_MIN_VAL_LINES}-line floor")
        return [
            {"name": "content", "frac": self.shingle_frac,
             "call": _call(self.shingle_frac, CONTAMINATED, SUSPECT),
             "meaningful": True, "read": True, "why_not": None,
             "says": f"{self.shingle_frac:.1%} of validation content "
                     f"fingerprints are found in training"},
            {"name": "document", "frac": self.doc_frac,
             "call": _call(self.doc_frac, DOC_CONTAMINATED, DOC_SUSPECT),
             "meaningful": self.doc_aligned, "read": self.doc_aligned,
             "why_not": None if self.doc_aligned else
                        "the split cut through a document, so document counts "
                        "are not meaningful",
             "says": f"{self.doc_frac:.1%} of validation documents are "
                     f"byte-identical to a training one"},
            {"name": "line", "frac": self.line_frac,
             "call": _call(self.line_frac, LINE_CONTAMINATED, LINE_SUSPECT),
             "meaningful": True, "read": self.lines_read,
             "why_not": None if self.lines_read else
                        f"the holdout is {self.val_lines} line(s), under the "
                        f"{LINE_MIN_VAL_LINES}-line floor",
             "says": f"{self.line_frac:.1%} of validation lines appear "
                     f"verbatim in training{below}"},
        ]

    def _calls(self) -> list[tuple[str, str]]:
        """The arms that get a vote, as (call, sentence). See _signals."""
        return [(s["call"], s["says"]) for s in self._signals() if s["read"]]

    @property
    def verdict(self) -> str:
        return max((c for c, _ in self._calls()), key=_RANK.__getitem__)

    @property
    def reason(self) -> str:
        """Which signal produced the verdict, in words. A verdict whose own
        summary quotes a different number than the one that caused it sends the
        reader looking in the wrong place."""
        v = self.verdict
        if v == "CLEAN":
            docs = (f", documents {self.doc_frac:.1%}" if self.doc_aligned else "")
            lines = (f"{self.line_frac:.1%}" if self.lines_read
                     else f"n/a on {self.val_lines} line(s)")
            return (f"nothing above a bar (content {self.shingle_frac:.1%}, "
                    f"lines {lines}{docs})")
        return "; ".join(r for c, r in self._calls() if c == v)

    @property
    def trustworthy(self) -> bool:
        return self.verdict == "CLEAN"

    def summary(self) -> str:
        return f"{self.verdict}: {self.reason}"

    def record(self) -> dict:
        """The row a writer persists: the verdict AND what produced it.

        WRITTEN HERE, ONCE, rather than at each call site. train.py, studio.py
        and this file's own main() each built their own row, and two of the
        three carried the verdict beside the content fraction alone. That was
        correct while content overlap WAS the verdict; it stopped being correct
        when the verdict became the worst of three signals, and nothing made the
        three writers notice. A row assembled from _signals() cannot fall behind
        the rule that way: an arm added to that table appears in every row that
        is written afterwards.

        WHAT EACH FIELD IS FOR:

          reason      the sentence the deciding arm produced. A row whose
                      verdict and whose only number disagree sends its reader
                      looking in the wrong place; this is the number that
                      caused it, in words.
          deciding    the arms whose call equals the verdict. On CLEAN that is
                      every arm read, which is the truth: they all agreed.
          *_frac      every arm's fraction, read or not. A fraction that was
                      measured but not READ is kept rather than nulled -- it is
                      a real count, it just is not a verdict -- except where the
                      count is not meaningful at all: on a positional split the
                      "documents" are fragments, so document_frac is null and
                      not_read says why.
          not_read    the arms that got no vote, and why. Without it a row can
                      read CLEAN beside line_frac 0.5 and look like a
                      contradiction when the truth is that the holdout had two
                      lines and the arm was never read.
        """
        v = self.verdict
        sig = self._signals()
        rec = {
            "verdict": v,
            "reason": self.reason,
            "deciding": [s["name"] for s in sig if s["read"] and s["call"] == v],
            "not_read": {s["name"]: s["why_not"] for s in sig if not s["read"]},
        }
        for s in sig:
            rec[f"{s['name']}_frac"] = s["frac"] if s["meaningful"] else None
        rec.update(doc_aligned=self.doc_aligned,
                   lines_readable=self.lines_readable,
                   lines_decisive=self.lines_decisive,
                   val_lines=self.val_lines, val_chars=self.val_chars)
        return rec

    def report(self) -> str:
        bar = "=" * 64
        lines = [
            bar,
            f"LEAKAGE SCAN                                  verdict: {self.verdict}",
            bar,
            f"  train {self.train_chars:>10,} chars     val {self.val_chars:>10,} chars",
            "",
            (f"  documents  {self.val_docs_in_train:>6,} / {self.val_docs:<6,} "
             f"of validation documents are byte-identical to a training one "
             f"({self.doc_frac:.1%})"
             if self.doc_aligned else
             "  documents     n/a  the split cut through a document, so document "
             "counts are not meaningful"),
            (f"  lines      {self.val_lines_in_train:>6,} / {self.val_lines:<6,} "
             f"of validation lines appear verbatim in training "
             f"({self.line_frac:.1%})"
             + ("" if self.lines_readable else
                f"   <- under the {LINE_MIN_VAL_LINES}-line floor, and read "
                f"anyway: {LINE_DECISIVE:.0%} or more is not a borderline "
                f"fraction")
             if self.lines_read else
             f"  lines         n/a  the holdout is {self.val_lines} line(s), under "
             f"the {LINE_MIN_VAL_LINES}-line floor: below it one recurring line is "
             f"worth {1 / LINE_MIN_VAL_LINES:.0%} of the fraction or more"),
            f"  content    {self.val_shingles_in_train:>6,} / {self.val_shingles:<6,} "
            f"of validation fingerprints are found in training "
            f"({self.shingle_frac:.1%})   <- the finest-grained",
            "",
            f"  verdict {self.verdict}: {self.reason}",
            "",
        ]
        if self.verdict == "CONTAMINATED":
            lines += [
                "  Validation loss from this split is NOT a measure of generalisation.",
                "  The model is being tested on text it trained on. Do not compare",
                "  configurations with it, and do not report it as a result.",
                "",
                "  Fix: split by document (Corpus(..., grouped=True)) so duplicated",
                "  material cannot land on both sides, and de-duplicate the corpus.",
            ]
        elif self.verdict == "SUSPECT":
            lines += [
                "  Some overlap. Small amounts are normal when documents share",
                "  vocabulary and boilerplate, but treat small val differences with",
                "  suspicion, and prefer train loss for close comparisons.",
            ]
        else:
            lines += [
                "  No signal above its bar. Note what that does and does not mean:",
                "  this is an EXACT-SUBSTRING scanner. It finds shared runs of >=74",
                "  characters at any offset, measured 100% recall. It does NOT find",
                "  renamed or rewritten copies: measured 0% recall on identifier-",
                "  renamed Python, where re-rendering whitespace and replacing string",
                "  literals removes essentially all of the signal it relies on.",
                "  CLEAN here means 'no copy-paste found', not 'val is independent'.",
            ]
        lines.append(bar)
        return "\n".join(lines)


def scan(train_text: str, val_text: str, doc_aligned: bool = True) -> Report:
    train_docs = set(documents(train_text))
    val_docs = documents(val_text)
    train_lines = set(train_text.splitlines())
    val_lines = [l for l in val_text.splitlines() if l.strip()]
    train_sh = shingles(train_text)
    val_sh = shingles(val_text)

    return Report(
        train_chars=len(train_text),
        val_chars=len(val_text),
        val_docs=len(val_docs),
        val_docs_in_train=sum(1 for d in val_docs if d in train_docs),
        val_lines=len(val_lines),
        val_lines_in_train=sum(1 for l in val_lines if l in train_lines),
        val_shingles=len(val_sh),
        val_shingles_in_train=len(val_sh & train_sh),
        doc_aligned=doc_aligned,
    )


def positional_split(text: str, val_frac: float = 0.1) -> tuple[str, str]:
    """The naive split: cut the corpus at 90% of its length. Kept so the scan
    can show you what it costs."""
    n = int(len(text) * (1 - val_frac))
    return text[:n], text[n:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="corpus.txt")
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--split", choices=["positional", "grouped"], default="positional",
                    help="which split to scan (default: positional, what data.py did)")
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    text = Path(args.data).read_text(encoding="utf-8", errors="ignore")
    if args.split == "positional":
        tr, va = positional_split(text, args.val_frac)
    else:
        tr, va = group_split(text, args.val_frac, args.seed)

    print(f"corpus: {Path(args.data).name}  {len(text):,} chars, "
          f"{len(documents(text)):,} documents, split={args.split}\n")
    rep = scan(tr, va, doc_aligned=(args.split == "grouped"))
    print(rep.report())
    # The leakage half of the row is Report.record(), not a dict spelled out
    # here: this file, train.py and studio.py each wrote their own and two of
    # them carried the verdict beside the content fraction alone, which is not
    # the signal that decides. See Report.record.
    #
    # split_fingerprint as well as the split's NAME: this row's whole content is
    # a verdict about one holdout, and "grouped" does not identify it. Two scans
    # of the same corpus at different seeds or val fractions are different
    # scans with the same corpus fingerprint. Both paths here split TEXT, so
    # both have a holdout to hash -- unlike Corpus's ungrouped path, which
    # splits tokens and has none. On the positional path the recorded seed is
    # inert (nothing consumes it); val_sha1 is what identifies the holdout.
    # No data_device: this file never puts anything on a device.
    runlog.record("leakage", corpus=runlog.corpus_fingerprint(text),
                  split=args.split,
                  split_fingerprint=runlog.split_fingerprint(
                      args.val_frac, args.seed, va),
                  leakage=rep.record())

    if args.split == "grouped":
        h = split_health(text, args.val_frac, args.seed)
        # Two ratios, two different failures, two different remedies - which the
        # single boolean this replaced could not tell apart. The comparison
        # itself lives in data.split_verdict so this file, the GUI and the
        # double-click launcher cannot answer the same question differently.
        verdict = split_verdict(h)
        if verdict:
            print(f"\n  WARNING: asked for a {h['requested_val_frac']:.0%} validation "
                  f"split, got {h['achieved_val_frac']:.1%}; the best any whole-document "
                  f"split could reach is {h['achievable_val_frac']:.1%}.")
            print(f"  {h['unique_documents']} unique document(s) after de-duplication, "
                  f"largest is {h['largest_unique_doc_frac']:.0%} of them.")
            if verdict == "empty":
                print("  Nothing was held back at all: there is no validation number.")
            elif verdict == "corpus":
                print("  The CORPUS cannot support the request: it needs more, smaller "
                      "documents.")
            elif verdict == "splitter":
                print("  The corpus could support it but this SPLIT fell short: try "
                      "another seed.")
            print("  Prefer train loss until then.")
            sys.exit(1)
    sys.exit(0 if rep.trustworthy else 1)


if __name__ == "__main__":
    main()
