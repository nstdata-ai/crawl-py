# nstdata crawl SDK (Python)

[English](README.md)

nstdata crawl 的 Python SDK，提供高级的网页抓取和爬虫服务接口。

## 安装

```bash
pip install nstdata-ai-crawl
```

## 功能特性

- **基础抓取:** 同步获取页面的 HTML 和 Markdown 格式内容。
- **截图与 PDF:** 支持整页截图与页面导出为 PDF。
- **浏览器动作编排:** 支持等待元素、表单填充、点击、滚动以及执行自定义 JavaScript。
- **自定义配置:** 携带 Cookie、自定义请求头、模拟移动端等。
- **正文提取与过滤:** 自动提取高质量文章正文，去除广告、导航栏和页脚。
- **代理支持:** 可指定代理类型（住宅代理、数据中心代理）及出口国家。
- **异步提交与轮询:** 针对耗时任务，支持异步提交并轮询查询结果。
- **批量抓取 (Crawl):** 按深度、最大页数等条件遍历站点。

## 快速开始

您可以参考 [main.py](./main.py) 了解所有场景的完整使用示例。

```python
import os
from nstdata_ai_crawl import NstDataClient, ScrapeRequestDto, Format

# 使用您的 API Token 初始化客户端
TOKEN = os.getenv("NSTDATA_API_TOKEN", "YOUR_API_TOKEN")

def main():
    with NstDataClient(TOKEN) as client:
        # 提交基础的抓取任务
        res = client.submit_scrape_task_sync(ScrapeRequestDto(
            url="https://example.com/",
            formats=[Format.MARKDOWN],
            timeout=60000,
        ))
        
        # 输出抓取到的 Markdown 内容
        print(res.data.get_markdown())

if __name__ == "__main__":
    main()
```
