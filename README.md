<p align="center">
  <img src="https://raw.githubusercontent.com/nstdata-ai/nstdata-mcp-server/main/docs/assets/mcp-banner.png" alt="Nstdata — Power AI Agent with Internet Data" width="960">
</p>

<h1 align="center">Nstdata Crawl SDK for Python</h1>

<p align="center">Retrieve web content from your Python applications through the Nstdata Crawl API.</p>

<p align="center">
  <a href="https://pypi.org/project/nstdata-ai-crawl/"><img src="https://img.shields.io/pypi/v/nstdata-ai-crawl?logo=pypi" alt="PyPI version"></a>
  <a href="https://pypi.org/project/nstdata-ai-crawl/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python" alt="Python versions"></a>
  <a href="https://github.com/nstdata-ai/crawl-py/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License"></a>
  <a href="https://github.com/nstdata-ai/crawl-py/stargazers"><img src="https://img.shields.io/github/stars/nstdata-ai/crawl-py?style=social" alt="GitHub stars"></a>
</p>

<p align="center">
  <a href="https://app.nstdata.io/?utm_source=github&amp;utm_medium=social&amp;utm_campaign=crawl-python-sdk&amp;utm_content=readme"><img src="https://img.shields.io/badge/Dashboard-4F46E5?style=for-the-badge&amp;logo=googlechrome&amp;logoColor=white" alt="Dashboard"></a>
  <a href="https://docs.nstdata.io/docs/crawl/?utm_source=github&amp;utm_medium=social&amp;utm_campaign=crawl-python-sdk&amp;utm_content=readme"><img src="https://img.shields.io/badge/Crawl_API_Docs-2563EB?style=for-the-badge&amp;logo=readthedocs&amp;logoColor=white" alt="Crawl API documentation"></a>
  <a href="https://discord.gg/sMsfTzCpe7"><img src="https://img.shields.io/badge/Join_our_Discord-5865F2?style=for-the-badge&amp;logo=discord&amp;logoColor=white" alt="Join our Discord"></a>
  <a href="https://x.com/nstdata"><img src="https://img.shields.io/badge/Follow_on_X-000000?style=for-the-badge&amp;logo=x&amp;logoColor=white" alt="Follow on X"></a>
</p>

[English](README.md) · [简体中文](README_zh.md)

---

Access the Nstdata Crawl API from your Python applications. Scrape individual pages, submit remote tasks, and crawl websites with configurable depth and page limits.

Retrieve content as Markdown, HTML, links, PDFs, screenshots, or raw bytes. The SDK uses synchronous Requests: remote asynchronous tasks do not provide a Python asyncio client.

[GitHub repository](https://github.com/nstdata-ai/crawl-py) · [Quick Start](https://github.com/nstdata-ai/crawl-py#quick-start) · [Usage guide](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md)

## Prerequisites

- Python 3.10 or later.

- A [Nstdata API key](https://app.nstdata.io/) with access to Crawl and available credits.

This package connects directly to the Crawl API. MCP is not required.

## Installation

Install the SDK in the Python environment used by your application. The current release is 1.0.1:

```sh
python -m pip install nstdata-ai-crawl
```

The installation name is `nstdata-ai-crawl`; the Python import name is `nstdata_ai_crawl`.

## Authentication

Set the API key in the environment where you run the script.

macOS / Linux:

```sh
export NSTDATA_API_TOKEN='your-api-key'
```

Windows PowerShell:

```powershell
$env:NSTDATA_API_TOKEN = "your-api-key"
```

Read the variable and pass it to `NstDataClient`. The SDK authenticates requests with `x-api-key`. Keep credentials out of source code and version control. Creating a .env file alone does not load it into these examples; export the variable or explicitly load the file in your application.

## Quick Start

Save this complete example as `quickstart.py`. It submits a single-page task, validates the result, and prints Markdown. Live service requests consume credits.

```python
import os
import sys
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
        if result.data.truncated is True:
            print('Warning: service returned truncated content; output is partial.', file=sys.stderr)
        print(markdown)
except NstDataApiError as error:
    raise SystemExit(f'Crawl failed: {error.kind}') from None
```

Run the script:

```sh
python quickstart.py
```

`submit_scrape_task_sync()` blocks while waiting for the service response. Content getters may make an additional request to download referenced content. Read content inside the `with` block, before the client closes.

## Output Formats

Use `formats` to request one or more outputs in a task.

| Format value | Read from result.data | Output |
| --- | --- | --- |
| markdown | get_markdown() | Text or None |
| html | get_html() | Text or None |
| links | links | Returned links field |
| pdf | get_pdf() | Bytes or None |
| screenshot | get_screenshot() | Bytes or None |
| rawData | get_raw_data() | Bytes or None |

For Markdown and HTML together, set `formats=["markdown", "html"]`. After validating the result, call `result.data.get_markdown()` and `result.data.get_html()`.

## Core Workflows

Run each example separately after configuring authentication. The workflow snippets below show the main operations; apply the result validation and error handling from Quick Start before using returned content.

### Submit an asynchronous scrape

Submit once and save the task ID to retrieve the result later. These Python calls remain synchronous.

```python
import os
from nstdata_ai_crawl import NstDataClient, ScrapeRequestDto, NstDataApiError

with NstDataClient(os.environ["NSTDATA_API_TOKEN"]) as client:
    task = client.submit_scrape_task(ScrapeRequestDto(
        url="https://example.com/",
        formats=["markdown"],
        onlyMainContent=True,
    ))
    if not isinstance(task.id, str) or not task.id.strip():
        raise NstDataApiError("invalid_response")
    print("Save task ID:", task.id)
    result = client.wait_for_scrape(
        task.id, max_polls=4, poll_interval=1, wait_timeout=120,
    )
    print(result.status, result.success)
```

Use `get_scrape_task_result(task_id)` for a single query, or `wait_for_scrape()` for bounded polling. Save the ID before polling. If local waiting reaches its limit, continue with the same ID; do not create another task automatically.

Terminal task failures can be returned as typed results. Validate status, success, and data before reading the body. See [task lifecycle and polling](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#async-tasks).

### Crawl a website

Set `maxPages` and `maxDepth` to bound discovery, wait for completion, then iterate through page results:

```python
import os
import sys
from nstdata_ai_crawl import NstDataClient, CrawlRequestDto, NstDataApiError

with NstDataClient(os.environ["NSTDATA_API_TOKEN"]) as client:
    crawl = client.submit_crawl_task(CrawlRequestDto(
        url="https://example.com/",
        formats=["markdown"],
        maxPages=2,
        maxDepth=1,
        onlyMainContent=False,
    ))
    if not isinstance(crawl.id, str) or not crawl.id.strip():
        raise NstDataApiError("invalid_response")
    print("Save crawl ID:", crawl.id)
    state = client.wait_for_crawl(
        crawl.id, max_polls=4, poll_interval=1, wait_timeout=120,
    )
    if state.status != "completed":
        raise NstDataApiError("task_failed")
    for page in client.iter_crawl_pages(crawl.id, limit=2, max_batches=10):
        print(page.url, page.status, page.success)
        if page.status != "completed" or page.success is not True or page.data is None:
            continue
        markdown = page.data.get_markdown()
        if markdown is None:
            raise NstDataApiError("missing_content")
        if page.data.truncated is True:
            print("Warning: page content is partial.", file=sys.stderr)
        print(markdown)
```

`maxPages` is an upper bound, not a promised result count. `onlyMainContent=False` retains navigation that may help discovery. A completed crawl can contain unsuccessful pages; inspect each row.

For manual pagination, use `list_crawl_pages(crawl_id, limit=20)`, then pass the returned `nextCursor` as `after_cursor`. Supply at most one of `after_cursor` and `before_cursor`. The per-request `limit` is separate from `maxPages`.

The iterator follows actual cursors, including after empty batches, and stops on repeated cursors or its batch limit. Retain collected rows as partial results if a later request fails. See [crawl and pagination details](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#site-crawls).

### Render JavaScript and run page actions

Configure `jsRender` when a page needs JavaScript or interactions before collection. Choose selectors that exist on the target page.

```python
import os
from nstdata_ai_crawl import NstDataClient, ScrapeRequestDto, JsRenderDto, ActionDto

with NstDataClient(os.environ["NSTDATA_API_TOKEN"]) as client:
    result = client.submit_scrape_task_sync(ScrapeRequestDto(
        url="https://example.com/",
        formats=["markdown"],
        jsRender=JsRenderDto(
            waitFor=1000,
            actions=[ActionDto.wait_selector("h1", 5000)],
        ),
        timeout=60000,
    ))
    print(result.status, result.success)
```

Actions execute in the Crawl service. Helpers cover clicking, filling, waits, scrolling, JavaScript, and screenshots. Validate the result before reading content. See [rendering and request options](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#request-options).

## Request Configuration

Use `ScrapeRequestDto` or `CrawlRequestDto`. Python method names use snake_case; DTO field names retain forms such as `onlyMainContent` and `maxPages`.

| Option | Purpose |
| --- | --- |
| formats | Select requested outputs |
| onlyMainContent | Focus on main page content |
| targetSelector, removeSelectors | Target or remove matching content |
| includeTags, excludeTags | Configure tag inclusion and exclusion |
| headers, cookies, mobile | Configure the target page request |
| proxy=ProxyDto(country="us") | Request a proxy country; import ProxyDto from nstdata_ai_crawl |
| jsRender | Configure rendering and page actions |
| timeout | Service-side task timeout, in milliseconds |
| maxPages, maxDepth | Bound website crawling |
| includeUrls, excludeUrls, ignoreQuery | Configure crawl URL selection |

DTO `timeout` accepts integer milliseconds from 1,000 to 60,000; `JsRenderDto.waitFor` accepts 1,000 to 30,000 milliseconds. Local HTTP timeouts use seconds. Request DTOs omit None and forward supplied values without coercion; the service validates them. Verify actual returned URLs when using URL filters.

[Request fields and constraints](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#request-options)

**Client and request controls**

```python
import os
from nstdata_ai_crawl import NstDataClient

with NstDataClient(
    os.environ["NSTDATA_API_TOKEN"],
    timeout=(10, 120),
    max_response_bytes=16777216,
) as client:
    result = client.get_scrape_task_result(
        "YOUR_TASK_ID",
        timeout=(5, 30),
    )
    print(result.status)
```

Replace YOUR_TASK_ID with a saved asynchronous scrape ID. The default connection/read inactivity timeout is (10, 120) seconds; the decoded response cap is 16 MiB per response. API calls and content getters accept per-call timeout overrides.

Requests timeouts are not a total wall-clock deadline. Wait helpers bound polling but cannot interrupt an already blocked synchronous call. Stopping local work does not cancel the remote task. Use a separate client for each concurrent worker.

## Results and Error Handling

| Condition | Handling |
| --- | --- |
| Task is not terminal | Query the same asynchronous task ID later |
| status is failed / expired, or success is False | Treat the task or page as unsuccessful |
| data is None | Do not call content getters |
| A getter returns None | Handle the missing output format |
| Empty string or bytes | Valid empty content; do not confuse it with None |
| data.truncated is True | Preserve the flag and treat output as partial |

Preserve source URL, task ID where available, status, success, metadata, and truncation when creating downstream documents. An absent truncation flag does not establish completeness.

`NstDataApiError` exposes `kind`, optional `status_code`, and optional `api_code`. These differ from the Node SDK error field names.

| Error kind | Meaning |
| --- | --- |
| http, api | HTTP failure or unsuccessful API envelope |
| timeout, transport | Local timeout or transport failure |
| invalid_json, invalid_response | Unparseable or malformed response |
| response_limit | Decoded response exceeds the byte cap |
| poll_limit, wait_limit | Local polling or waiting budget exhausted |
| page_limit, repeated_cursor | Pagination bound or repeated cursor reached |

Local input validation can raise `ValueError`. The examples use application-defined `task_failed` and `missing_content` checks. Version 1.0.1 exports `TaskStatus.EXPIRED` for the "expired" status. Failed or expired tasks can remain typed results rather than exceptions, so inspect status and success before consuming content. The existing string checks remain valid.

The default client does not retry automatically. A submission timeout can leave its outcome unknown, inspect task history before deciding whether to submit again.

[Timeouts and error reference](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#timeouts-and-errors)

## Troubleshooting

| Issue | What to check |
| --- | --- |
| ModuleNotFoundError | Install with python -m pip in the same environment that runs the script; import nstdata_ai_crawl. |
| Missing API key | Set NSTDATA_API_TOKEN in the running process. A .env file needs an explicit loader. |
| Authentication error | Check key validity and Crawl permissions; inspect status_code and api_code. |
| Task still running / polling limit | Keep the saved task ID and resume retrieval later. |
| Missing Markdown or HTML | Confirm the format was requested, status is completed, success is True, and data exists. Use the getter for deferred content. |
| Missing dynamic content | Configure jsRender and selectors/actions for the target page. |
| Local timeout | Distinguish seconds from DTO milliseconds. Preserve task IDs and avoid automatic resubmission. |
| Truncated content / response limit | Truncation is partial service output; response_limit is a local byte cap. Handle them separately. |
| Fewer crawl pages than expected | maxPages is a ceiling. Check discovered URLs, filters, page outcomes, and pagination cursors. |
| async / await integration | The current client is synchronous. Remote task mode does not provide native asyncio support. |

[Method reference](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#methods) · [API routes](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#api-routes) · [Release notes](https://github.com/nstdata-ai/crawl-py/blob/main/CHANGELOG.md) · [Report an SDK issue](https://github.com/nstdata-ai/crawl-py/issues)
