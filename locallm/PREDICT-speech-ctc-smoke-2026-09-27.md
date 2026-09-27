# Prediction: the from-scratch CTC acoustic model can overfit a handful of utterances

Registered before the run. This is a **pipeline smoke test, not an accuracy
claim about real speech**: `speech/synthetic.py` writes tone-plus-label WAV
files and their manifest with no download and no microphone, so passing this
says the plumbing works end to end (audio file I/O, log-mel features, the
`AcousticModel`, `torch.nn.functional.ctc_loss`, greedy decoding, WER/CER),
not that the model has learned anything about speech. The test this predicts
is `test_speech_ctc.py::SmokeTestOverfitsAHandfulOfUtterances`.

## Why this is worth registering rather than just running

The rest of this track's design (`DAWNR-SPEECH.md`) depends on this floor
holding before any lab time or GPU time is spent on real audio: a broken CTC
alignment, a decoder that never collapses repeats, or a feature extractor
that washes every utterance to indistinguishable features would each waste a
LibriSpeech download and a training run before showing up as "the model
never learns anything," which is a much more expensive way to find the same
bug. Six synthetic utterances at distinct tones is deliberately the easiest
possible version of this problem — if it cannot pass this, nothing past it
is worth attempting yet.

## What changes, and what does not

Fixed: 6 utterances (`go`, `stop`, `cat`, `dog`, `red`, `blue`), 0.8s each at
16 kHz, each a distinct tone (220 Hz to roughly 1.4 kHz) plus a little seeded
noise; a 40-mel-channel log-mel front end; an `AcousticModel` at
`conv_channels=64, rnn_hidden=64, rnn_layers=2` (measured at 141,021
parameters during development); Adam at lr 3e-3, gradient clipped to norm 5,
for 400 steps on the whole 6-utterance batch every step (full-batch gradient
descent — with 6 examples there is no minibatching to speak of); greedy
decoding; word and character error rate averaged over the 6 utterances.
`torch.manual_seed(0)` is fixed in the test, so this is a single seed, not a
multi-seed claim — appropriate for a smoke test, not for a result this
project would put in `SCOREBOARD.md`.

## Predictions

1. **The CTC loss is finite at every one of the 400 steps** (`zero_infinity`
   in `ctc_model.py` guards against the specific failure mode where an
   output length shorter than a target's repeat-driven minimum turns the
   loss infinite; this predicts that guard is never even needed here, since
   0.8s of audio gives far more frames than any of these 2-4 letter labels
   need).
2. **Final training loss (step 400) is below 0.05 nats.** During
   development (a separate, unregistered exploratory run, not this test)
   the same configuration reached 0.0032 by step 400 and crossed below 0.05
   by roughly step 150; 0.05 leaves a wide margin for this run's different
   seed and any subsequent code change before this file was committed.
3. **Mean word error rate over the 6 utterances is exactly 0.0, and so is
   mean character error rate.** Full memorization of 6 short, acoustically
   distinct labels is the whole point of a smoke test at this size; a
   nonzero WER here would mean the pipeline, not the model's capacity, is
   the problem, since 141k parameters is grossly oversized for 6 examples.
4. **The whole run (6 utterances, 400 steps, feature extraction, decode and
   scoring) completes in under 60 seconds on CPU.** The exploratory run
   measured 7.2 seconds; 60 is a loose bound meant to catch a real
   regression (an accidental O(n²) somewhere, a device mismatch forcing a
   silent fallback), not to be a tight target.

## What each outcome means

If all four hold, the floor DAWNR-SPEECH.md's "what to train, in what order"
section depends on is real, and the next step is a LibriSpeech `dev-clean`
run on the lab, with its own preregistered prediction, not this one. If
prediction 1 or 2 fails, the bug is in `ctc_model.py` or `audio_features.py`
and no real-data run should be attempted until it is found. If 3 fails while
1 and 2 hold, greedy decoding or the collapse rule in `ctc_decode.py` is
where to look first, since the loss having dropped that low without the
decoded text matching would mean the model learned the alignment but the
decoder is not reading it back correctly. Either way, the result is reported
in `FINDINGS-speech-ctc-smoke-2026-09-27.md`, including if it is not what
was predicted.
