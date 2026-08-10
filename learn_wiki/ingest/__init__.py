from learn_wiki.ingest.web import fetch_web
from learn_wiki.ingest.video import transcribe_video
from learn_wiki.models import SourceDocument

_VIDEO_HOSTS = ("youtube.com", "youtu.be")


def is_video_url(url: str) -> bool:
    return any(host in url for host in _VIDEO_HOSTS)


def ingest(url: str, *, web=fetch_web, video=transcribe_video) -> SourceDocument:
    if is_video_url(url):
        return video(url)
    return web(url)
