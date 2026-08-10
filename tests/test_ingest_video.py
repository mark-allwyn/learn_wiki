import pytest
from learn_wiki.ingest.video import transcribe_video
from learn_wiki.errors import IngestError


def test_local_transcription_is_default_path():
    doc = transcribe_video(
        "https://youtu.be/abc",
        download=lambda url: "/tmp/audio.m4a",
        transcribe=lambda path, model_size: ("Talk Title", "spoken words here"),
        captions=lambda url: "caption text",  # present, but not preferred
    )
    assert doc.source_type == "video"
    assert doc.text == "spoken words here"  # transcription used, not captions


def test_prefer_captions_uses_captions_when_available():
    doc = transcribe_video(
        "https://youtu.be/abc",
        prefer_captions=True,
        captions=lambda url: "caption text",
        download=lambda url: pytest.fail("should not download"),
        transcribe=lambda path, model_size: pytest.fail("should not transcribe"),
    )
    assert doc.text == "caption text"


def test_prefer_captions_falls_back_to_transcription():
    doc = transcribe_video(
        "https://youtu.be/abc",
        prefer_captions=True,
        captions=lambda url: None,  # no captions
        download=lambda url: "/tmp/a.m4a",
        transcribe=lambda path, model_size: ("T", "transcribed"),
    )
    assert doc.text == "transcribed"


def test_raises_when_nothing_available():
    with pytest.raises(IngestError):
        transcribe_video(
            "https://youtu.be/abc",
            download=lambda url: "/tmp/a.m4a",
            transcribe=lambda path, model_size: ("T", "  "),  # empty transcript
            captions=lambda url: None,
        )
