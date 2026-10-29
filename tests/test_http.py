"""Real Requests/HTTP boundary checks using loopback only."""
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import unittest
from urllib.parse import urlsplit, parse_qs

from nstdata_ai_crawl import NstDataClient, NstDataApiError, ScrapeRequestDto


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        rows = self.rows

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
                self.respond()

            def do_GET(self):
                self.body = None
                self.respond()

            def respond(self):
                rows.append({'path': self.path, 'method': self.command, 'key': self.headers.get('x-api-key'), 'body': self.body})
                if self.path.endswith('/redirect'):
                    self.send_response(302)
                    self.send_header('Location', '/leaked')
                    self.end_headers()
                    return
                self.send_response(200)
                if self.path.endswith('/gzip'):
                    self.send_header('Content-Encoding', 'gzip')
                    self.end_headers()
                    self.wfile.write(gzip.compress(b'X' * 70000))
                    return
                self.end_headers()
                if self.path.endswith('/slow'):
                    time.sleep(0.15)
                if '/storage/read?' in self.path:
                    body = '正文😀'.encode()
                elif self.command == 'POST' and 'async=true' in self.path:
                    body = json.dumps({'code': 200, 'err': False, 'data': {'id': 'task/one', 'status': 'processing'}}).encode()
                else:
                    body = json.dumps({'code': 200, 'err': False, 'data': {'status': 'completed', 'success': True,
                                       'data': {'markdownRef': 'opaque/+=', 'metadata': {'title': 'Fixture'}}}}).encode()
                try:
                    self.wfile.write(body)
                except OSError:
                    pass  # A timed-out caller has deliberately disconnected.

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = NstDataClient('fixture-token', base_url='http://127.0.0.1:' + str(self.server.server_port))
        self.client.session.trust_env = False
        self.addCleanup(self.client.close)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def test_async_encoded_result_and_lazy_ref_with_real_requests(self):
        submitted = self.client.submit_scrape_task(ScrapeRequestDto('https://target.invalid/', formats=['markdown']))
        result = self.client.get_scrape_task_result(submitted.id)
        self.assertEqual(result.data.get_markdown(), '正文😀')
        self.assertEqual(len(self.rows), 3)
        self.assertEqual(self.rows[1]['path'], '/api/v1/crawl/scrape/task%2Fone')
        self.assertEqual(parse_qs(urlsplit(self.rows[2]['path']).query), {'st': ['opaque/+=']})
        self.assertTrue(all(r['key'] == 'fixture-token' for r in self.rows))

    def test_redirect_is_not_followed(self):
        with self.assertRaises(NstDataApiError) as caught:
            self.client.get_crawl_status('redirect')
        self.assertEqual(caught.exception.status_code, 302)
        self.assertEqual(len(self.rows), 1)

    def test_header_encoding_error_is_safe_before_any_http_request(self):
        self.client.token = 'fixture-\u2603-private-token'
        with self.assertRaises(NstDataApiError) as caught:
            self.client.get_crawl_status('task')
        self.assertEqual(caught.exception.kind, 'transport')
        self.assertNotIn('private-token', str(caught.exception))
        self.assertEqual(self.rows, [])

    def test_body_read_inactivity_is_timeout_without_retry(self):
        with self.assertRaises(NstDataApiError) as caught:
            self.client.get_crawl_status('slow', timeout=(0.03, 0.03))
        self.assertEqual(caught.exception.kind, 'timeout')
        self.assertEqual(len(self.rows), 1)

    def test_gzip_decoded_bytes_are_capped(self):
        self.client.max_response_bytes = 1024
        with self.assertRaises(NstDataApiError) as caught:
            self.client.get_crawl_status('gzip')
        self.assertEqual(caught.exception.kind, 'response_limit')
        self.assertEqual(len(self.rows), 1)


if __name__ == '__main__':
    unittest.main()
