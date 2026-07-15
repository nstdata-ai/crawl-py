class Format:
    HTML = "html"
    MARKDOWN = "markdown"
    LINKS = "links"
    PDF = "pdf"
    SCREENSHOT = "screenshot"
    RAW_DATA = "rawData"

class TaskType:
    SCRAPE = "scrape"
    CRAWL = "crawl"

class TaskStatus:
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SCRAPING = "scraping"  # crawl 会话仍在抓取中

class ActionType:
    CLICK = "click"                                          # click an element; requires selector
    WAIT = "wait"                                            # wait a fixed time; requires milliseconds
    WAIT_SELECTOR = "waitSelector"                           # wait until element is visible; requires selector
    SCROLL_X = "scrollX"                                     # scroll horizontally by x pixels
    SCROLL_Y = "scrollY"                                     # scroll vertically by y pixels
    SCROLL_TO = "scrollTo"                                   # scroll to an element; requires selector
    FILL = "fill"                                            # fill an input; requires selector and text
    EXECUTE = "execute"                                      # run JavaScript on the page; requires execute
    SCREENSHOT = "screenshot"                                # capture screenshot; fullScreenshot / particularScreenshot / viewport
    WAIT_FOR_REQUEST_COMPLETION = "waitForRequestCompletion" # wait for a matching network response; requires urlPattern

class Proxy:
    """Proxy types for ScrapeRequestDto.proxy (defaults to residential when unset)."""
    RESIDENTIAL = "residential"
    DATACENTER = "datacenter"
