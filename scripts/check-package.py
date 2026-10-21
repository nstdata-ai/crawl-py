"""Inspect artifacts and exercise an isolated wheel install without API calls."""
from email.parser import BytesParser
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from zipfile import ZipFile

root = Path(__file__).resolve().parents[1]
version = '1.0.0'
library_files = ['nstdata_ai_crawl/' + name for name in ('__init__.py', 'client.py', 'constants.py', 'models.py')]
readme = (root / 'README.md').read_text(encoding='utf-8')
commands = []
examples = []
for name in ('README.md', 'README_zh.md'):
    text = (root / name).read_text(encoding='utf-8')
    assert 'python -m pip install nstdata-ai-crawl==' + version in text, 'README version mismatch'
    commands.append(re.findall(r'```sh\n([\s\S]*?)```', text))
    examples.append(re.findall(r'```python\n([\s\S]*?)```', text))
assert commands[0] == commands[1], 'Bilingual install commands differ'
assert examples[0] == examples[1], 'Bilingual Python examples differ'
assert '## ' + version + ' — Unreleased' in (root / 'CHANGELOG.md').read_text(), 'CHANGELOG version mismatch'
folder = Path(sys.argv[1] if len(sys.argv) > 1 else 'dist')
wheels = list(folder.glob('*.whl'))
sources = list(folder.glob('*.tar.gz'))
assert len(wheels) == len(sources) == 1, 'Expected one wheel and one sdist'
with ZipFile(wheels[0]) as archive:
    names = archive.namelist()
    assert {x for x in names if x.endswith('.py')} == set(library_files)
    for name in library_files:
        assert archive.read(name) == (root / name).read_bytes(), 'wheel source mismatch: ' + name
    assert all('.env' not in x and '_planning' not in x and not x.endswith('.pyc') for x in names)
    metadata = BytesParser().parsebytes(archive.read(next(x for x in names if x.endswith('/METADATA'))))
    assert metadata['Name'] == 'nstdata-ai-crawl'
    assert metadata['Version'] == version
    assert metadata['Requires-Python'] == '>=3.10'
    assert metadata['License-Expression'] == 'MIT'
    assert metadata.get_all('License-File') == ['LICENSE']
    assert metadata.get_all('Requires-Dist') == ['requests<3,>=2.34.2']
    assert metadata.get_payload(decode=True).decode('utf-8').strip() == readme.strip(), 'Wheel README mismatch'
    assert any(x.endswith('/LICENSE') for x in names)
with tarfile.open(sources[0]) as archive:
    names = archive.getnames()
    assert all('.env' not in x and '_planning' not in x and not x.endswith('.pyc') for x in names)
    assert any(x.endswith('/tests/test_http.py') for x in names)
    assert any(x.endswith('/README_zh.md') for x in names)
    prefix = 'nstdata_ai_crawl-' + version + '/'
    assert all(x == prefix.rstrip('/') or x.startswith(prefix) for x in names), 'sdist version mismatch'
    metadata = BytesParser().parsebytes(archive.extractfile(prefix + 'PKG-INFO').read())
    assert metadata['Version'] == version
    assert metadata['Requires-Python'] == '>=3.10'
    assert metadata['License-Expression'] == 'MIT'
    assert metadata.get_all('License-File') == ['LICENSE']
    assert metadata.get_all('Requires-Dist') == ['requests<3,>=2.34.2']
    assert metadata.get_payload(decode=True).decode('utf-8').strip() == readme.strip(), 'sdist README mismatch'
    for name in library_files + ['main.py', 'scripts/check-package.py', 'tests/test_client.py', 'tests/test_examples.py', 'tests/test_http.py',
                                 'README.md', 'README_zh.md', 'CHANGELOG.md', 'CONTRIBUTING.md']:
        assert archive.extractfile(prefix + name).read() == (root / name).read_bytes(), 'sdist source/document mismatch: ' + name
with tempfile.TemporaryDirectory(prefix='nstdata-crawl-wheel-') as temporary:
    checks = Path(temporary)
    installed = checks / 'installed'
    subprocess.run([
        sys.executable, '-m', 'pip', '--disable-pip-version-check', 'install',
        '--no-index', '--no-deps', '--no-compile', '--target', str(installed), str(wheels[0].resolve()),
    ], cwd=checks, check=True)
    shutil.copytree(root / 'tests', checks / 'tests', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('main.py', 'README.md', 'README_zh.md'):
        shutil.copyfile(root / name, checks / name)
    subprocess.run([sys.executable, '-I', '-B', '-c', '''
import sys
from pathlib import Path
import unittest

installed = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(installed))
import nstdata_ai_crawl
assert Path(nstdata_ai_crawl.__file__).resolve().is_relative_to(installed), 'Wheel import was shadowed'
suite = unittest.defaultTestLoader.discover(sys.argv[2])
result = unittest.TextTestRunner(verbosity=2).run(suite)
if result.testsRun == 0 or not result.wasSuccessful():
    raise SystemExit(1)
''', str(installed), str(checks / 'tests')], cwd=checks, check=True)
print('PASS: wheel/sdist contents and metadata; isolated target install, import origin and installed-wheel regressions (existing runtime dependencies)')
