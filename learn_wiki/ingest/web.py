import httpx
import trafilatura
from learn_wiki.models import SourceDocument
from learn_wiki.errors import IngestError


def _http_get(url: str) -> str:
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as exc:
        raise IngestError(f"could not fetch {url}: {exc}") from exc


def fetch_web(url: str, *, fetch=None) -> SourceDocument:
    fetch = fetch or _http_get
    html = fetch(url)
    text = trafilatura.extract(html) or ""
    if not text.strip():
        raise IngestError(f"no readable content extracted from {url}")
    meta = trafilatura.extract_metadata(html)
    title = (meta.title if meta and meta.title else url)
    return SourceDocument(url=url, source_type="web", title=title, text=text)
