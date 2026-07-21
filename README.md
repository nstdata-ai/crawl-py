# nstdata crawl SDK (Python)

[中文版](README_zh.md)

Python SDK for nstdata crawl, an advanced web scraping and crawling service.

## Installation

```bash
pip install nstdata-ai-crawl
```

## Features

- **Basic Scraping:** Get HTML and Markdown synchronously.
- **Screenshots & PDFs:** Take full-page screenshots and export pages as PDFs.
- **Browser Actions:** Orchestrate browser actions like wait for elements, fill forms, click buttons, scroll, and execute JS.
- **Custom Configuration:** Bring your own cookies, headers, and simulate mobile devices.
- **Content Filtering:** Automatically extract high-quality main content, filter out ads and navigational elements.
- **Proxy Location:** Specify proxy exit country.
- **Asynchronous Execution & Polling:** Submit time-consuming tasks and poll for results.
- **Batch Crawling:** Traverse entire sites with depth and page limits.

## Quick Start

See [main.py](./main.py) for a complete list of usage examples.

```python
import os
from nstdata_ai_crawl import NstDataClient, ScrapeRequestDto, Format

# Initialize the client with your API token
TOKEN = os.getenv("NSTDATA_API_TOKEN", "YOUR_API_TOKEN")

def main():
    with NstDataClient(TOKEN) as client:
        # Submit a basic scraping task
        res = client.submit_scrape_task_sync(ScrapeRequestDto(
            url="https://example.com/",
            formats=[Format.MARKDOWN],
            timeout=60000,
        ))
        
        # Output the resulting markdown
        print(res.data.get_markdown())

if __name__ == "__main__":
    main()
```
