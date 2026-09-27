"""chat_bridge.py — wire a Mic button onto an existing ChatPane, by composition.

Zero edits to ``chat_pane.py``: this reaches an already-built ``ChatPane``
instance the exact way ``home.py`` already does (``pane.b_send``,
``pane.entry``, ``pane.C``, ``pane.on_status`` are attributes ``chat_pane.py``
sets and other code reads) and grids one more sibling button beside the ones
``ChatPane._build`` already created, using that same file's own ``_Button``
helper class -- found on ``pane.b_send`` rather than imported directly, so
this keeps working even if that wrapper moves. Several tracks touch
``chat_pane.py`` in this repository at once; this is the one that does not
need to.

Nothing calls ``attach_mic_button`` yet -- it is a plain function, not a
side effect of importing this module. The one-line integration point,
whenever a speech checkpoint worth shipping exists, is right after building
a ``ChatPane``:

    from speech.chat_bridge import attach_mic_button
    self.chat = ChatPane(parent, palette, q, checkpoint_dir, on_status)
    attach_mic_button(self.chat, speech_checkpoint=SPEECH_CHECKPOINT_DIR)

See ``DAWNR-SPEECH.md``, "hearing and speaking in the Tk app", for the plan
this is one piece of.
"""
from __future__ import annotations

from pathlib import Path

import look

from . import audio_io
from .audio_features import FeatureConfig, log_mel_spectrogram
from .ctc_decode import decode_text

NO_MIC = look.Say(look.NOT_APPLICABLE, "No microphone",
                  "No input device was found for sounddevice to record from.", "unsettled")
NO_MODEL = look.Say(look.NOT_APPLICABLE, "No speech model yet",
                    "No trained speech checkpoint was given. See DAWNR-SPEECH.md "
                    "for the training plan.", "unsettled")


def _transcribe_one(checkpoint_path: str | Path, waveform, sample_rate: int) -> str:
    import torch  # noqa: PLC0415 — only needed once a checkpoint is actually used

    from . import checkpoint as speech_checkpoint  # noqa: PLC0415
    model, vocab, config = speech_checkpoint.load_checkpoint(checkpoint_path)
    features = log_mel_spectrogram(waveform, FeatureConfig(sample_rate=sample_rate,
                                                          n_mels=config.n_mels))
    log_probs, out_lengths, _ = model(features.unsqueeze(0),
                                      torch.tensor([features.size(0)]))
    return decode_text(log_probs, out_lengths, vocab)[0]


def attach_mic_button(pane, *, speech_checkpoint: str | Path | None = None,
                      seconds: float = 4.0, sample_rate: int = 16_000):
    """Add a "Mic" button to ``pane``'s existing input row.

    Clicking it records ``seconds`` of audio and, when ``speech_checkpoint``
    names a checkpoint ``speech.checkpoint.load_checkpoint`` can load,
    transcribes it and inserts the text into ``pane.entry`` exactly as if it
    had been typed (the user still presses Send; nothing is sent on the
    model's own initiative). With no microphone or no checkpoint, or on any
    error, it reports a plain sentence through ``pane.on_status`` -- the same
    callback ``chat_pane.py`` already uses for every other "nothing to show
    yet" state -- rather than failing silently or crashing the window.

    Returns the created button.
    """
    row = pane.b_send.master
    button_cls = type(pane.b_send)

    def on_click():
        if not audio_io.microphone_available():
            pane.on_status(NO_MIC)
            return
        if speech_checkpoint is None:
            pane.on_status(NO_MODEL)
            return
        try:
            waveform = audio_io.record(seconds, sample_rate)
            text = _transcribe_one(speech_checkpoint, waveform, sample_rate)
        except Exception as e:                                        # noqa: BLE001
            pane.on_status(look.Say(look.REFUTED, "Could not transcribe",
                                    f"{type(e).__name__}: {e}", "refuted"))
            return
        pane.entry.delete(0, "end")
        pane.entry.insert(0, text)

    button = button_cls(row, pane.C, "Mic", on_click)
    button.grid(row=0, column=4, padx=(look.SPACE.item, 0))
    return button
