import time
import os

from nstdata_ai_crawl import (
    NstDataClient,
    ScrapeRequestDto,
    CrawlRequestDto,
    JsRenderDto,
    ActionDto,
    CookieDto,
    Format,
    Proxy,
    TaskType,
    TaskStatus,
)

# It's recommended to load the token from an environment variable for security
TOKEN = os.getenv("NSTDATA_API_TOKEN")


# Scenario 1: Basic scrape, synchronously return markdown and html
def example_basic_scrape(client: NstDataClient):
    res = client.submit_scrape_task_sync(ScrapeRequestDto(
        url="https://example.com/",
        formats=[Format.MARKDOWN, Format.HTML],
        timeout=60000,
    ))
    print(res.data.get_markdown())


# Scenario 2: Full page screenshot
def example_screenshot(client: NstDataClient):
    res = client.submit_scrape_task_sync(ScrapeRequestDto(
        url="https://example.com/",
        formats=[Format.SCREENSHOT],
        jsRender=JsRenderDto(
            waitFor=3000,
            actions=[ActionDto.screenshot(full=True)],
        ),
        timeout=60000,
    ))
    print(res.data.get_screenshot())


# Scenario 3: Export page to PDF
def example_pdf(client: NstDataClient):
    res = client.submit_scrape_task_sync(ScrapeRequestDto(
        url="https://example.com/",
        formats=[Format.PDF],
        timeout=60000,
    ))
    print(res.data.get_pdf())


# Scenario 4: Browser action orchestration - wait for element, fill form, click, scroll, execute JS, wait for response
def example_browser_actions(client: NstDataClient):
    res = client.submit_scrape_task_sync(ScrapeRequestDto(
        url="https://example.com/",
        formats=[Format.MARKDOWN],
        jsRender=JsRenderDto(
            waitForSelector="body",
            actions=[
                ActionDto.wait_selector("h1", timeout_ms=5000),
                ActionDto.fill("#search-input", "hello"),
                ActionDto.click("#search-button"),
                ActionDto.wait(1000),
                ActionDto.scroll_y(800),
                ActionDto.execute_js("window.scrollTo(0, document.body.scrollHeight)"),
                ActionDto.wait_for_request("*example.com/api/*", timeout_ms=10000),
            ],
        ),
        timeout=60000,
    ))
    print(res.data.get_markdown())


# Scenario 5: Bring Cookies, custom headers, simulate mobile device
def example_cookies_and_headers(client: NstDataClient):
    res = client.submit_scrape_task_sync(ScrapeRequestDto(
        url="https://example.com/",
        formats=[Format.HTML],
        cookies=[
            CookieDto(name="session_id", value="abc123", domain="example.com", path="/", secure=True),
        ],
        headers={
            "Referer": "https://example.com/home",
        },
        mobile=True,
        timeout=60000,
    ))
    print(res.data.get_html())


# Scenario 6: Main content extraction and filtering, retain only main content
def example_content_filter(client: NstDataClient):
    res = client.submit_scrape_task_sync(ScrapeRequestDto(
        url="https://example.com/",
        formats=[Format.MARKDOWN],
        onlyMainContent=True,
        includeTags=["main", "article"],
        excludeTags=["nav", "footer"],
        targetSelector="main article",
        removeSelectors=[".ads", "#popup"],
        timeout=60000,
    ))
    print(res.data.get_markdown())


# Scenario 7: Specify proxy type and exit country
def example_proxy_and_country(client: NstDataClient):
    res = client.submit_scrape_task_sync(ScrapeRequestDto(
        url="https://example.com/",
        formats=[Format.MARKDOWN],
        proxy=Proxy.DATACENTER,  # Proxy.RESIDENTIAL can also be used (default)
        country="us",
        timeout=60000,
    ))
    print(res.data.get_markdown())


# Scenario 8: Asynchronous submission + polling results, suitable for time-consuming tasks
def example_async_polling(client: NstDataClient):
    submitted = client.submit_scrape_task(ScrapeRequestDto(
        url="https://example.com/",
        formats=[Format.MARKDOWN],
        timeout=60000,
    ))
    print("task id:", submitted.id)

    while True:
        res = client.get_scrape_task_result(submitted.id)
        if res.status == TaskStatus.COMPLETED:
            print(res.data.get_markdown())
            return
        if res.status == TaskStatus.FAILED:
            raise Exception(f"task failed: {res.errorCode} {res.errorMessage}")
        time.sleep(3)  # processing





# Scenario 11: Extract all links on the page and unprocessed raw response
def example_links_and_raw_data(client: NstDataClient):
    res = client.submit_scrape_task_sync(ScrapeRequestDto(
        url="https://example.com/",
        formats=[Format.LINKS, Format.RAW_DATA],
        timeout=60000,
    ))
    for link in res.data.links or []:
        print(link)
    print("rawData length:", len(res.data.get_raw_data() or ""))


# Scenario 12: Submit batch crawl tasks, traverse the site from the entry page by depth/page count
def example_crawl(client: NstDataClient):
    submitted = client.submit_crawl_task(CrawlRequestDto(
        url="https://example.com/",
        maxDepth=3,
        maxPages=10,
        includeUrls=["*example.com/blog/*", "*/docs/*"],
        excludeUrls=["*example.com/admin/*"],
        ignoreQuery=True,  # Ignore URL query parameters when expanding links to avoid duplicate pages
        formats=[Format.MARKDOWN],
        onlyMainContent=True,
        proxy=Proxy.RESIDENTIAL,
        timeout=60000,
    ))
    print("crawl task id:", submitted.id)

    # Poll session progress until terminal state; content of each page can be queried via task list (type=crawl), see scenario 9
    while True:
        st = client.get_crawl_status(submitted.id)
        print(f"status={st.status} total={st.total} completed={st.completed} "
              f"failed={st.failed} pending={st.pending}")
        if st.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break
        time.sleep(3)  # scraping / processing

    # Cursor pagination to get crawl content for each page
    cursor = None
    while True:
        pages = client.list_crawl_pages(submitted.id, after_cursor=cursor, limit=20)
        for page in pages.data or []:
            print("==", page.url, page.status)
            if page.success and page.data:
                md = page.data.get_markdown()
                print(md)
            elif page.errorMessage:
                print("error:", page.errorCode, page.errorMessage)
        if not pages.nextCursor:
            break
        cursor = pages.nextCursor


def main():
    if TOKEN == "YOUR_API_TOKEN":
        print("Please set your API token by modifying TOKEN or setting NSTDATA_API_TOKEN env var")
        return

    with NstDataClient(TOKEN) as client:
        # Uncomment the scenario you want to run
        example_basic_scrape(client)
        # example_screenshot(client)
        # example_pdf(client)
        # example_browser_actions(client)
        # example_cookies_and_headers(client)
        # example_content_filter(client)
        # example_proxy_and_country(client)
        # example_async_polling(client)
        # example_links_and_raw_data(client)
        # example_crawl(client)


if __name__ == "__main__":
    main()
