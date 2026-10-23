import json
import unittest
from unittest.mock import Mock, patch

import requests
from nstdata_ai_crawl import (
    NstDataClient, NstDataApiError, ScrapeRequestDto, CrawlRequestDto,
    ScrapeDataDto, TaskResultResponseDto, CrawlStatusResponseDto,
)


class Response:
    def __init__(self, payload=None, *, raw=None, status=200, chunks=None):
        self.status_code = status
        self.body = raw if raw is not None else json.dumps({'code': 200, 'err': False, 'data': payload}).encode()
        self.chunks = chunks
        self.closed = False

    def iter_content(self, chunk_size):
        yield from self.chunks if self.chunks is not None else [self.body]

    def close(self):
        self.closed = True


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.client = NstDataClient('secret-token')
        self.addCleanup(self.client.close)
        self.request = Mock()
        self.client.session.request = self.request

    def reply(self, payload=None, **kwargs):
        response = Response(payload, **kwargs)
        self.request.return_value = response
        return response

    def test_default_and_override_config_and_no_redirect(self):
        response = self.reply({'id': 'one'})
        self.client.submit_scrape_task(ScrapeRequestDto('https://target.invalid', formats=['markdown']))
        args, kw = self.request.call_args
        self.assertEqual(args, ('POST', 'https://api.nstdata.io/api/v1/crawl/scrape'))
        self.assertEqual(kw['params'], {'async': 'true'})
        self.assertEqual(kw['timeout'], (10, 120))
        self.assertFalse(kw['allow_redirects'])
        self.assertTrue(kw['stream'])
        self.assertEqual(kw['headers'], {'x-api-key': 'secret-token'})
        self.assertTrue(response.closed)
        with NstDataClient('token', base_url='https://custom.invalid/prefix/', timeout=5) as custom:
            self.assertEqual(custom.base_url, 'https://custom.invalid/prefix')
            self.assertEqual(custom.timeout, (5, 5))

    def test_sync_preserves_empty_inline_without_reading_reference(self):
        self.reply({'status': 'completed', 'success': True, 'data': {'markdown': '', 'markdownRef': 'do-not-read', 'metadata': {'title': 'Title', 'future': 1}}})
        result = self.client.submit_scrape_task_sync(ScrapeRequestDto('https://target.invalid', formats=['markdown']))
        self.assertEqual(result.data.get_markdown(), '')
        self.assertEqual(result.data.metadata.title, 'Title')
        self.assertEqual(self.request.call_count, 1)

    def test_failed_missing_data_and_future_fields(self):
        self.reply({'status': 'failed', 'success': False, 'data': None, 'errorCode': 'DENIED', 'future': True})
        result = self.client.get_scrape_task_result('id')
        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertEqual(result.errorCode, 'DENIED')

    def test_result_and_crawl_paths_encode_identifier(self):
        self.reply({})
        for method, suffix in [(self.client.get_scrape_task_result, '/scrape/one%2F%3F%23'),
                               (self.client.get_crawl_status, '/one%2F%3F%23')]:
            method('one/?#')
            self.assertTrue(self.request.call_args.args[1].endswith('/api/v1/crawl' + suffix))
        self.client.submit_crawl_task(CrawlRequestDto('https://target.invalid', formats=['markdown']))
        self.assertEqual(self.request.call_args.args[0], 'POST')
        self.assertTrue(self.request.call_args.args[1].endswith('/api/v1/crawl'))

    def test_cursor_parameters_and_all_page_states(self):
        self.reply({'data': [{'taskId': 'a', 'url': 'https://target.invalid/a', 'status': 'completed', 'success': True,
                              'data': {'markdown': 'A'}}, {'taskId': 'b', 'status': 'failed', 'success': False, 'data': None}], 'nextCursor': 'opaque/+=', 'future': 1})
        page = self.client.list_crawl_pages('site/id', after_cursor='a/+=', limit=2)
        self.assertEqual(self.request.call_args.kwargs['params'], {'after_cursor': 'a/+=', 'limit': 2})
        self.assertEqual(page.data[0].data.get_markdown(), 'A')
        self.assertFalse(page.data[1].success)
        self.assertIsNone(page.data[1].data)
        self.assertEqual(page.nextCursor, 'opaque/+=')

    def test_storage_reference_is_query_not_url_and_timeout_override(self):
        self.reply(raw='正文😀'.encode())
        data = self.client._data({'markdownRef': 'https://not-a-download.invalid/a?st=+'})
        self.assertEqual(data.get_markdown(timeout=(2, 3)), '正文😀')
        args, kw = self.request.call_args
        self.assertTrue(args[1].endswith('/api/v1/crawl/storage/read'))
        self.assertEqual(kw['params']['st'], 'https://not-a-download.invalid/a?st=+')
        self.assertEqual(kw['timeout'], (2, 3))
        self.assertEqual(data.get_markdown(), '正文😀')
        self.assertEqual(self.request.call_count, 1)

    def test_all_binary_getters_and_html_remain_lazy(self):
        for name, ref, expected in [('get_html', 'htmlRef', 'X'), ('get_pdf', 'pdfRef', b'X'),
                                    ('get_raw_data', 'rawDataRef', b'X'), ('get_screenshot', 'screenshotRef', b'X')]:
            self.reply(raw=b'X')
            data = self.client._data({ref: 'opaque'})
            self.assertEqual(getattr(data, name)(), expected)
        self.assertIsNone(ScrapeDataDto().get_markdown())

    def test_inline_binary_and_raw_content_survive_all_result_paths(self):
        for operation in ('sync', 'result', 'pages'):
            with self.subTest(operation=operation):
                self.request.reset_mock()
                data = {'pdf': 'JVBERi0xLjQK', 'screenshot': 'AP+A', 'rawData': '<p>雪</p>'}
                if operation == 'result':
                    data.update(pdfRef='do-not-read', screenshotRef='do-not-read', rawDataRef='do-not-read')
                self.reply({'data': [{'data': data}]} if operation == 'pages' else {'success': True, 'data': data})
                if operation == 'sync':
                    result = self.client.submit_scrape_task_sync(ScrapeRequestDto('https://target.invalid', formats=['pdf', 'screenshot', 'rawData']))
                elif operation == 'result':
                    result = self.client.get_scrape_task_result('task')
                else:
                    result = self.client.list_crawl_pages('crawl')
                content = result.data[0].data if operation == 'pages' else result.data
                for _ in range(2):
                    self.assertEqual(content.get_pdf(), b'%PDF-1.4\n')
                    self.assertEqual(content.get_screenshot(), b'\x00\xff\x80')
                    self.assertEqual(content.get_raw_data(), b'<p>\xe9\x9b\xaa</p>')
                self.assertEqual(self.request.call_count, 1)

    def test_result_identity_and_truncation_survive_all_result_paths(self):
        for flag in (True, False, None):
            for operation in ('sync', 'result', 'pages'):
                with self.subTest(flag=flag, operation=operation):
                    result_data = {'markdown': '# Fixture', 'truncated': flag}
                    payload = {'id': 'actual-task', 'taskId': 'page-task', 'success': True, 'data': result_data}
                    self.reply({'data': [payload]} if operation == 'pages' else payload)
                    if operation == 'sync':
                        result = self.client.submit_scrape_task_sync(ScrapeRequestDto('https://target.invalid', formats=['markdown']))
                    elif operation == 'result':
                        result = self.client.get_scrape_task_result('requested-task')
                    else:
                        result = self.client.list_crawl_pages('crawl')
                    if operation == 'pages':
                        content = result.data[0].data
                        self.assertEqual(result.data[0].taskId, 'page-task')
                    else:
                        content = result.data
                        self.assertEqual(result.id, 'actual-task')
                    self.assertIs(content.truncated, flag)
                    self.assertEqual(content.get_markdown(), '# Fixture')

    def test_invalid_inline_content_has_safe_errors_without_retrying(self):
        invalid = [
            {field: value}
            for field in ('pdf', 'screenshot')
            for value in (42, False, {}, [], 'private-response!', 'A', 'AQ=I', 'AQ===', 'AQ=', 'AAAA=', 'AAAA==', 'AAAA====', '雪')
        ] + [{'rawData': value} for value in (42, False, {}, [], '\ud800private-response')] \
          + [{'truncated': value} for value in ('true', 1, {}, [])]
        for data in invalid:
            for operation in ('sync', 'result', 'pages'):
                with self.subTest(data=data, operation=operation):
                    self.request.reset_mock()
                    response = self.reply({'data': [{'data': data}]} if operation == 'pages' else {'success': True, 'data': data})
                    with self.assertRaises(NstDataApiError) as caught:
                        if operation == 'sync':
                            self.client.submit_scrape_task_sync(ScrapeRequestDto('https://target.invalid', formats=['pdf']))
                        elif operation == 'result':
                            self.client.get_scrape_task_result('task')
                        else:
                            self.client.list_crawl_pages('crawl')
                    self.assertEqual(caught.exception.kind, 'invalid_response')
                    self.assertNotIn('private-response', str(caught.exception))
                    self.assertEqual(self.request.call_count, 1)
                    self.assertTrue(response.closed)

    def test_empty_absent_and_referenced_inline_bytes_remain_distinct(self):
        for field, getter in (('pdf', 'get_pdf'), ('screenshot', 'get_screenshot'), ('rawData', 'get_raw_data')):
            for value in ('', None):
                with self.subTest(field=field, value=value):
                    self.request.reset_mock()
                    self.request.side_effect = [Response({'data': {field: value, field + 'Ref': 'opaque'}}), Response(raw=b'\x00\xff\x80')]
                    data = self.client.get_scrape_task_result('task').data
                    expected = b'' if value == '' else b'\x00\xff\x80'
                    self.assertEqual(getattr(data, getter)(), expected)
                    self.assertEqual(getattr(data, getter)(), expected)
                    self.assertEqual(self.request.call_count, 1 if value == '' else 2)
                    self.request.side_effect = None
                    self.reply({'data': {field: value}})
                    missing = self.client.get_scrape_task_result('task').data
                    self.assertEqual(getattr(missing, getter)(), b'' if value == '' else None)

    def test_padded_unpadded_and_large_base64_do_not_change_raw_text_encoding(self):
        for encoded, expected in [('AQ==', b'\x01'), ('AQ', b'\x01'), ('AQI=', b'\x01\x02'), ('AQI', b'\x01\x02'),
                                  ('AP+A' * 65536, b'\x00\xff\x80' * 65536)]:
            with self.subTest(encoded_length=len(encoded)):
                self.reply({'data': {'pdf': encoded, 'screenshot': encoded, 'rawData': 'AQID'}})
                data = self.client.get_scrape_task_result('task').data
                self.assertEqual(data.get_pdf(), expected)
                self.assertEqual(data.get_screenshot(), expected)
                self.assertEqual(data.get_raw_data(), b'AQID')

    def test_new_response_fields_preserve_existing_positional_dto_arguments(self):
        result = TaskResultResponseDto(200, None, 'CODE', 'MESSAGE', 'failed', False)
        self.assertEqual(result.status, 'failed')
        self.assertIs(result.success, False)
        self.assertIsNone(result.id)
        data = ScrapeDataDto('html-ref', ['https://target.invalid'], 'markdown-ref', None, 'pdf-ref', 'raw-ref', 'image-ref')
        self.assertEqual(data.screenshotRef, 'image-ref')
        self.assertIsNone(data.truncated)

    def test_http_errors_and_redirect_are_safe_and_not_retried(self):
        for status in [301, 401, 403, 429, 500]:
            response = self.reply(raw=b'secret-token', status=status)
            before = self.request.call_count
            with self.assertRaises(NstDataApiError) as error:
                self.client.get_scrape_task_result('id')
            self.assertEqual(error.exception.status_code, status)
            self.assertEqual(error.exception.kind, 'http')
            self.assertNotIn('secret-token', str(error.exception))
            self.assertTrue(response.closed)
            self.assertEqual(self.request.call_count - before, 1)

    def test_api_and_invalid_json_errors_hide_response(self):
        for payload, kind in [(b'not-json secret-token', 'invalid_json'),
                              (json.dumps({'err': True, 'code': 403, 'msg': 'secret-token'}).encode(), 'api'),
                              (json.dumps({'err': 0, 'code': 200}).encode(), 'invalid_response'),
                              (json.dumps({'err': False, 'code': True}).encode(), 'invalid_response'),
                              (json.dumps({'err': False, 'code': 200, 'data': []}).encode(), 'invalid_response')]:
            response = self.reply(raw=payload)
            with self.assertRaises(NstDataApiError) as error:
                self.client.get_crawl_status('id')
            self.assertEqual(error.exception.kind, kind)
            self.assertNotIn('secret-token', str(error.exception))
            self.assertTrue(response.closed)

    def test_response_scalars_are_checked_before_exposing_typed_results(self):
        request = ScrapeRequestDto('https://target.invalid', formats=['markdown'])
        cases = [
            (lambda: self.client.submit_scrape_task(request), {'id': 42}),
            (lambda: self.client.submit_crawl_task(CrawlRequestDto('https://target.invalid', formats=['markdown'])),
             {'cached': 0}),
            (lambda: self.client.submit_scrape_task_sync(request), {'success': 'false'}),
            (lambda: self.client.get_scrape_task_result('task'), {'status': {'private-response': True}}),
            (lambda: self.client.get_crawl_status('crawl'), {'completed': True}),
            (lambda: self.client.get_crawl_status('crawl'), {'total': '10'}),
            (lambda: self.client.get_crawl_status('crawl'), {'code': False}),
            (lambda: self.client.list_crawl_pages('crawl'), {'nextCursor': 42}),
            (lambda: self.client.list_crawl_pages('crawl'), {'data': [{'taskId': False}]}),
            (lambda: self.client.list_crawl_pages('crawl'), {'data': [{'url': []}]}),
            (lambda: self.client.list_crawl_pages('crawl'), {'data': [{'success': 1}]}),
        ]
        for invoke, payload in cases:
            with self.subTest(payload=payload):
                self.request.reset_mock()
                response = self.reply(payload)
                with self.assertRaises(NstDataApiError) as error:
                    invoke()
                self.assertEqual(error.exception.kind, 'invalid_response')
                self.assertNotIn('private-response', str(error.exception))
                self.assertEqual(self.request.call_count, 1)
                self.assertTrue(response.closed)

    def test_nested_invalid_json_uses_safe_error_and_closes_response(self):
        response = self.reply(raw=b'[' * 2000 + b'"private-response"' + b']' * 2000)
        with self.assertRaises(NstDataApiError) as error:
            self.client.get_crawl_status('crawl')
        self.assertEqual(error.exception.kind, 'invalid_json')
        self.assertNotIn('private-response', str(error.exception))
        self.assertTrue(response.closed)
        self.assertEqual(self.request.call_count, 1)

    def test_timeout_and_connection_errors_are_not_retried(self):
        for raised, kind in [(requests.Timeout('secret-token'), 'timeout'),
                             (requests.ConnectionError('secret-token'), 'transport')]:
            self.request.side_effect = raised
            before = self.request.call_count
            with self.assertRaises(NstDataApiError) as error:
                self.client.submit_scrape_task(ScrapeRequestDto('https://target.invalid', formats=['markdown']))
            self.assertEqual(error.exception.kind, kind)
            self.assertNotIn('secret-token', str(error.exception))
            self.assertEqual(self.request.call_count - before, 1)

    def test_decoded_body_limit_and_close(self):
        self.client.max_response_bytes = 3
        response = self.reply(chunks=[b'ab', b'cd'])
        with self.assertRaises(NstDataApiError) as error:
            self.client.read_storage('ref')
        self.assertEqual(error.exception.kind, 'response_limit')
        self.assertTrue(response.closed)

    def test_dto_private_fields_cannot_be_injected(self):
        self.reply({'status': 'completed', 'data': {'markdown': 'safe', '_client': 'external', '_markdown': 'wrong'}})
        result = self.client.get_scrape_task_result('id')
        self.assertEqual(result.data.get_markdown(), 'safe')
        self.assertIs(result.data._client, self.client)

    def test_malformed_content_does_not_become_an_empty_page(self):
        for data in [[], 'text', {'markdown': 123}, {'metadata': []}]:
            self.reply({'status': 'completed', 'data': data})
            with self.assertRaises(NstDataApiError):
                self.client.get_scrape_task_result('id')
        self.reply({'data': {}})
        with self.assertRaises(NstDataApiError):
            self.client.list_crawl_pages('site')

    def test_references_links_and_metadata_reject_invalid_types_on_every_result_path(self):
        invalid = [{field: value} for field in ('htmlRef', 'markdownRef', 'pdfRef', 'rawDataRef', 'screenshotRef')
                   for value in (False, 42, [], {})]
        invalid += [{'links': value} for value in ('private-response', {}, [None], [42], ['valid', False])]
        invalid += [{'metadata': {field: value}} for field in ('canonical', 'description', 'language', 'ogImage', 'title')
                    for value in (False, 42, [], {'private-response': True})]
        invalid += [{'metadata': {'statusCode': value}} for value in (True, '200', [], {}, 200.5, float('inf'), float('nan'))]
        for operation in ('sync', 'result', 'pages'):
            for data in invalid:
                with self.subTest(operation=operation, data=data):
                    self.request.reset_mock()
                    response = self.reply({'data': [{'data': data}]} if operation == 'pages' else {'data': data})
                    with self.assertRaises(NstDataApiError) as error:
                        if operation == 'sync':
                            self.client.submit_scrape_task_sync(ScrapeRequestDto('https://target.invalid', formats=['markdown']))
                        elif operation == 'result':
                            self.client.get_scrape_task_result('task')
                        else:
                            self.client.list_crawl_pages('crawl')
                    self.assertEqual(error.exception.kind, 'invalid_response')
                    self.assertNotIn('private-response', str(error.exception))
                    self.assertEqual(self.request.call_count, 1)
                    self.assertTrue(response.closed)

    def test_optional_content_preserves_null_empty_zero_and_valid_metadata(self):
        self.reply({'status': 'completed', 'data': {'markdown': None, 'html': None, 'links': None,
                    'markdownRef': None, 'metadata': None}})
        data = self.client.get_scrape_task_result('task').data
        self.assertIsNone(data.get_markdown())
        self.assertIsNone(data.get_html())
        self.assertIsNone(data.links)
        self.assertIsNone(data.metadata)
        self.assertEqual(self.request.call_count, 1)
        self.reply({'data': {'markdown': '', 'markdownRef': 'unused', 'links': [],
                    'metadata': {'title': '', 'language': None, 'statusCode': 0, 'future': 'ignored'}}})
        data = self.client.get_scrape_task_result('task').data
        self.assertEqual(data.get_markdown(), '')
        self.assertEqual(data.links, [])
        self.assertEqual(data.metadata.title, '')
        self.assertIsNone(data.metadata.language)
        self.assertEqual(data.metadata.statusCode, 0)
        self.assertEqual(self.request.call_count, 2)

    def test_local_input_validation_sends_nothing(self):
        for value in ['', None, ' ', 'bad\nkey']:
            with self.assertRaises(ValueError):
                NstDataClient(value)
        for url in ['ftp://host', 'https://user:password@host', 'https://host?q=1', 'https://host#frag']:
            with self.assertRaises(ValueError):
                NstDataClient('token', base_url=url)
        for value in [0, -1, True, float('inf'), (1,), (1, None)]:
            with self.assertRaises(ValueError):
                NstDataClient('token', timeout=value)
        for invoke in [lambda: self.client.list_crawl_pages('id', after_cursor='a', before_cursor='b'),
                       lambda: self.client.list_crawl_pages('id', limit=0),
                       lambda: self.client.get_crawl_status(''),
                       lambda: self.client.submit_scrape_task(ScrapeRequestDto('https://target.invalid'))]:
            with self.assertRaises(ValueError):
                invoke()
        self.request.assert_not_called()

    def test_invalid_reference_text_has_safe_typed_error(self):
        self.reply(raw=b'\xffprivate-body')
        data = self.client._data({'markdownRef': 'opaque'})
        with self.assertRaises(NstDataApiError) as error:
            data.get_markdown()
        self.assertEqual(error.exception.kind, 'invalid_response')
        self.assertNotIn('private-body', str(error.exception))

    def test_context_closes_session_on_failure(self):
        with patch('nstdata_ai_crawl.client.requests.Session') as session:
            with self.assertRaises(RuntimeError):
                with NstDataClient('token'):
                    raise RuntimeError('local')
            session.return_value.close.assert_called_once()

    def test_wait_resumes_same_id_then_preserves_terminal_failure(self):
        self.request.side_effect = [Response({'status': 'processing'}), Response({'status': 'failed', 'success': False})]
        result = self.client.wait_for_scrape('persisted/id', max_polls=2, poll_interval=0)
        self.assertFalse(result.success)
        self.assertEqual(self.request.call_count, 2)
        self.assertTrue(all(call.args[0] == 'GET' for call in self.request.call_args_list))

    def test_wait_poll_cap_expired_and_unknown_status(self):
        self.reply({'status': 'processing'})
        with self.assertRaises(NstDataApiError) as error:
            self.client.wait_for_scrape('id', max_polls=2, poll_interval=0)
        self.assertEqual(error.exception.kind, 'poll_limit')
        self.assertEqual(self.request.call_count, 2)
        self.reply({'status': 'expired'})
        self.assertEqual(self.client.wait_for_crawl('id').status, 'expired')
        self.reply({'status': 'unexpected'})
        with self.assertRaises(NstDataApiError) as error:
            self.client.wait_for_crawl('id')
        self.assertEqual(error.exception.kind, 'invalid_response')

    def test_wait_budget_between_calls(self):
        self.reply({'status': 'processing'})
        with patch('nstdata_ai_crawl.client.time.monotonic', side_effect=[0, 0, 2, 2]), \
                patch('nstdata_ai_crawl.client.time.sleep'):
            with self.assertRaises(NstDataApiError) as error:
                self.client.wait_for_crawl('id', wait_timeout=1, max_polls=3)
        self.assertEqual(error.exception.kind, 'wait_limit')
        self.assertEqual(self.request.call_count, 1)

    def test_iter_empty_cursor_duplicate_and_failed_rows(self):
        self.request.side_effect = [Response({'data': [], 'nextCursor': 'a/+='}),
                                   Response({'data': [{'taskId': 'x', 'url': 'same', 'success': True},
                                                      {'taskId': 'x', 'url': 'same', 'success': False}]})]
        pages = list(self.client.iter_crawl_pages('site', max_batches=2))
        self.assertEqual([page.taskId for page in pages], ['x', 'x'])
        self.assertFalse(pages[1].success)
        self.assertEqual(self.request.call_args.kwargs['params']['after_cursor'], 'a/+=')

    def test_iter_cycle_and_page_cap_are_explicit(self):
        self.reply({'data': [], 'nextCursor': 'same'})
        with self.assertRaises(NstDataApiError) as error:
            list(self.client.iter_crawl_pages('site'))
        self.assertEqual(error.exception.kind, 'repeated_cursor')
        self.assertEqual(self.request.call_count, 2)
        with self.assertRaises(NstDataApiError) as error:
            list(self.client.iter_crawl_pages('site', max_batches=1))
        self.assertEqual(error.exception.kind, 'page_limit')


if __name__ == '__main__':
    unittest.main()
