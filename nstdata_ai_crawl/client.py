import requests
import base64
from typing import Optional, Dict
from .models import (
    ScrapeRequestDto,
    CrawlRequestDto,
    SubmitResponseDto,
    TaskResultResponseDto,
    PageMetadataDto,
    ScrapeDataDto,
    CrawlStatusResponseDto,
    CrawlPageItemResponseDto,
    CrawlPageListResponseDto
)

# Built-in API endpoint.
_BASE_URL = "https://api.nstproxy.com"

def _build(cls, data: dict):
    """Construct a DTO from a response dict, ignoring keys the DTO doesn't
    declare so server-side field additions don't break the client."""
    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

class NstDataClient:
    def __init__(self, token: str):
        self.base_url = _BASE_URL
        self.token = token
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        return {"x-api-key": self.token}

    def _unwrap(self, resp: requests.Response) -> dict:
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or "err" not in data or "code" not in data:
            raise Exception("API error: invalid response envelope")
        if data.get("err") or data.get("code") != 200:
            raise Exception(f"API error: code={data.get('code')} msg={data.get('msg')}")
        return data.get("data") or {}

    def submit_scrape_task(self, req: ScrapeRequestDto) -> SubmitResponseDto:
        if not req.url:
            raise ValueError("url is required")
        if not req.formats:
            raise ValueError("formats must contain at least one format")
        url = f"{self.base_url}/api/v1/crawl/scrape"
        resp = self.session.post(url, params={"async": "true"}, json=req.to_dict(), headers=self._get_headers())
        data = self._unwrap(resp)
        return _build(SubmitResponseDto, data)

    def submit_scrape_task_sync(self, req: ScrapeRequestDto) -> TaskResultResponseDto:
        if not req.url:
            raise ValueError("url is required")
        if not req.formats:
            raise ValueError("formats must contain at least one format")
        url = f"{self.base_url}/api/v1/crawl/scrape"
        resp = self.session.post(url, json=req.to_dict(), headers=self._get_headers())
        data = self._unwrap(resp)
        
        if 'data' in data and data['data'] is not None:
            if 'metadata' in data['data'] and data['data']['metadata'] is not None:
                data['data']['metadata'] = _build(PageMetadataDto, data['data']['metadata'])
            raw = data['data']
            data['data'] = _build(ScrapeDataDto, raw)
            data['data']._html = raw.get('html')
            data['data']._markdown = raw.get('markdown')
            data['data']._client = self
            
        return _build(TaskResultResponseDto, data)

    def submit_crawl_task(self, req: CrawlRequestDto) -> SubmitResponseDto:
        if not req.url:
            raise ValueError("url is required")
        if not req.formats:
            raise ValueError("formats must contain at least one format")
        url = f"{self.base_url}/api/v1/crawl"
        resp = self.session.post(url, json=req.to_dict(), headers=self._get_headers())
        data = self._unwrap(resp)
        return _build(SubmitResponseDto, data)

    def get_crawl_status(self, crawl_id: str) -> CrawlStatusResponseDto:
        url = f"{self.base_url}/api/v1/crawl/{crawl_id}"
        resp = self.session.get(url, headers=self._get_headers())
        data = self._unwrap(resp)
        return _build(CrawlStatusResponseDto, data)

    def list_crawl_pages(self, crawl_id: str, after_cursor: Optional[str] = None, before_cursor: Optional[str] = None, limit: Optional[int] = None) -> CrawlPageListResponseDto:
        url = f"{self.base_url}/api/v1/crawl/{crawl_id}/pages"
        params = {}
        if after_cursor is not None:
            params["after_cursor"] = after_cursor
        if before_cursor is not None:
            params["before_cursor"] = before_cursor
        if limit is not None:
            params["limit"] = limit

        resp = self.session.get(url, params=params, headers=self._get_headers())
        data = self._unwrap(resp)

        if 'data' in data and data['data'] is not None:
            items = []
            for item in data['data']:
                if item.get('data') is not None:
                    if item['data'].get('metadata') is not None:
                        item['data']['metadata'] = _build(PageMetadataDto, item['data']['metadata'])
                    raw = item['data']
                    item['data'] = _build(ScrapeDataDto, raw)
                    item['data']._html = raw.get('html')
                    item['data']._markdown = raw.get('markdown')
                    
                    item['data']._client = self
                items.append(_build(CrawlPageItemResponseDto, item))
            data['data'] = items

        return _build(CrawlPageListResponseDto, data)

    def get_scrape_task_result(self, task_id: str) -> TaskResultResponseDto:
        url = f"{self.base_url}/api/v1/crawl/scrape/{task_id}"
        resp = self.session.get(url, headers=self._get_headers())
        data = self._unwrap(resp)
        
        if 'data' in data and data['data'] is not None:
            if 'metadata' in data['data'] and data['data']['metadata'] is not None:
                data['data']['metadata'] = _build(PageMetadataDto, data['data']['metadata'])
            raw = data['data']
            data['data'] = _build(ScrapeDataDto, raw)
            data['data']._html = raw.get('html')
            data['data']._markdown = raw.get('markdown')
            data['data']._client = self
            
        return _build(TaskResultResponseDto, data)

    def read_storage(self, st: str) -> bytes:
        url = f"{self.base_url}/api/v1/crawl/storage/read"
        resp = self.session.get(url, params={"st": st}, headers=self._get_headers())
        resp.raise_for_status()
        return resp.content



    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
