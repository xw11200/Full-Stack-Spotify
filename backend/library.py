import os
import re
from mutagen.mp3 import MP3

from backend.database import Database
from backend.song import Song

DASH = r"[-–—]"  # hyphen, en-dash, em-dash

def parse_filename(filename: str) -> tuple[str, str, int]:
    """
    Parse: 'Title - Artist (m:ss).mp3' or 'Title - Artist.mp3'
    Returns: (title, artist, duration_seconds or 0)
    """
    name = os.path.splitext(filename)[0]  # strip .mp3
    # Title  -  Artist   (optional mm:ss)
    m = re.match(rf"^(.*?)\s*{DASH}\s*(.*?)\s*(?:\((\d+):(\d+)\))?$", name)
    if not m:
        # Try just "Title (mm:ss)"
        m2 = re.match(r"^(.*?)\s*\((\d+):(\d+)\)$", name)
        if m2:
            title = m2.group(1).strip()
            artist = "Unknown"
            mins, secs = int(m2.group(2)), int(m2.group(3))
            return title, artist, mins * 60 + secs
        # Fallback: whole name is title
        return name.strip(), "Unknown", 0

    title = m.group(1).strip()
    artist = m.group(2).strip() or "Unknown"
    if m.group(3) and m.group(4):
        mins, secs = int(m.group(3)), int(m.group(4))
        return title, artist, mins * 60 + secs
    return title, artist, 0

class MusicLibrary:
    """
    A simple music library that loads songs from a folder.
    
    Attributes:
        songs (list[Song]): The list of songs in the library.
    """
    def __init__(self, database: Database | None = None):
        self.songs = []
        self.database = database

    def load_from_folder(self, folder_path: str) -> None:
        """
        Load songs from the specified folder.

        Args:
            folder_path (str): Path to the folder containing MP3 files.
        """
        self.songs.clear()
        if not os.path.exists(folder_path):
            print("Folder not found.")
            return

        self._normalize_filenames(folder_path)

        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".mp3"):
                path = os.path.join(folder_path, filename)

                # Parse title/artist/(optional)duration from filename
                parsed_title, parsed_artist, parsed_duration = parse_filename(filename)

                # Prefer Mutagen duration; fall back to parsed duration if Mutagen fails
                try:
                    audio = MP3(path)
                    duration = getattr(audio.info, "length", 0) or parsed_duration
                except Exception:
                    duration = parsed_duration

                song = Song(
                    title=parsed_title,
                    artist=parsed_artist,
                    file_path=path,
                    duration=duration
                )
                self.songs.append(song)

        print(f"Loaded {len(self.songs)} songs from {folder_path}")
        self._sync_database()

    def display_songs(self):
        """
        Display the list of loaded songs.
        """
        if not self.songs:
            print("No songs loaded.")
            return
        for i, song in enumerate(self.songs, 1):
            print(f"{i}. {song}")

    def _sync_database(self) -> None:
        """Persist the current library snapshot if a database is configured."""
        if self.database:
            self.database.sync_songs(self.songs)

    def _normalize_filenames(self, folder_path: str) -> None:
        """
        Rename files containing spotdl placeholders (e.g. .{ext}) to .mp3 so they parse cleanly.
        """
        for filename in os.listdir(folder_path):
            if ".{ext}" not in filename:
                continue
            old_path = os.path.join(folder_path, filename)
            new_name = filename.replace(".{ext}", ".mp3")
            new_path = os.path.join(folder_path, new_name)
            if os.path.exists(new_path):
                continue
            try:
                os.rename(old_path, new_path)
            except OSError:
                pass
