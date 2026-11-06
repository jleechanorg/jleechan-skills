"""Offline selection/side-effect regressions; discovery checks are instruction-only."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
import post_approved as publisher
import stage_in_aside as cli_stage
import stage_in_aside_mcp as mcp_stage
from platform_policy import parse_platforms

EXCLUDED = ['linkedin', 'linkedin_short', 'instagram', 'facebook', 'threads']
KEYS = ['twitter', 'reddit_example'] + EXCLUDED


def drafts(tmp_path):
    files = {}
    for key in KEYS:
        path = tmp_path / f'{key}.md'
        path.write_text('## Title\n\nExample\n\n## Body\n\nA source-faithful draft.\n')
        files[key] = str(path)
    # A stale broad manifest is not per-request platform authorization.
    (tmp_path / 'manifest.json').write_text(json.dumps({'mode': 'draft', 'platforms': KEYS, 'files': files}))
    return tmp_path


def argv(monkeypatch, module, directory, *extra):
    monkeypatch.setattr(sys, 'argv', [module.__file__, '--drafts', str(directory), *extra])


def test_default_draft_is_local_and_honest(tmp_path):
    result = subprocess.run([sys.executable, str(SKILL / 'scripts/draft_social_post.py'),
        '--intent', 'An observation', '--out', str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert {p.name for p in tmp_path.glob('*.md')} == {'reddit.md', 'twitter.md'}
    manifest = json.loads((tmp_path / 'manifest.json').read_text())
    assert manifest['platforms'] == ['reddit', 'twitter']
    assert manifest['mode'] == 'draft'
    assert manifest['discovery_status'] == 'not_performed'
    assert manifest['reddit_subs'] == []  # No unresearched community recommendations.
    assert not list((tmp_path / 'screenshots').iterdir())
    assert not (tmp_path / 'posted.json').exists()
    assert 'stage in Aside' not in result.stdout


@pytest.mark.parametrize('platform', EXCLUDED)
def test_explicit_draft_opt_in(tmp_path, platform):
    result = subprocess.run([sys.executable, str(SKILL / 'scripts/draft_social_post.py'),
        '--intent', 'An observation', '--platforms', platform, '--out', str(tmp_path)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert {p.stem for p in tmp_path.glob('*.md')} == {platform}


@pytest.mark.parametrize('module', [cli_stage, mcp_stage])
@pytest.mark.parametrize('only,expected', [(None, {'twitter', 'reddit_example'}),
    ('linkedin', {'linkedin'}), ('threads', {'threads'}), ('x', {'twitter'}),
    ('reddit_example', {'reddit_example'})])
def test_staging_scopes_actual_browser_calls(tmp_path, monkeypatch, module, only, expected):
    directory = drafts(tmp_path)
    calls = []
    def stage(key, *args, **kwargs):
        calls.append(key)
        return {'status': 'staged'}
    monkeypatch.setattr(cli_stage, 'aside_repr', lambda *a, **k: 'ASIDE_OK')
    monkeypatch.setattr(cli_stage, 'stage_platform', stage)
    monkeypatch.setattr(cli_stage, 'stage_reddit', lambda sub, *a, **k: stage('reddit_' + sub))
    monkeypatch.setattr(mcp_stage, 'mcp_init', lambda: 'offline-test')
    monkeypatch.setattr(mcp_stage, 'stage_one', lambda session, key, *a, **k: stage(key))
    monkeypatch.setattr(mcp_stage.time, 'sleep', lambda _: None)
    argv(monkeypatch, module, directory, *(['--only', only] if only else []))
    module.main()
    assert set(calls) == expected


def publish(monkeypatch, directory, *extra):
    argv(monkeypatch, publisher, directory, '--approval-token', 'POST APPROVED', *extra)
    return publisher.main()


def test_latest_draft_cannot_publish_with_old_token(tmp_path, monkeypatch):
    calls = Mock()
    monkeypatch.setattr(publisher, 'click_submit_via_aside', calls)
    assert publish(monkeypatch, drafts(tmp_path)) == 2
    calls.assert_not_called()
    assert not (tmp_path / 'posted.json').exists()


@pytest.mark.parametrize('platforms,expected', [(None, {'twitter', 'reddit_example'}),
    ('linkedin', {'linkedin'}), ('facebook,threads', {'facebook', 'threads'}),
    ('instagram', set())])
def test_publish_scope(tmp_path, monkeypatch, platforms, expected):
    calls = []
    def submit(key, url):
        calls.append(key)
        return {'status': 'posted', 'url': 'https://example.org/post'}
    monkeypatch.setattr(publisher, 'click_submit_via_aside', submit)
    extra = ['--publish-request'] + (['--platforms', platforms] if platforms else [])
    assert publish(monkeypatch, drafts(tmp_path), *extra) == 0
    assert set(calls) == expected


@pytest.mark.parametrize('status', ['posted', 'existing', 'timeout', 'unknown', 'submitting'])
def test_approved_existing_or_uncertain_post_is_not_repeated(tmp_path, monkeypatch, status):
    directory = drafts(tmp_path)
    record = {'status': status, 'url': 'https://x.com/example/status/123'}
    (directory / 'posted.json').write_text(json.dumps({'results': {'twitter': record}}))
    calls = Mock()
    monkeypatch.setattr(publisher, 'click_submit_via_aside', calls)
    assert publish(monkeypatch, directory, '--publish-request', '--platforms', 'twitter') == 0
    calls.assert_not_called()
    assert json.loads((directory / 'posted.json').read_text())['results']['twitter'] == record


def test_token_allowlist_cannot_be_broadened(tmp_path, monkeypatch):
    calls = Mock()
    monkeypatch.setattr(publisher, 'click_submit_via_aside', calls)
    argv(monkeypatch, publisher, drafts(tmp_path), '--approval-token', 'POST APPROVED twitter',
         '--publish-request', '--platforms', 'linkedin')
    with pytest.raises(SystemExit) as error:
        publisher.main()
    assert error.value.code == 2
    calls.assert_not_called()


def test_x_is_not_meta_threads_and_empty_is_not_all():
    assert parse_platforms(' X,reddit ') == ['twitter', 'reddit']
    assert parse_platforms('threads') == ['threads']
    for invalid in ['', 'all', 'typo']:
        with pytest.raises(ValueError):
            parse_platforms(invalid)


def test_multi_source_discovery_instruction_contract():
    # Structural regression only. No assertion here proves a live search occurred.
    text = (SKILL / 'SKILL.md').read_text()
    start = text.index('## Phase 0')
    contract = text[start:text.index('## Twitter/X browser workflow')]
    for requirement in ['each input source URL', 'every input source URL',
            'original media', 'exact existing thread URL', 'current rules URL',
            'checked-at date', 'prior-user-post/reply evidence', 'discussion date/latest activity',
            '`standalone`', '`reply`', '`existing`', '`skip`', 'Coverage limits',
            'source URL', 'not_performed', 'cannot establish that a real discovery run occurred']:
        assert requirement.lower() in contract.lower()
    assert 'Do not pool multiple source posts' in contract
    assert 'no duplicate draft' in contract
    assert 'No auto-stage on /social' in text
    assert 'keep Threads/Facebook cross-share disabled' in text


@pytest.mark.parametrize('subs', [None, 'example', 'example,sibling'])
def test_scoped_reddit_draft_creates_only_selected_subreddit(tmp_path, subs):
    args = [sys.executable, str(SKILL / 'scripts/draft_social_post.py'),
            '--intent', 'An observation', '--platforms', 'reddit_example', '--out', str(tmp_path)]
    if subs is not None:
        args += ['--reddit-subs', subs]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert {p.stem for p in tmp_path.glob('*.md')} == {'reddit_example'}
    manifest = json.loads((tmp_path / 'manifest.json').read_text())
    assert manifest['reddit_subs'] == ['example']
    assert set(manifest['files']) == {'reddit_example', 'reddit_example_title'}


def test_disjoint_reddit_draft_selection_reports_error(tmp_path):
    result = subprocess.run([sys.executable, str(SKILL / 'scripts/draft_social_post.py'),
        '--intent', 'An observation', '--platforms', 'reddit_example',
        '--reddit-subs', 'sibling', '--out', str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'no subreddit' in result.stderr.lower()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('token_scope,flag_scope,expected', [
    ('reddit_example', 'reddit', {'reddit_example'}),
    ('reddit', 'reddit_example', {'reddit_example'}),
    ('reddit_example', 'reddit_example', {'reddit_example'}),
    ('reddit_example,twitter', 'reddit,x', {'reddit_example', 'twitter'}),
    ('reddit_example,reddit_sibling', 'reddit_example', {'reddit_example'}),
])
def test_publisher_exact_scope_intersection(tmp_path, monkeypatch, token_scope, flag_scope, expected):
    directory = drafts(tmp_path)
    sibling = directory / 'reddit_sibling.md'
    sibling.write_text('A sibling draft that may not be authorized.')
    manifest = json.loads((directory / 'manifest.json').read_text())
    manifest['files']['reddit_sibling'] = str(sibling)
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    calls = []
    def submit(key, url):
        calls.append(key)
        return {'status': 'posted', 'url': 'https://example.org/post'}
    monkeypatch.setattr(publisher, 'click_submit_via_aside', submit)
    argv(monkeypatch, publisher, directory, '--approval-token', 'POST APPROVED ' + token_scope,
         '--publish-request', '--platforms', flag_scope)
    assert publisher.main() == 0
    assert set(calls) == expected


@pytest.mark.parametrize('token_scope,flag_scope', [
    ('reddit_example', 'reddit_sibling'), ('twitter', 'linkedin'),
    ('reddit_example', ''), ('reddit_example', 'reddit_'),
    (',', 'reddit'), ('reddit_', 'reddit'),
])
def test_empty_or_invalid_publish_scope_is_error(tmp_path, monkeypatch, capsys, token_scope, flag_scope):
    calls = Mock()
    monkeypatch.setattr(publisher, 'click_submit_via_aside', calls)
    argv(monkeypatch, publisher, drafts(tmp_path), '--approval-token', 'POST APPROVED ' + token_scope,
         '--publish-request', '--platforms', flag_scope)
    with pytest.raises(SystemExit) as error:
        publisher.main()
    assert error.value.code == 2
    assert 'error:' in capsys.readouterr().err
    calls.assert_not_called()
    assert not (tmp_path / 'posted.json').exists()


def test_reddit_promotion_rules_are_a_prerequisite_instruction_contract():
    # Instruction coverage only, not evidence that live subreddit rules were checked.
    text = (SKILL / 'SKILL.md').read_text()
    start = text.index('## Phase 0')
    contract = text[start:text.index('## Twitter/X browser workflow')]
    for requirement in ['before recommending a destination or drafting for it',
            'promotion eligibility', 'affiliation disclosure', 'required flair',
            'frequency/duplicate limits', 'AI/bot restrictions', 'account eligibility',
            'rule source URL', 'check date', '`allowed`', '`conditional`',
            '`prohibited`', '`unverified`', 'inaccessible or ambiguous',
            'do not assume promotion is allowed', 'verified alternative',
            'does not grant publication permission']:
        assert requirement in contract
