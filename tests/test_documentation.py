import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile


spec = importlib.util.spec_from_file_location(
    'documentation_check', Path(__file__).resolve().parents[1] / 'scripts/check-documentation.py')
documentation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(documentation)


class DocumentationTests(unittest.TestCase):
    def test_install_command_is_default_and_literal(self):
        command = 'python -m pip install nstdata-ai-crawl'
        self.assertEqual(documentation.documented_install('```sh\n' + command + '\n```'),
                         command.split())
        for text in [command + '==1.0.0', command + ' --extra-index-url https://other.invalid',
                     command + '; echo ignored', 'python -m pip install /local.whl']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                documentation.documented_install('```sh\n' + text + '\n```')

    def test_wheel_metadata_requires_one_distribution(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / 'fixture.whl'
            for entries in [[], ['one.dist-info/METADATA', 'two.dist-info/METADATA']]:
                with ZipFile(path, 'w') as archive:
                    for name in entries:
                        archive.writestr(name, 'Name: fixture\nVersion: 1.0.0\n')
                with self.assertRaises(ValueError):
                    documentation.wheel_metadata(path)
            with ZipFile(path, 'w') as archive:
                archive.writestr('fixture.dist-info/METADATA', 'Name: fixture\nVersion: 1.0.0\n')
                archive.writestr('fixture/_vendor/other.dist-info/METADATA',
                                 'Name: other\nVersion: 2.0.0\n')
            self.assertEqual(documentation.wheel_metadata(path), ('fixture', '1.0.0'))
