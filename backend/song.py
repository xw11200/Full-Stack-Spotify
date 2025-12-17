from mutagen.mp3 import MP3

class Song:
    """
    Represents a song in the music library.
    Attributes:
        title (str): The title of the song.
        artist (str): The artist of the song.
        file_path (str): The file path to the song.
        length (float): The duration of the song in seconds.
    """
    def __init__(self, title: str, artist: str, file_path: str, duration: float = None):
        self.title = title
        self.artist = artist
        self.file_path = file_path

        if duration is not None and duration > 0:
            self.length = duration
        else:
            try:
                audio = MP3(file_path)
                self.length = audio.info.length
            except Exception:
                self.length = 0

    def __str__(self) -> str:
        """
        Returns a string representation of the song.
        """
        minutes = int(self.length // 60)
        seconds = int(self.length % 60)
        return f"{self.title} - {self.artist} ({minutes}:{seconds:02d})"