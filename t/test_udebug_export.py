"""The uDebug bundle is dawnr's own: a lane written by OpenAI never reaches it (user's rule, 2026-10-13)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import udebug_export as ux  # noqa: E402


def lane(root: Path, name: str, provider: str) -> Path:
    d = root / name / "UVa-100" / "s1"
    d.mkdir(parents=True)
    (d / "record.json").write_text(json.dumps({"judge": "UVa", "id": "100", "provider": provider, "model": "m"}))
    (d / "result.json").write_text(json.dumps({"judge_name": "UVa", "id": "100", "parse": "python", "accepted": True,
                                               "judge": {"status": "pass", "passed": 1, "total": 1}}))
    return root / name


def test_an_openai_lane_is_excluded_and_named(tmp_path):
    lane(tmp_path, "teacher-solve-r1-O1-repair", "openai")
    lane(tmp_path, "teacher-solve-r1-D1-repair", "bedrock-cli")
    excluded: set = set()
    found = ux.scan_lanes([str(tmp_path / "teacher-*")], excluded)
    assert excluded == {"teacher-solve-r1-O1-repair"}
    assert [o["lane"] for o in found[("UVa", "100")]] == ["teacher-solve-r1-D1-repair"]


def test_a_lane_without_records_is_not_excluded(tmp_path):
    (tmp_path / "teacher-empty").mkdir()
    excluded: set = set()
    assert ux.scan_lanes([str(tmp_path / "teacher-*")], excluded) == {}
    assert excluded == set()
