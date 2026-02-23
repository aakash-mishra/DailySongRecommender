"""
Profiler Agent

Deterministic data-collection agent — no LLM involved.
Uses the Spotify MCP server to build a complete picture of the user's
music taste: full Liked Songs library, genre distribution, and average
audio features.

This agent intentionally does not use Claude. Not everything in an
agentic system needs an LLM. Deterministic data pipelines should stay
deterministic.
"""
import asyncio
import json
import sys
import os
import logging
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

log = logging.getLogger(__name__)

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SPOTIFY_SERVER = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "mcp_servers", "spotify_server.py")


async def build_profile(max_liked_songs: int = 2000) -> dict:
    """Fetch the user's full music profile via the Spotify MCP server.

    Returns a dict with:
        liked_song_ids       — set of all fetched liked track IDs
        liked_song_count     — total liked songs on Spotify (may exceed max_liked_songs)
        top_genres           — list of genres ranked by frequency
        comfort_zone_genres  — the top-5 genres (user's core territory)
        genre_distribution   — {genre: count} for top 30 genres
        avg_audio_features   — mean feature vector over top 200 liked tracks
        top_artists          — list of top-10 artist dicts
    """
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", SPOTIFY_SERVER],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=30)
            log.info("Spotify MCP session ready.")

            # ------------------------------------------------------------------
            # 1. Collect liked songs (paginated)
            # ------------------------------------------------------------------
            all_liked_ids: list[str] = []
            offset = 0
            page_size = 50
            total_on_spotify: int | None = None

            while True:
                result = await session.call_tool(
                    "get_liked_songs", {"limit": page_size, "offset": offset}
                )
                data = json.loads(result.content[0].text)

                if total_on_spotify is None:
                    total_on_spotify = data["total"]
                    log.info(f"Library has {total_on_spotify} liked songs total.")

                tracks = data["tracks"]
                if not tracks:
                    break

                for t in tracks:
                    all_liked_ids.append(t["id"])

                offset += page_size
                if offset >= min(max_liked_songs, total_on_spotify):
                    break

            log.info(f"Fetched {len(all_liked_ids)} liked song IDs.")

            # ------------------------------------------------------------------
            # 2. Top artists → genre distribution
            # ------------------------------------------------------------------
            artists_result = await session.call_tool(
                "get_top_artists", {"limit": 50, "time_range": "long_term"}
            )
            artists_data = json.loads(artists_result.content[0].text)

            genre_counter: Counter = Counter()
            for artist in artists_data["artists"]:
                for genre in artist["genres"]:
                    genre_counter[genre] += 1

            top_genres = [g for g, _ in genre_counter.most_common(20)]
            comfort_zone_genres = [g for g, _ in genre_counter.most_common(5)]

            # ------------------------------------------------------------------
            # 3. Audio features (deprecated endpoint — skipped)
            # ------------------------------------------------------------------
            # NOTE: Spotify deprecated the audio-features endpoint in Nov 2024.
            # It's no longer available for new applications. Skipping this analysis.
            avg_features: dict[str, float] = {}

            return {
                "liked_song_ids": all_liked_ids,   # list; caller can convert to set
                "liked_song_count": total_on_spotify,
                "top_genres": top_genres,
                "comfort_zone_genres": comfort_zone_genres,
                "genre_distribution": dict(genre_counter.most_common(30)),
                "avg_audio_features": avg_features,
                "top_artists": artists_data["artists"][:10],
            }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    profile = asyncio.run(build_profile(max_liked_songs=200))

    print(f"\nLiked songs in library : {profile['liked_song_count']}")
    print(f"Fetched IDs            : {len(profile['liked_song_ids'])}")
    print(f"Comfort zone genres    : {profile['comfort_zone_genres']}")
    print(f"Top genres (20)        : {profile['top_genres']}")
    print("\nAverage audio features:")
    for k, v in profile["avg_audio_features"].items():
        print(f"  {k:<20} {v:.4f}")
