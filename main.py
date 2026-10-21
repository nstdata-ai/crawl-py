import os

from nstdata_ai_crawl import NstDataClient, NstDataApiError, ScrapeRequestDto, CrawlRequestDto

TOKEN = os.getenv('NSTDATA_API_TOKEN')


def markdown(result):
    if result.success is False or result.status in ('failed', 'expired'):
        raise NstDataApiError('task_failed')
    if result.status != 'completed' or result.success is not True or result.data is None:
        raise NstDataApiError('missing_content')
    text = result.data.get_markdown()
    if text is None:
        raise NstDataApiError('missing_content')
    return text


def example_basic_scrape(client: NstDataClient):
    result = client.submit_scrape_task_sync(ScrapeRequestDto(
        url='https://example.com/', formats=['markdown'], onlyMainContent=True, timeout=60000,
    ))
    print(markdown(result))


def example_async_polling(client: NstDataClient):
    submitted = client.submit_scrape_task(ScrapeRequestDto(
        url='https://example.com/', formats=['markdown'], onlyMainContent=True, timeout=60000,
    ))
    if not isinstance(submitted.id, str) or not submitted.id.strip():
        raise NstDataApiError('invalid_response')
    print('Save task ID before waiting:', submitted.id)
    result = client.wait_for_scrape(submitted.id, max_polls=20, poll_interval=1, wait_timeout=120)
    print(markdown(result))


def example_crawl(client: NstDataClient):
    submitted = client.submit_crawl_task(CrawlRequestDto(
        url='https://example.com/', formats=['markdown'], maxDepth=1, maxPages=10,
        onlyMainContent=True, timeout=60000,
    ))
    if not isinstance(submitted.id, str) or not submitted.id.strip():
        raise NstDataApiError('invalid_response')
    print('Save crawl ID before waiting:', submitted.id)
    state = client.wait_for_crawl(submitted.id, max_polls=20, poll_interval=1, wait_timeout=120)
    if state.status != 'completed':
        raise NstDataApiError('task_failed')
    for page in client.iter_crawl_pages(submitted.id, limit=20, max_batches=10):
        print(page.url, page.status)
        if page.success is True and page.status == 'completed':
            print(markdown(page))
        else:
            print('Page failed or pending')


def main():
    if not TOKEN or not TOKEN.strip() or TOKEN == 'YOUR_API_TOKEN':
        raise ValueError('Set NSTDATA_API_TOKEN locally before running the online example')
    with NstDataClient(TOKEN, max_response_bytes=1048576) as client:
        # Run one approved workflow; the alternatives submit additional tasks.
        example_basic_scrape(client)
        # example_async_polling(client)
        # example_crawl(client)


if __name__ == '__main__':
    try:
        main()
    except (NstDataApiError, ValueError):
        raise SystemExit('Crawl example failed; check configuration and task state. No automatic retry.') from None
