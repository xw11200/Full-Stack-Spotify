import json
from backend.song import Song
from backend.library import MusicLibrary

class Playlist:
    """
    Represents a music playlist.

    Attributes:
        name (str): The name of the playlist.
        songs (list[Song]): The list of songs in the playlist.
    """
    def __init__(self, name: str):
        self.name = name
        self.songs = []

    def add_song(self, song: Song) -> None:
        """
        Adds a song to the playlist.

        Args:
            song (Song): The song to add.
        """
        if song not in self.songs:
            self.songs.append(song)
            print(f"Added {song.title} to playlist '{self.name}'")

    def remove_song(self, song_or_path: Song | str) -> None:
        """
        Removes a song from the playlist by Song object or file path/title string.

        Args:
            song_or_path (Song | str): The song (or identifier) to remove.
        """
        if isinstance(song_or_path, Song):
            identifier = song_or_path.file_path
        else:
            identifier = song_or_path

        for idx, song in enumerate(self.songs):
            if song.file_path == identifier:
                removed = self.songs.pop(idx)
                print(f"Removed {removed.title} from playlist '{self.name}'")
                return

        if isinstance(song_or_path, str):
            matches = [i for i, song in enumerate(self.songs) if song.title == song_or_path]
            if len(matches) == 1:
                removed = self.songs.pop(matches[0])
                print(f"Removed {removed.title} from playlist '{self.name}'")
                return

        print("Song not found in playlist.")

    def list_songs(self) -> None:
        """
        Lists all songs in the playlist.
        """
        if not self.songs:
            print(f"Playlist '{self.name}' is empty.")
        else:
            print(f"Playlist '{self.name}':")
            for i, song in enumerate(self.songs, 1):
                print(f"{i}. {song}")

    def save_to_file(self, filepath: str) -> None:
        """
        Saves the playlist to a file.
        
        Args:
            filepath (str): The path to the file where the playlist will be saved.
        """
        data = [s.file_path for s in self.songs]
        with open(filepath, "w") as f:
            json.dump(data, f)
        print(f"Playlist saved to {filepath}")

    def load_from_file(self, filepath: str, library: MusicLibrary) -> None:
        """
        Loads the playlist from a file.
        
        Args:
            filepath (str): The path to the file from which the playlist will be loaded.
            library (MusicLibrary): The music library to reference for song objects.
        """
        try:
            with open(filepath, "r") as f:
                paths = json.load(f)
            self.songs.clear()
            missing = []
            for p in paths:
                song = next((s for s in library.songs if s.file_path == p), None)
                if song:
                    if song not in self.songs:
                        self.songs.append(song)
                else:
                    missing.append(p)
            print(f"Loaded playlist '{self.name}' from file.")
            if missing:
                print(f"Warning: {len(missing)} song(s) from the saved playlist were not found in the library.")
        except FileNotFoundError:
            print("No saved playlist found.")
