# Hearing with pretrained weights: registered 2026-10-01 10:54Z

## What this is

`AMBITION.md`'s row "to hear and speak" was started from scratch (a CTC recogniser that overfits a
handful of utterances, `DAWNR-SPEECH.md`). The plan of record (`internal/LADDER-PLAN-2026-10-01.md`)
takes it to pretrained recognisers and voices with permissive licences, measured by word error rate
on a public test set, offline. This is the hearing half.

## What it stands on

- Whisper (Radford et al., arXiv:2212.04356, the paper's text read 2026-10-01): appendix D.1.1,
  greedy decoding, LibriSpeech test-clean word error rate 5.6 for tiny.en and **4.2 for base.en**;
  D.1.2, beam search with temperature fallback, 5.4 and 4.1. The rate is computed after the
  paper's own text normaliser (`whisper/normalizers/english.py` in openai/whisper, fetched).
- whisper.cpp (github.com/ggml-org/whisper.cpp, MIT, README fetched): the C/C++ port that runs the
  same weights on a CPU with no Python and no network once the model file is on disk.
- LibriSpeech (openslr.org/12, CC BY 4.0): test-clean, 2,620 utterances, 5.4 hours.

## The measurement

- **Model**: Whisper base.en (74M parameters, MIT), the ggml file whisper.cpp's own download script
  fetches; greedy decoding with no temperature fallback; 8 threads of the lab's CPU at the lowest
  priority; nothing reaches the network while it transcribes.
- **Data**: every utterance of LibriSpeech test-clean, FLAC converted to 16 kHz 16-bit WAV with ffmpeg.
- **Score**: word error rate over the whole set (total edits over total reference words), both
  sides passed through Whisper's `EnglishTextNormalizer`.

## Predictions

65. The word error rate is between 3.7 and 4.7 (the paper's 4.2 for greedy, plus or minus half a
    point for the port and for this machine's arithmetic). Falsified outside.
66. It transcribes faster than real time by at least ten times on 8 threads (5.4 hours of audio
    in under 33 minutes). Falsified otherwise.

## Amendment, 2026-10-01 10:55Z, before any voice is downloaded: speaking

The same row asks for a voice. Seed-TTS's public evaluation (github.com/BytedanceSpeech/seed-tts-eval,
fetched; arXiv:2406.02430) scores synthesized English speech by an ASR model's word error rate on
it. Here:

- **Voice**: Piper (github.com/rhasspy/piper, MIT; the repository was archived in 2025 and its
  successor is GPL, so the last MIT release, 2023.11.14-2, is the one used) with the
  `en_US-ljspeech-medium` voice (trained on LJ Speech, public domain; its model card fetched).
- **Sentences**: the transcripts of the first 200 LibriSpeech test-clean utterances in sorted order.
- **Score**: Whisper base.en (the recogniser measured above, greedy) transcribes Piper's speech;
  word error rate against the sentences after Whisper's normaliser, beside the same recogniser's
  rate on the human recordings of the same 200 sentences.

67. Piper's speech is transcribed with a word error rate of at most 10%. Falsified above.
68. That rate is within 5 points of the recogniser's rate on the human recordings of the same
    sentences. Falsified otherwise.

## Outcome of the hearing half, 2026-10-01 11:19Z

Whisper base.en (148 MB ggml file, MIT) under whisper.cpp built from source on the lab, greedy with no
temperature fallback, 8 threads at the lowest priority beside other jobs, every one of LibriSpeech
test-clean's 2,620 utterances (16 kHz WAV converted with ffmpeg); scored after Whisper's own normaliser
(`locallm/speech/wer.py`):

| | utterances | reference words | word errors | word error rate |
|---|---:|---:|---:|---:|
| this machine | 2,620 | 53,027 | 2,193 | **4.14%** |
| the paper, greedy (arXiv:2212.04356, D.1.1) | 2,620 | | | 4.2% |

5.4 hours of audio took 1,204 seconds: 16 times faster than real time.

65. **Between 3.7% and 4.7%: holds.** 4.14%, within a tenth of the published figure.
66. **At least ten times faster than real time: holds.** Sixteen.

**Reading.** dawnr can hear: a recogniser with a permissive licence, running offline on a CPU,
reproduces its paper's accuracy on the standard test set here.
