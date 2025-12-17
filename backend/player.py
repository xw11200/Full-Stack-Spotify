import threading
import time

import pygame
from backend.song import Song

class Player:
    """
    A simple music player class.
    
    Attributes:
        current_song (Song | None): The currently loaded song.
        is_playing (bool): Indicates if a song is currently playing.
        paused (bool): Indicates if playback is paused.
        _monitor_thread (threading.Thread | None): Thread to monitor playback status.
    """
    def __init__(self):
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self.current_song = None
        self.is_playing = False
        self.paused = False
        self._monitor_thread = None

    def play(self, song: Song) -> None:
        """
        Plays the given song.

        Args:
            song (Song): The song to play.
        """
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

        try:
            pygame.mixer.music.load(song.file_path)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Error playing song: {e}")
            self.current_song = None
            self.is_playing = False
            self.paused = False
            return

        self.current_song = song
        self.is_playing = True
        self.paused = False
        self._start_monitor_thread()
        print(f"Now playing: {song.title}")

    def pause(self) -> None:
        """
        Pauses the current song.
        """
        if self.is_playing and not self.paused:
            pygame.mixer.music.pause()
            self.paused = True
            print("Paused")
        elif self.paused:
            pygame.mixer.music.unpause()
            self.paused = False
            print("Resumed")
            if not self.is_playing:
                self.is_playing = True

    def stop(self) -> None:
        """
        Stops the current song.
        """
        if self.is_playing or pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        self.is_playing = False
        self.paused = False
        self.current_song = None
        print("Stopped playback")

    def set_volume(self, level: float) -> None:
        """
        Sets the volume level.

        Args:
            level (float): Volume level between 0.0 and 1.0.
        """
        pygame.mixer.music.set_volume(level)
        print(f"Volume set to {int(level*100)}%")

    def _start_monitor_thread(self) -> None:
        """
        Track when playback naturally finishes so state flags stay in sync.
        """
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        def monitor():
            while self.is_playing and (pygame.mixer.music.get_busy() or self.paused):
                time.sleep(0.2)
            if not self.is_playing:
                return
            self.is_playing = False
            self.paused = False
            self.current_song = None

        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()
