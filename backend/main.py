import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

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

# --- Initialize Library ---
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

# You can add Lyrics and Playlist endpoints here later!
