import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'harbor_experiment.py'


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def test_snapshot_excludes_future_and_preserves_repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'old').write_text('old')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'old')
    old = git(repo, 'rev-parse', 'HEAD')
    (repo / 'future').write_text('future')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'future')
    (repo / 'dirty').write_text('local')
    before = git(repo, 'status', '--porcelain')
    out = tmp_path / 'snapshot'
    result = cli('snapshot', '--repo', repo, '--commit', old, '--output', out)
    assert result.returncode == 0, result.stderr
    assert (out / 'old').read_text() == 'old'
    assert not (out / 'future').exists() and not (out / '.git').exists()
    assert git(repo, 'status', '--porcelain') == before
    receipt = json.loads((tmp_path / 'snapshot.receipt.json').read_text())
    assert receipt['repository_commit'] == old
    assert receipt['sha256']


def test_snapshot_rejects_symlink_and_existing_destination(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'link').symlink_to('target')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'link')
    sha = git(repo, 'rev-parse', 'HEAD')
    assert cli('snapshot', '--repo', repo, '--commit', sha, '--output', tmp_path / 'out').returncode != 0
    existing = tmp_path / 'existing'
    existing.mkdir()
    assert cli('snapshot', '--repo', repo, '--commit', sha, '--output', existing).returncode != 0


def test_snapshot_rejects_lfs_gitlink_and_output_inside_repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'pointer').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:' + '1' * 64 + '\nsize 1\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'lfs')
    sha = git(repo, 'rev-parse', 'HEAD')
    assert cli('snapshot', '--repo', repo, '--commit', sha, '--output', tmp_path / 'lfs').returncode != 0
    (repo / 'pointer').unlink()
    git(repo, 'rm', 'pointer')
    git(repo, 'update-index', '--add', '--cacheinfo', '160000,' + sha + ',submodule')
    git(repo, 'commit', '-qm', 'gitlink')
    assert cli('snapshot', '--repo', repo, '--commit', git(repo, 'rev-parse', 'HEAD'), '--output', tmp_path / 'gitlink').returncode != 0
    git(repo, 'update-index', '--force-remove', 'submodule')
    (repo / 'file').write_text('x')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'normal')
    assert cli('snapshot', '--repo', repo, '--commit', git(repo, 'rev-parse', 'HEAD'), '--output', repo / 'output').returncode != 0
    assert not (repo / 'output').exists()
