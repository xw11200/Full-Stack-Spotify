from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Any

from backend.song import Song


class Database:
    """Simple SQLite helper that persists songs and playlists."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parent
        default_path = base_dir.parent / "data" / "spotify.db"
        self.db_path = Path(db_path or default_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    duration REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS playlist_songs (
                    playlist_id INTEGER NOT NULL,
                    song_id INTEGER NOT NULL,
                    position INTEGER,
                    PRIMARY KEY (playlist_id, song_id),
                    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
                )
                """
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def sync_songs(self, songs: Iterable[Song]) -> None:
        """Upsert songs from the in-memory library and prune stale rows."""
        songs = list(songs)
        incoming_paths = {s.file_path for s in songs}
        with self._connection() as conn:
            for song in songs:
                conn.execute(
                    """
                    INSERT INTO songs (title, artist, file_path, duration)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(file_path) DO UPDATE SET
                        title=excluded.title,
                        artist=excluded.artist,
                        duration=excluded.duration
                    """,
                    (song.title, song.artist, song.file_path, float(song.length)),
                )

            if incoming_paths:
                placeholders = ",".join("?" for _ in incoming_paths)
                conn.execute(
                    f"DELETE FROM songs WHERE file_path NOT IN ({placeholders})",
                    tuple(incoming_paths),
                )
            else:
                conn.execute("DELETE FROM songs")

    def list_songs(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, title, artist, file_path, duration FROM songs ORDER BY title"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_song(self, song_id: int) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT id, title, artist, file_path, duration FROM songs WHERE id = ?",
                (song_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_playlist(self, name: str) -> int:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Playlist name cannot be empty")
        with self._connection() as conn:
            cursor = conn.execute("INSERT INTO playlists(name) VALUES (?)", (cleaned,))
            return cursor.lastrowid

    def delete_playlist(self, playlist_id: int) -> None:
        with self._connection() as conn:
            conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))

    def rename_playlist(self, playlist_id: int, new_name: str) -> None:
        cleaned = new_name.strip()
        if not cleaned:
            raise ValueError("Playlist name cannot be empty")
        with self._connection() as conn:
            conn.execute(
                "UPDATE playlists SET name = ? WHERE id = ?",
                (cleaned, playlist_id),
            )

    def list_playlists(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, name, created_at FROM playlists ORDER BY name"
            ).fetchall()
        return [dict(row) for row in rows]

    def add_song_to_playlist(self, playlist_id: int, song_id: int, position: int | None = None) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO playlist_songs (playlist_id, song_id, position)
                VALUES (?, ?, ?)
                """,
                (playlist_id, song_id, position),
            )

    def remove_song_from_playlist(self, playlist_id: int, song_id: int) -> None:
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM playlist_songs WHERE playlist_id = ? AND song_id = ?",
                (playlist_id, song_id),
            )

    def playlist_songs(self, playlist_id: int) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.title, s.artist, s.file_path, s.duration
                FROM playlist_songs ps
                JOIN songs s ON s.id = ps.song_id
                WHERE ps.playlist_id = ?
                ORDER BY COALESCE(ps.position, s.title)
                """,
                (playlist_id,),
            ).fetchall()
        return [dict(row) for row in rows]
