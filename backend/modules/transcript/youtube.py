import json
import os
import re

import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
)

_LANG_PREF = ("en", "en-US", "en-GB", "en-orig", "a.en", "ur", "hi")


def extract_video_id(url: str):
    patterns = (
        r"(?:v=|/)([0-9A-Za-z_-]{11})",
        r"youtu\.be/([0-9A-Za-z_-]{11})",
        r"embed/([0-9A-Za-z_-]{11})",
    )
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def classify_youtube_error(exc: Exception):
    msg = str(exc).lower()
    cause = getattr(exc, "cause", "") or ""
    cause_low = str(cause).lower()
    combined = f"{msg} {cause_low}"

    if isinstance(exc, VideoUnplayable):
        if any(
            k in combined
            for k in ("copyright", "blocked", "content owner", "claim", "licensed")
        ):
            return (
                "copyright",
                "Copyright / content restriction: YouTube does not allow transcript "
                "for this video. Try another video or upload your own file.",
            )
        return (
            "unplayable",
            "This video cannot be played or transcribed on YouTube.",
        )

    if any(k in combined for k in ("copyright", "content owner", "blocked by")):
        return (
            "copyright",
            "Copyright restriction: transcript cannot be generated for this video.",
        )

    if isinstance(exc, AgeRestricted):
        return ("restricted", "Age-restricted video — transcript is not available.")

    if isinstance(exc, (RequestBlocked, VideoUnavailable)):
        return ("blocked", "Video unavailable or YouTube blocked the request.")

    if isinstance(exc, TranscriptsDisabled):
        return ("no_subtitles", None)

    if isinstance(exc, CouldNotRetrieveTranscript):
        return ("no_subtitles", None)

    return ("unknown", str(exc)[:300])


def _fetch_via_transcript_api(video_id: str):
    api = YouTubeTranscriptApi()
    langs = list(_LANG_PREF)
    last_exc = None

    def _join(fetched):
        return " ".join(snippet.text.strip() for snippet in fetched).strip()

    try:
        return _join(api.fetch(video_id, languages=langs))
    except Exception as exc:
        last_exc = exc

    try:
        for transcript in api.list(video_id):
            try:
                return _join(transcript.fetch())
            except Exception as exc:
                last_exc = exc
    except Exception as exc:
        last_exc = exc

    if last_exc:
        raise last_exc
    raise RuntimeError("No transcript found")


def _json3_to_plain(raw: str) -> str:
    data = json.loads(raw)
    parts = []
    for event in data.get("events") or []:
        for seg in event.get("segs") or []:
            text = (seg.get("utf8") or "").replace("\n", " ").strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _vtt_to_plain(vtt: str) -> str:
    lines = []
    last = None
    for raw in vtt.splitlines():
        line = re.sub(r"<[^>]+>", "", raw).strip()
        if not line or line == "WEBVTT" or "-->" in line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if line == last:
            continue
        lines.append(line)
        last = line
    return " ".join(lines)


def _pick_subtitle_url(info):
    best = None
    for field in ("subtitles", "automatic_captions"):
        bucket = info.get(field) or {}
        for lang in _LANG_PREF:
            entries = bucket.get(lang)
            if not entries:
                continue
            for fmt in entries:
                url = fmt.get("url")
                if not url:
                    continue
                ext = (fmt.get("ext") or "").lower()
                if ext == "vtt":
                    return url
                if ext in ("srv3", "json3", "ttml") and best is None:
                    best = url
    return best


def _fetch_via_ytdlp(url: str):
    ydl_opts = {"skip_download": True, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    sub_url = _pick_subtitle_url(info)
    if not sub_url:
        return None

    res = requests.get(sub_url, timeout=60)
    res.raise_for_status()
    body = res.text.strip()
    if body.startswith("{"):
        text = _json3_to_plain(body)
    else:
        text = _vtt_to_plain(body)
    text = re.sub(r"^Kind:\s*captions\s*Language:\s*\w+\s*", "", text, flags=re.I)
    return text.strip() if text else None


def fetch_youtube_transcript(url: str):
    """
    Return (text, error_code, error_message).
    error_code is None on success.
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None, "invalid_url", "Invalid YouTube link."

    on_pa = bool(os.getenv("PYTHONANYWHERE_SITE"))

    try:
        text = _fetch_via_transcript_api(video_id)
        if text and len(text.split()) >= 2:
            return text, None, None
    except Exception as exc:
        code, msg = classify_youtube_error(exc)
        if code == "copyright":
            return None, code, msg
        if code in ("restricted", "blocked", "unplayable"):
            return None, code, msg

    if not on_pa:
        try:
            text = _fetch_via_ytdlp(url)
            if text and len(text.split()) >= 2:
                return text, None, None
        except Exception as exc:
            code, msg = classify_youtube_error(exc)
            if code == "copyright":
                return None, code, msg

    if on_pa:
        return (
            None,
            "no_subtitles",
            "No captions found for this video. Try a video with subtitles, or upload your own video/audio file (max 20 MB).",
        )

    return None, "no_subtitles", None


def download_audio(url: str):
    os.makedirs("temp", exist_ok=True)
    ydl_opts = {
        "format": "bestaudio[filesize<20M]/bestaudio/best",
        "outtmpl": "temp/audio.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        ext = info.get("ext") or "webm"
        path = f"temp/audio.{ext}"
        if os.path.isfile(path):
            return path
        for name in os.listdir("temp"):
            if name.startswith("audio."):
                return os.path.join("temp", name)
    return "temp/audio.webm"
