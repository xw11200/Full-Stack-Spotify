import os
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import imageio_ffmpeg

# Import your existing classes
from .database import Database
from .library import MusicLibrary
from .playlist import Playlist
from .lyrics_fetcher import get_lyrics
from mutagen.id3 import ID3, ID3NoHeaderError
# import lyrics-fetcher (renamed to valid python module name if needed, or import dynamically)

app = FastAPI(title="Spotify Lite API")

# Allow the frontend (React/HTML) to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (for development)
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR.parent / "data" / "songs"
FRONTEND_DIR = BASE_DIR.parent / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"
ENV_FILE = BASE_DIR.parent / ".env"
_ENV_LOADED = False


def _load_env_file() -> None:
    """Load key=value pairs from .env into os.environ once."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    if ENV_FILE.exists():
        try:
            with ENV_FILE.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            pass
    _ENV_LOADED = True

# --- Initialize Library ---
_load_env_file()
database = Database()
library = MusicLibrary(database=database)
print(f"Server scanning songs in: {DATA_PATH}")
library.load_from_folder(str(DATA_PATH))

# Serve the frontend assets if they exist so users only hit one server
if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
def read_root():
    """
    Serve the main HTML file if it exists, otherwise keep the old JSON message.
    """
    if INDEX_FILE.exists():
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), media_type="text/html")
    return {"message": "Spotify Lite Server is Running!"}

@app.get("/songs")
def get_all_songs():
    """Returns a list of all songs scanned by MusicLibrary."""
    # Convert Song objects to JSON-friendly dictionaries
    return database.list_songs()

@app.get("/stream/{song_id}")
def stream_music(song_id: int):
    """Serves the actual MP3 file to the browser."""
    song = database.get_song(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    if not os.path.exists(song["file_path"]):
        raise HTTPException(status_code=404, detail="File missing")
        
    return FileResponse(song["file_path"], media_type="audio/mpeg")

def _load_album_art(file_path: str):
    """
    Extract embedded album art from an MP3 file.
    Returns tuple of (bytes, mime) or (None, None) if missing.
    """
    try:
        tags = ID3(file_path)
    except ID3NoHeaderError:
        return None, None
    except Exception:
        return None, None

    for key in tags.keys():
        if key.startswith("APIC"):
            apic = tags[key]
            mime = getattr(apic, "mime", "image/jpeg") or "image/jpeg"
            return apic.data, mime
    return None, None

@app.get("/lyrics/{song_id}")
def fetch_lyrics(song_id: int):
    """Return lyrics for a song via the lyrics_fetcher helper."""
    song = database.get_song(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    lyrics_text = get_lyrics(song["artist"], song["title"])
    return {
        "title": song["title"],
        "artist": song["artist"],
        "lyrics": lyrics_text
    }

@app.get("/cover/{song_id}")
def get_album_cover(song_id: int):
    """Return embedded album art for the requested song."""
    song = database.get_song(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    art_bytes, mime = _load_album_art(song["file_path"])
    if not art_bytes:
        raise HTTPException(status_code=404, detail="Album art not found")
    return Response(content=art_bytes, media_type=mime)

class DownloadRequest(BaseModel):
    url: str


def _ensure_spotify_credentials() -> None:
    """SpotDL needs Spotify API credentials available."""
    missing = [
        key for key in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")
        if not os.environ.get(key)
    ]
    if missing:
        joined = ", ".join(missing)
        raise HTTPException(
            status_code=500,
            detail=f"Missing Spotify API credentials ({joined}). "
                   "Add them to your environment or .env file."
        )


def _spotdl_commands(url: str) -> list[list[str]]:
    """Build possible spotdl CLI commands (new + legacy syntax)."""
    binary = os.environ.get("SPOTDL_BIN", "spotdl")
    if not shutil.which(binary):
        raise HTTPException(
            status_code=500,
            detail="spotdl executable not found. Install it with 'pip install spotdl'."
        )

    ffmpeg_path = _resolve_ffmpeg_path()
    output_template = str(DATA_PATH / "{title} — {artist}")
    shared_opts = [
        "--format", "mp3",
        "--bitrate", "320k",
        "--output", output_template,
        "--ffmpeg", ffmpeg_path,
    ]

    new_cmd = [binary, "download", url, *shared_opts]
    legacy_cmd = [binary, url, *shared_opts]
    return [new_cmd, legacy_cmd]


@app.post("/download")
def download_song(request: DownloadRequest):
    url = request.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="A Spotify/Apple Music link is required.")

    _ensure_spotify_credentials()
    errors: list[str] = []
    for command in _spotdl_commands(url):
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(DATA_PATH),
                check=False,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=500,
                detail="spotdl executable not found. Install it with 'pip install spotdl'."
            )

        if result.returncode == 0:
            library.load_from_folder(str(DATA_PATH))
            return {"status": "success", "message": "Track imported successfully."}

        error_text = result.stderr.strip() or result.stdout.strip() or ""
        errors.append(error_text)
        if "usage:" not in error_text.lower():
            break

    detail = errors[-1] if errors else "SpotDL failed to download the requested track."
    raise HTTPException(status_code=500, detail=detail)


def _resolve_ffmpeg_path() -> str:
    """Return a usable ffmpeg binary path or raise if none is available."""
    env_path = os.environ.get("FFMPEG_BIN")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return str(candidate)
        located = shutil.which(env_path)
        if located:
            return located

    system_path = shutil.which("ffmpeg")
    if system_path:
        return system_path

    if imageio_ffmpeg:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

    raise HTTPException(
        status_code=500,
        detail="FFmpeg is required for SpotDL. Install ffmpeg, set FFMPEG_BIN, "
               "or add imageio-ffmpeg to provide a bundled binary."
    )
