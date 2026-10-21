# Nstdata Crawl SDK for Python

[中文](README_zh.md)

A synchronous client for single-page scraping, site crawling, cursor pagination and deferred downloads.

## Install

Requires Python 3.10+ and Requests >=2.34.2,<3. Version `1.0.0` is prepared locally and not yet published. After publication, install with:

```sh
python -m pip install nstdata-ai-crawl==1.0.0
```

Published `0.1.1` has different behavior. Review [CHANGELOG.md](CHANGELOG.md) before upgrading; the package name `nstdata-ai-crawl` and import `nstdata_ai_crawl` are retained. Local archive installation and source builds are covered in [Contributing](CONTRIBUTING.md).

## Single page

Set `NSTDATA_API_TOKEN` in your environment. Running this example creates one task and may consume credits.

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

## Tasks and results

| Method | Purpose |
|---|---|
| `submit_scrape_task_sync` | Submit and consume a synchronous single-page result |
| `submit_scrape_task` | Submit once, then save the returned ID |
| `get_scrape_task_result`, `wait_for_scrape` | Read or wait for an existing scrape |
| `submit_crawl_task`, `get_crawl_status`, `wait_for_crawl` | Submit and inspect a site crawl |
| `list_crawl_pages`, `iter_crawl_pages` | Read cursor-paginated results |
| `read_storage` | Read an opaque storage reference |

Requests use `https://api.nstdata.io/api/v1/crawl` and `x-api-key`. Sync scrape uses `/scrape`; async adds `?async=true`. Results use `/scrape/{id}`, site progress `/{id}`, pages `/{id}/pages`, storage `/storage/read?st=…`. IDs and query values are encoded by the client.

Async and site submissions are not retried. Preserve the ID before further calls. Wait helpers accept `max_polls`, `poll_interval` and `wait_timeout`; page iteration accepts `limit` and `max_batches`. Failed/expired tasks remain typed results. Local interruption does not cancel remote work.

Pagination preserves service order, duplicate URLs and failed rows. An empty page can still have a next cursor; repeated cursors and batch limits raise errors. Previously yielded pages remain partial if a later read fails. Site completion does not establish every page succeeded.

Crawl traversal filters are forwarded unchanged; the SDK does not interpret their matching syntax.

Deferred getters read only when called and cache successful results, including empty strings. Missing text is `None`, distinct from `''`. Use `get_markdown()` and other getters rather than treating a storage reference as a URL. `rawData` is bytes, not a structured-JSON extraction guarantee.

PDF/screenshot/raw-data getters return `bytes`. Inline PDF/screenshots are decoded from Base64; inline raw text is encoded as UTF-8. Present inline content, including empty content, takes precedence over references. Otherwise getters read and cache the referenced bytes.

Results retain service-provided `id` and `data.truncated`, including `False`. An absent truncation flag is unknown; a synchronous result ID alone does not guarantee that its content can be queried again.

## Timeouts and errors

`NstDataClient(token, *, base_url=..., timeout=(10, 120), max_response_bytes=16777216)` keeps the positional token constructor. API/storage methods and getters accept a per-call `timeout` override, in seconds. DTO `timeout` remains server-side milliseconds.

DTO `timeout` uses integer milliseconds from 1000 to 60000; `jsRender.waitFor` uses integer milliseconds from 1000 to 30000. Action wait times and scroll coordinates are integers. DTO values are forwarded without coercion; the service validates them.

Requests timeouts bound connection and read inactivity, not total wall-clock duration. `wait_timeout` bounds checks/sleeps and clips HTTP timeouts but cannot interrupt a blocked synchronous call. There is no native asyncio cancellation. Use a separate client for each concurrent worker.

Decoded response bodies default to a 16 MiB cap per response; chunk and parser copies add memory overhead. Redirects are rejected. The default Session does not retry. TLS verification remains enabled, and Requests environment proxy/CA behavior applies. Context-manager exit closes the Session.

`NstDataApiError` exposes `kind`, optional `status_code` and `api_code`; raw response/network messages are omitted. Input validation raises `ValueError`. A failed task is a result, not an HTTP exception. Treat task fields and webpage content as untrusted data.

Malformed inline Base64, non-string inline content, invalid UTF-8 raw text, invalid reference/link/metadata types and non-boolean truncation flags raise `NstDataApiError(kind='invalid_response')` without response values. Null inline values are treated as absent.

## Development

See [Contributing](CONTRIBUTING.md) for setup, builds and package checks. Tests use mocks and loopback HTTP. Running `main.py` sends a real scrape; importing it does not.

[Contributing](CONTRIBUTING.md) · [API documentation](https://docs.nstdata.io/docs/crawl) · [MIT license](LICENSE)
