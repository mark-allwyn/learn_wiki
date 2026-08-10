# Run deliberately: pytest tests/smoke/test_video_transcribe.py -v
# Requires ffmpeg installed and network access. Uses a short public clip.
from learn_wiki.ingest.video import transcribe_video

SHORT_CLIP = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"  # replace with a short clip you trust


def test_real_transcription_produces_text():
    doc = transcribe_video(SHORT_CLIP, model_size="tiny")
    assert doc.source_type == "video"
    assert len(doc.text) > 0
