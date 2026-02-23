import sqlite3
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id TEXT NOT NULL UNIQUE,
                track_name TEXT NOT NULL,
                artist TEXT NOT NULL,
                spotify_url TEXT NOT NULL,
                genre TEXT,
                explanation TEXT,
                recommended_at TEXT NOT NULL
            )
        """)
        conn.commit()


def was_recommended(track_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM recommendations WHERE track_id = ?", (track_id,)
        ).fetchone()
        return row is not None


def log_recommendation(
    track_id: str,
    track_name: str,
    artist: str,
    spotify_url: str,
    genre: str,
    explanation: str,
):
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO recommendations
               (track_id, track_name, artist, spotify_url, genre, explanation, recommended_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                track_id,
                track_name,
                artist,
                spotify_url,
                genre,
                explanation,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()


def get_history(limit: int = 30) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM recommendations ORDER BY recommended_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


if __name__ == "__main__":
    init_db()
    log_recommendation(
        track_id="test_id_123",
        track_name="Test Song",
        artist="Test Artist",
        spotify_url="https://open.spotify.com/track/test",
        genre="test-genre",
        explanation="This is a test entry.",
    )
    history = get_history(limit=5)
    print(f"DB at {DB_PATH} — {len(history)} record(s):")
    for row in history:
        print(f"  [{row['recommended_at'][:10]}] {row['track_name']} by {row['artist']}")
