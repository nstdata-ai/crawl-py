"""Exercise release guards with synthetic metadata; never upload distributions."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/release.py'
spec = importlib.util.spec_from_file_location('crawl_release', SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'setup.py').write_text("setup(name='nstdata-ai-crawl', version='1.0.0')\n")
        self.environment = {
            'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REPOSITORY': release.REPOSITORY,
            'GITHUB_REF': 'refs/heads/main', 'GITHUB_SHA': 'a' * 40, 'RELEASE_COMMIT': 'a' * 40,
            'RELEASE_VERSION': '1.0.0', 'GH_TOKEN': 'fixture-read-token',
            'GITHUB_OUTPUT': str(self.root / 'output'),
            'GITHUB_STEP_SUMMARY': str(self.root / 'summary'),
        }
        self.settings = {
            'can_admins_bypass': False,
            'protection_rules': [{'type': 'required_reviewers', 'reviewers': [{'id': 1}]}],
            'deployment_branch_policy': {'custom_branch_policies': True, 'protected_branches': False},
        }
        self.policies = {'total_count': 1, 'branch_policies': [{'id': 2, 'name': 'main', 'type': 'branch'}]}
        self.registry = {'status': 404}
        self.calls = []
        self.requests = []

    def command(self, arguments, cwd):
        self.calls.append((arguments, cwd))
        if arguments[:3] == ['git', 'rev-parse', 'HEAD']:
            return 'a' * 40 + '\n'
        if arguments[:2] == ['git', 'status']:
            return ''
        if arguments[1:3] == ['-m', 'build']:
            folder = Path(arguments[-1])
            folder.mkdir()
            for filename in release.filenames('1.0.0'):
                (folder / filename).write_bytes(filename.encode())
        if arguments[1] == 'scripts/check-package.py':
            self.assertFalse((Path(arguments[-1]).parent / 'manifest.json').exists())
        return ''

    def fetch(self, url, token=None):
        self.requests.append((url, token))
        if 'deployment-branch-policies' in url:
            return {'status': 200, 'data': self.policies}
        if 'api.github.com' in url:
            return {'status': 200, 'data': self.settings}
        self.assertIsNone(token)
        return self.registry

    def prepare(self):
        directory = self.root / 'release'
        release.main('prepare', directory, self.environment, self.fetch, self.command, self.root)
        self.environment['RELEASE_MANIFEST_SHA256'] = release.digest((directory / 'manifest.json').read_bytes())
        return directory

    def published_metadata(self, manifest):
        return {'status': 200, 'data': {
            'info': {'name': release.NAME, 'version': '1.0.0'},
            'urls': [{'filename': name, 'digests': {'sha256': digest}, 'yanked': False}
                     for name, digest in manifest['files'].items()],
        }}

    def test_source_rejects_wrong_identity_version_commit_or_stored_token(self):
        release.validate_source(self.environment, self.root, self.command)
        changes = {'GITHUB_EVENT_NAME': 'push', 'GITHUB_REPOSITORY': 'other/crawl-py',
                   'GITHUB_REF': 'refs/tags/v1.0.0', 'RELEASE_COMMIT': 'b' * 40,
                   'RELEASE_VERSION': '1.0.0rc1', 'TWINE_PASSWORD': 'private-fixture-token'}
        for key, value in changes.items():
            with self.subTest(key=key), self.assertRaises(release.ReleaseError):
                release.validate_source({**self.environment, key: value}, self.root, self.command)
        (self.root / 'setup.py').write_text("setup(name='other-package', version='1.0.0')\n")
        with self.assertRaises(release.ReleaseError):
            release.validate_source(self.environment, self.root, self.command)

    def test_environment_requires_reviewers_no_bypass_and_only_main_branch(self):
        release.check_environment(self.environment, self.fetch)
        for key, value in [('can_admins_bypass', True), ('protection_rules', []),
                           ('deployment_branch_policy', {'custom_branch_policies': False})]:
            original = copy.deepcopy(self.settings)
            self.settings[key] = value
            with self.subTest(key=key), self.assertRaises(release.ReleaseError):
                release.check_environment(self.environment, self.fetch)
            self.settings = original
        for branches in [[], [{'name': 'main', 'type': 'tag'}],
                         [{'name': '*', 'type': 'branch'}]]:
            self.policies['branch_policies'] = branches
            with self.subTest(branches=branches), self.assertRaises(release.ReleaseError):
                release.check_environment(self.environment, self.fetch)

    def test_prepare_builds_once_checks_same_files_then_freezes_hashes(self):
        directory = self.prepare()
        manifest = release.verify_artifacts(directory, self.environment)
        self.assertEqual(set(manifest['files']), release.filenames('1.0.0'))
        self.assertEqual(sum(args[1:3] == ['-m', 'build'] for args, _ in self.calls), 1)
        self.assertEqual(sum(len(args) > 1 and args[1] == 'scripts/check-package.py'
                             for args, _ in self.calls), 1)
        self.assertIn('manifest_sha256=' + self.environment['RELEASE_MANIFEST_SHA256'],
                      (self.root / 'output').read_text())
        with self.assertRaises(release.ReleaseError):
            release.main('prepare', directory, self.environment, self.fetch, self.command, self.root)

    def test_artifact_tampering_links_and_unexpected_files_are_rejected(self):
        directory = self.prepare()
        archive = next((directory / 'dist').glob('*.whl'))
        original = archive.read_bytes()
        archive.write_bytes(b'changed')
        with self.assertRaises(release.ReleaseError):
            release.verify_artifacts(directory, self.environment)
        archive.unlink()
        other = self.root / 'external'
        other.write_bytes(original)
        archive.symlink_to(other)
        with self.assertRaises(release.ReleaseError):
            release.verify_artifacts(directory, self.environment)
        archive.unlink()
        archive.write_bytes(original)
        (directory / 'dist/unexpected.txt').write_text('extra')
        with self.assertRaises(release.ReleaseError):
            release.verify_artifacts(directory, self.environment)
        (directory / 'dist/unexpected.txt').unlink()
        (directory / 'manifest.json').write_text('{}')
        with self.assertRaises(release.ReleaseError):
            release.verify_artifacts(directory, self.environment)

    def test_publish_attestations_are_only_accepted_after_upload(self):
        directory = self.prepare()
        for name in release.filenames('1.0.0'):
            (directory / 'dist' / (name + '.publish.attestation')).write_text('{}')
        with self.assertRaises(release.ReleaseError):
            release.verify_artifacts(directory, self.environment)
        release.verify_artifacts(directory, self.environment, allow_attestations=True)

    def test_registry_refuses_existing_missing_changed_or_yanked_releases(self):
        release.check_registry('1.0.0', fetch=self.fetch)
        directory = self.prepare()
        manifest = release.verify_artifacts(directory, self.environment)
        self.registry = self.published_metadata(manifest)
        with self.assertRaises(release.ReleaseError):
            release.check_registry('1.0.0', fetch=self.fetch)
        release.check_registry('1.0.0', manifest['files'], self.fetch)
        for key, value in [('urls', []), ('info', {'name': 'other', 'version': '1.0.0'})]:
            previous = copy.deepcopy(self.registry)
            self.registry['data'][key] = value
            with self.subTest(key=key), self.assertRaises(release.ReleaseError):
                release.check_registry('1.0.0', manifest['files'], self.fetch)
            self.registry = previous
        self.registry['data']['urls'][0]['yanked'] = True
        with self.assertRaises(release.ReleaseError):
            release.check_registry('1.0.0', manifest['files'], self.fetch)
        self.registry = self.published_metadata(manifest)
        self.registry['data']['urls'][0]['digests']['sha256'] = '0' * 64
        with self.assertRaises(release.ReleaseError):
            release.check_registry('1.0.0', manifest['files'], self.fetch)

    def test_verify_never_builds_or_uploads_and_existing_version_stops_it(self):
        directory = self.prepare()
        self.calls.clear()
        release.main('verify', directory, self.environment, self.fetch, self.command, self.root)
        self.assertTrue(all(args[0] == 'git' for args, _ in self.calls))
        self.registry = {'status': 200, 'data': {}}
        with self.assertRaises(release.ReleaseError):
            release.main('verify', directory, self.environment, self.fetch, self.command, self.root)

    def test_published_checks_hashes_and_unversioned_clean_install_before_success(self):
        directory = self.prepare()
        manifest = release.verify_artifacts(directory, self.environment)
        self.registry = self.published_metadata(manifest)
        self.calls.clear()
        release.main('published', directory, self.environment, self.fetch, self.command, self.root)
        installs = [args for args, _ in self.calls if 'install' in args]
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0][-1], release.NAME)
        self.assertIn('--isolated', installs[0])
        self.assertIn('https://pypi.org/simple', installs[0])
        self.assertIn('clean public installation passed', (self.root / 'summary').read_text())

    def test_request_rejects_redirects_oversized_metadata_and_closes_http_errors(self):
        body = io.BytesIO(b'private-response-data')
        error = HTTPError('https://pypi.org/', 302, 'redirect', {}, body)
        with patch.object(release, 'build_opener') as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaisesRegex(release.ReleaseError, 'HTTP 302'):
                release.request_json('https://pypi.org/')
        self.assertTrue(body.closed)
        with patch.object(release, 'build_opener') as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'x' * 1048577
            with self.assertRaisesRegex(release.ReleaseError, 'response limit'):
                release.request_json('https://pypi.org/')

    def test_invalid_cli_mode_stops_before_network_without_disclosing_tokens(self):
        result = subprocess.run([sys.executable, str(SCRIPT), 'unsupported', str(self.root)],
                                capture_output=True, text=True,
                                env={'TWINE_PASSWORD': 'private-fixture-token'}, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Use prepare, verify or published', result.stderr)
        self.assertNotIn('private-fixture-token', result.stderr + result.stdout)


if __name__ == '__main__':
    unittest.main()
