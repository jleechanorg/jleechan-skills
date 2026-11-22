import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import prw_metrics  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "prw"


def test_fixture_pipeline_collect_aggregate_render(tmp_path):
    golden = json.loads((FIXTURES / "metrics_golden.json").read_text(encoding="utf-8"))
    records_expected = json.loads((FIXTURES / "records_fixture.json").read_text(encoding="utf-8"))
    cutoff = golden["cutoff"]
    repos = golden["repos"]

    records, health = prw_metrics.collect(repos, cutoff, prw_metrics.replay_runner(str(FIXTURES)))
    assert records == records_expected
    assert health == golden["health"]

    annotations = {"labels": {}, "status": "ABSENT"}
    metrics = prw_metrics.aggregate(records, health, annotations, cutoff)
    assert metrics == golden

    out = prw_metrics.render(metrics)
    assert re.findall(r"^## ([1-7])\. ", out, flags=re.M) == ["1", "2", "3", "4", "5", "6", "7"]


def test_main_replays_fixtures_to_output_file(tmp_path):
    out = tmp_path / "out.md"
    rc = prw_metrics.main([
        "--repos", "example-org/example-repo",
        "--input-dir", str(FIXTURES),
        "--cutoff", "2026-11-14T00:00:00Z",
        "--output", str(out),
        "--annotations", str(tmp_path / "missing.json"),
    ])
    assert rc == 0
    assert out.read_text(encoding="utf-8").count("\n## ") >= 7
