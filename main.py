import os
import re
import asyncio
import urllib.parse
from pathlib import Path

import yt_dlp
import imageio_ffmpeg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

# Add imageio_ffmpeg's binary path directly to the environment PATH
# This ensures yt-dlp can find and use FFmpeg natively on Render!
ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
os.environ["PATH"] += os.pathsep + ffmpeg_dir

app = FastAPI(title="ytdl")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent

# ── routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    html_file = BASE_DIR / "index.html"
    if not html_file.exists():
        return HTMLResponse(content="<h1>index.html not found!</h1>", status_code=404)
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/info")
async def get_info(url: str = Query(...)):
    try:
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Safely fetch video details using yt-dlp
            info = ydl.extract_info(url, download=False)
        
        # Returns standard data matching what your frontend maps to
        return {
            "title":     info.get("title", "Unknown"),
            "duration":  info.get("duration", 0),
            "thumbnail": info.get("thumbnail", ""),
            "channel":   info.get("uploader", ""),
            "url":       url,
            "formats":   {}, 
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/download")
async def download(
    url:     str = Query(...),
    fmt:     str = Query("mp4"),
    quality: str = Query("1080"),
):
    try:
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = re.sub(r'[^\w\s\-.]', '', info.get("title", "video")).strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch video details: {str(e)}")

    filename = f"{title}.{fmt}"
    
    if fmt == "mp3":
        media_type = "audio/mpeg"
        # Extract best audio stream and pipe directly to stdout
        cmd = [
            "yt-dlp",
            "-f", "ba[ext=m4a]/ba",
            "-o", "-",
            "--quiet",
            url
        ]
    else:
        media_type = "video/mp4"
        quality_map = {"1080": 1080, "720": 720, "480": 480, "360": 360}
        target_height = quality_map.get(quality, 1080)
        
        # Select single progressive stream so it pipes sequentially over stdout without crashing
        cmd = [
            "yt-dlp",
            "-f", f"best[height<={target_height}][ext=mp4]/best[ext=mp4]/best",
            "-o", "-",
            "--quiet",
            url
        ]

    # ── Real-Time Streaming and Logging Logic ──────────────────────────────
    async def stream_file():
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        bytes_streamed = 0
        while True:
            chunk = await process.stdout.read(1024 * 64)
            if not chunk:
                break
            bytes_streamed += len(chunk)
            
            # This replaces your old terminal progress updates 
            # Providing real-time throughput metrics straight into your Render logs!
            print(f"Streaming {filename}: {bytes_streamed / (1024*1024):.2f} MB transferred", flush=True)
            yield chunk
            
        await process.wait()

    return StreamingResponse(
        stream_file(),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
