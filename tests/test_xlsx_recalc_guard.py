"""Real archive/CLI preflight fixtures; LibreOffice and workbook loading are mocked."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class RecalcGuardTests(unittest.TestCase):
    def module(self):
        path = Path(os.environ.get('RECALC_TEST_SCRIPT', ROOT / '.claude/skills/xlsx/scripts/recalc.py'))
        dependencies = {
            'openpyxl': types.SimpleNamespace(load_workbook=Mock()),
            'office.soffice': types.SimpleNamespace(get_soffice_env=Mock(return_value={})),
        }
        with patch.dict(sys.modules, dependencies):
            spec = importlib.util.spec_from_file_location('recalc_guard', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module

    def test_external_parts_and_relationships_block_before_macro_setup_without_rewrite(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'linked.xlsx'
            for name, body in [
                ('xl/externalLinks/externalLink1.xml', '<externalLink/>'),
                ('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Type="http://example.test/externalLink" Target="linked.xml"/></Relationships>'),
            ]:
                with ZipFile(path, 'w') as archive:
                    archive.writestr(name, body)
                before = path.read_bytes()
                with patch.object(module, 'setup_libreoffice_macro', return_value=False) as setup:
                    result = module.recalc(path)
                    self.assertIn('External workbook links', result['error'])
                    setup.assert_not_called()
                self.assertEqual(path.read_bytes(), before)
                with patch.object(module, 'setup_libreoffice_macro', return_value=False) as setup:
                    self.assertIn('Failed to setup', module.recalc(path, force=True)['error'])
                    setup.assert_called_once_with()
                self.assertEqual(path.read_bytes(), before)

    def test_normal_hyperlinks_are_allowed_and_malformed_archives_fail_closed(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'book.xlsx'
            with ZipFile(path, 'w') as archive:
                archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Type="http://example.test/hyperlink" TargetMode="External" Target="https://example.test/"/></Relationships>')
            self.assertFalse(module.external_workbook_links(path))
            path.write_bytes(b'not a zip workbook')
            for force in [False, True]:
                with patch.object(module, 'setup_libreoffice_macro', return_value=False) as setup:
                    self.assertIn('Cannot verify', module.recalc(path, force=force)['error'])
                    setup.assert_not_called()
            # An early external-link finding must not conceal later bad XML.
            with ZipFile(path, 'w') as archive:
                archive.writestr('xl/externalLinks/externalLink1.xml', '<externalLink/>')
                archive.writestr('xl/_rels/workbook.xml.rels', '<broken')
            with patch.object(module, 'setup_libreoffice_macro', return_value=False) as setup:
                self.assertIn('Cannot verify', module.recalc(path, force=True)['error'])
                setup.assert_not_called()

    def test_force_and_timeout_cli_contract(self):
        module = self.module()
        for arguments, seconds, force in [
            (['book.xlsx', '--force'], 30, True),
            (['book.xlsx', '45', '--force'], 45, True),
            (['book.xlsx'], 30, False),
        ]:
            with patch.object(sys, 'argv', ['recalc.py'] + arguments), patch.object(module, 'recalc', return_value={'status': 'success'}) as recalc:
                module.main()
                recalc.assert_called_once_with('book.xlsx', seconds, force=force)


if __name__ == '__main__':
    unittest.main()
