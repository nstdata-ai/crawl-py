# Python SDK 使用指南

[English](guide.md) · [快速开始](../README_zh.md)

## 方法

| 方法 | 输入／结果 |
|---|---|
| `submit_scrape_task_sync` | `ScrapeRequestDto` → `TaskResultResponseDto` |
| `submit_scrape_task` | `ScrapeRequestDto` → 含任务 ID 的 `SubmitResponseDto` |
| `get_scrape_task_result` | 任务 ID → `TaskResultResponseDto` |
| `wait_for_scrape` | 已有任务 ID、轮询边界 → 单页终态结果 |
| `submit_crawl_task` | `CrawlRequestDto` → 含整站 ID 的 `SubmitResponseDto` |
| `get_crawl_status`、`wait_for_crawl` | 已有整站 ID → `CrawlStatusResponseDto` |
| `list_crawl_pages` | 整站 ID、单向游标、可选 `limit` → `CrawlPageListResponseDto` |
| `iter_crawl_pages` | 整站 ID、`limit`、`max_batches` → 页面迭代器 |
| `read_storage` | 不透明存储引用 → `bytes` |

## 异步任务

提交一次并保存 `submitted.id`，后续查询复用该 ID。此例创建一个单页任务；查询和延迟下载也可能消耗额度。

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

只查询一次可用 `get_scrape_task_result(task_id, timeout=...)`，有界轮询使用 `wait_for_scrape`。`failed`／`expired` 和 `success=False` 保留为终态结果。提交缺失 ID 或返回结果不确定时，不应直接重新提交；先核对任务历史再决定下一步。

## 整站抓取

此例最多创建两页，只读取已完成且成功的页面正文。`maxPages` 是上限，不保证返回该数量。

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

`onlyMainContent=False` 包含导航内容，有助于链接发现。过滤条件原样转发；核对实际返回 URL，不据此推断完整匹配语法。

`list_crawl_pages(crawl_id, after_cursor=..., limit=...)` 返回 `data`、`nextCursor` 和 `prevCursor`，`after_cursor` 与 `before_cursor` 至多传一个。`iter_crawl_pages` 沿实际下一游标读取，包括空页之后的游标，并保留顺序、重复 URL 和失败行。游标重复或批次超限时停止。后续读取失败时，之前产出的页面仍是部分结果；整站状态完成不代表每一页成功。

## 正文与引用

| `result.data` 的 getter | 返回值 |
|---|---|
| `get_markdown`、`get_html` | UTF-8 文本或 `None` |
| `get_pdf`、`get_screenshot`、`get_raw_data` | `bytes` 或 `None` |

内联内容存在时优先使用，包括空文本／空字节；否则 getter 下载相应不透明引用，并缓存成功结果。失败读取不缓存。每个 getter 支持按次覆盖本地 `timeout`。原始数据为字节，不代表结构化 JSON 提取。

内联 PDF／截图按 Base64 解码，内联原始文本按 UTF-8 编码。`read_storage(st)` 直接读取引用字节。HTML／Markdown 引用下载须为有效 UTF-8；原始字节读取保留响应内容。

向下游传递内容时保留 `page.url`、`page.taskId`、状态／成功标记、`data.metadata` 和 `data.truncated`。正文缺失是 `None`，不是空正文。`truncated=True` 表示服务内容不完整，缺失标记表示未知。同步结果的可选 `id` 只是诊断标识，不保证能通过异步查询接口再次取得结果。

## 请求选项

```python
from nstdata_ai_crawl import ScrapeRequestDto, ProxyDto, JsRenderDto, ActionDto

request = ScrapeRequestDto(
    url='https://example.com/', formats=['markdown', 'links'],
    proxy=ProxyDto(country='us'),
    jsRender=JsRenderDto(waitFor=1000, actions=[ActionDto.wait_selector('main', 5000)]),
    onlyMainContent=True, timeout=60000,
)
```

`ScrapeRequestDto` 和 `CrawlRequestDto` 原样序列化已传值、不做类型转换，省略 `None`，由服务校验字段值。必须设置非空 `url` 和 `formats`。可配置字段包括：

- `formats`：`markdown`、`html`、`links`、`pdf`、`screenshot`、`rawData`，也可使用导出的 `Format` 常量。
- `cookies`、`headers`、`proxy=ProxyDto(country=...)`、`mobile`。
- `onlyMainContent`、`includeTags`、`excludeTags`、`removeSelectors`、`targetSelector`。
- `jsRender=JsRenderDto(actions=..., waitFor=..., waitForSelector=...)`；动作 helper 包括点击、填充、等待、选择器／网络等待、滚动、JavaScript 和截图，由 Crawl 服务执行。
- 整站专用的 `maxDepth`、`maxPages`、`includeUrls`、`excludeUrls`、`ignoreQuery`。

DTO 的 `timeout` 为 1000–60000 整数毫秒；`JsRenderDto.waitFor` 为 1000–30000 整数毫秒。动作等待时间和滚动坐标使用整数。本地 HTTP 超时独立配置，支持小数秒。

## 超时与错误

`NstDataClient(token, *, base_url='https://api.nstdata.io', timeout=(10, 120), max_response_bytes=16777216)` 接受位置参数 Token。API／存储方法和 getter 的按次 `timeout` 使用秒，可传正数或 `(connect, read)` 元组。

Requests 超时限制连接和读取空闲时间，不是总墙钟期限。等待 helper 默认最多 20 次查询、间隔 1 秒、`wait_timeout=120`；会裁剪每次 HTTP 超时并限制检查／休眠，但不能打断已经阻塞的同步调用。不提供原生 asyncio 取消，并发 worker 应使用各自独立的客户端。

每个解码响应默认最多 16 MiB，分块和解析副本另占内存。拒绝重定向，默认 Session 不重试；保留 TLS 验证及 Requests 环境代理／CA 行为。退出上下文管理器会关闭 Session。

`NstDataApiError` 提供 `kind`、可选 `status_code` 和 `api_code`，不输出原始服务响应／网络错误消息：

| kind | 含义 |
|---|---|
| `http`、`api` | 非 2xx HTTP 状态或失败 API envelope |
| `timeout`、`transport` | 本地连接／读取超时，或传输／编码失败 |
| `invalid_json`、`invalid_response` | JSON 无法解析，或已知响应字段不符合类型 |
| `response_limit` | 解码响应超出配置的字节上限 |
| `poll_limit`、`wait_limit` | 查询次数或本地等待预算用尽 |
| `page_limit`、`repeated_cursor` | 分页超限或游标重复 |

已存在的已知标量字段按 DTO 类型校验；缺失／null 的可选字段仍保留可选语义，未知字段忽略。引用、链接、metadata、内联内容、Base64 和截断标记均校验。本地参数校验抛出 `ValueError`。示例中的 `task_failed`／`missing_content` 是调用方为内容要求定义的 kind。

任务失败保留为结果，不转换成 HTTP 异常。网页正文和任务字段按不可信数据处理。超时或本地中断不会取消远端任务；提交结果未知时不得自动重新创建。

## API 路由

客户端使用 `x-api-key` 和配置的域名，并编码任务 ID 及查询值。

| 操作 | 路由 |
|---|---|
| 同步／异步单页 | `POST /api/v1/crawl/scrape`，异步增加 `?async=true` |
| 单页结果 | `GET /api/v1/crawl/scrape/{id}` |
| 整站／状态 | `POST /api/v1/crawl`、`GET /api/v1/crawl/{id}` |
| 页面 | `GET /api/v1/crawl/{id}/pages`，带游标／limit 参数 |
| 存储 | `GET /api/v1/crawl/storage/read?st=...` |
