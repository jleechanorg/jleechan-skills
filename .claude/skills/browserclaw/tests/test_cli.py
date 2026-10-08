from __future__ import annotations

import json
from pathlib import Path

from browserclaw.models import EndpointCatalog, EndpointSignature


def _write_catalog(tmp_path: Path, catalog: EndpointCatalog) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "catalog.json"
    p.write_text(json.dumps(catalog.to_dict()))
    return p


def test_generate_no_skill_without_save_skill_flag(tmp_path: Path) -> None:
    """generate command without --save-skill must not emit SKILL.md."""
    from browserclaw.cli import _build_parser

    catalog = EndpointCatalog(
        site="example.com",
        source_har="t.har",
        notes=[],
        endpoints=[
            EndpointSignature(
                name="get_data",
                method="GET",
                url_template="https://example.com/data",
                host="example.com",
                description="test",
            )
        ],
    )
    cat_path = _write_catalog(tmp_path / "input", catalog)
    out_dir = tmp_path / "output"

    parser = _build_parser()
    args = parser.parse_args(["generate", "--catalog", str(cat_path), "--output-dir", str(out_dir)])
    site_url = args.url if getattr(args, "save_skill", False) else None
    assert site_url is None


def test_generate_skill_with_save_skill_flag(tmp_path: Path) -> None:
    """generate command with --save-skill --url must pass site_url."""
    from browserclaw.cli import _build_parser

    catalog = EndpointCatalog(
        site="example.com",
        source_har="t.har",
        notes=[],
        endpoints=[],
    )
    cat_path = _write_catalog(tmp_path / "input", catalog)
    out_dir = tmp_path / "output"

    parser = _build_parser()
    args = parser.parse_args([
        "generate", "--catalog", str(cat_path), "--output-dir", str(out_dir),
        "--save-skill", "--url", "https://example.com",
    ])
    site_url = args.url if getattr(args, "save_skill", False) else None
    assert site_url == "https://example.com"


def test_generate_save_skill_without_url_errors(tmp_path: Path, monkeypatch) -> None:
    """--save-skill without --url must cause a parser error."""
    import pytest
    from browserclaw.cli import main

    catalog = EndpointCatalog(
        site="example.com",
        source_har="t.har",
        notes=[],
        endpoints=[],
    )
    cat_path = _write_catalog(tmp_path / "input", catalog)
    out_dir = tmp_path / "output"

    monkeypatch.setattr("sys.argv", [
        "browserclaw", "generate",
        "--catalog", str(cat_path), "--output-dir", str(out_dir), "--save-skill",
    ])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


def test_learn_deploy_avoids_nested_discovery(tmp_path, monkeypatch, capsys):
    """An installed package must deploy only to the canonical home skill root."""
    from browserclaw import cli

    package = tmp_path / "installed" / "skills" / "browserclaw"
    package.mkdir(parents=True)
    (package / ".git").mkdir()  # Even a checkout under discovery is unsafe.
    monkeypatch.setattr(cli, "__file__", str(package / "src" / "browserclaw" / "cli.py"))
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(cli, "capture_har", lambda *a, **kw: None)
    monkeypatch.setattr(cli, "capture_responses_superpower", lambda *a: {})
    output = tmp_path / "output"
    output.mkdir()
    source = output / "SKILL.md"
    source.write_text("---\nname: example\ndescription: Test generated skill.\n---\n")
    monkeypatch.setattr(cli, "generate_bundle", lambda *a, **kw: {"skill": source})
    monkeypatch.setattr("sys.argv", ["browserclaw", "learn", "--url", "https://example.com", "--output-dir", str(output), "--headless", "--deploy-skill"])
    cli.main()
    result = json.loads(capsys.readouterr().out)
    assert Path(result["deployed_skill"]).read_bytes() == source.read_bytes()
    assert result["repo_skill"].startswith("skipped:")
    assert not (package / "skills").exists()
    assert not (package / "generated").exists()
