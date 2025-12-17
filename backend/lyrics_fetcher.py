import os
import re
import json
from pathlib import Path
from typing import Optional

CACHE_FILE = os.path.join("data", "lyrics_cache.json")
CRED_FILE = os.path.join("data", "credentials.json")
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_ENV_LOADED = False

# Lazy import so the rest of the app runs even if lyrics aren't used yet
_genius = None
_genius_ready = False

def _load_env_file() -> None:
    """
    Loads key=value pairs from the local .env into os.environ without overriding
    variables that are already set in the environment.
    """
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

def _load_token() -> Optional[str]:
    """
    Load the Genius API token from environment variable or credentials file.

    Returns:
        Optional[str]: The Genius API token, or None if not found.
    """
    _load_env_file()
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
    Initialize the Genius API client with a Fake Browser User-Agent.
    """
    global _genius, _genius_ready
    if _genius_ready:
        return
    token = _load_token()
    if not token:
        _genius_ready = False
        return
    try:
        import lyricsgenius
        
        # 1. Define a "Real Browser" User-Agent
        fake_user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        _genius = lyricsgenius.Genius(
            token,
            skip_non_songs=True,
            excluded_terms=["(Remix)", "(Live)"],
            timeout=15,          # Increase timeout slightly
            retries=3,           # Increase retries
            remove_section_headers=True,
            user_agent=fake_user_agent  # <--- CRITICAL FIX
        )
        
        # 2. Be extremely polite to avoid bans
        _genius.sleep_time = 1.0 # Wait 1 second between requests
        _genius.verbose = False
        _genius_ready = True
        print(f"Genius Client Initialized (User-Agent set)")
        
    except Exception as e:
        print(f"CRITICAL GENIUS ERROR: {e}")
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
    Fetch lyrics for a given artist and title using the Genius API, with caching.
    
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
        print(f"Found in cache: {artist} - {title}")
        return cached
    elif isinstance(cached, dict) and "lyrics" in cached:
        print(f"Found in cache (dict): {artist} - {title}")
        return cached["lyrics"]

    _init_genius()
    if not _genius_ready:
        return _fallback_message("no API token or client init failed")

    # --- DEBUGGING PRINTS ---
    print(f"SEARCHING GENIUS: Artist='{artist}', Title='{title}'")

    lyrics_text = None
    try:
        # 1. Try exact search
        song = _genius.search_song(title=title, artist=artist)
        if song and song.lyrics:
            print("Match found (Exact)")
            lyrics_text = song.lyrics
        else:
            # 2. Try looser search
            query = f"{title} {artist}".strip()
            print(f"Exact match failed. Trying fallback query: '{query}'")
            song2 = _genius.search_song(query)
            if song2 and song2.lyrics:
                print("Match found (Fallback)")
                lyrics_text = song2.lyrics
    
    except Exception as e:
        # THIS IS THE MOST IMPORTANT LINE:
        print(f"GENIUS SEARCH FAILED: {type(e).__name__}: {e}")
        lyrics_text = None

    if not lyrics_text:
        print("No lyrics found after all attempts.")
        lyrics_text = _fallback_message("not found")
    else:
        # Clean up
        lyrics_text = _strip_trailing_credits(lyrics_text)
        # Save to cache
        cache[key] = lyrics_text
        _save_cache(cache)

    return lyrics_text