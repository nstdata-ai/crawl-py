import importlib.util
import re
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from nstdata_ai_crawl import NstDataApiError, ScrapeDataDto, TaskResultResponseDto, CrawlStatusResponseDto, CrawlPageItemResponseDto
from test_client import Response

spec = importlib.util.spec_from_file_location('crawl_examples', Path(__file__).resolve().parents[1] / 'main.py')
examples = importlib.util.module_from_spec(spec)
spec.loader.exec_module(examples)


class ExamplesTests(unittest.TestCase):
    def test_guide_programs_execute_bounded_workflows_with_actual_client(self):
        for name in ('guide.md', 'guide_zh.md'):
            source = Path(__file__).resolve().parents[1] / 'docs' / name
            blocks = re.findall(r'```python\n([\s\S]*?)```', source.read_text())
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

    def test_readme_examples_reject_missing_markdown_but_preserve_empty_text(self):
        for name in ('README.md', 'README_zh.md'):
            source = Path(__file__).resolve().parents[1] / name
            code = re.findall(r'```python\n([\s\S]*?)```', source.read_text())[0]
            for text, expected_error in [(None, True), ('', False), ('# Fixture', False)]:
                content = ScrapeDataDto()
                content._markdown = text
                with patch.dict('os.environ', {'NSTDATA_API_TOKEN': 'fixture-token'}), \
                        patch('nstdata_ai_crawl.NstDataClient') as factory:
                    factory.return_value.__enter__.return_value.submit_scrape_task_sync.return_value = TaskResultResponseDto(
                        status='completed', success=True, data=content)
                    if expected_error:
                        with self.assertRaises(NstDataApiError):
                            exec(compile(code, name, 'exec'), {})
                    else:
                        namespace = {}
                        exec(compile(code, name, 'exec'), namespace)
                        self.assertEqual(namespace['markdown'], text)

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
