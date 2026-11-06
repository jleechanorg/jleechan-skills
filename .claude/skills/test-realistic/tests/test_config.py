"""Unit tests for config.py -- the per-project config contract loader.

These tests are the enforcement mechanism for STATE.md's design mandate:
this skill must contain ZERO project names/ports/paths, and every project
using it MUST supply a complete, validated config -- a missing required
field must fail loud at load time, never silently default.
"""

from __future__ import annotations

import pytest
from config import ConfigError, find_config_path, load_config

MINIMAL_VALID_TOML = """
project_name = "example-app"
repo_root = "."
base_url = "http://127.0.0.1:9999"
feature_surface_vocabulary = ["rendered.body_text", "rendered.title"]
dispatch_command = ["python3", "dispatch.py", "--output-root", "{output_root}"]
"""


def _write_config(tmp_path, content: str):
    config_path = tmp_path / ".test-realistic.toml"
    config_path.write_text(content)
    return config_path


class TestLoadConfig:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ConfigError, match="No project config found"):
            load_config(tmp_path / ".test-realistic.toml")

    def test_valid_minimal_config_loads(self, tmp_path):
        config_path = _write_config(tmp_path, MINIMAL_VALID_TOML)
        config = load_config(config_path)
        assert config.project_name == "example-app"
        assert config.base_url == "http://127.0.0.1:9999"
        assert config.feature_surface_vocabulary == (
            "rendered.body_text",
            "rendered.title",
        )
        # defaults filled in
        assert len(config.personas) == 5
        assert config.actor_fixtures == ()
        assert config.turns_default == 15

    def test_missing_required_field_raises(self, tmp_path):
        broken = MINIMAL_VALID_TOML.replace('project_name = "example-app"\n', "")
        config_path = _write_config(tmp_path, broken)
        with pytest.raises(ConfigError, match="missing required field"):
            load_config(config_path)

    def test_missing_feature_surface_vocabulary_raises(self, tmp_path):
        broken = MINIMAL_VALID_TOML.replace(
            'feature_surface_vocabulary = ["rendered.body_text", "rendered.title"]\n', ""
        )
        config_path = _write_config(tmp_path, broken)
        with pytest.raises(ConfigError, match="missing required field"):
            load_config(config_path)

    def test_empty_feature_surface_vocabulary_raises(self, tmp_path):
        broken = MINIMAL_VALID_TOML.replace(
            'feature_surface_vocabulary = ["rendered.body_text", "rendered.title"]',
            "feature_surface_vocabulary = []",
        )
        config_path = _write_config(tmp_path, broken)
        with pytest.raises(ConfigError, match="non-empty list"):
            load_config(config_path)

    def test_malformed_toml_raises(self, tmp_path):
        config_path = _write_config(tmp_path, "this is not [ valid toml")
        with pytest.raises(ConfigError, match="not valid TOML"):
            load_config(config_path)

    def test_repo_root_must_exist(self, tmp_path):
        broken = MINIMAL_VALID_TOML.replace(
            'repo_root = "."', 'repo_root = "/nonexistent/path/xyz123"'
        )
        config_path = _write_config(tmp_path, broken)
        with pytest.raises(ConfigError, match="does not exist"):
            load_config(config_path)

    def test_explicit_empty_actor_fixtures_is_accepted(self, tmp_path):
        """Regression: actor_fixtures = [] is a legitimate "no character
        concept" declaration, not an error -- caught live during the D2 real
        run when this raised ConfigError for the exact TOML a project would
        write to say "I have no actor fixtures"."""
        with_empty = MINIMAL_VALID_TOML + "\nactor_fixtures = []\n"
        config_path = _write_config(tmp_path, with_empty)
        config = load_config(config_path)
        assert config.actor_fixtures == ()

    def test_actor_fixtures_wrong_type_still_raises(self, tmp_path):
        broken = MINIMAL_VALID_TOML + "\nactor_fixtures = 5\n"
        config_path = _write_config(tmp_path, broken)
        with pytest.raises(ConfigError, match="actor_fixtures"):
            load_config(config_path)

    def test_personas_override_respected(self, tmp_path):
        with_personas = MINIMAL_VALID_TOML + '\npersonas = ["solo_agent"]\n'
        config_path = _write_config(tmp_path, with_personas)
        config = load_config(config_path)
        assert config.personas == ("solo_agent",)

    def test_turns_default_must_be_positive(self, tmp_path):
        broken = MINIMAL_VALID_TOML + "\nturns_default = 0\n"
        config_path = _write_config(tmp_path, broken)
        with pytest.raises(ConfigError, match="positive integer"):
            load_config(config_path)

    def test_dispatch_command_must_be_string_list(self, tmp_path):
        broken = MINIMAL_VALID_TOML.replace(
            'dispatch_command = ["python3", "dispatch.py", "--output-root", "{output_root}"]',
            "dispatch_command = 5",
        )
        config_path = _write_config(tmp_path, broken)
        with pytest.raises(ConfigError, match="dispatch_command"):
            load_config(config_path)


class TestFindConfigPath:
    def test_finds_in_current_dir(self, tmp_path):
        _write_config(tmp_path, MINIMAL_VALID_TOML)
        found = find_config_path(tmp_path)
        assert found == tmp_path / ".test-realistic.toml"

    def test_finds_in_parent_dir(self, tmp_path):
        _write_config(tmp_path, MINIMAL_VALID_TOML)
        subdir = tmp_path / "packages" / "mobile"
        subdir.mkdir(parents=True)
        found = find_config_path(subdir)
        assert found == tmp_path / ".test-realistic.toml"

    def test_raises_when_not_found(self, tmp_path):
        with pytest.raises(ConfigError, match="No .test-realistic.toml found"):
            find_config_path(tmp_path)
