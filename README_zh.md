# Nstdata Crawl Python SDK

[English](README.md)

通过 Nstdata Crawl 获取网页内容的同步 Python 客户端。

## 功能

| 能力 | 指南 |
|---|---|
| 单页抓取 | 读取 Markdown、HTML、链接、PDF、截图或原始字节。 |
| 异步任务 | [提交一次，按任务 ID 接续](docs/guide_zh.md#异步任务)。 |
| 整站抓取 | [限制抓取范围，按游标读取页面](docs/guide_zh.md#整站抓取)。 |
| 延迟结果 | [按需读取引用正文](docs/guide_zh.md#正文与引用)。 |
| 页面选项 | [配置渲染、动作、过滤、Cookie、请求头和代理国家](docs/guide_zh.md#请求选项)。 |

## 安装

需要 Python 3.10+。

```sh
python -m pip install nstdata-ai-crawl
```

从 `0.1.1` 升级前，请阅读[兼容性变化](CHANGELOG.md#100)。

## 快速开始

在环境中设置 API Key（macOS/Linux）：

```sh
export NSTDATA_API_TOKEN='your-api-key'
```

将以下程序保存为 `quickstart.py`。它提交一次单页任务并输出 Markdown；服务调用会消耗额度。

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

运行：

```sh
python quickstart.py
```

getter 自动处理内联内容和延迟引用。缺失内容为 `None`；空字符串是有效的空正文。完整工作流、方法输入／结果及失败处理见[使用指南](docs/guide_zh.md)。

## 限制

- 本地 HTTP 超时使用秒；请求 DTO 的超时使用服务端毫秒。
- 客户端使用同步 Requests。连接／读取超时不是总墙钟期限，停止本地工作也不会取消远端任务。
- 创建请求不自动重试，后续调用前应保存返回的任务 ID。

[超时与错误](docs/guide_zh.md#超时与错误) · [贡献说明](CONTRIBUTING.md) · [API 文档](https://docs.nstdata.io/docs/crawl) · [MIT 许可](LICENSE)
