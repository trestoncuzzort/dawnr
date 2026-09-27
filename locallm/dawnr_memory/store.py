"""store.py: one person's memory on disk -- a folder per person, a JSON file per record, owner-only.

Where it lives. The app's data folder, found by platformdirs' user_data_dir rule (github.com/tox-dev/platformdirs,
unix.py, macos.py and windows.py, read 2026-09-27; the XDG Base Directory Specification for Linux): $XDG_DATA_HOME
when it is an absolute path (the specification says a relative one is invalid and is ignored), else
~/.local/share, on Linux and other Unix; ~/Library/Application Support on macOS; %LOCALAPPDATA% on Windows (the
local, not the roaming, folder: a person's memory stays on this machine). Then dawnr/memory/<person>/.
DAWNR_DATA_DIR replaces the data folder, and the harness configuration's "memory": {"root": ...} names another
memory folder outright.

    <root>/<person>/settings.json               the person's switches: remember, recall
    <root>/<person>/episodes/e-<16 hex>.json    a dated summary of one session
    <root>/<person>/facts/f-<16 hex>.json       something true about the person, with the words that said so
    <root>/<person>/preferences/p-<16 hex>.json how they like things done, with the words that said so
    <root>/<person>/notes/n-<16 hex>.json       what the person pinned themselves

Why a file per record and not one database file: the person can read their memory with any text editor, and
forgetting a record removes the one file that held it -- no page of a database, journal or index is left holding
the text (SQLite, for one, keeps deleted rows in free pages unless secure_delete is on). What removing a file
cannot promise is said plainly in DAWNR-MEMORY.md: unlinking is not wiping the medium (GNU coreutils' shred
manual: journaling and copy-on-write file systems and SSD wear levelling keep old blocks).

Owner-only. Folders are made with mode 0o700 and files opened with 0o600, then set to exactly that (the umask can
only take bits away); a person's folders found looser are tightened, while a memory folder an operator pointed at
and dawnr did not make keeps its permissions (dawnr does not change a folder that is not its own). On Windows
os.chmod sets only the read-only flag, and os.mkdir honours 0o700 from Python 3.13
by giving the folder an access list for the current user and administrators (docs.python.org/3/library/os.html,
os.mkdir and os.chmod); on older Pythons the folder inherits the access list of %LOCALAPPDATA%, which is per-user.

Isolation. A MemoryStore is bound to one person when it is made, and every path it touches is built from that
person's validated id, a kind's fixed folder name and a record id matching a fixed pattern: nothing from a record,
a transcript or a caller's string becomes a path component unchecked. An id from another person's store names a
file that does not exist here; a symbolic link where a folder or a record should be is refused, not followed; a
folder that belongs to another account is refused.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import shutil
import stat
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
FORMAT = "dawnr-memory"
KINDS = ("episode", "fact", "preference", "note")
FOLDERS = {"episode": "episodes", "fact": "facts", "preference": "preferences", "note": "notes"}
PREFIX = {"episode": "e", "fact": "f", "preference": "p", "note": "n"}
_KIND_OF = {p: k for k, p in PREFIX.items()}
RECORD_ID = re.compile(r"([efpn])-[0-9a-f]{16}")
PERSON = re.compile(r"[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?")
SESSION = re.compile(r"[A-Za-z0-9_.-]{1,64}")
# device names Windows reserves in every folder: a person called "con" would be a folder nobody can open there
RESERVED = frozenset({"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(10)} | {f"lpt{i}" for i in range(10)})
MAX_TEXT = {"episode": 600, "fact": 200, "preference": 200, "note": 2000}
MAX_EVIDENCE = 300
MAX_SESSIONS = 20                 # sessions listed on one fact; the oldest drop off
MAX_FILE = 64 * 1024              # a record file bigger than this was not written by dawnr and is not read
DIR_MODE, FILE_MODE = 0o700, 0o600
TMP = ".tmp-"
STALE_TMP = 3600.0                # a temporary file this old is left over from a crash and is removed
SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {"remember": True, "recall": True}
ORIGINS = ("rules", "model", "person")
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
FIELDS = {"slot", "evidence", "source_session", "sessions", "last_seen", "seen", "session", "date", "turns",
          "tools", "check", "tainted"}


class StoreError(Exception):
    """The memory folder is not safe to use as it is (a link, another owner's, not a folder); nothing was read."""


# ------------------------------------------------------------------- time --

def fmt_time(epoch: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, timezone.utc).strftime(TIME_FORMAT)


def parse_time(text) -> float | None:
    try:
        return datetime.strptime(str(text), TIME_FORMAT).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


# ------------------------------------------------------------------- text --

def clean_text(text, limit: int) -> str:
    """One line of printable text, at most `limit` characters.

    Whitespace runs (line breaks included) become one space, then control, format (zero-width, bidirectional
    overrides), surrogate and private-use characters are dropped: a record cannot carry a line break, a hidden
    character or a reordering of the text into the span dawnr reads it from."""
    text = re.sub(r"\s+", " ", str(text or ""))
    text = "".join(c for c in text if unicodedata.category(c) not in ("Cc", "Cf", "Cs", "Co"))
    text = text.strip()
    return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


# ----------------------------------------------------------------- places --

def normalize_person(person) -> str:
    """A person id as stored: lowercase (so "Ann" and "ann" are one folder on every file system), validated."""
    p = str(person if person is not None else "").strip().lower()
    if not PERSON.fullmatch(p) or p in RESERVED:
        raise ValueError(f"a person id is 1 to 64 of a-z, 0-9, '_' and '-', starting and ending with a letter or "
                         f"digit, and not a name Windows reserves (con, nul, com1, ...); got {person!r}")
    return p


def data_root(env=None, platform: str | None = None, home: str | Path | None = None) -> Path:
    """The app's data folder: DAWNR_DATA_DIR, else the platform's per-user data folder, then dawnr."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    override = env.get("DAWNR_DATA_DIR", "")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise StoreError(f"DAWNR_DATA_DIR must be an absolute path, not {override!r}")
        return path
    home = Path(home) if home is not None else Path.home()
    if platform == "win32":
        local = env.get("LOCALAPPDATA", "")
        base = Path(local) if local else home / "AppData" / "Local"
    elif platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        xdg = env.get("XDG_DATA_HOME", "")
        base = Path(xdg) if xdg and os.path.isabs(xdg) else home / ".local" / "share"
    return base / "dawnr"


def memory_root(env=None, platform: str | None = None, home: str | Path | None = None) -> Path:
    return data_root(env, platform, home) / "memory"


def _private_dir(path: Path, tighten: bool = True) -> None:
    """Make `path` an owner-only folder, or refuse a link, a file or another account's folder in its place.

    An existing folder is tightened to owner-only when `tighten` is set (a person's folder and its kind folders,
    which are dawnr's by name); the memory root is tightened only if dawnr made it, so a root an operator points
    at an existing folder of theirs keeps its permissions (the person folders inside it are owner-only anyway)."""
    try:
        os.mkdir(path, DIR_MODE)
        made = True
    except FileExistsError:
        made = False
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode):
        raise StoreError(f"{path} is a symbolic link; dawnr's memory never follows one")
    if not stat.S_ISDIR(st.st_mode):
        raise StoreError(f"{path} is not a folder")
    if os.name == "posix":
        if st.st_uid != os.getuid():
            raise StoreError(f"{path} belongs to another account")
        if (made or tighten) and stat.S_IMODE(st.st_mode) != DIR_MODE:
            os.chmod(path, DIR_MODE)


def _fsync_dir(folder: Path) -> None:
    """Make a rename or an unlink in `folder` durable (POSIX; Windows has no directory handle to sync)."""
    if os.name != "posix":
        return
    try:
        fd = os.open(folder, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_owner_only(path: Path, payload: bytes, tag: str) -> None:
    """Write `payload` to `path` atomically: an owner-only temporary file, synced, then renamed over it."""
    folder = path.parent
    tmp = folder / f"{TMP}{tag}-{secrets.token_hex(4)}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(tmp, flags, FILE_MODE)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        if os.name == "posix":
            os.chmod(tmp, FILE_MODE)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    _fsync_dir(folder)


def _read_file(path: Path) -> bytes | None:
    """The bytes of `path` (at most MAX_FILE + 1 of them), None if it is missing; a link is refused (OSError)."""
    if os.path.islink(path):
        raise OSError(f"{path.name} is a symbolic link")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as f:
        return f.read(MAX_FILE + 1)


def _problem(record, kind: str, record_id: str) -> str:
    """Why a record read from disk cannot be used, or ""."""
    if not isinstance(record, dict):
        return "not a JSON object"
    if record.get("schema") != SCHEMA:
        return f"schema {record.get('schema')!r}, not {SCHEMA}"
    if record.get("id") != record_id:
        return "its id is not its file name"
    if record.get("kind") != kind:
        return "its kind is not its folder"
    if not isinstance(record.get("text"), str) or not record["text"].strip():
        return "it has no text"
    return ""


class MemoryStore:
    """One person's memory. Bound to that person when made; nothing it does reads or writes outside their folder."""

    def __init__(self, root: str | Path, person: str):
        self.person = normalize_person(person)
        root = Path(root).expanduser()
        self.root = root if root.is_absolute() else Path.cwd() / root
        self.dir = self.root / self.person
        self.problems: list[str] = []            # records skipped when reading, with why
        self._ensure()
        self._sweep()

    # ------------------------------------------------------------ places --

    def _ensure(self) -> None:
        self.root.parent.mkdir(parents=True, exist_ok=True)
        _private_dir(self.root, tighten=False)
        _private_dir(self.dir)
        for folder in FOLDERS.values():
            _private_dir(self.dir / folder)

    def _folder(self, kind: str) -> Path:
        folder = self.dir / FOLDERS[kind]
        st = os.lstat(folder)
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            raise StoreError(f"{folder} is not a plain folder; dawnr's memory never follows a link")
        return folder

    def path_of(self, record_id) -> Path | None:
        """Where a record of this person lives, or None for an id that is not one (nothing is looked up)."""
        m = RECORD_ID.fullmatch(str(record_id or ""))
        if not m:
            return None
        return self.dir / FOLDERS[_KIND_OF[m.group(1)]] / f"{record_id}.json"

    def _sweep(self, now: float | None = None) -> None:
        """Remove temporary files a crash left behind (they can hold a record's text)."""
        now = time.time() if now is None else now
        for folder in [self.dir] + [self.dir / f for f in FOLDERS.values()]:
            with contextlib.suppress(OSError):
                for entry in os.scandir(folder):
                    if entry.name.startswith(TMP) and now - entry.stat(follow_symlinks=False).st_mtime > STALE_TMP:
                        with contextlib.suppress(OSError):
                            os.unlink(entry.path)

    def _drop_tmp(self, folder: Path, record_id: str) -> None:
        with contextlib.suppress(OSError):
            for entry in os.scandir(folder):
                if entry.name.startswith(f"{TMP}{record_id}-"):
                    with contextlib.suppress(OSError):
                        os.unlink(entry.path)

    # ------------------------------------------------------------- reads --

    def records(self, kinds=KINDS) -> list[dict]:
        """Every readable record of these kinds, newest first; unreadable files are skipped and named in problems."""
        out = []
        if not os.path.lexists(self.dir):
            return out
        for kind in kinds:
            try:
                folder = self._folder(kind)
            except FileNotFoundError:
                continue
            for entry in sorted(os.scandir(folder), key=lambda e: e.name):
                name = entry.name
                if name.startswith(TMP):
                    continue
                record_id = name[:-5] if name.endswith(".json") else ""
                m = RECORD_ID.fullmatch(record_id)
                if not m or _KIND_OF[m.group(1)] != kind:
                    self.problems.append(f"{FOLDERS[kind]}/{name}: not a record file name")
                    continue
                try:
                    raw = _read_file(Path(entry.path))
                except OSError as e:
                    self.problems.append(f"{FOLDERS[kind]}/{name}: not read: {e}")
                    continue
                if raw is None:
                    continue
                if len(raw) > MAX_FILE:
                    self.problems.append(f"{FOLDERS[kind]}/{name}: over {MAX_FILE} bytes")
                    continue
                try:
                    record = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, ValueError) as e:
                    self.problems.append(f"{FOLDERS[kind]}/{name}: not JSON: {e}")
                    continue
                why = _problem(record, kind, record_id)
                if why:
                    self.problems.append(f"{FOLDERS[kind]}/{name}: {why}")
                    continue
                out.append(record)
        out.sort(key=lambda r: (str(r.get("updated") or r.get("created") or ""), r["id"]), reverse=True)
        return out

    def get(self, record_id) -> dict | None:
        """One record of this person by id, or None (an id of another person's names nothing here)."""
        path = self.path_of(record_id)
        if path is None or not os.path.lexists(self.dir):
            return None
        kind = _KIND_OF[str(record_id)[0]]
        try:
            self._folder(kind)
            raw = _read_file(path)
        except FileNotFoundError:
            return None
        except OSError as e:
            raise StoreError(f"{record_id}: not read: {e}") from None
        if raw is None or len(raw) > MAX_FILE:
            return None
        try:
            record = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        return None if _problem(record, kind, str(record_id)) else record

    def settings(self) -> dict:
        path = self.dir / SETTINGS_FILE
        try:
            raw = _read_file(path)
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (OSError, UnicodeDecodeError, ValueError):
            data = {}
        out = dict(DEFAULT_SETTINGS)
        if isinstance(data, dict):
            out.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS and isinstance(v, bool)})
        return out

    def export(self) -> dict:
        """Everything remembered about this person, as one JSON object (GDPR article 20's "structured, commonly
        used and machine-readable format")."""
        return {"format": FORMAT, "schema": SCHEMA, "person": self.person, "exported": fmt_time(),
                "settings": self.settings(), "records": self.records()}

    # ------------------------------------------------------------ writes --

    def put(self, record: dict) -> dict:
        """Write one record (validated) under its id, replacing what that id held."""
        record_id = str(record.get("id"))
        path = self.path_of(record_id)
        if path is None:
            raise ValueError(f"not a record id: {record_id!r}")
        kind = _KIND_OF[record_id[0]]
        why = _problem(record, kind, record_id)
        if why:
            raise ValueError(f"record {record_id}: {why}")
        if len(record["text"]) > MAX_TEXT[kind]:
            raise ValueError(f"record {record_id}: the text is over {MAX_TEXT[kind]} characters")
        payload = (json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")
        if len(payload) > MAX_FILE:
            raise ValueError(f"record {record_id} is over {MAX_FILE} bytes")
        self._ensure()
        write_owner_only(path, payload, record_id)
        return record

    def add(self, kind: str, text: str, *, origin: str = "person", confidence: float = 1.0,
            now: float | None = None, **fields) -> dict:
        """A new record of `kind`; `fields` are the kind's own (slot, evidence, source_session, session, ...)."""
        if kind not in KINDS:
            raise ValueError(f"kind {kind!r} is not one of {KINDS}")
        if origin not in ORIGINS:
            raise ValueError(f"origin {origin!r} is not one of {ORIGINS}")
        unknown = set(fields) - FIELDS
        if unknown:
            raise ValueError(f"unknown record fields: {', '.join(sorted(unknown))}")
        text = clean_text(text, MAX_TEXT[kind])
        if not text:
            raise ValueError("a record needs some text")
        stamp = fmt_time(now)
        self._ensure()
        folder = self._folder(kind)
        while True:
            record_id = f"{PREFIX[kind]}-{secrets.token_hex(8)}"
            if not os.path.lexists(folder / f"{record_id}.json"):
                break
        record = {"schema": SCHEMA, "id": record_id, "kind": kind, "text": text, "origin": origin,
                  "confidence": round(min(1.0, max(0.0, float(confidence))), 3), "created": stamp, "updated": stamp}
        if kind in ("fact", "preference"):
            session = fields.get("source_session")
            record.update(slot=clean_text(fields.get("slot") or "", 80).lower() or None,
                          evidence=clean_text(fields.get("evidence", ""), MAX_EVIDENCE),
                          source_session=session,
                          sessions=list(fields.get("sessions") or ([session] if session else [])),
                          last_seen=stamp, seen=int(fields.get("seen", 1)))
        else:
            record.update({k: v for k, v in fields.items() if k in FIELDS})
        return self.put(record)

    def pin(self, text: str, now: float | None = None) -> dict:
        """A note the person writes themselves: always recalled first, never changed by extraction."""
        return self.add("note", text, origin="person", confidence=1.0, now=now)

    def correct(self, record_id, text: str, now: float | None = None) -> dict:
        """The person's own wording replaces the record's. The words that established a fact go with the old
        text (what was corrected away is not kept), and so does its tie to the session it came from: it is the
        person's record now, and forgetting that session does not take it."""
        record = self.get(record_id)
        if record is None:
            raise KeyError(f"no record {record_id!r} for {self.person}")
        kind = record["kind"]
        new = clean_text(text, MAX_TEXT[kind])
        if not new:
            raise ValueError("a correction needs some text")
        stamp = fmt_time(now)
        record.update(text=new, origin="person", confidence=1.0, updated=stamp)
        if kind in ("fact", "preference"):
            record.update(evidence=f"corrected by the person on {stamp[:10]}", last_seen=stamp, source_session=None,
                          sessions=[])
        return self.put(record)

    def set_settings(self, **changes) -> dict:
        unknown = set(changes) - set(DEFAULT_SETTINGS)
        if unknown:
            raise ValueError(f"unknown settings: {', '.join(sorted(unknown))} (known: {', '.join(DEFAULT_SETTINGS)})")
        out = self.settings()
        for key, value in changes.items():
            if not isinstance(value, bool):
                raise ValueError(f"{key} is true or false")
            out[key] = value
        self._ensure()
        payload = (json.dumps(out, indent=1, sort_keys=True) + "\n").encode("utf-8")
        write_owner_only(self.dir / SETTINGS_FILE, payload, "settings")
        return out

    # ----------------------------------------------------------- forgets --

    def forget(self, record_id) -> bool:
        """Delete one record's file (and any temporary copy of it); True if there was one to delete."""
        path = self.path_of(record_id)
        if path is None or not os.path.lexists(self.dir):
            return False
        try:
            folder = self._folder(_KIND_OF[str(record_id)[0]])
        except FileNotFoundError:
            return False
        self._drop_tmp(folder, str(record_id))
        try:
            os.unlink(path)
        except FileNotFoundError:
            return False
        _fsync_dir(folder)
        return True

    def forget_session(self, session_id: str) -> list[str]:
        """Forget what one session contributed: its episode and every fact or preference it established. A fact
        established earlier and only repeated in this session keeps its record and loses the session from its list."""
        session_id = str(session_id)
        gone = []
        for record in self.records():
            if record.get("session") == session_id or record.get("source_session") == session_id:
                if self.forget(record["id"]):
                    gone.append(record["id"])
            elif session_id in (record.get("sessions") or []):
                record["sessions"] = [s for s in record["sessions"] if s != session_id]
                self.put(record)
        return gone

    def forget_everything(self) -> int:
        """Remove this person's whole folder; how many files were in it. Other people's folders are untouched."""
        if not os.path.lexists(self.dir):
            return 0
        if os.path.islink(self.dir):
            os.unlink(self.dir)           # a link in place of the folder: remove the link, never what it points to
            return 0
        count = sum(len(files) for _dirs, _subdirs, files in os.walk(self.dir))
        shutil.rmtree(self.dir)
        _fsync_dir(self.root)
        return count
