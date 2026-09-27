# dawnr's speech: hearing and speaking, trained here

`AMBITION.md`'s table lists it plainly: "to hear and speak: speech recognition,
text to speech — not started" is now "design and data first," and this file
is that design, plus the first piece actually built: a from-scratch CTC
automatic speech recognition (ASR) model, measured on a CPU smoke test. Text
to speech (TTS) is designed below but not yet implemented — see "what to
train, in what order" for why ASR goes first.

Everything here follows the same rule as the rest of dawnr: **nothing is
claimed without a measurement.** The smoke test's prediction was written and
committed before it ran (`PREDICT-speech-ctc-smoke-2026-09-27.md`); its
outcome is `FINDINGS-speech-ctc-smoke-2026-09-27.md`. Nothing below claims
LibriSpeech-scale accuracy, because nothing at that scale has been trained
yet — that is explicitly future work, sized and sequenced, not measured.

## Where this fits

- **Offline-first.** Once trained, hearing and speaking run with no network,
  the same as the rest of dawnr. The network is used exactly once per
  corpus, to download it — a tool, never a dependency (`AMBITION.md`,
  "the network is a tool, never a dependency").
- **The person controls the microphone the same way they control every other
  tool.** `audio_io.py` never opens a stream on its own initiative; whatever
  calls it (today: a test; later: a chat window's Mic button) is itself a
  tool call under the harness's allow/ask/deny policy (`DAWNR-HARNESS.md`
  section 7). dawnr does not grant itself microphone access any more than it
  grants itself shell access.
- **Held-out boundary.** `t/loop_filter.py`'s held-out problem set is a set of
  *programming* problem ids; nothing in a speech corpus can contain one, so
  there is no overlap to police there. The boundary this track owns instead:
  a LibriSpeech `dev-*`/`test-*` split, once designated for evaluation, is
  never mixed into a training manifest. `dataset.py` does not enforce this by
  itself yet (there is only a training-data problem to enforce it against
  once a real training run exists) — noted here as a commitment for the run
  that does.
- **Everything is a measurement first.** The architecture below cites its
  sources; the numbers below are either measured (the smoke test) or labeled
  as a target from someone else's published run (Conformer, Whisper),
  never presented as this project's own result until they are.

## What is built now (`locallm/speech/`)

| File | What it is |
|---|---|
| `text.py` | `CTCVocab`: blank + 26 lowercase letters + space + apostrophe. `normalize()` folds accents and case, drops anything outside the alphabet by name. |
| `audio_features.py` | Log-mel spectrogram from a raw waveform, `torch.stft` plus a hand-built triangular mel filterbank — no torchaudio, no librosa. |
| `ctc_model.py` | `AcousticModel`: a strided Conv1d front end into a bidirectional GRU stack into a linear CTC head. `torch.nn.functional.ctc_loss` does the forward-backward recursion. |
| `ctc_decode.py` | Greedy decoding: argmax per frame, collapse repeats, drop blanks. |
| `metrics.py` | Word and character error rate (edit distance over the reference length), checked against jiwer's published edge cases. |
| `dataset.py` | A `manifest.jsonl` (`{"audio": path, "text": transcript}`) to padded CTC batches. Reads 16-bit PCM WAV with the standard library's `wave` module only. |
| `synthetic.py` | A handful of synthetic tone-plus-label utterances and their manifest — what the smoke test trains on. No download, no microphone. |
| `checkpoint.py` | Save/load an `AcousticModel`, `weights_only=True`, with an alphabet-consistency check — the same shape and the same safety property as `locallm/checkpoint.py`'s GPT loader. |
| `download_librispeech.py`, `download_ljspeech.py` | Stdlib-only downloaders. Run these **on the lab workstation**, not the desktop (see "where this runs"). |
| `prepare_manifest.py` | A downloaded corpus to `manifest.jsonl`: converts LibriSpeech's FLAC to 16-bit PCM WAV once (via `ffmpeg`, the one external tool this whole track needs, and only on the lab); LJSpeech needs no conversion. |
| `audio_io.py` | Microphone in, speaker out. Optional dependency (`sounddevice`), imported lazily. |
| `chat_bridge.py` | Wires a Mic button onto an existing `ChatPane` **by composition, with zero edits to `chat_pane.py`** — see "hearing and speaking in the Tk app". |

Every module above is tested: `test_speech_text.py`, `test_speech_metrics.py`,
`test_speech_audio_features.py`, `test_speech_ctc.py`, `test_speech_ctc_decode.py`,
`test_speech_dataset.py`, `test_speech_checkpoint.py`, `test_speech_audio_io.py`,
`test_speech_download.py`, `test_speech_prepare_manifest.py` — 95 cases, CPU only,
under 8 seconds total (nearly all of it the smoke test below), no network and
no audio hardware required for any of them.

## Automatic speech recognition: the design

**CTC, not attention, and not Whisper's architecture.** The task this
project is closest to in spirit — a small model, trained from random
weights, on a machine you own — is answered by Connectionist Temporal
Classification (Graves et al., ICML 2006; the worked explanation this
project read is Hannun, "Sequence Modeling With CTC", distill.pub/2017/ctc,
fetched 2026-09-27): a blank symbol plus a collapse rule (merge repeats, drop
blanks) removes the need for a frame-to-character alignment, and inference is
one forward pass plus a cheap decode, not autoregressive generation. Whisper
(Radford et al., "Robust Speech Recognition via Large-Scale Weak
Supervision", arXiv:2212.04356, fetched 2026-09-27) is a sequence-to-sequence
encoder-decoder trained on 680,000 hours; even its smallest "tiny" release
(39M parameters) assumes data at a scale nobody trains from scratch on one
machine. It is cited here only as the scale reference the operator asked
for, never as an architecture to copy.

**The template: Deep Speech 2's shape, at a fraction of its size.** Deep
Speech 2 (Amodei et al., arXiv:1512.02595, fetched 2026-09-27) established
the recipe every small CTC acoustic model since has followed: a strided
convolutional front end (cuts the frame rate the way a stride-2 pooling
layer would) feeding bidirectional recurrent layers into a linear CTC head.
`ctc_model.py`'s `AcousticModel` is exactly that shape — one `Conv1d`
(stride 2), a `GRU` stack (2 layers, bidirectional), a linear head — sized
in the thousands to low millions of parameters depending on preset, not Deep
Speech 2's cluster scale.

**Features: log-mel, not MFCCs.** `audio_features.py` frames the waveform,
takes the power spectrum, applies a triangular mel filterbank (the standard
recipe: practicalcryptography.com's MFCC tutorial, fetched 2026-09-27) and
stops at the log — no DCT, no liftering. A neural acoustic model reads the
(correlated) filterbank energies directly; the DCT step of classic MFCCs
exists to decorrelate features for an HMM/GMM's diagonal covariance
assumption, which a neural network does not need.

**Decoding: greedy today, a documented gap.** `ctc_decode.py` takes the
per-frame argmax and collapses it. This is the cheapest decoder CTC admits
and enough to know whether the model has learned anything at all. Beam
search with a language model over the same collapse rule is standard
practice for a real deployment and is *not implemented* — noted here so it
reads as a known gap, not an oversight.

## The data plan

| Corpus | License | Size | For |
|---|---|---|---|
| [LibriSpeech](https://www.openslr.org/12) (Panayotov, Chen, Povey & Khudanpur, ICASSP 2015) | CC BY 4.0 | dev-clean 337 MB … train-clean-100 6.3 GB … train-other-500 30 GB | ASR |
| [LJSpeech](https://keithito.com/LJ-Speech-Dataset/) 1.1 | Public domain | 2.6 GB (13,100 clips, ~24h, single speaker) | TTS (design only, not yet trained) |

Both were confirmed directly (fetched 2026-09-27): LibriSpeech's license and
every split's official MD5 come straight from
`openslr.org/resources/12/md5sum.txt`, baked into `download_librispeech.py`
so a corrupted or partial download is refused rather than trained on.
LJSpeech publishes no checksum, so `download_ljspeech.py` verifies the two
facts the dataset page does publish instead: exactly 13,100 rows in
`metadata.csv`, and one `.wav` per row.

**Budget: 80 GB total, enforced before a byte downloads.** Every downloader
sums what is already under the shared `locallm/corpora/speech/` root
(already covered by the existing `.gitignore` rule for `locallm/corpora/`)
and refuses a split that would cross 80 GB, rather than filling a disk
partway through a multi-hour transfer. `--budget-gb` raises it deliberately.

**Where this runs.** Both downloaders and `prepare_manifest.py` are stdlib
(plus, for LibriSpeech's FLAC-to-WAV step, one `ffmpeg` subprocess call) —
disk and network work, not GPU work, so it runs **on the lab workstation**
(`ssh` per the operator's lab config; `git pull --ff-only` first), the same
split this project already draws between CPU/disk-heavy pipeline work and
the desktop's one shared GPU. Nothing in this track downloaded anything
during this session: the scripts are written and unit-tested against
synthetic fixtures (`test_speech_download.py`, `test_speech_prepare_manifest.py`),
never against the real network, so a real download is the next session's
first step on the lab, not a claim made here.

## What to train, in what order

1. **Done, this session: the CPU smoke test.** `test_speech_ctc.py`'s
   `SmokeTestOverfitsAHandfulOfUtterances` — a ~141k-parameter preset
   overfitting 6 synthetic utterances. This is a floor, not a claim about
   real speech (`synthetic.py`'s docstring says so plainly): it exists to
   catch a broken pipeline — a wrong CTC alignment, a decoder that never
   collapses, a feature extractor that washes every utterance to the same
   features — before any real corpus or GPU time is spent on it. Predicted
   in `PREDICT-speech-ctc-smoke-2026-09-27.md`, measured in
   `FINDINGS-speech-ctc-smoke-2026-09-27.md`.
2. **Next: LibriSpeech `dev-clean` (337 MB), on the lab, then a short GPU
   fit on the desktop.** The smallest real split, chosen so a mistake in
   `prepare_manifest.py`'s FLAC handling or in the model's sizing against
   real (not synthetic) utterance lengths is found on a corpus small enough
   to redo the same day. This is a real accuracy measurement — a WER number
   this project has actually produced — not a synthetic-data smoke test, and
   it needs its own preregistered prediction before it runs, per the same
   rule as everything else in this repository. It does not fit inside a
   30-minute, under-5-GB GPU smoke slot; it is the first speech run that
   needs a dedicated, scheduled GPU session, planned but not claimed here.
3. **Then: `train-clean-100` (6.3 GB), full training on the desktop's RTX
   4080.** The first split large enough that a from-scratch CTC model's word
   error rate is a real, citable number rather than a proof of life.
4. **Only if the `train-clean-100` number says data is the limit:**
   `train-clean-360` or `train-other-500`. This project's own headline
   lesson so far is that data, not architecture, has been the limiting
   factor for its text model (`AMBITION.md` section 3: "capacity is already
   measured to 875M … the data to justify it is the missing half"); the same
   question — does more data or a bigger model move the number — is worth
   asking here too, measured rather than assumed, before spending the disk
   budget on 30 more gigabytes.
5. **A stronger architecture, only once data stops being the bottleneck:**
   Conformer (Gulati et al., arXiv:2005.08100, fetched 2026-09-27) reports
   2.7%/6.3% WER on LibriSpeech test/test-other from a **10M-parameter**
   variant — almost exactly this project's own 10.9M point on the parameter
   curve `AMBITION.md` section 3 already measures its text model on, which
   makes a Conformer-sized upgrade a natural next rung on the same ladder,
   not a new one. Not attempted until step 3 or 4 shows the current
   architecture, not the data, is the ceiling.
6. **Text to speech, after ASR has a real (non-synthetic) measurement.**
   Design below; `AMBITION.md`'s ordering ("trustworthy core first and
   breadth after") is why this project's second speech direction waits for
   the first one's floor to be real.

## Text to speech: design only, not yet built

**Tacotron 2's shape** (Shen et al., "Natural TTS Synthesis by Conditioning
WaveNet on Mel Spectrogram Predictions", arXiv:1712.05884, fetched
2026-09-27): a sequence-to-sequence network maps characters to a mel
spectrogram, then a vocoder turns the spectrogram into a waveform. LJSpeech
is the standard corpus for exactly this pairing — its own dataset page
points at `github.com/keithito/tacotron` as example training code, confirmed
by reading that repository's README (fetched 2026-09-27), which also
confirms the on-disk shape `prepare_manifest.py`'s LJSpeech path already
matches: `LJSpeech-1.1/metadata.csv` beside `wavs/`.

**Staged, because a learned vocoder is not a smoke test.** The first
checkpoint worth measuring predicts mel spectrograms and reconstructs audio
with Griffin-Lim (a fixed, non-learned phase-reconstruction algorithm) —
worse-sounding than a learned vocoder, but a real, immediate MOS-free sanity
check (does the predicted spectrogram look like the target spectrogram at
all) that needs no second model trained first. A learned vocoder (WaveNet in
the original paper; a lighter GAN-based vocoder such as HiFi-GAN is the more
current, faster-to-train choice for one RTX 4080) is the second stage, once
the mel predictor itself is measured.

**Not started because ASR is the track this session measured.** The task
this file answers to asked for the design, the data plan, and what to train
in what order — this section is that design. Building it is future work,
sequenced above as "text to speech, after ASR has a real measurement."

## Metrics

**Word error rate (WER) and character error rate (CER)**, both edit distance
over the reference length (`metrics.py`). Checked against jiwer's own
published edge cases (Apache-2.0; fetched 2026-09-27) rather than assumed:
an empty reference does not divide by zero, it floors the denominator at 1,
so `wer("", "silence") == 1` and `wer("", "peaceful silence") == 2` — an
"error rate" that can exceed 1 when the reference is empty and the model
hallucinates words, by construction. `test_speech_metrics.py` reproduces
jiwer's exact documented numbers.

**No number in this file is a WER on real speech.** The only measurement
made this session is the synthetic smoke test's own WER/CER (both driven to
zero by construction — see `FINDINGS-speech-ctc-smoke-2026-09-27.md`), which
is a pipeline-correctness check, not an accuracy claim. The first accuracy
claim this project is entitled to make is LibriSpeech `dev-clean` WER, once
run.

## Hearing and speaking in the Tk app

**The plan.** A "Mic" button beside Send/Stop in the chat card: press it,
`audio_io.record()` captures a few seconds through `sounddevice` (MIT,
PortAudio bindings, chosen over PyAudio for needing no C-extension build
step of its own; fetched 2026-09-27), the acoustic model transcribes it, the
text lands in the same entry box a typed message would — the person still
presses Send, so nothing reaches the model on its own initiative. Speaking
back is the mirror image: a trained TTS checkpoint's waveform plays through
`audio_io.play()`.

**Optional and lazy, like every other soft dependency this project already
has.** `audio_io.py` never imports `sounddevice` at module scope, only
inside `record()`/`play()`, exactly like `home.py`'s `tkinterdnd2`
(drag-and-drop) and `ingest.py`'s `charset_normalizer` (encoding detection):
importing `locallm.speech` — or running the whole app — never requires
audio hardware or an audio library to be present. `microphone_available()`
lets a caller grey out the button instead of letting a click fail.

**Built this session, wired by composition, not by editing `chat_pane.py`.**
`chat_bridge.py`'s `attach_mic_button(pane, ...)` reaches an already-built
`ChatPane` through the attributes it already exposes to `home.py`
(`pane.b_send`, `pane.entry`, `pane.C`, `pane.on_status`) and grids one more
button beside the ones `ChatPane._build` already created, using that same
file's own button-wrapper class rather than importing it directly. **Zero
lines of `chat_pane.py` changed.** Nothing calls `attach_mic_button` yet —
it is one call away, documented in that module's own docstring, for whenever
a speech checkpoint exists that is worth shipping in the app. Until then, a
click reports "no trained speech checkpoint yet" through the pane's own
status callback rather than pretending to transcribe with a model that does
not exist.

**Permissions.** Recording is a tool call like any other under
`DAWNR-HARNESS.md`'s allow/ask/deny policy (section 7): this track adds the
mechanism, not a standing grant. dawnr does not grant itself microphone
access any more than it grants itself shell access — the same sentence
`AMBITION.md`'s "dawnr grows with the person using it" table uses for acting
on the machine at all.

## Open questions, stated plainly

- **Real WER is unmeasured.** Everything numeric in this file about
  LibriSpeech-scale accuracy (the Conformer comparison point) is someone
  else's published result, cited for scale, not this project's own.
- **The held-out boundary for speech has no enforcement code yet**, because
  there is no training run to enforce it against yet. It is a commitment
  here, to be turned into a gate (mirroring `t/loop_filter.py`'s role for
  the text side) before `dev-clean`/`test-clean` are ever at risk of
  entering a training manifest.
- **Beam search and a language model over the CTC output** are standard
  practice this design defers; greedy decoding is enough to know whether
  the model has learned anything, not enough for a competitive WER.
- **The vocoder for TTS** (Griffin-Lim first, a learned vocoder second) is a
  design choice, not a measured comparison — nobody has trained either one
  here yet.
