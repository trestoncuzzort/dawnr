# Findings: the CTC acoustic model overfits six synthetic utterances

Predicted in `PREDICT-speech-ctc-smoke-2026-09-27.md`. Measured by running
`test_speech_ctc.py::SmokeTestOverfitsAHandfulOfUtterances` exactly as
committed, CPU only (`systemd-run --user --scope -p MemoryMax=2G`, per this
project's memory-safety rule for torch runs on this machine), one seed
(`torch.manual_seed(0)`).

## Result

    [speech smoke] 7.3s, loss 41.10 -> 0.0033, meanWER 0.000, meanCER 0.000,
    hyps ['go', 'stop', 'cat', 'dog', 'red', 'blue']

Labels, in order: `go stop cat dog red blue`. The decoded hypotheses match
every label exactly.

## Predictions against the measurement

1. **CTC loss finite at every one of the 400 steps.** Held -- the test
   asserts this inline every step and did not fail.
2. **Final loss below 0.05 nats.** Held, with a wide margin: **0.0033**,
   close to the unregistered development run's 0.0032 at the same
   configuration and step count (a different run, different seed context,
   consistent result).
3. **Mean WER and mean CER exactly 0.0.** Held exactly: both **0.000**, and
   every one of the six decoded strings matches its label character for
   character (`go`, `stop`, `cat`, `dog`, `red`, `blue`).
4. **Under 60 seconds.** Held: **7.3s**, in the same range as the
   development run's 7.24s.

All four predictions held. Nothing here was softened or re-run to fit --
this is the first and only execution of this committed test.

## What this does and does not establish

**Does:** the whole pipeline this track built runs correctly end to end on
real files on disk -- `synthetic.py`'s WAV writer, `dataset.py`'s stdlib
`wave` reader, `audio_features.py`'s STFT-based log-mel extraction,
`ctc_model.py`'s conv+BiGRU+CTC forward and backward pass, `ctc_decode.py`'s
greedy collapse, and `metrics.py`'s WER/CER -- and a 141k-parameter model can
use gradient descent on that pipeline's loss to drive both the loss and the
error rate to (near) zero on a handful of easily-separable examples. That is
the floor `DAWNR-SPEECH.md`'s "what to train, in what order" section
requires before spending any lab time or GPU time on real audio.

**Does not:** say anything about word error rate on real speech. Six
half-second tones with distinct pitches are, by construction, far easier to
tell apart than phonemes in continuous speech, and 400 full-batch gradient
steps over 6 fixed examples is memorization, not generalization to unheard
audio. The first number this project is entitled to call an ASR accuracy
result is a LibriSpeech `dev-clean` WER, not measured here and not claimed
here (`DAWNR-SPEECH.md`, "what to train, in what order", step 2).

## What was learned

The pipeline's weakest untested joint going in was the interaction between
`torch.stft`'s centered framing and `AcousticConfig.output_length`'s
analytic formula for the conv front end's downsampled length -- a one-frame
mismatch there would either crash `pack_padded_sequence` or, worse, silently
misalign which frames `F.ctc_loss` is allowed to score. It did not
mismatch (`test_speech_ctc.AcousticConfigTest.test_output_length_formula`
and the smoke test's own clean convergence both exercise it), but the actual
bug this session's own testing caught was different and more mundane: an
early draft of `audio_features.log_mel_spectrogram` used `torch.stft`'s
default reflect-padding, which crashes on a waveform shorter than half an
STFT frame (found by a unit test using a 10-sample waveform, not by the
smoke test itself, whose utterances are all 0.8s). Switched to
`pad_mode="constant"`, which has no such minimum length. The general lesson,
consistent with this project's existing one (`AGENTS.md` rule 1): a
deliberately extreme edge case in a unit test found a real crash that every
"normal-length" check, including this file's own smoke test, would have
missed entirely.
