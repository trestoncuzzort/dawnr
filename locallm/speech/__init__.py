"""speech — dawnr hears and speaks, trained here, from random weights.

Design: ../../DAWNR-SPEECH.md. That file is the plan (data, order, metrics);
this package is what is actually built so far: a from-scratch CTC acoustic
model for automatic speech recognition (ASR), the log-mel front end it reads,
a character vocabulary and greedy decoder, WER/CER scoring, dataset and
manifest plumbing, download and preprocessing scripts meant to run on the lab
workstation, and an optional, lazily-imported microphone/speaker layer for
the Tk app. Text-to-speech (TTS) is designed in DAWNR-SPEECH.md but not yet
implemented; see that file's "what to train, in what order" section for why.

Every module here is importable with only the standard library and torch
(already a hard dependency of locallm). numpy is used where it already ships
alongside torch. Anything that touches real audio hardware or a real
downloaded corpus keeps its own extra dependency behind a lazy, in-function
import, exactly like ``tkinterdnd2`` in home.py and ``charset_normalizer`` in
ingest.py, so importing this package never requires anything beyond what
locallm already needs.
"""
