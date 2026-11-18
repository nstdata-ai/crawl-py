<p align="center">
  <img src="https://raw.githubusercontent.com/nstdata-ai/nstdata-mcp-server/main/docs/assets/mcp-banner.png" alt="Nstdata — Power AI Agent with Internet Data" width="960">
</p>

<h1 align="center">Nstdata Crawl SDK for Python</h1>

<p align="center">在 Python 应用中调用 Nstdata Crawl API，获取网页内容。</p>

<p align="center">
  <a href="https://pypi.org/project/nstdata-ai-crawl/"><img src="https://img.shields.io/pypi/v/nstdata-ai-crawl?logo=pypi" alt="PyPI version"></a>
  <a href="https://pypi.org/project/nstdata-ai-crawl/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python" alt="Python versions"></a>
  <a href="https://github.com/nstdata-ai/crawl-py/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License"></a>
  <a href="https://github.com/nstdata-ai/crawl-py/stargazers"><img src="https://img.shields.io/github/stars/nstdata-ai/crawl-py?style=social" alt="GitHub stars"></a>
</p>

<p align="center">
  <a href="https://app.nstdata.io/?utm_source=github&amp;utm_medium=social&amp;utm_campaign=crawl-python-sdk&amp;utm_content=readme"><img src="https://img.shields.io/badge/Dashboard-4F46E5?style=for-the-badge&amp;logo=googlechrome&amp;logoColor=white" alt="Dashboard"></a>
  <a href="https://docs.nstdata.io/zh-CN/docs/crawl/?utm_source=github&amp;utm_medium=social&amp;utm_campaign=crawl-python-sdk&amp;utm_content=readme"><img src="https://img.shields.io/badge/Crawl_API_Docs-2563EB?style=for-the-badge&amp;logo=readthedocs&amp;logoColor=white" alt="Crawl API documentation"></a>
  <a href="https://discord.gg/sMsfTzCpe7"><img src="https://img.shields.io/badge/Join_our_Discord-5865F2?style=for-the-badge&amp;logo=discord&amp;logoColor=white" alt="Join our Discord"></a>
  <a href="https://x.com/nstdata"><img src="https://img.shields.io/badge/Follow_on_X-000000?style=for-the-badge&amp;logo=x&amp;logoColor=white" alt="Follow on X"></a>
</p>

[English](README.md) · [简体中文](README_zh.md)

---

在 Python 应用中调用 Nstdata Crawl API，抓取单个网页、提交远端任务，或按深度与页面数限制抓取网站。

获取 Markdown、HTML、链接、PDF、截图或原始字节。SDK 使用同步 Requests；远端异步任务并不代表客户端支持 Python asyncio。

[GitHub 仓库](https://github.com/nstdata-ai/crawl-py) · [快速开始](#快速开始) · [完整使用指南](docs/guide_zh.md)

## 环境要求

- Python 3.10 及以上版本。
- 一个 [Nstdata API Key](https://app.nstdata.io/) 和可用额度，使用调用 Crawl 的同一个 Key。

安装包直接连接 Crawl API，无需 MCP。

## 安装

在运行应用的 Python 环境中安装 SDK，当前版本为 1.0.1：

```sh
python -m pip install nstdata-ai-crawl
```

安装名称为 `nstdata-ai-crawl`，Python 导入名称为 `nstdata_ai_crawl`。

## 认证

在运行脚本的环境中设置 API Key。

macOS / Linux：

```sh
export NSTDATA_API_TOKEN='your-api-key'
```

Windows PowerShell：

```powershell
$env:NSTDATA_API_TOKEN = "your-api-key"
```

读取环境变量并传给 `NstDataClient`。SDK 使用 `x-api-key` 认证。不要将凭据写入源码或提交到版本控制。仅创建 `.env` 不会自动加载环境变量；应导出变量或在应用中显式加载文件。

## 快速开始

将完整示例保存为 `quickstart.py`。它提交一次单页任务，验证结果并输出 Markdown。实际服务请求会消耗额度。

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

运行脚本：

```sh
python quickstart.py
```

`submit_scrape_task_sync()` 会阻塞等待服务响应。内容 getter 可能额外下载引用内容，因此应在 `with` 块内、客户端关闭前读取正文。

## 输出格式

通过 `formats` 在一次任务中请求一种或多种输出。

| 格式值 | 从 `result.data` 读取 | 输出 |
| --- | --- | --- |
| `markdown` | `get_markdown()` | 字符串或 `None` |
| `html` | `get_html()` | 字符串或 `None` |
| `links` | `links` | 返回的链接字段 |
| `pdf` | `get_pdf()` | 字节或 `None` |
| `screenshot` | `get_screenshot()` | 字节或 `None` |
| `rawData` | `get_raw_data()` | 字节或 `None` |

同时请求 Markdown 和 HTML 时，设置 `formats=["markdown", "html"]`。验证任务成功后，调用 `result.data.get_markdown()` 和 `result.data.get_html()`。原始数据是字节，并不执行结构化 JSON 提取。

## 核心工作流

先配置认证，每个示例分别运行。下方片段展示主要操作；使用返回内容前，应应用快速开始中的状态验证和错误处理。

### 提交异步单页抓取

只提交一次，保存任务 ID 后再读取结果。这些 Python 调用仍然是同步调用。

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

`get_scrape_task_result(task_id)` 查询一次；`wait_for_scrape()` 执行有上限的轮询。应先保存 ID 再轮询。本地等待达到限制时，继续使用同一个 ID，不要自动创建新任务。

终态任务失败也可能作为类型化结果返回。读取正文前，检查状态、`success` 和 `data`。详见[任务生命周期和轮询](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#async-tasks)。

### 抓取网站

设置 `maxPages` 和 `maxDepth` 限制发现范围，等待完成后迭代页面结果：

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

`maxPages` 是上限，不保证返回相同数量的页面。`onlyMainContent=False` 保留可能有助于发现链接的导航内容。整站任务完成后仍可能有失败页面，应逐页检查。

手动分页可调用 `list_crawl_pages(crawl_id, limit=20)`，然后将返回的 `nextCursor` 作为下一次的 `after_cursor`。`after_cursor` 和 `before_cursor` 最多提供一个。单次读取的 `limit` 与 `maxPages` 不同。

迭代器根据实际游标继续读取，包括空批次之后仍有游标的情况，并在游标重复或达到批次数上限时停止。后续请求失败时，已收集的数据属于部分结果，应保留。详见[抓取和分页](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#site-crawls)。

### 渲染 JavaScript 与页面交互

页面需要执行 JavaScript 或交互后才能提取内容时，配置 `jsRender`，并选择实际存在的元素：

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

操作在 Crawl 服务端执行。辅助方法覆盖点击、输入、等待、滚动、JavaScript 和截图。读取内容前先验证结果。详见[渲染与请求配置](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#request-options)。

## 请求配置

使用 `ScrapeRequestDto` 或 `CrawlRequestDto`。Python 方法名采用 snake_case，DTO 字段则保留 `onlyMainContent` 和 `maxPages` 等形式。

| 参数 | 用途 |
| --- | --- |
| `formats` | 选择输出格式 |
| `onlyMainContent` | 聚焦正文 |
| `targetSelector`、`removeSelectors` | 指定或移除匹配内容 |
| `includeTags`、`excludeTags` | 标签保留与排除 |
| `headers`、`cookies`、`mobile` | 目标页面请求设置 |
| `proxy=ProxyDto(country="us")` | 请求出口国家；从 `nstdata_ai_crawl` 导入 `ProxyDto` |
| `jsRender` | 渲染与页面操作 |
| `timeout` | 服务端超时，单位为毫秒 |
| `maxPages`、`maxDepth` | 网站抓取范围 |
| `includeUrls`、`excludeUrls`、`ignoreQuery` | 抓取 URL 筛选 |

DTO 的 `timeout` 接受 1,000–60,000 整数毫秒；`JsRenderDto.waitFor` 接受 1,000–30,000 毫秒。本地 HTTP 超时则以秒为单位。DTO 省略 `None`，不强制转换已提供的值，由服务验证。使用 URL 过滤器时应核对实际返回的 URL。

[请求字段和约束](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#request-options)

### 客户端与请求控制

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

将 `YOUR_TASK_ID` 替换为已保存的异步任务 ID。默认连接/读取空闲超时为 `(10, 120)` 秒，每个解码响应的默认上限为 16 MiB。API 方法和内容 getter 可覆盖单次调用的超时。

Requests 超时不等同于整个工作流的总截止时间。等待辅助方法能限制轮询，但不能中断已经阻塞的同步调用。本地停止不会取消远端任务。并发 worker 应分别使用客户端。

## 结果与错误处理

| 情况 | 处理方式 |
| --- | --- |
| 任务尚未到达终态 | 稍后查询同一个异步 ID |
| 状态为 `failed` / `expired`，或 `success is False` | 视为任务或页面失败 |
| `data is None` | 不调用内容 getter |
| getter 返回 `None` | 处理输出格式缺失 |
| 空字符串或空字节 | 有效空内容，与 `None` 不同 |
| `data.truncated is True` | 保留标记并将内容视为部分输出 |

生成下游文档时，保留源 URL、可用的任务 ID、状态、`success`、元数据和截断信息。缺少截断标记并不能证明内容完整。

`NstDataApiError` 提供 `kind`、可选的 `status_code` 和 `api_code`，字段名与 Node.js SDK 不同。

| 错误类别 | 含义 |
| --- | --- |
| `http`、`api` | HTTP 失败或 API 错误信封 |
| `timeout`、`transport` | 本地超时或传输失败 |
| `invalid_json`、`invalid_response` | 响应无法解析或结构错误 |
| `response_limit` | 解码响应超过本地字节上限 |
| `poll_limit`、`wait_limit` | 达到轮询或等待限制 |
| `page_limit`、`repeated_cursor` | 达到分页限制或游标重复 |

本地输入验证可能抛出 `ValueError`。示例中的 `task_failed` 和 `missing_content` 是应用层主动检查。版本 1.0.1 导出 `TaskStatus.EXPIRED`，对应 `"expired"` 状态；字符串判断仍然有效。失败或过期任务可能作为类型化结果返回，因此使用内容前必须检查状态和 `success`。

默认客户端不会自动重试。提交超时时，结果可能未知；决定是否重新提交前，请先检查任务历史。

[超时与错误说明](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#timeouts-and-errors)

## 常见问题

| 问题 | 检查项 |
| --- | --- |
| `ModuleNotFoundError` | 在运行脚本的同一环境中用 `python -m pip` 安装，并导入 `nstdata_ai_crawl` |
| 缺少 API Key | 在运行进程中设置 `NSTDATA_API_TOKEN`；`.env` 需要显式加载 |
| 认证失败 | 检查 Key、Crawl 访问权限，以及 `status_code` 和 `api_code` |
| 仍在运行或轮询达到上限 | 保存任务 ID，稍后继续读取 |
| 缺少 Markdown / HTML | 确认请求了格式、任务成功完成且有 `data`，使用 getter 读取引用内容 |
| 动态内容缺失 | 配置适合页面的 `jsRender` 选择器与操作 |
| 本地超时 | 区分本地秒数和 DTO 毫秒，保留 ID 并避免自动重提 |
| 截断或响应过大 | 服务截断与本地 `response_limit` 是两种情况，应分别处理 |
| 页面数量少于预期 | `maxPages` 是上限，应检查 URL、过滤器、页面结果和游标 |
| asyncio 接入 | 当前客户端为同步实现，远端异步任务不提供原生 asyncio 支持 |

[方法参考](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#methods) · [API 路由](https://github.com/nstdata-ai/crawl-py/blob/main/docs/guide.md#api-routes) · [更新记录](https://github.com/nstdata-ai/crawl-py/blob/main/CHANGELOG.md) · [反馈 SDK 问题](https://github.com/nstdata-ai/crawl-py/issues)
