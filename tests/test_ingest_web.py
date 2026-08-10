import pytest
from learn_wiki.ingest.web import fetch_web
from learn_wiki.errors import IngestError

HTML = """
<html><head><title>My Post</title></head>
<body><article><h1>Context Windows</h1>
<p>A context window is the amount of text a model can attend to at once.
Chunking improves how much relevant content fits.</p></article></body></html>
"""


def test_fetch_web_extracts_title_and_text():
    doc = fetch_web("https://blog.example/post", fetch=lambda url: HTML)
    assert doc.source_type == "web"
    assert doc.url == "https://blog.example/post"
    assert "context window" in doc.text.lower()


def test_fetch_web_raises_on_empty_content():
    with pytest.raises(IngestError):
        fetch_web("https://blog.example/empty", fetch=lambda url: "<html></html>")
