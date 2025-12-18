# Full-Stack Spotify Lite

A lightweight full‑stack music player that pairs a FastAPI backend with a vanilla HTML/JS frontend. It scans a local `data/songs` folder for MP3s, serves them to the browser, streams audio, fetches album art and lyrics, and can import tracks directly from Spotify/Apple Music links via SpotDL.

## Features
- **FastAPI backend** exposing `/songs`, `/stream/{id}`, `/cover/{id}`, and `/lyrics/{id}` endpoints.
- **SQLite catalog** that keeps song metadata, paths, and playlists in sync with the filesystem.
- **Browser UI** (plain HTML/CSS/JS) for browsing the library, viewing lyrics, playing audio, and initiating imports.
- **Lyrics support** through the Genius API with caching so repeated requests stay fast/offline.
- **Track importer** powered by [SpotDL](https://github.com/spotDL/spotify-downloader) to pull tracks (with album art + metadata) from Spotify/Apple Music links directly into `data/songs`.

## Project structure
```
backend/
  main.py           # FastAPI app + download endpoint
  library.py        # Library scanner + filename normalization
  database.py       # SQLite helper for songs/playlists
  lyrics_fetcher.py # Genius integration & caching
  player.py         # Local pygame player (optional CLI use)
  playlist.py, song.py
frontend/
  index.html        # Single-page UI (served statically)
data/
  songs/            # MP3 files are stored/scanned here
  spotify.db        # SQLite file (auto created)
  lyrics_cache.json # Generated cache
.env                # Secrets and credentials (not committed)
```

## Requirements
Install Python 3.11+ (project tested with 3.11/3.12). Dependencies live in `requirements.txt`:
```
pip install -r requirements.txt
```
This installs FastAPI, Uvicorn, Mutagen, pygame, lyricsgenius, SpotDL, and imageio-ffmpeg.

### External tools
- **SpotDL CLI** (installed automatically via `pip install spotdl`, but ensure it’s on PATH).
- **FFmpeg** – SpotDL requires it for conversions. Either:
  - install it system-wide (`brew install ffmpeg` / package manager),
  - set `FFMPEG_BIN` in `.env`, or
  - rely on the bundled binary from `imageio-ffmpeg` (auto-configured in the backend).

## Environment variables
Create a `.env` file at the repo root (already ignored by git). Required keys:
```env
# Genius / lyrics
GENIUS_API_TOKEN=your_genius_token

# Spotify API (create an app at https://developer.spotify.com/)
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Optional overrides
SPOTDL_BIN=/path/to/spotdl        # defaults to 'spotdl'
FFMPEG_BIN=/usr/local/bin/ffmpeg  # skip if on PATH or using imageio-ffmpeg
```

## Running the app
1. **Populate songs**: Drop MP3 files into `data/songs` (or use the import flow once running).
2. **Start the backend**:
   ```
   uvicorn backend.main:app --reload
   ```
   On startup the server scans `data/songs`, syncs metadata into `data/spotify.db`, and serves static assets from `frontend/`.
3. **Open the UI**: Visit `http://127.0.0.1:8000/` (FastAPI serves `frontend/index.html`).
4. **Importing tracks**: Click “⬇︎ Import Track”, paste a Spotify/Apple Music link, and the backend will run SpotDL, normalize filenames (e.g., `Song — Artist.mp3`), and refresh the catalog automatically.

## Development tips
- To reset the library, delete the `data/songs` contents and restart; the SQLite DB will resync automatically.
- `data/lyrics_cache.json` caches Genius responses; delete it if switching tokens or testing failures.
- The frontend uses vanilla JS—adjust `frontend/index.html` if you need new controls or UI tweaks.

## Troubleshooting
- **Import errors**: The UI now surfaces SpotDL stderr; check FastAPI logs for full context. Common issues include missing Spotify credentials, invalid links, or FFmpeg not found.
- **Lyrics unavailable**: Ensure `GENIUS_API_TOKEN` is set and valid; the backend falls back to a helpful message if not.
- **Album art missing**: Some MP3s lack embedded art; SpotDL usually embeds it automatically, otherwise `/cover/{id}` will 404.

## Future ideas
- Add playlist CRUD endpoints backed by `backend/database.py`.
- Swap the static frontend for a React/Vue client if needed.
- Extend the importer to support bulk playlists or other providers.

Enjoy building on Spotify Lite! Contributions and customizations welcome. 
