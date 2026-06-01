import os
import re
import urllib.parse
from pathlib import Path

import httpx
import imageio_ffmpeg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

os.environ["PATH"] += os.pathsep + imageio_ffmpeg.get_ffmpeg_exe().rsplit("/", 1)[0]

app = FastAPI(title="ytdl")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "6d17e6275fmsh6816e08a32191dcp157126jsn5236c140a20f")
RAPIDAPI_HOST = "youtube-to-mp315.p.rapidapi.com"

HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
}


# ── helpers ────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/").split("?")[0]
    qs = urllib.parse.parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    raise HTTPException(status_code=400, detail="Could not extract video ID from URL")


# ── routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    html_file = BASE_DIR / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/info")
async def get_info(url: str = Query(...)):
    video_id = extract_video_id(url)
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            res = await client.get(
                f"https://{RAPIDAPI_HOST}/dl",
                params={"id": video_id},
                headers=HEADERS,
            )
            data = res.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    if res.status_code != 200 or data.get("status") == "fail":
        raise HTTPException(status_code=400, detail=data.get("mess", "Failed to fetch video info"))

    return {
        "title":     data.get("title", "Unknown"),
        "duration":  data.get("duration", "?"),
        "thumbnail": data.get("thumb", ""),
        "channel":   data.get("a", ""),
        "url":       url,
        "formats":   data.get("links", {}),
    }


@app.get("/download")
async def download(
    url:     str = Query(...),
    fmt:     str = Query("mp4"),
    quality: str = Query("1080"),
):
    video_id = extract_video_id(url)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            res = await client.get(
                f"https://{RAPIDAPI_HOST}/dl",
                params={"id": video_id},
                headers=HEADERS,
            )
            data = res.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    if res.status_code != 200 or data.get("status") == "fail":
        raise HTTPException(status_code=400, detail=data.get("mess", "Failed to fetch video"))

    links = data.get("links", {})

    # Pick the right download URL
    download_url = None
    if fmt == "mp3":
        mp3_links = links.get("mp3", {})
        # grab first available mp3
        for k, v in mp3_links.items():
            download_url = v.get("url")
            break
    else:
        mp4_links = links.get("mp4", {})
        # try to match quality, fall back to best available
        quality_map = {"1080": "1080", "720": "720", "480": "480", "360": "360", "240": "240", "144": "144"}
        target = quality_map.get(quality, "1080")
        for k, v in mp4_links.items():
            if target in k:
                download_url = v.get("url")
                break
        if not download_url:
            # fallback to first available
            for k, v in mp4_links.items():
                download_url = v.get("url")
                break

    if not download_url:
        raise HTTPException(status_code=400, detail="No download URL found for requested format")

    # Stream the file from the download URL to the client
    title = re.sub(r'[^\w\s\-.]', '', data.get("title", "video")).strip()
    filename = f"{title}.{fmt}"
    media_type = "audio/mpeg" if fmt == "mp3" else "video/mp4"

    async def stream_file():
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            async with client.stream("GET", download_url) as r:
                async for chunk in r.aiter_bytes(chunk_size=1024 * 64):
                    yield chunk

    return StreamingResponse(
        stream_file(),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
