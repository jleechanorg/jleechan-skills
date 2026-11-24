import json

from scripts import prw_metrics as m


def test_nearest_rank_percentiles():
    values = list(range(1, 11))
    assert m.nearest_rank_percentile(values, 50) == 5
    assert m.nearest_rank_percentile(values, 75) == 8
    assert m.nearest_rank_percentile(values, 90) == 9
    assert m.nearest_rank_percentile(values, 99) == 10
    assert m.nearest_rank_percentile([42], 99) == 42
    assert m.nearest_rank_percentile([9, 1, 5], 50) == 5
    assert m.nearest_rank_percentile([], 50) is None


def test_format_duration():
    assert m.format_duration(None) == "UNKNOWN"
    assert m.format_duration(0) == "0s"
    assert m.format_duration(45) == "45s"
    assert m.format_duration(9000) == "2h 30m"
    assert m.format_duration(226800) == "2d 15h"
    assert m.format_duration(86400 + 300) == "1d 5m"
    stamp = "2026-11-14T00:00:00Z"
    assert m.format_iso_utc(m.parse_iso_utc(stamp)) == stamp
    assert m.parse_iso_utc("2026-11-14T01:00:00+01:00") == m.parse_iso_utc(stamp)


def test_load_annotations_ok_absent_invalid(tmp_path):
    absent = {"labels": {}, "status": "ABSENT"}
    assert m.load_annotations(None) == absent
    assert m.load_annotations(str(tmp_path / "missing.json")) == absent

    good = {"example-org/example-repo#7": {"label": "good", "evidence": "https://example.test/e"}}
    path = tmp_path / "ok.json"
    path.write_text(json.dumps(good))
    assert m.load_annotations(str(path)) == {"labels": good, "status": "OK"}

    invalid = {"labels": {}, "status": "INVALID"}
    for body in (
        "not json",
        json.dumps([]),
        json.dumps({"example-org/example-repo#7": {"label": "great", "evidence": "x"}}),
        json.dumps({"no-number": {"label": "good", "evidence": "x"}}),
        json.dumps({"example-org/example-repo#7": {"label": "good"}}),
    ):
        path.write_text(body)
        assert m.load_annotations(str(path)) == invalid
