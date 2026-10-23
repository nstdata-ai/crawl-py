# Python SDK usage guide

[中文](guide_zh.md) · [Quick start](../README.md)

## Methods

| Method | Input / result |
|---|---|
| `submit_scrape_task_sync` | `ScrapeRequestDto` → `TaskResultResponseDto` |
| `submit_scrape_task` | `ScrapeRequestDto` → `SubmitResponseDto` with a task ID |
| `get_scrape_task_result` | Task ID → `TaskResultResponseDto` |
| `wait_for_scrape` | Known task ID and polling bounds → terminal scrape result |
| `submit_crawl_task` | `CrawlRequestDto` → `SubmitResponseDto` with a crawl ID |
| `get_crawl_status`, `wait_for_crawl` | Known crawl ID → `CrawlStatusResponseDto` |
| `list_crawl_pages` | Crawl ID, one cursor direction and optional `limit` → `CrawlPageListResponseDto` |
| `iter_crawl_pages` | Crawl ID, `limit`, `max_batches` → page iterator |
| `read_storage` | Opaque storage reference → `bytes` |

## Async tasks

Submit once, save `submitted.id`, then query that same ID. The example creates one single-page task; queries and deferred downloads may also consume quota.

```python
import os
from nstdata_ai_crawl import NstDataClient, ScrapeRequestDto, NstDataApiError

with NstDataClient(os.environ['NSTDATA_API_TOKEN']) as client:
    submitted = client.submit_scrape_task(ScrapeRequestDto(
        url='https://example.com/', formats=['markdown'], onlyMainContent=True,
    ))
    if not isinstance(submitted.id, str) or not submitted.id.strip():
        raise NstDataApiError('invalid_response')
    print('Save task ID:', submitted.id)
    result = client.wait_for_scrape(
        submitted.id, max_polls=4, poll_interval=1, wait_timeout=120,
    )
    if result.status != 'completed' or result.success is not True or result.data is None:
        raise NstDataApiError('task_failed')
    markdown = result.data.get_markdown()
    if markdown is None:
        raise NstDataApiError('missing_content')
```

Use `get_scrape_task_result(task_id, timeout=...)` for one query, or `wait_for_scrape` for bounded polling. `failed`/`expired` and `success=False` remain typed terminal results. A missing submission ID or an uncertain creation response does not justify submitting again; inspect task history before deciding what to do next.

## Site crawls

This example bounds creation to two pages and reads only successful completed page bodies. `maxPages` is an upper bound, not a promised count.

```python
import os
from nstdata_ai_crawl import NstDataClient, CrawlRequestDto, NstDataApiError

with NstDataClient(os.environ['NSTDATA_API_TOKEN']) as client:
    submitted = client.submit_crawl_task(CrawlRequestDto(
        url='https://quotes.toscrape.com/', formats=['markdown'],
        maxPages=2, maxDepth=1, includeUrls=['/page/2/'], onlyMainContent=False,
    ))
    if not isinstance(submitted.id, str) or not submitted.id.strip():
        raise NstDataApiError('invalid_response')
    print('Save crawl ID:', submitted.id)
    state = client.wait_for_crawl(
        submitted.id, max_polls=4, poll_interval=1, wait_timeout=120,
    )
    if state.status != 'completed':
        raise NstDataApiError('task_failed')
    for page in client.iter_crawl_pages(submitted.id, limit=2, max_batches=10):
        print(page.url, page.status, page.success)
        if page.status != 'completed' or page.success is not True or page.data is None:
            continue
        markdown = page.data.get_markdown()
        if markdown is None:
            raise NstDataApiError('missing_content')
        print(markdown)
```

`onlyMainContent=False` includes navigation and can help link discovery. Filters are forwarded unchanged; verify actual returned URLs instead of inferring the full matching grammar.

`list_crawl_pages(crawl_id, after_cursor=..., limit=...)` returns `data`, `nextCursor` and `prevCursor`. Supply at most one of `after_cursor` and `before_cursor`. `iter_crawl_pages` follows the actual next cursor, including after empty pages, and preserves order, duplicate URLs and failed rows. It stops on repeated cursors or the batch limit. Pages yielded before a later error remain partial results. An aggregate completed state does not establish that every page succeeded.

## Content and references

| Getter on `result.data` | Return value |
|---|---|
| `get_markdown`, `get_html` | UTF-8 text or `None` |
| `get_pdf`, `get_screenshot`, `get_raw_data` | `bytes` or `None` |

Present inline content takes precedence over a reference, including empty text/bytes. Otherwise the getter downloads the matching opaque reference and caches a successful result. A failed read is not cached. Each getter accepts a local `timeout` override. Raw data is bytes, not a structured JSON extraction guarantee.

Inline PDF/screenshots are Base64-decoded; inline raw text is UTF-8-encoded. `read_storage(st)` reads referenced bytes directly. HTML/Markdown reference downloads require valid UTF-8; raw byte reads preserve the response.

Preserve `page.url`, `page.taskId`, status/success, `data.metadata` and `data.truncated` when preparing downstream content. Missing content is `None`, not an empty body. `truncated=True` means partial service output; an absent flag is unknown. A synchronous result's optional `id` is diagnostic identity, not proof that the async endpoint can retrieve that result.

## Request options

```python
from nstdata_ai_crawl import ScrapeRequestDto, ProxyDto, JsRenderDto, ActionDto

request = ScrapeRequestDto(
    url='https://example.com/', formats=['markdown', 'links'],
    proxy=ProxyDto(country='us'),
    jsRender=JsRenderDto(waitFor=1000, actions=[ActionDto.wait_selector('main', 5000)]),
    onlyMainContent=True, timeout=60000,
)
```

`ScrapeRequestDto` and `CrawlRequestDto` serialize supplied values without coercion, omit `None` and let the service validate values. Set a nonempty `url` and `formats`. Available fields include:

- `formats`: `markdown`, `html`, `links`, `pdf`, `screenshot`, `rawData` (also exported as `Format` constants).
- `cookies`, `headers`, `proxy=ProxyDto(country=...)`, `mobile`.
- `onlyMainContent`, `includeTags`, `excludeTags`, `removeSelectors`, `targetSelector`.
- `jsRender=JsRenderDto(actions=..., waitFor=..., waitForSelector=...)`. Action helpers cover click, fill, wait, selector/network waits, scrolling, JavaScript and screenshots; the Crawl service executes them.
- Crawl-only `maxDepth`, `maxPages`, `includeUrls`, `excludeUrls`, `ignoreQuery`.

DTO `timeout` uses integer milliseconds from 1000 to 60000. `JsRenderDto.waitFor` uses integer milliseconds from 1000 to 30000. Action wait times and scroll coordinates are integers. Local HTTP timeouts are separate and accept fractional seconds.

## Timeouts and errors

`NstDataClient(token, *, base_url='https://api.nstdata.io', timeout=(10, 120), max_response_bytes=16777216)` accepts a token as its positional argument. API/storage methods and getters accept per-call `timeout` overrides in seconds, as a positive number or `(connect, read)` tuple.

Requests timeouts bound connection and read inactivity, not total wall-clock time. Wait helpers default to 20 polls, 1 second between polls and `wait_timeout=120`; they clip each HTTP timeout and bound checks/sleeps but cannot interrupt an already blocked synchronous call. There is no native asyncio cancellation. Use a separate client for each concurrent worker.

The decoded-body cap defaults to 16 MiB per response; chunk/parser copies add memory overhead. Redirects are rejected and the default Session does not retry. TLS verification and Requests environment proxy/CA behavior remain enabled. Context-manager exit closes the Session.

`NstDataApiError` exposes `kind`, optional `status_code` and `api_code`, without raw provider/network messages:

| Kind | Meaning |
|---|---|
| `http`, `api` | Non-2xx HTTP status or unsuccessful API envelope |
| `timeout`, `transport` | Local connection/read timeout or transport/encoding failure |
| `invalid_json`, `invalid_response` | Unparseable JSON or malformed known response fields |
| `response_limit` | Decoded response exceeds the configured byte cap |
| `poll_limit`, `wait_limit` | Poll count or local waiting budget exhausted |
| `page_limit`, `repeated_cursor` | Page iteration bound or repeated cursor |

Present known scalar fields are checked against their DTO types; missing/null optional fields remain optional and unknown fields are ignored. Known references, links, metadata, inline content, Base64 and truncation flags are validated. Local input validation raises `ValueError`. The examples use caller-defined `task_failed`/`missing_content` kinds for their content requirements.

Task failures remain results rather than HTTP exceptions. Treat page content and task fields as untrusted data. A timeout or interruption does not cancel remote work; an unknown submission outcome must not trigger automatic creation retries.

## API routes

The client uses `x-api-key` and the configured origin, encoding task IDs and query values.

| Operation | Route |
|---|---|
| Sync / async scrape | `POST /api/v1/crawl/scrape`; async adds `?async=true` |
| Scrape result | `GET /api/v1/crawl/scrape/{id}` |
| Crawl / status | `POST /api/v1/crawl`, `GET /api/v1/crawl/{id}` |
| Pages | `GET /api/v1/crawl/{id}/pages` with cursor/limit parameters |
| Storage | `GET /api/v1/crawl/storage/read?st=...` |
