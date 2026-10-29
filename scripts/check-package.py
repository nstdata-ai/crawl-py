"""Inspect artifacts and exercise an isolated wheel install without API calls."""
from email.parser import BytesParser
import ast
import base64
import csv
import configparser
import hashlib
import io
import runpy
import stat
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from zipfile import ZipFile
from urllib.parse import urljoin

if not __debug__:
    raise RuntimeError('Run package checks without Python optimization')

root = Path(__file__).resolve().parents[1]
setup_call = next(node for node in ast.walk(ast.parse((root / 'setup.py').read_text(encoding='utf-8')))
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'setup')
version = next(ast.literal_eval(item.value) for item in setup_call.keywords if item.arg == 'version')
assert re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version), 'Stable version required'
library_files = ['nstdata_ai_crawl/' + name for name in ('__init__.py', 'client.py', 'constants.py', 'models.py')]
readme = (root / 'README.md').read_text(encoding='utf-8')
documentation = ['README.md', 'README_zh.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'SECURITY.md',
                 'docs/guide.md', 'docs/guide_zh.md']


def check_description(description):
    links = r'\[[^\]\n]+\]\(([^)\n]+)\)'
    assert re.findall(links, description) == [urljoin('https://github.com/nstdata-ai/crawl-py/blob/main/README.md', link)
                                             for link in re.findall(links, readme)]
    assert re.sub(links, '[link]', description).strip() == re.sub(links, '[link]', readme).strip()


commands = []
examples = []
for name in ('README.md', 'README_zh.md'):
    text = (root / name).read_text(encoding='utf-8')
    assert re.search(r'^python -m pip install nstdata-ai-crawl$', text, re.MULTILINE), 'README install command mismatch'
    commands.append(re.findall(r'```sh\n([\s\S]*?)```', text))
    examples.append(re.findall(r'```python\n([\s\S]*?)```', text))
assert commands[0] == commands[1], 'Bilingual install commands differ'
assert examples[0] == examples[1], 'Bilingual Python examples differ'
assert re.findall(r'```python\n([\s\S]*?)```', (root / 'docs/guide.md').read_text(encoding='utf-8')) == \
       re.findall(r'```python\n([\s\S]*?)```', (root / 'docs/guide_zh.md').read_text(encoding='utf-8')), 'Bilingual guide programs differ'
for name in documentation:
    source = root / name
    for target in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', source.read_text(encoding='utf-8')):
        if re.match(r'^[a-z]+:', target):
            continue
        relative, _, anchor = target.partition('#')
        linked = source.parent / relative if relative else source
        assert linked.is_file(), 'Missing documentation link: ' + target
        if anchor:
            slugs = [re.sub(r'[^\w -]', '', heading.lower()).replace(' ', '-')
                     for heading in re.findall(r'^#+ (.+)$', linked.read_text(encoding='utf-8'), re.MULTILINE)]
            assert anchor in slugs, 'Missing documentation anchor: ' + target
assert re.search(r'^## ' + re.escape(version) + r'$', (root / 'CHANGELOG.md').read_text(encoding='utf-8'), re.MULTILINE), 'CHANGELOG version mismatch'
folder = Path(sys.argv[1] if len(sys.argv) > 1 else 'dist')
assert folder.is_dir() and not folder.is_symlink(), 'Expected a regular artifact directory'
folder = folder.resolve()
wheels = list(folder.glob('*.whl'))
sources = list(folder.glob('*.tar.gz'))
assert len(wheels) == len(sources) == 1, 'Expected one wheel and one sdist'
assert all(p.is_file() and not p.is_symlink() for p in [*wheels, *sources]), 'Artifacts must be regular files'
with ZipFile(wheels[0]) as archive:
    names = archive.namelist()
    dist_info = 'nstdata_ai_crawl-' + version + '.dist-info/'
    expected = set(library_files) | {dist_info + name for name in
        ('METADATA', 'WHEEL', 'top_level.txt', 'RECORD', 'licenses/LICENSE')}
    assert set(names) == expected and len(names) == len(expected), 'Unexpected or duplicate wheel files'
    assert all(stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG)
               for item in archive.infolist()), 'Wheel contains non-regular files'
    rows = list(csv.reader(io.StringIO(archive.read(dist_info + 'RECORD').decode('utf-8'))))
    assert len(rows) == len(expected) and {row[0] for row in rows} == expected, 'Invalid wheel RECORD'
    for name, digest, size in rows:
        if name == dist_info + 'RECORD':
            assert digest == size == '', 'Invalid RECORD self entry'
        else:
            data = archive.read(name)
            actual = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode('ascii')
            assert digest == 'sha256=' + actual and size == str(len(data)), 'Wheel RECORD differs: ' + name
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
    check_description(metadata.get_payload(decode=True).decode('utf-8'))
    assert any(x.endswith('/LICENSE') for x in names)
with tarfile.open(sources[0]) as archive:
    names = archive.getnames()
    assert len(names) == len(set(names)), 'Duplicate sdist members'
    assert all(item.isfile() or item.isdir() for item in archive.getmembers()), 'sdist contains non-regular members'
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
    check_description(metadata.get_payload(decode=True).decode('utf-8'))
    source_files = set(library_files + ['main.py', 'setup.py', 'pyproject.toml',
                                       'MANIFEST.in', 'requirements.txt', 'LICENSE', *documentation])
    source_files.update(path.relative_to(root).as_posix() for folder_name in ('scripts', 'tests')
                        for path in (root / folder_name).glob('*.py'))
    egg_info = {'PKG-INFO', 'SOURCES.txt', 'dependency_links.txt', 'requires.txt', 'top_level.txt'}
    allowed = source_files | {'PKG-INFO', 'setup.cfg'} | {'nstdata_ai_crawl.egg-info/' + name for name in egg_info}
    assert {item.name[len(prefix):] for item in archive.getmembers() if item.isfile()} == allowed, 'Unexpected sdist files'
    generated = configparser.ConfigParser()
    generated.read_string(archive.extractfile(prefix + 'setup.cfg').read().decode('utf-8'))
    assert generated.sections() == ['egg_info'] and dict(generated['egg_info']) == {'tag_build': '', 'tag_date': '0'}, 'Unexpected generated setup configuration'
    directories = {prefix.rstrip('/')} | {str(parent) for name in allowed
        for parent in (Path(prefix) / name).parents if str(parent) != '.'}
    assert all(item.name.rstrip('/') in directories for item in archive.getmembers() if item.isdir()), 'Unexpected sdist directories'
    for name in source_files:
        assert archive.extractfile(prefix + name).read() == (root / name).read_bytes(), 'sdist source/document mismatch: ' + name
with tempfile.TemporaryDirectory(prefix='nstdata-crawl-wheel-') as temporary:
    checks = Path(temporary)
    installed = checks / 'installed'
    subprocess.run([
        sys.executable, '-m', 'pip', '--disable-pip-version-check', 'install',
        '--no-index', '--no-deps', '--no-compile', '--target', str(installed), str(wheels[0].resolve()),
    ], cwd=checks, check=True)
    (checks / 'tests').mkdir()
    for name in ('test_client.py', 'test_examples.py', 'test_http.py'):
        shutil.copyfile(root / 'tests' / name, checks / 'tests' / name)
    shutil.copytree(root / 'docs', checks / 'docs')
    for name in ('main.py', 'README.md', 'README_zh.md'):
        shutil.copyfile(root / name, checks / name)
    subprocess.run([sys.executable, '-I', '-B', '-c', '''
import sys
from pathlib import Path
import unittest
import socket

connect = socket.socket.connect
def loopback_only(self, address):
    if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise RuntimeError('Only loopback is allowed in installed SDK tests')
    return connect(self, address)
socket.socket.connect = loopback_only

installed = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(installed))
import nstdata_ai_crawl
assert Path(nstdata_ai_crawl.__file__).resolve().is_relative_to(installed), 'Wheel import was shadowed'
suite = unittest.defaultTestLoader.discover(sys.argv[2])
result = unittest.TextTestRunner(verbosity=2).run(suite)
if result.testsRun == 0 or result.skipped or not result.wasSuccessful():
    raise SystemExit(1)
''', str(installed), str(checks / 'tests')], cwd=checks, check=True)
runpy.run_path(str(root / 'scripts/check-documentation.py'))['check_documented_install'](root, wheels[0])
print('PASS: exact wheel/sdist metadata and source bytes; installed SDK regressions; bilingual native pip installs with complete dependencies')
