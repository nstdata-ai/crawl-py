# Nstdata Crawl Python SDK

[English](README.md)

同步客户端，支持单页抓取、整站爬取、游标分页和延迟正文下载。

## 安装

需要 Python 3.10+、Requests >=2.34.2,<3。`1.0.0` 已本地准备、尚未发布；发布后使用以下命令安装：

```sh
python -m pip install nstdata-ai-crawl==1.0.0
```

已发布的 `0.1.1` 行为不同，升级前阅读 [CHANGELOG.md](CHANGELOG.md)。包名 `nstdata-ai-crawl` 和导入名 `nstdata_ai_crawl` 保持不变。本地归档安装和源码构建见[贡献说明](CONTRIBUTING.md)。

## 单页抓取

在环境中设置 `NSTDATA_API_TOKEN`。运行此例会创建一个任务，可能消耗额度。

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

## 任务与结果

| 方法 | 用途 |
|---|---|
| `submit_scrape_task_sync` | 同步提交单页并直接消费结果 |
| `submit_scrape_task` | 异步提交一次，保存返回 ID |
| `get_scrape_task_result`、`wait_for_scrape` | 查询或等待已有单页任务 |
| `submit_crawl_task`、`get_crawl_status`、`wait_for_crawl` | 提交与查询整站任务 |
| `list_crawl_pages`、`iter_crawl_pages` | 读取游标分页结果 |
| `read_storage` | 读取存储引用 |

请求使用 `https://api.nstdata.io/api/v1/crawl` 和 `x-api-key`。同步单页为 `/scrape`，异步增加 `?async=true`；结果 `/scrape/{id}`、整站进度 `/{id}`、分页 `/{id}/pages`、存储 `/storage/read?st=…`。客户端负责 ID 和查询值编码。

异步／整站提交不自动重试，后续调用前先保存 ID。等待函数通过 `max_polls`、`poll_interval`、`wait_timeout` 限制调用；分页通过 `limit`、`max_batches` 限制读取。失败／过期任务保留为结果；本地中断不取消远端任务。

分页保留服务顺序、重复 URL 和失败行；空页仍可能有下一游标。重复游标或批次超限抛错，后续读取失败时，之前已产出的页面仍是部分结果。整站完成不代表全部页面成功。

整站遍历过滤条件原样转发，SDK 不解释其匹配语法。

延迟 getter 按需下载并缓存成功结果，包括空字符串。缺正文为 `None`，与 `''` 不同；使用 `get_markdown()` 等方法，不将引用当作 URL。`rawData` 为字节，不代表结构化 JSON 提取。

PDF／截图／原始数据 getter 返回 `bytes`。内联 PDF／截图按 Base64 解码，内联原始文本按 UTF-8 转为字节。内联内容存在时优先使用，包括空内容；否则读取并缓存引用字节。

结果保留服务实际返回的 `id` 和 `data.truncated`，包括 `False`。缺失截断标记表示未知；同步结果带有 ID，不代表正文一定可以再次查询。

## 超时与错误

`NstDataClient(token, *, base_url=..., timeout=(10, 120), max_response_bytes=16777216)` 保留位置参数 Token。API／存储方法和 getter 支持按次覆盖 `timeout`，单位为秒；DTO 的 `timeout` 仍是服务端毫秒值。

DTO 的 `timeout` 为 1000–60000 的整数毫秒值，`jsRender.waitFor` 为 1000–30000 的整数毫秒值；动作等待时间和滚动坐标也使用整数。DTO 值原样传递，由服务端校验，不自动转换类型。

Requests 超时约束连接与读取空闲时间，不是总墙钟期限。`wait_timeout` 限制检查／休眠并裁剪 HTTP 超时，不能打断已阻塞的同步调用；不提供原生 asyncio 取消。并发 worker 应各用独立客户端。

每个解码响应默认上限 16 MiB，分块和解析副本另占内存。拒绝重定向，默认 Session 不重试；保持 TLS 验证和 Requests 的环境代理／CA 行为。退出上下文管理器会关闭 Session。

`NstDataApiError` 提供 `kind`、可选 `status_code` 和 `api_code`，不输出原始响应／网络错误消息；参数校验抛出 `ValueError`。任务失败保留结果，不转换为 HTTP 异常。网页内容和任务字段按不可信数据处理。

无效内联 Base64、非字符串内联内容、无法编码为 UTF-8 的原始文本、无效引用／链接／metadata 类型及非布尔截断标记，均抛出 `NstDataApiError(kind='invalid_response')`，不包含响应值。内联值为 `null` 时按缺失处理。

## 开发

环境准备、构建和包检查见[贡献说明](CONTRIBUTING.md)。测试使用 mock 和本机 HTTP。运行 `main.py` 会提交真实任务；导入不会。

[贡献说明](CONTRIBUTING.md) · [API 文档](https://docs.nstdata.io/docs/crawl) · [MIT 许可](LICENSE)
