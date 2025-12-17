import os
import re
import json
from typing import Optional

CACHE_FILE = os.path.join("data", "lyrics_cache.json")
CRED_FILE = os.path.join("data", "credentials.json")
GENIUS_API_TOKEN = "d1teN_44PiYvoYQa6pS_Z4ocjWAk5LMpDRhefTjIhmW97mgSX8tQgC8fI91yYi_X"

# Lazy import so the rest of the app runs even if lyrics aren't used yet
_genius = None
_genius_ready = False

def _load_token() -> Optional[str]:
    """
    Load the Genius API token from environment variable or credentials file.

    Returns:
        Optional[str]: The Genius API token, or None if not found.
    """
    if GENIUS_API_TOKEN:
        return GENIUS_API_TOKEN
    # Prefer env var
    tok = os.environ.get("GENIUS_API_TOKEN")
    if tok:
        return tok
    # Fallback to credentials file
    if os.path.exists(CRED_FILE):
        try:
            with open(CRED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("GENIUS_API_TOKEN")
        except Exception:
            pass
    return None

def _init_genius():
    """
    Initialize the Genius API client.
    """
    global _genius, _genius_ready
    if _genius_ready:
        return
    token = _load_token()
    if not token:
        _genius_ready = False
        return
    try:
        import lyricsgenius  # pip install lyricsgenius
        _genius = lyricsgenius.Genius(
            token,
            skip_non_songs=True,
            excluded_terms=["(Remix)", "(Live)"],
            timeout=10,
            retries=2,
            remove_section_headers=True,   # remove [Chorus], [Verse 1], etc.
        )
        # Be polite with rate limits
        _genius.sleep_time = 0.5
        _genius.verbose = False
        _genius_ready = True
    except Exception:
        _genius_ready = False

def _load_cache() -> dict:
    """
    Load the lyrics cache from a file.

    Returns:
        dict: The lyrics cache.
    """
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_cache(cache: dict) -> None:
    """
    Save the lyrics cache to a file.

    Args:
        cache (dict): The lyrics cache.
    """
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4, ensure_ascii=False)

def _norm_key(artist: str, title: str) -> str:
    """
    Normalizes artist and title into a cache key.
    Strips common noise from names.

    Args:
        artist (str): The artist name.
        title (str): The song title.

    Returns:
        str: The cache key.
    """
    def clean(s: str) -> str:
        """
        Cleans the input string by normalizing whitespace and removing common noise.
        Regular expressions are used to remove phrases like "(Official Video)" or "(Audio)".
                
        Args:
            s (str): The input string to clean.

        Returns:
            str: The cleaned string.
        """
        s = s.lower().strip()
        # normalize common filename noise
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"\(.*?official.*?video.*?\)", "", s)
        s = re.sub(r"\(.*?audio.*?\)", "", s)
        s = re.sub(r"feat\.?|ft\.", "feat", s)
        s = s.replace("_", " ")
        return s.strip()
    return f"{clean(artist)}|{clean(title)}"

def _strip_trailing_credits(lyrics: str) -> str:
    """
    Strips trailing credits like "Embed", URLs, etc. from lyrics text.

    Args:
        lyrics (str): The lyrics text.

    Returns:
        str: The cleaned lyrics text.
    """
    # Remove “Embed”, trailing URLs, etc.
    lines = lyrics.strip().splitlines()
    cleaned = []
    for ln in lines:
        if ln.strip().lower().endswith("embed"):
            continue
        if ln.strip().startswith("https://") or ln.strip().startswith("http://"):
            continue
        cleaned.append(ln)
    txt = "\n".join(cleaned).strip()
    # collapse excess blank lines
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt

def _fallback_message(reason: str) -> str:
    """
    Generate a fallback message when lyrics are unavailable.

    Args:
        reason (str): The reason for unavailability.

    Returns:
        str: The fallback message.
    """
    return f"Lyrics unavailable ({reason}). Make sure GENIUS_API_TOKEN is set."

def get_lyrics(artist: str, title: str) -> str:
    """
    Fetch lyrics from Genius with caching.
    - Tries exact (artist, title)
    - Falls back to smart search by 'title artist'
    - Caches hits and misses so we avoid repeated lookups
    
    Args:
        artist (str): The artist name.
        title (str): The song title.
        
    Returns:
        str: The lyrics text, or an error message.
    """
    cache = _load_cache()
    key = _norm_key(artist, title)

    cached = cache.get(key)
    if isinstance(cached, str):
        return cached
    elif isinstance(cached, dict) and "lyrics" in cached:
        return cached["lyrics"]

    _init_genius()
    if not _genius_ready:
        msg = _fallback_message("no API token or client init failed")
        return msg

    # — Try exact match first
    lyrics_text = None
    try:
        # search_song(title, artist) often does a good job for exact
        song = _genius.search_song(title=title, artist=artist)
        if song and song.lyrics:
            lyrics_text = song.lyrics
        else:
            # — Fallback: looser search combining both
            query = f"{title} {artist}".strip()
            song2 = _genius.search_song(query)
            if song2 and song2.lyrics:
                lyrics_text = song2.lyrics
    except Exception:
        lyrics_text = None

    if not lyrics_text:
        lyrics_text = _fallback_message("not found")

    lyrics_text = _strip_trailing_credits(lyrics_text)

    cache[key] = lyrics_text
    _save_cache(cache)
    return lyrics_text
