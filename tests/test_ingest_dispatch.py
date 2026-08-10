from learn_wiki.ingest import ingest, is_video_url
from learn_wiki.models import SourceDocument


def test_is_video_url():
    assert is_video_url("https://youtu.be/abc")
    assert is_video_url("https://www.youtube.com/watch?v=abc")
    assert not is_video_url("https://blog.example/post")


def test_dispatch_routes_video():
    doc = SourceDocument("https://youtu.be/abc", "video", "t", "x")
    out = ingest("https://youtu.be/abc",
                 video=lambda url: doc,
                 web=lambda url: (_ for _ in ()).throw(AssertionError("web called")))
    assert out is doc


def test_dispatch_routes_web():
    doc = SourceDocument("https://blog.example/p", "web", "t", "x")
    out = ingest("https://blog.example/p",
                 web=lambda url: doc,
                 video=lambda url: (_ for _ in ()).throw(AssertionError("video called")))
    assert out is doc
