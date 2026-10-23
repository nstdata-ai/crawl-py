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

Requires Python 3.10+. Version `1.0.0` is not yet published; after publication:

```sh
python -m pip install nstdata-ai-crawl==1.0.0
```

For a local archive or source build, see [Contributing](CONTRIBUTING.md). Upgrading from `0.1.1` changes runtime requirements, the default API origin and error behavior; see [CHANGELOG](CHANGELOG.md).

## Quick start

Set `NSTDATA_API_TOKEN` in your environment. This example creates one task and may consume credits.

```python
import os
from nstdata_ai_crawl import NstDataClient, ScrapeRequestDto, NstDataApiError

with NstDataClient(os.environ['NSTDATA_API_TOKEN'], max_response_bytes=1048576) as client:
    result = client.submit_scrape_task_sync(ScrapeRequestDto(
        url='https://example.com/', formats=['markdown'], onlyMainContent=True,
        timeout=60000,  # Upstream milliseconds, separate from local HTTP seconds.
    ))
    if result.success is False or result.status in ('failed', 'expired'):
        raise NstDataApiError('task_failed')
    if result.status != 'completed' or result.success is not True or result.data is None:
        raise NstDataApiError('missing_content')
    markdown = result.data.get_markdown()
    if markdown is None:
        raise NstDataApiError('missing_content')
    # None is absent content; '' is a successful empty body. Preserve source/title.
```

The getters handle inline content and deferred references. Missing content is `None`; an empty string is a valid empty body. See the [usage guide](docs/guide.md) for complete workflows, method inputs/results and failure handling.

## Limits

- Local HTTP timeouts use seconds; request DTO timeouts use server-side milliseconds.
- This client uses synchronous Requests. Connection/read timeouts are not a total wall-clock deadline, and stopping local work does not cancel a remote task.
- Creation is not retried automatically. Keep returned task IDs before further calls.

[Timeouts and errors](docs/guide.md#timeouts-and-errors) · [Contributing](CONTRIBUTING.md) · [API documentation](https://docs.nstdata.io/docs/crawl) · [MIT license](LICENSE)
