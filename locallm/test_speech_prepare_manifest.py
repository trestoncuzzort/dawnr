"""Tests for speech/prepare_manifest.py's orchestration logic. No network,
no torch. The LibriSpeech path's FLAC conversion itself needs ffmpeg, which
this environment does not have (checked directly: `_require_ffmpeg` raising
is tested for real, unmocked); the file-walking and manifest-writing logic
around it is tested with `_convert_flac` stubbed out, since that call is a
thin, separately-inspectable subprocess wrapper.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from speech.prepare_manifest import _require_ffmpeg, prepare_librispeech, prepare_ljspeech  # noqa: E402


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class RequireFfmpegTest(unittest.TestCase):
    def test_raises_a_plain_actionable_message_when_absent(self):
        with self.assertRaises(SystemExit) as ctx:
            _require_ffmpeg("definitely-not-a-real-binary-xyz")
        self.assertIn("PATH", str(ctx.exception))

    def test_does_not_raise_for_a_binary_that_exists(self):
        _require_ffmpeg("true")   # every POSIX system has /usr/bin/true or /bin/true


class PrepareLjspeechTest(unittest.TestCase):
    def _make_corpus(self, tmp: Path, rows) -> Path:
        root = tmp / "LJSpeech-1.1"
        (root / "wavs").mkdir(parents=True)
        lines = []
        for clip_id, transcript, normalized in rows:
            lines.append(f"{clip_id}|{transcript}|{normalized}")
            (root / "wavs" / f"{clip_id}.wav").write_bytes(b"RIFF....WAVEfmt ")  # existence is all that matters here
        (root / "metadata.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return root

    def test_uses_the_normalized_third_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = self._make_corpus(tmp, [("LJ001-0001", "It cost $50.", "It cost fifty dollars.")])
            out = tmp / "manifest.jsonl"
            count = prepare_ljspeech(root, out)
            rows = _read_jsonl(out)
        self.assertEqual(count, 1)
        self.assertEqual(rows[0]["text"], "it cost fifty dollars")   # normalized through CTCVocab too
        self.assertTrue(rows[0]["audio"].endswith("LJ001-0001.wav"))

    def test_skips_a_row_whose_wav_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = self._make_corpus(tmp, [("LJ001-0001", "hello", "hello")])
            (root / "wavs" / "LJ001-0001.wav").unlink()
            out = tmp / "manifest.jsonl"
            with self.assertRaises(SystemExit):     # zero rows survive -> _write_manifest refuses
                prepare_ljspeech(root, out)

    def test_missing_metadata_is_refused_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty"
            root.mkdir()
            with self.assertRaises(SystemExit) as ctx:
                prepare_ljspeech(root, Path(tmp) / "out.jsonl")
            self.assertIn("metadata.csv", str(ctx.exception))


class PrepareLibrispeechTest(unittest.TestCase):
    def test_walks_trans_files_and_writes_one_row_per_utterance(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            chapter = tmp / "LibriSpeech" / "dev-clean" / "1272" / "128104"
            chapter.mkdir(parents=True)
            (chapter / "1272-128104-0000.flac").write_bytes(b"fLaC....")
            (chapter / "1272-128104-0001.flac").write_bytes(b"fLaC....")
            (chapter / "1272-128104.trans.txt").write_text(
                "1272-128104-0000 MISTER QUILTER IS THE APOSTLE\n"
                "1272-128104-0001 NOR IS MISTER QUILTER'S MANNER\n", encoding="utf-8")
            out = tmp / "dev-clean.jsonl"

            with mock.patch("speech.prepare_manifest._convert_flac") as fake_convert:
                def make_stub_wav(src, dst, *a, **k):
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(b"RIFF....WAVEfmt ")
                fake_convert.side_effect = make_stub_wav
                count = prepare_librispeech(tmp / "LibriSpeech" / "dev-clean", out, ffmpeg="true")

            rows = _read_jsonl(out)
        self.assertEqual(count, 2)
        self.assertEqual(fake_convert.call_count, 2)
        self.assertEqual(rows[0]["text"], "mister quilter is the apostle")
        self.assertEqual(rows[1]["text"], "nor is mister quilter's manner")

    def test_skips_a_transcript_with_no_matching_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            chapter = tmp / "1"
            chapter.mkdir()
            (chapter / "1-1.trans.txt").write_text("1-1-0000 HAS NO AUDIO FILE\n", encoding="utf-8")
            with mock.patch("speech.prepare_manifest._convert_flac"):
                with self.assertRaises(SystemExit):   # zero surviving rows
                    prepare_librispeech(tmp, tmp / "out.jsonl", ffmpeg="true")

    def test_missing_root_is_refused_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            with self.assertRaises(SystemExit) as ctx:
                prepare_librispeech(missing, Path(tmp) / "out.jsonl", ffmpeg="true")
            self.assertIn(str(missing), str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
