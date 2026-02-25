"""
Spotify MCP Server

Exposes Spotify API operations as MCP tools. Runs as a subprocess;
communicates with the parent process via stdio JSON-RPC (FastMCP default).

IMPORTANT: never write to stdout — it is the MCP protocol channel.
Use sys.stderr for all diagnostic output.
"""
import sys
import os
import json
import logging

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="[spotify-server] %(message)s")
log = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP
from core.spotify_auth import get_spotify_client

mcp = FastMCP("spotify")

# Initialise once at startup — the cached token is refreshed automatically
# by spotipy when it expires.
try:
    sp = get_spotify_client()
    log.info("Spotify client ready.")
except Exception as e:
    log.error(f"Failed to initialise Spotify client: {e}")
    raise


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_liked_songs(limit: int = 50, offset: int = 0) -> str:
    """Fetch one page of the user's Liked Songs library.

    Use repeatedly with increasing offset to paginate through the full library.
    Spotify's maximum per page is 50. The response includes a 'total' field so
    you know when to stop.

    Args:
        limit: Tracks to return per page (max 50).
        offset: Zero-based starting position for pagination.
    """
    result = sp.current_user_saved_tracks(limit=min(limit, 50), offset=offset)
    tracks = []
    for item in result["items"]:
        track = item["track"]
        if track is None:
            continue
        tracks.append({
            "id": track["id"],
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "artist_id": track["artists"][0]["id"],
            "spotify_url": track["external_urls"]["spotify"],
            "popularity": track["popularity"],
        })
    return json.dumps({"tracks": tracks, "total": result["total"], "offset": offset})


@mcp.tool()
def get_top_artists(limit: int = 50, time_range: str = "long_term") -> str:
    """Fetch the user's top artists with their associated genres.

    Args:
        limit: Number of artists to return (max 50).
        time_range: Listening window — 'short_term' (4 weeks),
                    'medium_term' (6 months), or 'long_term' (all time).
    """
    result = sp.current_user_top_artists(limit=min(limit, 50), time_range=time_range)
    artists = []
    for artist in result["items"]:
        artists.append({
            "id": artist["id"],
            "name": artist["name"],
            "genres": artist["genres"],
            "popularity": artist["popularity"],
        })
    return json.dumps({"artists": artists})


@mcp.tool()
def search_tracks(query: str, limit: int = 20) -> str:
    """Search Spotify for tracks by genre, artist, keyword, or any combination.

    Genre search syntax:  genre:"post-rock"
    Artist search syntax: artist:"Mogwai"
    Free-text:            "atmospheric guitar instrumental"

    Args:
        query: Spotify search query string.
        limit: Number of results to return (max 50).
    """
    result = sp.search(q=query, limit=min(limit, 50), type="track")
    tracks = []
    for item in result["tracks"]["items"]:
        tracks.append({
            "id": item["id"],
            "name": item["name"],
            "artist": item["artists"][0]["name"],
            "spotify_url": item["external_urls"]["spotify"],
            "popularity": item["popularity"],
        })
    return json.dumps({"tracks": tracks})


@mcp.tool()
def get_recommendations(
    seed_genres: list = None,
    seed_artists: list = None,
    seed_tracks: list = None,
    limit: int = 20,
    target_energy: float = None,
    target_valence: float = None,
) -> str:
    """Get song recommendations from Spotify's recommendation engine.

    Spotify requires 1–5 total seeds (across genres, artists, and tracks combined).
    Seed genres MUST be from Spotify's official genre list — common valid values
    include: 'ambient', 'folk', 'post-rock', 'math-rock', 'shoegaze', 'krautrock',
    'bossanova', 'afrobeat', 'j-pop', 'flamenco', 'bluegrass', etc.
    Do NOT invent genre names; use standard Spotify genre slugs.

    Use this with non-comfort-zone genres to discover novel tracks.

    Args:
        seed_genres: List of Spotify genre slugs (e.g. ['post-rock', 'ambient']).
        seed_artists: List of Spotify artist IDs.
        seed_tracks: List of Spotify track IDs.
        limit: Number of recommendations (max 100).
        target_energy: Desired energy level 0.0–1.0 (optional).
        target_valence: Desired mood/positivity 0.0–1.0 (optional).
    """
    log.info(f"get_recommendations called with seed_genres: {seed_genres}")
    kwargs: dict = {"limit": min(limit, 100)}
    if seed_genres:
        kwargs["seed_genres"] = seed_genres[:5]
    if seed_artists:
        kwargs["seed_artists"] = seed_artists[:5]
    if seed_tracks:
        kwargs["seed_tracks"] = seed_tracks[:5]
    if target_energy is not None:
        kwargs["target_energy"] = target_energy
    if target_valence is not None:
        kwargs["target_valence"] = target_valence

    try:
        result = sp.recommendations(**kwargs)
    except Exception as e:
        # Return the error as a structured message so Claude can recover
        return json.dumps({"error": str(e), "hint": "Check that seed_genres are valid Spotify genre slugs."})

    tracks = []
    for track in result["tracks"]:
        tracks.append({
            "id": track["id"],
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "artist_id": track["artists"][0]["id"],
            "spotify_url": track["external_urls"]["spotify"],
            "popularity": track["popularity"],
        })
    return json.dumps({"tracks": tracks})


if __name__ == "__main__":
    mcp.run(transport="stdio")
