import os
import re
import tempfile
import urllib.parse
from pathlib import Path
import imageio.plugins.ffmpeg as _ffmpeg_plugin
import yt_dlp
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI(title="ytdl")
os.environ["PATH"] += os.pathsep + str(_ffmpeg_plugin.get_exe().parent)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent

# Cookies file — checks env var first, then falls back to project root
COOKIES_FILE = Path(os.getenv("COOKIES_PATH", BASE_DIR / "cookies.txt"))

COMMON_OPTS = {
    "quiet": True,
    "no_warnings": True,
    **({"cookiefile": str(COOKIES_FILE)} if COOKIES_FILE.exists() else {}),
}


# ── helpers ────────────────────────────────────────────────────────────────

def clean_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    clean_qs = {k: v for k, v in qs.items() if k == "v"}
    if parsed.hostname == "youtu.be":
        video_id = parsed.path.lstrip("/").split("?")[0]
        return f"https://www.youtube.com/watch?v={video_id}"
    clean = parsed._replace(query=urllib.parse.urlencode(clean_qs, doseq=True))
    return urllib.parse.urlunparse(clean) if clean_qs else url


QUALITY_MAP = {
    "144":  "bestvideo[height<=144]+bestaudio/best[height<=144]",
    "240":  "bestvideo[height<=240]+bestaudio/best[height<=240]",
    "360":  "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "480":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "720":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "1440": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "2160": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "max":  "bestvideo+bestaudio/best",
}


# ── routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    html_file = BASE_DIR / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/info")
def get_info(url: str = Query(...)):
    url = clean_url(url)
    try:
        with yt_dlp.YoutubeDL(COMMON_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "title":     info.get("title", "Unknown"),
            "duration":  info.get("duration_string", "?"),
            "thumbnail": info.get("thumbnail", ""),
            "channel":   info.get("channel", ""),
            "url":       url,
        }
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/download")
def download(
    url:     str = Query(...),
    fmt:     str = Query("mp4"),
    quality: str = Query("1080"),
):
    url = clean_url(url)
    tmp_dir = tempfile.mkdtemp()
    outtmpl = os.path.join(tmp_dir, "%(title)s.%(ext)s")

    if fmt == "mp3":
        opts = {
            **COMMON_OPTS,
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
        }
    else:
        opts = {
            **COMMON_OPTS,
            "format": QUALITY_MAP.get(quality, "bestvideo+bestaudio/best"),
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
        }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    files = list(Path(tmp_dir).iterdir())
    if not files:
        raise HTTPException(status_code=500, detail="Download produced no file")

    out_file = files[0]
    safe_name = re.sub(r'[^\w\s\-.]', '', out_file.name).strip()
    media_type = "audio/mpeg" if fmt == "mp3" else "video/mp4"

    return FileResponse(
        path=str(out_file),
        media_type=media_type,
        filename=safe_name,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
