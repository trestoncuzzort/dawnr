"""pane.py: the few calls the chat window makes into per-person learning, and nothing else.

chat_pane.py keeps its hooks to one line each (DAWNR-LEARNING.md lists them);
everything they need is here: whether learning is on for this machine's user
and under which name, recording each reply, the Good / Not this / Correct...
buttons, a "that's wrong" turn, and putting the person's adapter on the model
when it is loaded.

Learning is off until the person turns it on (settings.json in the people
folder, which the window's settings dialog writes): nothing is remembered about
anyone who did not ask for it, and every step says in a sentence what was kept.
Standard library only, except attach_adapter(), which needs torch and is only
called once a real model is loaded.
"""
from __future__ import annotations

import json
from pathlib import Path

from .feedback import Recorder, final_program, parts_of, person_id

SETTINGS = "settings.json"
DEFAULT_PERSON = "me"


class PaneLearning:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.recorder: Recorder | None = None
        self.model_identity: dict | None = None
        self.attached_for: str | None = None        # whose adapter state the model is in (None: learning off)

    # ----------------------------------------------------------- settings --
    def settings(self) -> dict:
        path = self.root / SETTINGS
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError):
            data = {}
        return {"enabled": bool(data.get("enabled", False)), "person": str(data.get("person") or DEFAULT_PERSON)}

    def save_settings(self, enabled: bool, person: str) -> str:
        pid = person_id(person or DEFAULT_PERSON)
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / (SETTINGS + ".tmp")
        tmp.write_text(json.dumps({"enabled": bool(enabled), "person": pid}, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.root / SETTINGS)
        self.recorder = None
        return (f"Learning from {pid}'s feedback is on; it is kept in {self.root / pid} and nowhere else."
                if enabled else "Learning is off: nothing new is remembered.")

    def enabled(self) -> bool:
        return self.settings()["enabled"]

    def _recorder(self) -> Recorder | None:
        if not self.enabled():
            return None
        if self.recorder is None:
            self.recorder = Recorder(self.settings()["person"], self.root, model=self.model_identity or {})
        return self.recorder

    # -------------------------------------------------------------- hooks --
    def sync(self, model, checkpoint_dir: Path) -> str | None:
        """Before every reply: make the model carry exactly what the settings say, and say so when it changes.

        Learning on for a person: that person's fresh adapter is attached (or none,
        if there is none yet), and replies are recorded for them. Learning off, or
        another name: the previous person's adapter comes off first. Replies are
        recorded only once the base is identified (an answer is kept with the
        weights that wrote it), so a window whose model cannot be identified
        records nothing rather than something unattributed."""
        settings = self.settings()
        want = settings["person"] if settings["enabled"] else None
        if want == self.attached_for:
            return None
        self.recorder, self.model_identity, self.attached_for = None, None, None
        try:
            from model import has_lora, remove_lora
            if has_lora(model):
                remove_lora(model)
        except Exception:                                        # noqa: BLE001  (a stand-in model has no adapter)
            pass
        if want is None:
            return "Learning is off: no adapter is in use and nothing new is remembered."
        try:
            from . import adapters
            identity = adapters.base_identity(checkpoint_dir)
            rec = self._recorder()
            rec.model = dict(identity)
            status = adapters.attach(model, rec.store, identity)
        except Exception as e:                                   # noqa: BLE001  (said, never silent)
            return f"Learning is on, but this model could not be identified, so nothing is recorded: {e}"
        self.model_identity, self.attached_for = identity, want
        said = adapters.describe(status)
        try:                                                     # the profile is refreshed once per window session
            from . import style_profile as PR
            prof = PR.refresh(rec.store)
            if PR.effective(prof):
                said += " Your style: " + "; ".join(line for line in PR.describe(prof)
                                                    if not line.endswith("not known yet")) + "."
        except Exception as e:                                   # noqa: BLE001  (said, never silent)
            said += f" (Your style profile could not be read: {e}.)"
        return said

    def in_style(self, messages: list[dict]) -> str | None:
        """Put the last answer in the person's style (their profile, style_profile.py) when that changes it.

        The conversation's last message is replaced by the rewritten answer, so
        what is recorded, rated and continued from is what the person saw; the
        rewritten program is returned for the window to show, or None when the
        profile is empty, learning is off, or nothing changes. A rewrite the t
        tool fails where the original passed is never used (style_profile.apply)."""
        rec = self._recorder() if self.model_identity is not None else None
        if rec is None or len(messages) < 2 or messages[-1].get("role") != "assistant":
            return None
        from . import style_profile as PR
        from .feedback import content_text
        prof = PR.load(rec.store.dir)
        if not PR.effective(prof):
            return None
        user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        styled = PR.apply(prof, messages[-1]["content"], user if isinstance(user, str) else "")
        if content_text(styled) == content_text(messages[-1]["content"]):
            return None
        messages[-1] = {"role": "assistant", "content": styled}
        return final_program(styled)

    def user_turn(self, text: str) -> str | None:
        rec = self._recorder() if self.model_identity is not None else None
        return rec.user_turn(text) if rec is not None else None

    def replied(self, messages: list[dict]) -> None:
        rec = self._recorder() if self.model_identity is not None else None
        if rec is not None:
            rec.answered(messages)

    def thumbs(self, up: bool) -> str:
        rec = self._recorder() if self.model_identity is not None else None
        return rec.thumbs(up) if rec is not None else self.off_sentence()

    def correct(self, text: str) -> str:
        rec = self._recorder() if self.model_identity is not None else None
        return rec.edit_program(text) if rec is not None else self.off_sentence()

    def last_answer_text(self) -> str:
        """What the Correct... dialog starts from: the last answer's program, else its text."""
        rec = self._recorder() if self.model_identity is not None else None
        if rec is None or rec.last_id is None:
            return ""
        answer = rec.store.get(rec.last_id)["answer"]
        program = final_program(answer)
        if program:
            return program
        return "".join(p.get("text", "") for p in parts_of(answer) if p.get("type") == "text")

    def off_sentence(self) -> str:
        if self.enabled():
            return "There is no answer from this model to rate yet."
        return "Learning is off. Turn it on in Settings to have dawnr learn from your feedback."
