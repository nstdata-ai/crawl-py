"""Check one reviewed build before and after the official PyPI publishing action."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPRedirectHandler, Request


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'nstdata-ai/crawl-py'
NAME = 'nstdata-ai-crawl'
ENVIRONMENT = 'pypi-production'


class ReleaseError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReleaseError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def execute(arguments, cwd=ROOT):
    try:
        return subprocess.run(arguments, cwd=cwd, check=True, capture_output=True,
                              text=True, timeout=180).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise ReleaseError('Release command failed; inspect this stage before another run') from error


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def request_json(url, token=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'Nstdata-release-check'}
    if token:
        headers.update(Authorization='Bearer ' + token,
                       **{'X-GitHub-Api-Version': '2026-03-10'})
    try:
        with build_opener(NoRedirect()).open(Request(url, headers=headers), timeout=20) as response:
            require(response.status == 200, 'Release metadata returned HTTP ' + str(response.status))
            data = response.read(1048577)
            require(len(data) <= 1048576, 'Release metadata exceeds the response limit')
            return {'status': response.status, 'data': json.loads(data)}
    except HTTPError as error:
        status = error.code
        error.close()
        if status == 404:
            return {'status': 404}
        raise ReleaseError('Release metadata returned HTTP ' + str(status)) from error


def validate_source(environment, root=ROOT, command=execute):
    require(environment.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'Manual dispatch required')
    require(environment.get('GITHUB_REPOSITORY') == REPOSITORY, 'Wrong release repository')
    require(environment.get('GITHUB_REF') == 'refs/heads/main', 'Release must use main')
    commit = environment.get('RELEASE_COMMIT', '')
    version = environment.get('RELEASE_VERSION', '')
    require(re.fullmatch(r'[a-f0-9]{40}', commit), 'Full reviewed commit required')
    require(commit == environment.get('GITHUB_SHA'), 'Reviewed commit must match workflow commit')
    require(re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version),
            'Stable release version required')
    calls = [node for node in ast.walk(ast.parse((root / 'setup.py').read_text(encoding='utf-8')))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id == 'setup']
    require(len(calls) == 1, 'Expected one package metadata definition')
    metadata = {item.arg: ast.literal_eval(item.value) for item in calls[0].keywords
                if item.arg in ('name', 'version')}
    require(metadata == {'name': NAME, 'version': version}, 'Source name or version mismatch')
    require(command(['git', 'rev-parse', 'HEAD'], root).strip() == commit, 'Source HEAD changed')
    require(not command(['git', 'status', '--porcelain', '--untracked-files=no'], root).strip(),
            'Tracked source changed')
    require(not any(environment.get(name) for name in
                    ('TWINE_PASSWORD', 'PYPI_TOKEN', 'PYPI_API_TOKEN')),
            'Use trusted publishing without a stored PyPI token')


def check_environment(environment, fetch=request_json):
    token = environment.get('GH_TOKEN')
    require(token, 'GitHub read token required')
    url = 'https://api.github.com/repos/' + REPOSITORY + '/environments/' + ENVIRONMENT
    result = fetch(url, token)
    require(result['status'] == 200, 'Configure pypi-production before dispatch')
    settings = result['data']
    require(settings.get('can_admins_bypass') is False, 'Disable environment administrator bypass')
    require(any(rule.get('type') == 'required_reviewers' and rule.get('reviewers')
                for rule in settings.get('protection_rules', [])), 'Required reviewers must be configured')
    policy = settings.get('deployment_branch_policy') or {}
    require(policy.get('custom_branch_policies') is True and policy.get('protected_branches') is False,
            'Use selected deployment branches')
    policies = fetch(url + '/deployment-branch-policies?per_page=100', token)
    require(policies['status'] == 200, 'Cannot inspect environment branch rules')
    branches = policies['data'].get('branch_policies', [])
    require(policies['data'].get('total_count') == 1 and len(branches) == 1
            and branches[0].get('name') == 'main' and branches[0].get('type') == 'branch',
            'Allow only the main branch in pypi-production')


def filenames(version):
    prefix = 'nstdata_ai_crawl-' + version
    return {prefix + '-py3-none-any.whl', prefix + '.tar.gz'}


def regular_file(path):
    require(path.is_file() and not path.is_symlink(), 'Release files must be regular files')
    return path.read_bytes()


def verify_artifacts(directory, environment, allow_attestations=False):
    require(directory.is_dir() and not directory.is_symlink(), 'Release directory is missing or linked')
    require({path.name for path in directory.iterdir()} == {'dist', 'manifest.json'},
            'Unexpected release directory entries')
    contents = regular_file(directory / 'manifest.json')
    require(digest(contents) == environment.get('RELEASE_MANIFEST_SHA256'),
            'Manifest changed after checks')
    manifest = json.loads(contents)
    require(manifest.get('name') == NAME and manifest.get('version') == environment['RELEASE_VERSION']
            and manifest.get('commit') == environment['GITHUB_SHA'], 'Manifest identity mismatch')
    expected = filenames(environment['RELEASE_VERSION'])
    require(isinstance(manifest.get('files'), dict) and set(manifest['files']) == expected,
            'Manifest must contain exactly one wheel and one sdist')
    folder = directory / 'dist'
    require(folder.is_dir() and not folder.is_symlink(), 'Distribution directory is missing or linked')
    extras = {path.name for path in folder.iterdir()} - expected
    allowed = {name + '.publish.attestation' for name in expected} if allow_attestations else set()
    require(extras <= allowed, 'Unexpected distribution files')
    for path in folder.iterdir():
        data = regular_file(path)
        if path.name in expected:
            require(digest(data) == manifest['files'][path.name], 'Archive changed after checks')
    require(expected <= {path.name for path in folder.iterdir()}, 'Distribution file missing')
    return manifest


def check_registry(version, files=None, fetch=request_json):
    result = fetch('https://pypi.org/pypi/' + NAME + '/' + version + '/json')
    if files is None:
        require(result['status'] == 404, 'Version already exists; inspect PyPI instead of republishing')
        return
    require(result['status'] == 200, 'Published version is not visible; inspect before another run')
    data = result['data']
    require(data.get('info', {}).get('name') == NAME and data['info'].get('version') == version,
            'Published package identity differs')
    entries = data.get('urls', [])
    require(len(entries) == 2 and {item.get('filename') for item in entries} == set(files),
            'Published file set differs')
    for entry in entries:
        require(entry.get('digests', {}).get('sha256') == files[entry['filename']]
                and entry.get('yanked') is False, 'Published file integrity or availability differs')


def main(mode, directory, environment=None, fetch=request_json, command=execute, root=ROOT):
    environment = os.environ if environment is None else environment
    require(mode in ('prepare', 'verify', 'published'), 'Use prepare, verify or published')
    require(directory is not None and directory.is_absolute(), 'Absolute release directory required')
    validate_source(environment, root, command)
    if mode == 'prepare':
        require(not directory.exists(), 'Use a fresh release directory')
        check_environment(environment, fetch)
        check_registry(environment['RELEASE_VERSION'], fetch=fetch)
        directory.mkdir(parents=True)
        folder = directory / 'dist'
        command([sys.executable, '-m', 'build', '--outdir', str(folder)], root)
        require(folder.is_dir() and not folder.is_symlink() and {path.name for path in folder.iterdir()} ==
                filenames(environment['RELEASE_VERSION']), 'Build must produce exactly one wheel and one sdist')
        command([sys.executable, 'scripts/check-package.py', str(folder)], root)
        manifest = {'name': NAME, 'version': environment['RELEASE_VERSION'],
                    'commit': environment['GITHUB_SHA'],
                    'files': {path.name: digest(regular_file(path)) for path in sorted(folder.iterdir())}}
        content = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
        (directory / 'manifest.json').write_bytes(content)
        with open(environment['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            stream.write('manifest_sha256=' + digest(content) + '\n')
        with open(environment['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write('## Distributions ready for approval\n\nCommit: `' + manifest['commit']
                         + '`\n\nVersion: `' + manifest['version'] + '`\n\n')
            for name, sha256 in manifest['files'].items():
                stream.write('- `' + name + '` SHA256: `' + sha256 + '`\n')
    else:
        manifest = verify_artifacts(directory, environment, allow_attestations=mode == 'published')
        if mode == 'verify':
            check_environment(environment, fetch)
            check_registry(manifest['version'], fetch=fetch)
        else:
            check_registry(manifest['version'], manifest['files'], fetch)
            with tempfile.TemporaryDirectory(prefix='nstdata-pypi-install-') as temporary:
                location = Path(temporary)
                command([sys.executable, '-m', 'venv', str(location / 'venv')], location)
                python = location / 'venv' / 'bin' / 'python'
                command([str(python), '-m', 'pip', '--isolated', '--disable-pip-version-check',
                         'install', '--no-input', '--no-cache-dir', '--retries', '0',
                         '--index-url', 'https://pypi.org/simple', NAME], location)
                program = ("import importlib.metadata, pathlib, sysconfig, nstdata_ai_crawl as sdk; "
                           "assert importlib.metadata.version('nstdata-ai-crawl') == "
                           + repr(manifest['version']) + "; "
                           "assert pathlib.Path(sdk.__file__).resolve().is_relative_to("
                           "pathlib.Path(sysconfig.get_paths()['purelib']).resolve()); "
                           "assert all(hasattr(sdk, name) for name in "
                           "('NstDataClient', 'NstDataApiError', 'ScrapeRequestDto'))")
                command([str(python), '-I', '-c', program], location)
                command([str(python), '-m', 'pip', '--isolated', 'check'], location)
            with open(environment['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
                stream.write('\nPublished `' + NAME + '==' + manifest['version']
                             + '`; registry hashes and clean public installation passed.\n')


if __name__ == '__main__':
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else None,
             Path(sys.argv[2]) if len(sys.argv) > 2 else None)
    except Exception as error:
        print(str(error) if isinstance(error, ReleaseError)
              else 'Release check failed (' + type(error).__name__ + ')', file=sys.stderr)
        print('Release stopped. Inspect PyPI, including a possible partial release, before another run.',
              file=sys.stderr)
        raise SystemExit(1)
