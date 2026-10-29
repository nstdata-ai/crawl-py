import importlib.util
from contextlib import redirect_stdout
import io
import json
import os
import runpy
import shlex
import subprocess
import sys
import threading
from tempfile import TemporaryDirectory
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
import re
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from nstdata_ai_crawl import NstDataApiError, ScrapeDataDto, TaskResultResponseDto, CrawlStatusResponseDto, CrawlPageItemResponseDto
from test_client import Response

spec = importlib.util.spec_from_file_location('crawl_examples', Path(__file__).resolve().parents[1] / 'main.py')
examples = importlib.util.module_from_spec(spec)
spec.loader.exec_module(examples)


class ExamplesTests(unittest.TestCase):
    def test_guide_programs_execute_bounded_workflows_with_actual_client(self):
        for name in ('guide.md', 'guide_zh.md'):
            source = Path(__file__).resolve().parents[1] / 'docs' / name
            blocks = re.findall(r'```python\n([\s\S]*?)```', source.read_text(encoding='utf-8'))
            self.assertEqual(len(blocks), 3)
            for index, code in enumerate(blocks):
                with self.subTest(document=name, workflow=index):
                    responses = []
                    if index == 0:
                        responses = [Response({'id': 'saved-task', 'status': 'processing'}),
                                     Response({'status': 'completed', 'success': True,
                                               'data': {'markdownRef': 'returned-ref'}}),
                                     Response(raw=b'')]
                    elif index == 1:
                        responses = [Response({'id': 'saved-crawl', 'status': 'scraping'}),
                                     Response({'status': 'completed', 'total': 2, 'completed': 1, 'failed': 1}),
                                     Response({'data': [
                                         {'url': 'https://target.invalid/', 'status': 'completed',
                                          'success': True, 'data': {'markdownRef': 'returned-ref'}},
                                         {'url': 'https://target.invalid/failed', 'status': 'failed', 'success': False},
                                     ]}), Response(raw=b'# Fixture')]
                    with patch.dict('os.environ', {'NSTDATA_API_TOKEN': 'fixture-token'}), \
                            patch('nstdata_ai_crawl.client.requests.Session.request', side_effect=responses) as request, \
                            patch('builtins.print'):
                        namespace = {}
                        exec(compile(code, name, 'exec'), namespace)
                    self.assertTrue(all(response.closed for response in responses))
                    if index < 2:
                        self.assertEqual(request.call_count, len(responses))
                        self.assertEqual(sum(call.args[0] == 'POST' for call in request.call_args_list), 1)
                        self.assertTrue(all(call.args[0] == 'GET' for call in request.call_args_list[1:]))
                        self.assertEqual(request.call_args.kwargs['params'], {'st': 'returned-ref'})
                        self.assertEqual(request.call_args.kwargs['headers']['x-api-key'], 'fixture-token')
                    if index == 0:
                        self.assertEqual(namespace['markdown'], '')
                        self.assertTrue(request.call_args_list[1].args[1].endswith('/scrape/saved-task'))
                    elif index == 1:
                        self.assertEqual(request.call_args_list[0].kwargs['json']['maxPages'], 2)
                        self.assertFalse(request.call_args_list[0].kwargs['json']['onlyMainContent'])
                        self.assertEqual(request.call_args_list[2].kwargs['params'], {'limit': 2})
                    else:
                        request.assert_not_called()
                        self.assertEqual(namespace['request'].to_dict()['jsRender']['actions'][0]['type'], 'waitSelector')

    def test_missing_token_never_creates_client(self):
        with patch.object(examples, 'TOKEN', None), patch.object(examples, 'NstDataClient') as client:
            with self.assertRaises(ValueError):
                examples.main()
            client.assert_not_called()

    def test_async_failure_is_terminal_without_resubmission(self):
        client = Mock()
        client.submit_scrape_task.return_value.id = 'persisted'
        client.wait_for_scrape.return_value = TaskResultResponseDto(status='failed', success=False)
        with patch('builtins.print'), self.assertRaises(NstDataApiError):
            examples.example_async_polling(client)
        client.submit_scrape_task.assert_called_once()
        self.assertEqual(client.wait_for_scrape.call_args.args, ('persisted',))

    def test_expired_crawl_does_not_read_pages(self):
        client = Mock()
        client.submit_crawl_task.return_value.id = 'persisted'
        client.wait_for_crawl.return_value = CrawlStatusResponseDto(status='expired')
        with patch('builtins.print'), self.assertRaises(NstDataApiError):
            examples.example_crawl(client)
        client.iter_crawl_pages.assert_not_called()

    def test_basic_and_async_examples_reject_missing_or_unfinished_markdown(self):
        for status, success, content in [('processing', True, ScrapeDataDto()),
                                         ('completed', True, ScrapeDataDto()),
                                         ('completed', None, ScrapeDataDto())]:
            for operation in ('basic', 'async'):
                with self.subTest(status=status, success=success, operation=operation):
                    client = Mock()
                    result = TaskResultResponseDto(status=status, success=success, data=content)
                    client.submit_scrape_task_sync.return_value = result
                    client.submit_scrape_task.return_value.id = 'persisted'
                    client.wait_for_scrape.return_value = result
                    with patch('builtins.print'), self.assertRaises(NstDataApiError):
                        if operation == 'basic':
                            examples.example_basic_scrape(client)
                        else:
                            examples.example_async_polling(client)

    def run_program(self, source, responses, token='fixture-token'):
        output = io.StringIO()
        failure = None
        environment = {} if token is None else {'NSTDATA_API_TOKEN': token}
        close_session = requests.Session.close
        with patch.dict(os.environ, environment, clear=True), \
                patch('requests.Session.request', side_effect=responses) as request, \
                patch('requests.Session.close', autospec=True, side_effect=close_session) as close, \
                redirect_stdout(output):
            try:
                runpy.run_path(str(source), run_name='__main__')
            except SystemExit as error:
                failure = str(error)
        for response in responses:
            if isinstance(response, Response):
                self.assertTrue(response.closed)
        self.assertEqual(close.call_count, 0 if token is None or not token.strip() else 1)
        return output.getvalue(), failure, request.call_args_list

    def test_readme_programs_execute_real_client_and_preserve_result_states(self):
        cases = [
            ({'status': 'completed', 'success': True, 'data': {'markdown': '# Fixture'}},
             None, '# Fixture\n', None),
            ({'status': 'completed', 'success': True, 'data': {'markdown': ''}},
             None, '\n', None),
            ({'status': 'completed', 'success': True, 'data': {'markdownRef': 'returned-ref'}},
             b'# Referenced', '# Referenced\n', None),
            ({'status': 'completed', 'success': True, 'data': None},
             None, '', 'missing_content'),
            ({'status': 'completed', 'success': True, 'data': {}},
             None, '', 'missing_content'),
            ({'status': 'failed', 'success': False, 'data': {'markdown': 'ignore'}},
             None, '', 'task_failed'),
            ({'status': 'expired', 'success': False}, None, '', 'task_failed'),
            ({'status': 'processing', 'success': True, 'data': {'markdown': 'ignore'}},
             None, '', 'missing_content'),
            ({'status': 'completed', 'success': None, 'data': {'markdown': 'ignore'}},
             None, '', 'missing_content'),
        ]
        for name in ('README.md', 'README_zh.md'):
            source = Path(__file__).resolve().parents[1] / name
            code = re.findall(r'```python\n([\s\S]*?)```', source.read_text(encoding='utf-8'))[0]
            with TemporaryDirectory() as temporary:
                program = Path(temporary) / 'quickstart.py'
                program.write_text(code, encoding='utf-8')
                for payload, referenced, expected_output, error_kind in cases:
                    with self.subTest(document=name, result=payload):
                        responses = [Response(payload)]
                        if referenced is not None:
                            responses.append(Response(raw=referenced))
                        output, failure, calls = self.run_program(program, responses)
                        self.assertEqual(output, expected_output)
                        self.assertEqual(failure, 'Crawl failed: ' + error_kind if error_kind else None)
                        self.assertEqual(len(calls), len(responses))
                        self.assertEqual(calls[0].args[0], 'POST')
                        self.assertIsNone(calls[0].kwargs['params'])
                        if referenced is not None:
                            self.assertEqual(calls[1].args[0], 'GET')
                            self.assertEqual(calls[1].kwargs['params'], {'st': 'returned-ref'})

    def test_readme_programs_require_token_and_report_safe_transport_errors(self):
        for name in ('README.md', 'README_zh.md'):
            source = Path(__file__).resolve().parents[1] / name
            code = re.findall(r'```python\n([\s\S]*?)```', source.read_text(encoding='utf-8'))[0]
            with TemporaryDirectory() as temporary:
                program = Path(temporary) / 'quickstart.py'
                program.write_text(code, encoding='utf-8')
                for token in (None, '', ' '):
                    with self.subTest(document=name, token=token):
                        output, failure, calls = self.run_program(program, [], token)
                        self.assertEqual(output, '')
                        self.assertEqual(failure, 'Set NSTDATA_API_TOKEN in your environment.')
                        self.assertEqual(calls, [])
                for response, kind in [(Response(status=503, raw=b'private-response'), 'http'),
                                       (requests.ConnectionError('private-connection'), 'transport')]:
                    with self.subTest(document=name, error=kind):
                        output, failure, calls = self.run_program(program, [response])
                        self.assertEqual(output, '')
                        self.assertEqual(failure, 'Crawl failed: ' + kind)
                        self.assertEqual(len(calls), 1)
                        self.assertNotIn('private', failure)
                        self.assertNotIn('fixture-token', failure)

    def test_main_entry_submits_one_task_and_prints_markdown(self):
        source = Path(__file__).resolve().parents[1] / 'main.py'
        response = Response({'status': 'completed', 'success': True,
                             'data': {'markdown': '# Main entry'}})
        output, failure, calls = self.run_program(source, [response])
        self.assertEqual(output, '# Main entry\n')
        self.assertIsNone(failure)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[0], 'POST')
        self.assertIsNone(calls[0].kwargs['params'])

    def test_documented_cli_runs_in_an_isolated_process_with_real_loopback_http(self):
        readme = (Path(__file__).resolve().parents[1] / 'README.md').read_text(encoding='utf-8')
        code = re.findall(r'```python\n([\s\S]*?)```', readme)[0]
        commands = [shlex.split(block) for block in re.findall(r'```sh\n([\s\S]*?)```', readme)]
        self.assertEqual(commands[-1], ['python', 'quickstart.py'])
        self.assertEqual(commands[-2], ['export', 'NSTDATA_API_TOKEN=your-api-key'])
        rows = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                rows.append((self.command, self.path, body))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'code': 200, 'err': False, 'data': {
                    'status': 'completed', 'success': True,
                    'data': {'markdownRef': 'fixture-reference'},
                }}).encode())

            def do_GET(self):
                rows.append((self.command, self.path, None))
                self.send_response(200)
                self.end_headers()
                self.wfile.write('# Native CLI fixture'.encode())

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: thread.join(timeout=2))
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = 'http://127.0.0.1:' + str(server.server_port)
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / 'quickstart.py').write_text(code, encoding='utf-8')
            events = folder / 'cleanup.json'
            (folder / 'sitecustomize.py').write_text(f'''
import atexit, json, socket
from pathlib import Path
from urllib.parse import urlsplit
import requests
events = []
atexit.register(lambda: Path({str(events)!r}).write_text(json.dumps(events)))
original_connect = socket.socket.connect
def connect(self, address):
    if not isinstance(address, tuple) or address[:2] != ('127.0.0.1', {server.server_port}):
        raise RuntimeError('Only fixture connections are allowed')
    return original_connect(self, address)
socket.socket.connect = connect
original_resolve = socket.getaddrinfo
def resolve(host, *args, **kwargs):
    if host != '127.0.0.1':
        raise RuntimeError('Only fixture resolution is allowed')
    return original_resolve(host, *args, **kwargs)
socket.getaddrinfo = resolve
original_request = requests.Session.request
def request(self, method, url, **kwargs):
    parsed = urlsplit(url)
    allowed = {{('POST', '/api/v1/crawl/scrape'), ('GET', '/api/v1/crawl/storage/read')}}
    if parsed.scheme != 'https' or parsed.netloc != 'api.nstdata.io' or \\
            (method, parsed.path) not in allowed or parsed.query or parsed.fragment:
        raise RuntimeError('Only known fixture routes are allowed')
    return original_request(self, method, {origin!r} + parsed.path, **kwargs)
requests.Session.request = request
for cls, label in [(requests.Session, 'session'), (requests.Response, 'response')]:
    original = cls.close
    def close(self, original=original, label=label):
        result = original(self)
        events.append(label)
        return result
    cls.close = close
''', encoding='utf-8')
            package_root = Path(sys.modules['nstdata_ai_crawl'].__file__).resolve().parent.parent
            environment = {
                'PATH': str(Path(sys.executable).parent) + os.pathsep + os.defpath,
                'PYTHONPATH': str(folder) + os.pathsep + str(package_root),
                'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                'NSTDATA_API_TOKEN': 'fixture-token',
            }
            guard_check = f'''
import requests, socket
from pathlib import Path
import nstdata_ai_crawl
assert Path(nstdata_ai_crawl.__file__).resolve().parent.parent == Path({str(package_root)!r})
assert requests.Session.request.__module__ == 'sitecustomize'
assert socket.socket.connect.__module__ == 'sitecustomize'
for operation in [lambda: requests.get('https://unexpected.invalid/'),
                  lambda: socket.create_connection(('192.0.2.1', 80))]:
    try:
        operation()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Fixture guard was not active')
'''
            subprocess.run([sys.executable, '-c', guard_check], cwd=folder,
                           env=environment, check=True, capture_output=True, text=True, timeout=10)
            result = subprocess.run([sys.executable, *commands[-1][1:]], cwd=folder,
                                    env=environment, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '# Native CLI fixture\n')
            self.assertEqual(result.stderr, '')
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0][:2], ('POST', '/api/v1/crawl/scrape'))
            self.assertEqual(rows[0][2]['formats'], ['markdown'])
            self.assertEqual(rows[1][0], 'GET')
            self.assertEqual(parse_qs(urlsplit(rows[1][1]).query), {'st': ['fixture-reference']})
            self.assertCountEqual(json.loads(events.read_text()), ['response', 'response', 'session'])
            environment.pop('NSTDATA_API_TOKEN')
            missing = subprocess.run([sys.executable, *commands[-1][1:]], cwd=folder,
                                     env=environment, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(missing.returncode, 0)
            self.assertEqual(missing.stdout, '')
            self.assertEqual(missing.stderr.strip(), 'Set NSTDATA_API_TOKEN in your environment.')
            self.assertEqual(len(rows), 2)
            self.assertEqual(json.loads(events.read_text()), [])

    def test_examples_preserve_empty_markdown_and_bound_existing_id_reads(self):
        client = Mock()
        content = ScrapeDataDto()
        content._markdown = ''
        result = TaskResultResponseDto(status='completed', success=True, data=content)
        client.submit_scrape_task_sync.return_value = result
        client.submit_scrape_task.return_value.id = 'saved-scrape'
        client.submit_crawl_task.return_value.id = 'saved-crawl'
        client.wait_for_scrape.return_value = result
        client.wait_for_crawl.return_value = CrawlStatusResponseDto(status='completed')
        client.iter_crawl_pages.return_value = [
            CrawlPageItemResponseDto(status='completed', success=True, data=content),
            CrawlPageItemResponseDto(status='failed', success=False),
        ]
        with patch('builtins.print') as output:
            examples.example_basic_scrape(client)
            examples.example_async_polling(client)
            examples.example_crawl(client)
        self.assertEqual(client.submit_scrape_task_sync.call_count, 1)
        self.assertEqual(client.submit_scrape_task.call_count, 1)
        self.assertEqual(client.submit_crawl_task.call_count, 1)
        client.wait_for_scrape.assert_called_once_with('saved-scrape', max_polls=20, poll_interval=1, wait_timeout=120)
        client.wait_for_crawl.assert_called_once_with('saved-crawl', max_polls=20, poll_interval=1, wait_timeout=120)
        client.iter_crawl_pages.assert_called_once_with('saved-crawl', limit=20, max_batches=10)
        self.assertEqual(client.submit_crawl_task.call_args.args[0].maxPages, 10)
        output.assert_any_call('')
        output.assert_any_call('Page failed or pending')

    def test_missing_submission_id_does_not_query_or_resubmit(self):
        for value in (None, '', ' ', 42):
            for operation in ('async', 'crawl'):
                with self.subTest(value=value, operation=operation):
                    client = Mock()
                    client.submit_scrape_task.return_value.id = value
                    client.submit_crawl_task.return_value.id = value
                    with patch('builtins.print'), self.assertRaises(NstDataApiError):
                        if operation == 'async':
                            examples.example_async_polling(client)
                        else:
                            examples.example_crawl(client)
                    client.wait_for_scrape.assert_not_called()
                    client.wait_for_crawl.assert_not_called()
                    self.assertEqual(client.submit_scrape_task.call_count + client.submit_crawl_task.call_count, 1)
