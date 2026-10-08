"""Physical runtime accounting; test-only auditor is never imported by runtime."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = Path('.claude/skills/dot-portfolio-coordinator')
MANIFEST = PACKAGE / 'references/runtime-files.json'


def physical_lines(data):
    return data.count(b'\n') + int(bool(data) and not data.endswith(b'\n'))


def added_lines(diff):
    return sum(line.startswith('+') and not line.startswith('+++') for line in diff.splitlines())


def enforce_limit(count, maximum=1000):
    if count > maximum:
        raise ValueError(f'{count} physical runtime lines exceed {maximum}')


def audit(root, manifest, shared_diff=''):
    files = manifest['files']
    expected = set(files)
    actual = {str(path.relative_to(root)) for path in root.rglob('*') if path.is_file()}
    if actual != expected:
        raise ValueError(f'runtime inventory mismatch: missing={expected-actual}, unlisted={actual-expected}')
    total = added_lines(shared_diff)
    for name in files:
        path = root / name
        data = path.read_bytes()
        count = physical_lines(data)
        if count > files[name]:
            raise ValueError(f'{name}: {count} exceeds allocation {files[name]}')
        total += count
        if path.suffix == '.py':
            tree = ast.parse(data, filename=name)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or '']
                    for module in imports:
                        if module.split('.')[0] not in __import__('sys').stdlib_module_names:
                            local = str(Path(name).parent / (module.replace('.', '/') + '.py'))
                            if local not in expected:
                                raise ValueError(f'{name}: unmanifested import {module}')
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'exec', 'eval', '__import__'}:
                    raise ValueError(f'{name}: dynamic executable dependency requires explicit audit')
            if re.search(r'\b(?:tests|fixtures)\b|coordinator-portfolio|portfolio-coordinator-sender', data.decode()):
                raise ValueError(f'{name}: discarded or test runtime dependency')
    enforce_limit(total, manifest['limit'])
    return total


class PhysicalAccountingTests(unittest.TestCase):
    def test_exact_boundary(self):
        enforce_limit(1000)
        with self.assertRaises(ValueError):
            enforce_limit(1001)

    def test_blank_comments_and_partial_final_line(self):
        self.assertEqual(physical_lines(b''), 0)
        self.assertEqual(physical_lines(b'\n# comment\nx'), 3)
        self.assertEqual(physical_lines(b'\n# comment\nx\n'), 3)

    def test_shared_replacements_count_added_side_not_net(self):
        diff = '--- a/x\n+++ b/x\n@@ -1 +1,2 @@\n-old\n+new\n+\n'
        self.assertEqual(added_lines(diff), 2)

    def test_transitive_helpers_count_and_unlisted_files_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'worker.py').write_text('import helper\n')
            (root/'helper.py').write_text('# retained helper\n\n')
            manifest = {'files': {'worker.py': 2, 'helper.py': 2}, 'limit': 1000}
            self.assertEqual(audit(root, manifest), 3)
            del manifest['files']['helper.py']
            with self.assertRaisesRegex(ValueError, 'unlisted'):
                audit(root, manifest)

    def test_engine_moved_to_fixture_cannot_escape_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'worker.py').write_text('from tests.fixtures import engine\n')
            with self.assertRaisesRegex(ValueError, 'unmanifested import'):
                audit(root, {'files': {'worker.py': 2}, 'limit': 1000})

    def test_dynamic_test_import_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'worker.py').write_text('__import__("test" + "s.fixture")\n')
            with self.assertRaisesRegex(ValueError, 'dynamic executable'):
                audit(root, {'files': {'worker.py': 2}, 'limit': 1000})

    def test_allocation_sum_is_950_plus_50(self):
        manifest = json.loads((ROOT/MANIFEST).read_text())
        self.assertEqual(sum(manifest['files'].values()) + manifest['shared_allocation'], 950)
        self.assertEqual(950 + manifest['reserve'], manifest['limit'])
        self.assertLessEqual(physical_lines((ROOT/MANIFEST).read_bytes()), 20)

    def test_frozen_dependencies_match_recorded_baseline(self):
        manifest = json.loads((ROOT/MANIFEST).read_text())
        for name, expected in manifest['shared'].items():
            data = subprocess.check_output(['git', 'show', f"{manifest['baseline']}:{name}"], cwd=ROOT)
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected)

    def test_complete_runtime_manifest_fits(self):
        manifest = json.loads((ROOT/MANIFEST).read_text())
        diff = subprocess.check_output(['git', 'diff', '--no-ext-diff', manifest['baseline'], '--', *manifest['shared']], cwd=ROOT, text=True)
        self.assertLessEqual(added_lines(diff), manifest['shared_allocation'])
        self.assertLessEqual(audit(ROOT/PACKAGE, manifest, diff), 1000)


if __name__ == '__main__':
    unittest.main()
