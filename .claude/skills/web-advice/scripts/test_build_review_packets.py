import hashlib
import json
import re

import pytest
import subprocess

from build_review_packets import build_review_packets
from web_advice_transport import assert_review_packet_complete


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_builds_lossless_review_packet_with_base_and_diff_provenance(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "web-advice@example.invalid")
    _git(repo, "config", "user.name", "web-advice test")
    (repo / "code.py").write_text("stable = True\n", encoding="utf-8")
    (repo / "deleted.txt").write_text("old bytes\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    (repo / "code.py").write_text("stable = True\nchanged = 1\n", encoding="utf-8")
    (repo / "new_test.py").write_text("def test_change(): pass\n", encoding="utf-8")
    (repo / "no_newline.py").write_bytes(b"exact-no-newline")
    (repo / "deleted.txt").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "verification_report.json").write_text(
        '{"result":"PASS"}\n', encoding="utf-8"
    )
    (evidence / "metadata.json").write_text(
        json.dumps({"git_provenance": {"git_head": head}}) + "\n",
        encoding="utf-8",
    )
    raw = evidence / "raw"
    raw.mkdir()
    (raw / "bq.json").write_text('{"rows":12}\n', encoding="utf-8")
    checksum_lines = []
    for relative in ("verification_report.json", "metadata.json", "raw/bq.json"):
        digest = hashlib.sha256((evidence / relative).read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {relative}")
    (evidence / "SHA256SUMS.txt").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )

    output = tmp_path / "packets"
    packet = build_review_packets(
        repo,
        base,
        head,
        evidence,
        output,
        ["SHA256SUMS.txt", "verification_report.json", "raw/bq.json"],
        "PR_TEST",
    )

    assert_review_packet_complete(packet)
    assert {item["path"] for item in packet["changed_files"]} == {
        "code.py",
        "deleted.txt",
        "new_test.py",
        "no_newline.py",
    }
    code_packet_path = output / "PR_TEST_FULL_CODE_FILES.txt"
    code_packet = code_packet_path.read_text()
    assert "BEGIN FILE deleted.txt status=deleted source_size=10" in code_packet
    assert "stable = True\nchanged = 1" in code_packet
    assert "def test_change(): pass" in code_packet

    packet_bytes = code_packet_path.read_bytes()
    marker = b"BEGIN FILE no_newline.py "
    header_start = packet_bytes.index(marker)
    header_end = packet_bytes.index(b"\n", header_start)
    header = packet_bytes[header_start:header_end].decode()
    payload_size = int(re.search(r"payload_bytes=(\d+)", header).group(1))
    payload_start = header_end + 1
    assert packet_bytes[payload_start : payload_start + payload_size] == b"exact-no-newline"
    assert packet_bytes[payload_start + payload_size :].startswith(
        b"END FILE no_newline.py"
    )

    base_diff_packet = (
        output / "PR_TEST_BASE_CODE_FILES_AND_DIFF.txt"
    ).read_text()
    assert "BEGIN FILE code.py status=base" in base_diff_packet
    assert "stable = True\n" in base_diff_packet
    assert "BEGIN FILE deleted.txt status=base" in base_diff_packet
    assert "BEGIN FILE base...head.patch status=diff" in base_diff_packet
    assert "+changed = 1" in base_diff_packet
    assert packet["diff_index_attached"] is True
    assert {item["path"] for item in packet["base_code_files"]} == {
        "code.py",
        "deleted.txt",
    }

    evidence_packet = (output / "PR_TEST_FULL_ES_EVIDENCE.txt").read_text()
    assert "BEGIN FILE raw/bq.json" in evidence_packet
    manifest = json.loads(
        (output / "PR_TEST_REVIEW_PACKET_MANIFEST.json").read_text()
    )
    assert manifest["head_sha"] == head
    assert manifest["packet_attachment_names"] == [
        "PR_TEST_FULL_CODE_FILES.txt",
        "PR_TEST_BASE_CODE_FILES_AND_DIFF.txt",
        "PR_TEST_ES_REVIEW_INDEX.txt",
        "PR_TEST_FULL_ES_EVIDENCE.txt",
    ]

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        build_review_packets(
            repo,
            base,
            head,
            evidence,
            output,
            ["SHA256SUMS.txt", "verification_report.json", "raw/bq.json"],
            "PR_TEST",
        )

    with pytest.raises(ValueError, match="cannot contain path separators"):
        build_review_packets(
            repo,
            base,
            head,
            evidence,
            tmp_path / "escaped",
            ["SHA256SUMS.txt", "verification_report.json", "raw/bq.json"],
            "../../escape",
        )
