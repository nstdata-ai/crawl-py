from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field

from .constants import ActionType


def _to_clean_dict(obj) -> Dict[str, Any]:
    def _clean(v):
        if isinstance(v, dict):
            return {k: _clean(x) for k, x in v.items() if x is not None}
        elif isinstance(v, list):
            return [_clean(x) for x in v if x is not None]
        return v
    return _clean(asdict(obj))

@dataclass
class CookieDto:
    domain: Optional[str] = None # Domain the cookie belongs to
    httpOnly: Optional[bool] = None # True if the cookie is HTTP-only
    name: Optional[str] = None # Name of the cookie
    path: Optional[str] = None # Path for the cookie
    secure: Optional[bool] = None # True if the cookie requires HTTPS
    value: Optional[str] = None # Value of the cookie

@dataclass
class ProxyDto:
    country: Optional[str] = None # Proxy exit country code (e.g., 'us', 'gb')

@dataclass
class ActionDto:
    execute: Optional[str] = None # JavaScript code snippet to execute
    fullScreenshot: Optional[bool] = None # Set to true to capture a full-page screenshot
    key: Optional[str] = None # Keyboard key to press
    milliseconds: Optional[float] = None # Milliseconds to wait
    particularScreenshot: Optional[str] = None # CSS selector of an element to screenshot
    selector: Optional[str] = None # CSS selector for the action target
    text: Optional[str] = None # Text to type into an input field
    type: Optional[str] = None # Type of action (e.g., 'click', 'wait', 'fill')
    urlPattern: Optional[str] = None # URL pattern to wait for (regex support)
    waitSelector: Optional[str] = None # CSS selector to wait for
    x: Optional[float] = None # X coordinate for scroll/click
    y: Optional[float] = None # Y coordinate for scroll/click

    # Factory helpers: each one sets `type` plus the fields that action
    # requires, so callers don't need to remember which fields pair with
    # which type.

    @classmethod
    def click(cls, selector: str) -> "ActionDto":
        """Click the element matched by selector."""
        return cls(type=ActionType.CLICK, selector=selector)

    @classmethod
    def wait(cls, milliseconds: float) -> "ActionDto":
        """Pause for a fixed time in milliseconds."""
        return cls(type=ActionType.WAIT, milliseconds=milliseconds)

    @classmethod
    def wait_selector(cls, selector: str, timeout_ms: Optional[float] = None) -> "ActionDto":
        """Wait until the element matched by selector is visible."""
        return cls(type=ActionType.WAIT_SELECTOR, selector=selector, milliseconds=timeout_ms)

    @classmethod
    def scroll_x(cls, pixels: int) -> "ActionDto":
        """Scroll the window horizontally by pixels."""
        return cls(type=ActionType.SCROLL_X, text=str(pixels), x=pixels)

    @classmethod
    def scroll_y(cls, pixels: int) -> "ActionDto":
        """Scroll the window vertically by pixels."""
        return cls(type=ActionType.SCROLL_Y, text=str(pixels), y=pixels)

    @classmethod
    def scroll_to(cls, selector: str) -> "ActionDto":
        """Scroll to the element matched by selector."""
        return cls(type=ActionType.SCROLL_TO, selector=selector)

    @classmethod
    def fill(cls, selector: str, text: str) -> "ActionDto":
        """Type text into the input matched by selector."""
        return cls(type=ActionType.FILL, selector=selector, text=text)

    @classmethod
    def execute_js(cls, script: str) -> "ActionDto":
        """Run a JavaScript snippet on the page."""
        return cls(type=ActionType.EXECUTE, execute=script)

    @classmethod
    def screenshot(cls, full: bool = False, selector: Optional[str] = None) -> "ActionDto":
        """Capture a screenshot: full page if full=True, the element matched
        by selector if given, otherwise the current viewport."""
        return cls(type=ActionType.SCREENSHOT, fullScreenshot=full or None, particularScreenshot=selector)

    @classmethod
    def wait_for_request(cls, url_pattern: str, timeout_ms: Optional[float] = None) -> "ActionDto":
        """Wait for a network response whose URL matches url_pattern
        (supports * wildcard)."""
        return cls(type=ActionType.WAIT_FOR_REQUEST_COMPLETION, urlPattern=url_pattern, milliseconds=timeout_ms)

@dataclass
class JsRenderDto:
    actions: Optional[List[ActionDto]] = None # List of browser actions to perform
    waitFor: Optional[float] = None # Global wait time in milliseconds
    waitForSelector: Optional[str] = None # CSS selector to wait for before proceeding

@dataclass
class ScrapeRequestDto:
    url: str # The URL to scrape
    cookies: Optional[List[CookieDto]] = None # Optional cookies to include in the request
    proxy: Optional[ProxyDto] = None # Proxy settings, such as exit country
    excludeTags: Optional[List[str]] = None # HTML tags to remove entirely (e.g., ['nav', 'footer'])
    formats: Optional[List[str]] = None # Desired output formats (e.g., ['markdown', 'html', 'links'])
    headers: Optional[Dict[str, str]] = None # Custom HTTP headers
    includeTags: Optional[List[str]] = None # Tags to keep. WARNING: strips all other tags (keeping text), which may break markdown
    jsRender: Optional[JsRenderDto] = None # JavaScript rendering instructions
    mobile: Optional[bool] = None # Whether to emulate a mobile device
    onlyMainContent: Optional[bool] = None # Automatically extract main article content and remove noise
    removeSelectors: Optional[List[str]] = None # CSS selectors for elements to remove (e.g., ['.ads', '#popup'])
    targetSelector: Optional[str] = None # CSS selector to restrict extraction to a specific element
    timeout: Optional[float] = None # Request timeout in milliseconds

    def to_dict(self) -> Dict[str, Any]:
        return _to_clean_dict(self)

@dataclass
class CrawlRequestDto:
    """Scrape options plus crawl traversal controls
    (maxDepth, maxPages, includeUrls, excludeUrls, ignoreQuery)."""
    url: str # The starting URL to crawl
    cookies: Optional[List[CookieDto]] = None # Optional cookies to include in the request
    proxy: Optional[ProxyDto] = None # Proxy settings, such as exit country
    excludeTags: Optional[List[str]] = None # HTML tags to remove entirely
    excludeUrls: Optional[List[str]] = None # Regex patterns to exclude specific URLs from crawling
    formats: Optional[List[str]] = None # Desired output formats (e.g., ['markdown', 'html'])
    headers: Optional[Dict[str, str]] = None # Custom HTTP headers
    ignoreQuery: Optional[bool] = None # Whether to ignore URL query parameters for deduplication
    includeTags: Optional[List[str]] = None # Tags to keep. WARNING: strips all other tags
    includeUrls: Optional[List[str]] = None # Regex patterns to only crawl matching URLs
    jsRender: Optional[JsRenderDto] = None # JavaScript rendering instructions
    maxDepth: Optional[int] = None # Maximum depth of links to follow
    maxPages: Optional[int] = None # Maximum number of pages to crawl
    mobile: Optional[bool] = None # Whether to emulate a mobile device
    onlyMainContent: Optional[bool] = None # Automatically extract main article content
    removeSelectors: Optional[List[str]] = None # CSS selectors for elements to remove
    targetSelector: Optional[str] = None # CSS selector to restrict extraction
    timeout: Optional[float] = None # Request timeout in milliseconds

    def to_dict(self) -> Dict[str, Any]:
        return _to_clean_dict(self)

@dataclass
class SubmitResponseDto:
    cached: Optional[bool] = None # True if the response was served from cache
    code: Optional[int] = None # HTTP status code
    id: Optional[str] = None # Task ID
    status: Optional[str] = None # Task status message

@dataclass
class PageMetadataDto:
    canonical: Optional[str] = None # Canonical URL of the page
    description: Optional[str] = None # Meta description text
    language: Optional[str] = None # Document language code
    ogImage: Optional[str] = None # OpenGraph preview image URL
    statusCode: Optional[int] = None # HTTP response status code
    title: Optional[str] = None # Page title

@dataclass
class ScrapeDataDto:
    htmlRef: Optional[str] = None # Reference link to fetch the HTML content
    links: Optional[List[str]] = None # List of extracted hyperlinks
    markdownRef: Optional[str] = None # Reference link to fetch the Markdown content
    metadata: Optional[PageMetadataDto] = None # Extracted page metadata and SEO tags
    pdfRef: Optional[str] = None # Reference link to fetch the PDF
    rawDataRef: Optional[str] = None # Reference link to fetch the raw data
    screenshotRef: Optional[str] = None # Reference link to fetch the screenshot


    _html: Optional[str] = field(default=None, repr=False, init=False)
    _markdown: Optional[str] = field(default=None, repr=False, init=False)
    _pdf: Optional[bytes] = field(default=None, repr=False, init=False)
    _rawData: Optional[bytes] = field(default=None, repr=False, init=False)
    _screenshot: Optional[bytes] = field(default=None, repr=False, init=False)
    _client: Any = field(default=None, repr=False, init=False)

    def get_html(self) -> Optional[str]:
        if self._html is not None:
            return self._html
        if self.htmlRef and self._client:
            self._html = self._client.read_storage(self.htmlRef).decode('utf-8')
            return self._html
        return None

    def get_markdown(self) -> Optional[str]:
        if self._markdown is not None:
            return self._markdown
        if self.markdownRef and self._client:
            self._markdown = self._client.read_storage(self.markdownRef).decode('utf-8')
            return self._markdown
        return None

    def get_pdf(self) -> Optional[bytes]:
        if self._pdf is not None:
            return self._pdf
        if self.pdfRef and self._client:
            self._pdf = self._client.read_storage(self.pdfRef)
            return self._pdf
        return None

    def get_raw_data(self) -> Optional[bytes]:
        if self._rawData is not None:
            return self._rawData
        if self.rawDataRef and self._client:
            self._rawData = self._client.read_storage(self.rawDataRef)
            return self._rawData
        return None

    def get_screenshot(self) -> Optional[bytes]:
        if self._screenshot is not None:
            return self._screenshot
        if self.screenshotRef and self._client:
            self._screenshot = self._client.read_storage(self.screenshotRef)
            return self._screenshot
        return None

@dataclass
class TaskResultResponseDto:
    code: Optional[int] = None # Custom status code
    data: Optional[ScrapeDataDto] = None # The extracted scrape/crawl data
    errorCode: Optional[str] = None # Error code identifier if any
    errorMessage: Optional[str] = None # Detailed error message
    status: Optional[str] = None # Current status (e.g., 'completed', 'failed')
    success: Optional[bool] = None # True if the task executed successfully

@dataclass
class CrawlStatusResponseDto:
    """Aggregate progress of a crawl session."""
    code: Optional[int] = None # Custom status code
    completed: Optional[int] = None # Number of completed pages
    failed: Optional[int] = None # Number of failed pages
    id: Optional[str] = None # Crawl task ID
    pending: Optional[int] = None # Number of pending pages
    status: Optional[str] = None # Current status message
    total: Optional[int] = None # Total number of discovered pages

@dataclass
class CrawlPageItemResponseDto:
    """One page's normalized result within a crawl session."""
    data: Optional[ScrapeDataDto] = None # Extracted data for this page
    errorCode: Optional[str] = None # Error code if any
    errorMessage: Optional[str] = None # Detailed error message
    status: Optional[str] = None # Status of this page extraction
    success: Optional[bool] = None # True if extraction was successful
    taskId: Optional[str] = None # ID of the specific page task
    url: Optional[str] = None # URL of the scraped page

@dataclass
class CrawlPageListResponseDto:
    """Cursor-paginated list of crawl page results."""
    code: Optional[int] = None # Custom status code
    completed: Optional[int] = None # Number of completed pages
    data: Optional[List[CrawlPageItemResponseDto]] = None # List of page results
    nextCursor: Optional[str] = None # Cursor for fetching the next page of results
    prevCursor: Optional[str] = None # Cursor for fetching the previous page of results
    total: Optional[int] = None # Total number of pages
