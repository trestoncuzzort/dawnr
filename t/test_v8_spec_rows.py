"""Teacher outputs retain their provenance when added to an existing training set."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import v8_spec_rows


def test_teacher_label_is_written_to_added_rows_and_receipt_only(tmp_path, monkeypatch):
    base = {"prompt": "base", "chosen": "answer", "tag": "original"}
    added = {"prompt": "new", "chosen": "teacher answer", "task_id": 7, "source": "spec"}
    (tmp_path / "base.jsonl").write_text(json.dumps(base) + "\n")
    (tmp_path / "kept.jsonl").write_text('{"task_id":7}\n')
    monkeypatch.setattr(v8_spec_rows.se, "pool", lambda _: {})
    monkeypatch.setattr(v8_spec_rows.spec_first_rows, "build_from_specs", lambda *_: ([dict(added)], {}))
    label = "cohere:command-a-03-2025:pass-one"
    v8_spec_rows.main(["--base", str(tmp_path / "base.jsonl"), "--kept", str(tmp_path / "kept.jsonl"),
                      "--out", str(tmp_path / "rows.jsonl"), "--report", str(tmp_path / "receipt.json"),
                      "--tag", label])
    rows = [json.loads(line) for line in (tmp_path / "rows.jsonl").read_text().splitlines()]
    assert rows[0] == base
    assert rows[1]["tag"] == label
    assert json.loads((tmp_path / "receipt.json").read_text())["kept"]["tag"] == label
