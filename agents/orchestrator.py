"""
Orchestrator Agent

Coordinates the full recommendation pipeline:
  1. Build user music profile (profiler)
  2. Find a novel recommendation (Claude recommendation agent)
  3. Send the recommendation email (email MCP server)
  4. Log to SQLite history

This is the single entry point called by the CLI and the scheduler.
"""
import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

log = logging.getLogger(__name__)

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from agents.profiler import build_profile
from agents.recommendation_agent import find_novel_recommendation
from core.database import init_db, log_recommendation

EMAIL_SERVER = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "mcp_servers", "email_server.py")


async def run_pipeline(dry_run: bool = False) -> dict:
    """Run the full recommendation pipeline.

    Args:
        dry_run: If True, skip sending the email and writing to the DB.
                 Claude still runs (and still costs tokens); use this for
                 testing the recommendation logic without side effects.

    Returns:
        The recommendation dict produced by the Claude agent.
    """
    init_db()

    # ---- Step 1: Profile ----
    log.info("Building music taste profile...")
    profile = await build_profile(max_liked_songs=2000)
    log.info(
        f"Profile ready — {profile['liked_song_count']} liked songs, "
        f"comfort zone: {profile['comfort_zone_genres']}"
    )

    # ---- Step 2: Recommend ----
    log.info("Running recommendation agent...")
    recommendation = await find_novel_recommendation(profile)
    log.info(
        f"Recommendation: '{recommendation['track_name']}' "
        f"by {recommendation['artist']} ({recommendation['genre']})"
    )

    if dry_run:
        log.info("Dry run — skipping email and database write.")
        return recommendation

    # ---- Step 3: Send email ----
    log.info("Sending email via MCP email server...")
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", EMAIL_SERVER],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=30)
            result = await session.call_tool(
                "send_recommendation_email",
                {
                    "song_name": recommendation["track_name"],
                    "artist": recommendation["artist"],
                    "spotify_url": recommendation["spotify_url"],
                    "explanation": recommendation["explanation"],
                    "genre": recommendation["genre"],
                },
            )
            log.info(result.content[0].text if result.content else "Email sent.")

    # ---- Step 4: Log to DB ----
    log_recommendation(
        track_id=recommendation["track_id"],
        track_name=recommendation["track_name"],
        artist=recommendation["artist"],
        spotify_url=recommendation["spotify_url"],
        genre=recommendation.get("genre", "unknown"),
        explanation=recommendation["explanation"],
    )
    log.info("Recommendation logged to history database.")

    return recommendation
