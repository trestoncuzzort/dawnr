"""text.py — the character vocabulary a CTC acoustic model predicts.

A CTC output layer needs one reserved symbol with no letter of its own (the
"blank"), used to align a long sequence of acoustic frames onto a short
sequence of characters without a hand alignment (Graves et al. 2006; the
worked explanation this project read is Hannun, "Sequence Modeling With CTC",
distill.pub/2017/ctc, fetched 2026-09-27). This is a small, self-contained
vocabulary rather than a reuse of ``data.CharTokenizer``: that tokenizer is
built for a language model's next-token prediction over whatever characters a
training corpus happens to contain, with no reserved blank and no fixed
alphabet, which is a different contract than CTC needs (a small, FIXED
alphabet known before training, with index 0 reserved and never a target).

The alphabet is lowercase English letters, space and apostrophe -- the same
minimal charset Deep Speech 2 (Amodei et al., arXiv:1512.02595) trains on for
English, which is what both LibriSpeech and LJSpeech transcripts are written
in once folded to lowercase. Anything else in a transcript (digits, other
punctuation) is dropped rather than silently mapped to some nearby letter,
the same "refuse, do not guess" rule ``ingest.py`` applies to text encodings:
a transcript that needed a symbol outside this alphabet would otherwise train
the model on a wrong pairing between audio and text with no signal that
anything was lost.
"""
from __future__ import annotations

import re
import unicodedata

BLANK = 0
_LETTERS = "abcdefghijklmnopqrstuvwxyz"
_SYMBOLS = (" ", "'") + tuple(_LETTERS)          # index 1.. ; 0 is blank
_ALLOWED = re.compile(r"[^a-z' ]+")
_SPACES = re.compile(r" +")


class CTCVocab:
    """Fixed alphabet with blank at index 0. Stable across every model and
    checkpoint this project trains, so a checkpoint's ids never depend on
    which transcripts happened to be in the training manifest."""

    def __init__(self):
        self.symbols = _SYMBOLS
        self.stoi = {c: i + 1 for i, c in enumerate(self.symbols)}
        self.itos = {i + 1: c for i, c in enumerate(self.symbols)}
        self.itos[BLANK] = ""

    @property
    def vocab_size(self) -> int:
        return len(self.symbols) + 1                # + blank

    @property
    def blank_id(self) -> int:
        return BLANK

    def normalize(self, text: str) -> str:
        """Fold to the trainable alphabet: NFKD strips accents to their base
        letter (so e.g. an accented vowel in a proper noun still trains
        rather than vanishing), lowercase, drop anything not in the
        alphabet, and collapse repeated spaces so silence between words
        never encodes as several blank-adjacent space tokens."""
        folded = unicodedata.normalize("NFKD", text)
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
        folded = folded.lower()
        folded = _ALLOWED.sub(" ", folded)
        return _SPACES.sub(" ", folded).strip()

    def encode(self, text: str) -> list[int]:
        """Ids for the already-alphabet text ``normalize`` returns. Encoding
        text that was not normalized first and contains a character outside
        the alphabet raises, rather than silently dropping it here too --
        normalize() is where dropping is a visible, deliberate step."""
        try:
            return [self.stoi[c] for c in text]
        except KeyError as exc:
            raise ValueError(
                f"{exc.args[0]!r} is outside the CTC alphabet; call normalize() first") from exc

    def decode(self, ids) -> str:
        """Ids back to text. Never raises: a blank id (only ever produced by
        collapsing a decoder's own output, not by encode()) maps to ''."""
        return "".join(self.itos.get(int(i), "") for i in ids)
