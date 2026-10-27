# Nstdata Crawl SDK for Python

[中文](README_zh.md)

A synchronous Python client for retrieving webpage content through Nstdata Crawl.

## Features

| Capability | Guide |
|---|---|
| Single page | Retrieve Markdown, HTML, links, PDF, screenshots or raw bytes. |
| Async tasks | [Submit once and resume by task ID](docs/guide.md#async-tasks). |
| Site crawling | [Bound the crawl and read cursor-paginated pages](docs/guide.md#site-crawls). |
| Deferred results | [Read referenced content on demand](docs/guide.md#content-and-references). |
| Page options | [Configure rendering, actions, filtering, cookies, headers and proxy country](docs/guide.md#request-options). |

## Install

Requires Python 3.10+.

```sh
python -m pip install nstdata-ai-crawl
```

Upgrading from `0.1.1`? Review the [compatibility changes](CHANGELOG.md#100).

## Quick start

Set your API key in the environment (macOS/Linux):

```sh
export NSTDATA_API_TOKEN='your-api-key'
```

Save the following as `quickstart.py`. It submits one page task and prints Markdown; service calls consume credits.

```python
import os
from nstdata_ai_crawl import NstDataClient, ScrapeRequestDto, NstDataApiError

token = os.environ.get('NSTDATA_API_TOKEN')
if not token or not token.strip():
    raise SystemExit('Set NSTDATA_API_TOKEN in your environment.')

try:
    with NstDataClient(token, max_response_bytes=1048576) as client:
        result = client.submit_scrape_task_sync(ScrapeRequestDto(
            url='https://example.com/', formats=['markdown'],
            onlyMainContent=True, timeout=60000,
        ))
        if result.success is False or result.status in ('failed', 'expired'):
            raise NstDataApiError('task_failed')
        if result.status != 'completed' or result.success is not True or result.data is None:
            raise NstDataApiError('missing_content')
        markdown = result.data.get_markdown()
        if markdown is None:
            raise NstDataApiError('missing_content')
        print(markdown)
except NstDataApiError as error:
    raise SystemExit(f'Crawl failed: {error.kind}') from None
```

Run it:

```sh
python quickstart.py
```

The getters handle inline content and deferred references. Missing content is `None`; an empty string is a valid empty body. See the [usage guide](docs/guide.md) for complete workflows, method inputs/results and failure handling.

## Limits

- Local HTTP timeouts use seconds; request DTO timeouts use server-side milliseconds.
- This client uses synchronous Requests. Connection/read timeouts are not a total wall-clock deadline, and stopping local work does not cancel a remote task.
- Creation is not retried automatically. Keep returned task IDs before further calls.

[Timeouts and errors](docs/guide.md#timeouts-and-errors) · [Contributing](CONTRIBUTING.md) · [API documentation](https://docs.nstdata.io/docs/crawl) · [MIT license](LICENSE)
