import base64
import json
import math
import time
from dataclasses import fields
from urllib.parse import quote, urlsplit

import requests
from urllib3.exceptions import ReadTimeoutError

from .models import (
    ScrapeRequestDto, CrawlRequestDto, SubmitResponseDto, TaskResultResponseDto,
    PageMetadataDto, ScrapeDataDto, CrawlStatusResponseDto,
    CrawlPageItemResponseDto, CrawlPageListResponseDto,
)

_BASE_URL = 'https://api.nstdata.io'


class NstDataApiError(Exception):
    """Safe HTTP/API/transport diagnostics; task failures remain typed results."""

    def __init__(self, kind, *, status_code=None, api_code=None):
        self.kind = kind
        self.status_code = status_code
        self.api_code = api_code
        super().__init__('Nstdata request failed: ' + kind)


def _build(cls, data):
    if not isinstance(data, dict):
        raise NstDataApiError('invalid_response')
    names = {field.name for field in fields(cls) if field.init}
    return cls(**{key: value for key, value in data.items() if key in names})


def _timeout(value):
    values = value if isinstance(value, tuple) else (value, value)
    if len(values) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                               or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('timeout must be positive seconds or a (connect, read) tuple')
    return values


def _identifier(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Task ID or reference is required')
    return quote(value, safe='')


class NstDataClient:
    def __init__(self, token: str, *, base_url=_BASE_URL, timeout=(10, 120),
                 max_response_bytes=16 * 1024 * 1024):
        if not isinstance(token, str) or not token.strip() or '\r' in token or '\n' in token:
            raise ValueError('A nonempty API token is required')
        parsed = urlsplit(base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or \
                parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
            raise ValueError('base_url must be HTTP(S) without credentials, query or fragment')
        self.timeout = _timeout(timeout)
        if isinstance(max_response_bytes, bool) or not isinstance(max_response_bytes, int) or max_response_bytes <= 0:
            raise ValueError('max_response_bytes must be a positive integer')
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.max_response_bytes = max_response_bytes
        self.session = requests.Session()
        # Requests defaults to no retries. Keep redirects off to protect x-api-key.

    def _get_headers(self):
        return {'x-api-key': self.token}

    def _request(self, method, path, *, body=None, params=None, timeout=None, binary=False):
        request_timeout = self.timeout if timeout is None else _timeout(timeout)
        response = None
        try:
            response = self.session.request(
                method, self.base_url + path, json=body, params=params,
                headers=self._get_headers(), timeout=request_timeout,
                allow_redirects=False, stream=True,
            )
            if not 200 <= response.status_code < 300:
                raise NstDataApiError('http', status_code=response.status_code)
            chunks = []
            length = 0
            for chunk in response.iter_content(chunk_size=65536):
                length += len(chunk)
                if length > self.max_response_bytes:
                    raise NstDataApiError('response_limit', status_code=response.status_code)
                chunks.append(chunk)
            raw = b''.join(chunks)
            if binary:
                return raw
            try:
                envelope = json.loads(raw)
            except (ValueError, UnicodeError):
                raise NstDataApiError('invalid_json', status_code=response.status_code) from None
            if not isinstance(envelope, dict) or type(envelope.get('err')) is not bool \
                    or type(envelope.get('code')) is not int:
                raise NstDataApiError('invalid_response', status_code=response.status_code)
            if envelope['err'] or envelope['code'] != 200:
                raise NstDataApiError('api', status_code=response.status_code, api_code=envelope['code'])
            data = envelope.get('data')
            if data is None:
                return {}
            if not isinstance(data, dict):
                raise NstDataApiError('invalid_response', status_code=response.status_code)
            return data
        except requests.Timeout:
            raise NstDataApiError('timeout') from None
        except requests.ConnectionError as error:
            kind = 'timeout' if error.args and isinstance(error.args[0], ReadTimeoutError) else 'transport'
            raise NstDataApiError(kind) from None
        except requests.RequestException:
            raise NstDataApiError('transport') from None
        finally:
            if response is not None:
                response.close()

    def _data(self, raw):
        if raw is None:
            return None
        data = _build(ScrapeDataDto, raw)
        if data.truncated is not None and type(data.truncated) is not bool:
            raise NstDataApiError('invalid_response')
        for name in ('htmlRef', 'markdownRef', 'pdfRef', 'rawDataRef', 'screenshotRef'):
            if getattr(data, name) is not None and not isinstance(getattr(data, name), str):
                raise NstDataApiError('invalid_response')
        if data.links is not None and (not isinstance(data.links, list)
                                       or any(not isinstance(link, str) for link in data.links)):
            raise NstDataApiError('invalid_response')
        if data.metadata is not None:
            data.metadata = _build(PageMetadataDto, data.metadata)
            for name in ('canonical', 'description', 'language', 'ogImage', 'title'):
                value = getattr(data.metadata, name)
                if value is not None and not isinstance(value, str):
                    raise NstDataApiError('invalid_response')
            if data.metadata.statusCode is not None and type(data.metadata.statusCode) is not int:
                raise NstDataApiError('invalid_response')
        for name in ('html', 'markdown', 'pdf', 'screenshot', 'rawData'):
            value = raw.get(name)
            if value is not None and not isinstance(value, str):
                raise NstDataApiError('invalid_response')
            try:
                if value is not None and name in ('pdf', 'screenshot'):
                    if '=' in value and (len(value) % 4 or len(value) - len(value.rstrip('=')) > 2):
                        raise ValueError('Invalid Base64 padding')
                    value = base64.b64decode(value + '=' * (-len(value) % 4), validate=True)
                elif value is not None and name == 'rawData':
                    value = value.encode('utf-8')
            except ValueError:
                raise NstDataApiError('invalid_response') from None
            setattr(data, '_' + name, value)
        data._client = self
        return data

    def _result(self, raw):
        result = _build(TaskResultResponseDto, raw)
        result.data = self._data(raw.get('data'))
        return result

    @staticmethod
    def _submission(req):
        if not isinstance(req.url, str) or not req.url.strip():
            raise ValueError('url is required')
        if not req.formats:
            raise ValueError('formats must contain at least one format')
        return req.to_dict()

    def submit_scrape_task(self, req: ScrapeRequestDto, *, timeout=None) -> SubmitResponseDto:
        return _build(SubmitResponseDto, self._request('POST', '/api/v1/crawl/scrape',
                      params={'async': 'true'}, body=self._submission(req), timeout=timeout))

    def submit_scrape_task_sync(self, req: ScrapeRequestDto, *, timeout=None) -> TaskResultResponseDto:
        return self._result(self._request('POST', '/api/v1/crawl/scrape',
                            body=self._submission(req), timeout=timeout))

    def get_scrape_task_result(self, task_id: str, *, timeout=None) -> TaskResultResponseDto:
        return self._result(self._request('GET', '/api/v1/crawl/scrape/' + _identifier(task_id), timeout=timeout))

    def submit_crawl_task(self, req: CrawlRequestDto, *, timeout=None) -> SubmitResponseDto:
        return _build(SubmitResponseDto, self._request('POST', '/api/v1/crawl',
                      body=self._submission(req), timeout=timeout))

    def get_crawl_status(self, crawl_id: str, *, timeout=None) -> CrawlStatusResponseDto:
        return _build(CrawlStatusResponseDto, self._request('GET', '/api/v1/crawl/' + _identifier(crawl_id), timeout=timeout))

    def list_crawl_pages(self, crawl_id: str, after_cursor=None, before_cursor=None,
                         limit=None, *, timeout=None) -> CrawlPageListResponseDto:
        if after_cursor is not None and before_cursor is not None:
            raise ValueError('Use only one pagination direction')
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0):
            raise ValueError('limit must be a positive integer')
        params = {key: value for key, value in
                  [('after_cursor', after_cursor), ('before_cursor', before_cursor), ('limit', limit)] if value is not None}
        raw = self._request('GET', '/api/v1/crawl/' + _identifier(crawl_id) + '/pages', params=params, timeout=timeout)
        result = _build(CrawlPageListResponseDto, raw)
        if result.data is not None:
            if not isinstance(result.data, list):
                raise NstDataApiError('invalid_response')
            result.data = [_build(CrawlPageItemResponseDto, item) for item in result.data]
            for page, original in zip(result.data, raw['data']):
                page.data = self._data(original.get('data'))
        return result

    def read_storage(self, st: str, *, timeout=None) -> bytes:
        _identifier(st)
        return self._request('GET', '/api/v1/crawl/storage/read', params={'st': st}, timeout=timeout, binary=True)

    def _read_text_storage(self, st, *, timeout=None):
        raw = self.read_storage(st, timeout=timeout)
        try:
            return raw.decode('utf-8')
        except UnicodeError:
            raise NstDataApiError('invalid_response') from None

    def _wait(self, read, task_id, *, max_polls, poll_interval, wait_timeout):
        if isinstance(max_polls, bool) or not isinstance(max_polls, int) or max_polls <= 0:
            raise ValueError('max_polls must be a positive integer')
        if isinstance(poll_interval, bool) or not isinstance(poll_interval, (int, float)) \
                or not math.isfinite(poll_interval) or poll_interval < 0:
            raise ValueError('poll_interval must be finite nonnegative seconds')
        if isinstance(wait_timeout, bool) or not isinstance(wait_timeout, (int, float)) \
                or not math.isfinite(wait_timeout) or wait_timeout <= 0:
            raise ValueError('wait_timeout must be positive finite seconds')
        deadline = time.monotonic() + wait_timeout
        for poll in range(max_polls):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NstDataApiError('wait_limit')
            result = read(task_id, timeout=tuple(min(part, remaining) for part in self.timeout))
            if result.status in ('completed', 'failed', 'expired') or getattr(result, 'success', None) is False:
                return result
            if result.status not in ('processing', 'scraping'):
                raise NstDataApiError('invalid_response')
            if poll + 1 < max_polls:
                time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        raise NstDataApiError('poll_limit')

    def wait_for_scrape(self, task_id, *, max_polls=20, poll_interval=1, wait_timeout=120):
        """Poll a known ID; never submit a new task. Terminal failures stay results."""
        return self._wait(self.get_scrape_task_result, task_id, max_polls=max_polls,
                          poll_interval=poll_interval, wait_timeout=wait_timeout)

    def wait_for_crawl(self, crawl_id, *, max_polls=20, poll_interval=1, wait_timeout=120):
        return self._wait(self.get_crawl_status, crawl_id, max_polls=max_polls,
                          poll_interval=poll_interval, wait_timeout=wait_timeout)

    def iter_crawl_pages(self, crawl_id, *, limit=20, max_batches=100):
        """Yield actual page records in API order, including failures/duplicates."""
        if isinstance(max_batches, bool) or not isinstance(max_batches, int) or max_batches <= 0:
            raise ValueError('max_batches must be a positive integer')
        cursor = None
        cursors = set()
        for _ in range(max_batches):
            page = self.list_crawl_pages(crawl_id, after_cursor=cursor, limit=limit)
            if page.data is None:
                raise NstDataApiError('invalid_response')
            yield from page.data
            if page.nextCursor is None or page.nextCursor == '':
                return
            if not isinstance(page.nextCursor, str):
                raise NstDataApiError('invalid_response')
            if page.nextCursor in cursors:
                raise NstDataApiError('repeated_cursor')
            cursors.add(page.nextCursor)
            cursor = page.nextCursor
        raise NstDataApiError('page_limit')

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
