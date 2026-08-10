import tempfile
from learn_wiki.models import SourceDocument
from learn_wiki.errors import IngestError


def _default_download(url: str) -> str:
    import yt_dlp
    tmp = tempfile.mkdtemp()
    out = f"{tmp}/audio.%(ext)s"
    opts = {"format": "bestaudio/best", "outtmpl": out, "quiet": True, "noprogress": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


def _default_transcribe(audio_path: str, model_size: str) -> tuple[str, str]:
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio_path)
    text = " ".join(seg.text.strip() for seg in segments)
    return (audio_path, text)


def _default_captions(url: str) -> str | None:
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        vid = url.rsplit("/", 1)[-1].split("?")[0].split("&")[0]
        parts = YouTubeTranscriptApi.get_transcript(vid)
        return " ".join(p["text"] for p in parts)
    except Exception:
        return None


def transcribe_video(
    url: str,
    *,
    model_size: str = "small",
    prefer_captions: bool = False,
    download=None,
    transcribe=None,
    captions=None,
) -> SourceDocument:
    download = download or _default_download
    transcribe = transcribe or _default_transcribe
    captions = captions or _default_captions

    if prefer_captions:
        cap = captions(url)
        if cap and cap.strip():
            return SourceDocument(url=url, source_type="video", title=url, text=cap)

    audio_path = download(url)
    title, text = transcribe(audio_path, model_size)
    if text and text.strip():
        return SourceDocument(url=url, source_type="video", title=title or url, text=text)

    raise IngestError(f"could not obtain a transcript for {url}")
