"""Exercise documented pip installation against an isolated package index."""
from email.parser import BytesParser
import hashlib
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import quote, unquote, urlsplit
from zipfile import ZipFile


def documented_install(text):
    commands = [shlex.split(block.strip()) for block in
                re.findall(r'```sh\n([\s\S]*?)```', text)
                if block.strip().startswith('python -m pip install')]
    if commands != [['python', '-m', 'pip', 'install', 'nstdata-ai-crawl']]:
        raise ValueError('README must provide one default pip installation command')
    return commands[0]


def wheel_metadata(archive):
    with ZipFile(archive) as wheel:
        names = [name for name in wheel.namelist()
                 if name.count('/') == 1 and name.endswith('.dist-info/METADATA')]
        if len(names) != 1:
            raise ValueError('Wheel metadata is missing or ambiguous')
        metadata = BytesParser().parsebytes(wheel.read(names[0]))
    return metadata['Name'], metadata['Version']


def _run(command, cwd, environment):
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True,
                            text=True, timeout=120)
    if result.returncode:
        raise RuntimeError('Installation check command failed (exit '
                           + str(result.returncode) + '): ' + ' '.join(command[:4]))
    return result.stdout


def check_documented_install(root, wheel, wheelhouse=None):
    root, wheel = Path(root), Path(wheel).resolve()
    name, version = wheel_metadata(wheel)
    if name != 'nstdata-ai-crawl':
        raise ValueError('Unexpected SDK wheel name')
    commands = [documented_install((root / readme).read_text(encoding='utf-8'))
                for readme in ('README.md', 'README_zh.md')]
    environment = {key: os.environ[key] for key in ('PATH', 'TMPDIR', 'SystemRoot')
                   if key in os.environ}
    environment.update(PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK='1',
                       PIP_NO_INPUT='1', PIP_RETRIES='0', PIP_KEYRING_PROVIDER='disabled',
                       NETRC=os.devnull, PYTHONDONTWRITEBYTECODE='1')
    wheelhouse = wheelhouse or os.environ.get('NSTDATA_PYTHON_WHEELHOUSE')
    with TemporaryDirectory(prefix='nstdata-pip-docs-') as temporary:
        temporary = Path(temporary)
        if wheelhouse is None:
            wheelhouse = temporary / 'downloads'
            wheelhouse.mkdir()
            _run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
                  '--index-url', 'https://pypi.org/simple', '--dest', str(wheelhouse),
                  str(wheel)], temporary, environment)
        archives = {}
        for archive in [wheel, *sorted(Path(wheelhouse).glob('*.whl'))]:
            distribution, release = wheel_metadata(archive)
            if distribution == name and archive != wheel:
                continue
            archives[archive.name] = {'path': archive, 'name': distribution,
                                      'version': release,
                                      'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
        requests = []

        class Index(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                path = unquote(urlsplit(self.path).path)
                requests.append((path, bool(self.headers.get('Authorization'))))
                if self.headers.get('Authorization'):
                    self.send_error(403)
                    return
                if path.startswith('/simple/'):
                    project = path[len('/simple/'):].strip('/')
                    matches = [(filename, item) for filename, item in archives.items()
                               if re.sub(r'[-_.]+', '-', item['name']).lower() == project]
                    body = '\n'.join('<a href="/files/' + quote(filename) + '#sha256='
                                     + item['sha256'] + '">' + escape(filename) + '</a>'
                                     for filename, item in matches).encode()
                    content_type = 'text/html; charset=utf-8'
                elif path.startswith('/files/') and path[7:] in archives:
                    body = archives[path[7:]]['path'].read_bytes()
                    content_type = 'application/octet-stream'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        guard = temporary / 'guard'
        guard.mkdir()
        (guard / 'sitecustomize.py').write_text('''import socket
_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_getaddrinfo = socket.getaddrinfo
def _allowed(address):
    if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1'):
        raise OSError('DOCUMENTATION_NETWORK_BLOCKED')
def connect(self, address):
    _allowed(address)
    return _connect(self, address)
def connect_ex(self, address):
    _allowed(address)
    return _connect_ex(self, address)
def getaddrinfo(host, *args, **kwargs):
    if host not in ('127.0.0.1', '::1', 'localhost'):
        raise OSError('DOCUMENTATION_NETWORK_BLOCKED')
    return _getaddrinfo(host, *args, **kwargs)
socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.getaddrinfo = getaddrinfo
''', encoding='utf-8')
        index = ThreadingHTTPServer(('127.0.0.1', 0), Index)
        index.daemon_threads = True
        thread = Thread(target=index.serve_forever, daemon=True)
        thread.start()
        installed = []
        try:
            for number, command in enumerate(commands):
                project = temporary / ('project-' + str(number))
                project.mkdir()
                venv = project / 'venv'
                _run([sys.executable, '-m', 'venv', str(venv)], project, environment)
                python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
                assert 'include-system-site-packages = false' in (venv / 'pyvenv.cfg').read_text()
                local = dict(environment, PATH=str(python.parent) + os.pathsep
                             + environment.get('PATH', ''), PYTHONPATH=str(guard),
                             PIP_INDEX_URL='http://127.0.0.1:' + str(index.server_port)
                             + '/simple/', PIP_NO_CACHE_DIR='1')
                _run([str(python), '-c', '''import socket
try:
    socket.create_connection(('198.51.100.1', 80), timeout=0.01)
except OSError as error:
    assert str(error) == 'DOCUMENTATION_NETWORK_BLOCKED'
else:
    raise AssertionError('External network guard missing')
'''], project, local)
                before = _run([str(python), '-c', 'import importlib.metadata,json; '
                               'print(json.dumps([d.metadata["Name"] for d in '
                               'importlib.metadata.distributions()]))'], project, local)
                _run(command, project, local)
                _run([str(python), '-m', 'pip', 'check'], project, local)
                check = '''import importlib.metadata as metadata,json,sys,sysconfig
from pathlib import Path
from zipfile import ZipFile
base = Path(sysconfig.get_paths()['purelib']).resolve()
assert Path(sys.prefix).resolve() == Path(sys.argv[1]).resolve()
assert sys.prefix != sys.base_prefix
bootstrap = json.loads(sys.argv[2])
archives = json.loads(sys.argv[3])
verified = []
for distribution in metadata.distributions():
    name = distribution.metadata['Name']
    if name in bootstrap:
        continue
    choices = [a for a in archives if a['name'] == name and a['version'] == distribution.version]
    assert len(choices) == 1, 'Unexpected installed distribution: ' + name
    with ZipFile(choices[0]['path']) as archive:
        for filename in archive.namelist():
            if filename.endswith('/') or filename.endswith('.dist-info/RECORD'):
                continue
            archived_name = filename
            parts = Path(filename).parts
            if parts[0].endswith('.data'):
                if parts[1] not in ('purelib', 'platlib'):
                    continue
                filename = str(Path(*parts[2:]))
            destination = base / filename
            assert destination.resolve().is_relative_to(base)
            assert destination.read_bytes() == archive.read(archived_name), filename
    verified.append([name, distribution.version])
import nstdata_ai_crawl
assert Path(nstdata_ai_crawl.__file__).resolve().is_relative_to(base)
assert metadata.version('nstdata-ai-crawl') == sys.argv[4]
print(json.dumps(verified))
'''
                entries = [dict(item, path=str(item['path'])) for item in archives.values()]
                verified = _run([str(python), '-c', check, str(venv), before,
                                 json.dumps(entries), version], project, local)
                installed.append(json.loads(verified))
            assert requests and not any(auth for _, auth in requests)
            assert sum(path == '/files/' + wheel.name for path, _ in requests) == 2
        finally:
            index.shutdown()
            index.server_close()
            thread.join(timeout=5)
        print('PASS: bilingual default pip commands; two clean virtual environments, '
              'complete dependencies, import origin and installed wheel bytes')
        return {'version': version, 'installations': installed, 'requests': len(requests),
                'public_index_verified': False}


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python scripts/check-documentation.py /path/to/sdk.whl')
    check_documented_install(Path(__file__).resolve().parents[1], sys.argv[1])
