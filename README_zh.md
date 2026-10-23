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

需要 Python 3.10+。`1.0.0` 尚未发布；发布后使用：

```sh
python -m pip install nstdata-ai-crawl==1.0.0
```

本地归档安装或源码构建见[贡献说明](CONTRIBUTING.md)。从 `0.1.1` 升级会改变运行环境要求、默认 API 域名和错误行为，详见[变更记录](CHANGELOG.md)。

## 快速开始

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

getter 自动处理内联内容和延迟引用。缺失内容为 `None`；空字符串是有效的空正文。完整工作流、方法输入／结果及失败处理见[使用指南](docs/guide_zh.md)。

## 限制

- 本地 HTTP 超时使用秒；请求 DTO 的超时使用服务端毫秒。
- 客户端使用同步 Requests。连接／读取超时不是总墙钟期限，停止本地工作也不会取消远端任务。
- 创建请求不自动重试，后续调用前应保存返回的任务 ID。

[超时与错误](docs/guide_zh.md#超时与错误) · [贡献说明](CONTRIBUTING.md) · [API 文档](https://docs.nstdata.io/docs/crawl) · [MIT 许可](LICENSE)
