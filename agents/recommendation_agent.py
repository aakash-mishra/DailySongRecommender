"""
Recommendation Agent

Claude-powered agent that finds one novel, risky-but-rewarding song
recommendation tailored to the user's specific taste profile.

Uses the Claude Agent SDK, which spawns the local `claude` CLI and
authenticates against the user's Pro / Max subscription (no API key).
The SDK runs the tool-use loop internally — we just configure the MCP
server, pass the prompt, and read the final assistant message.
"""
import asyncio
import json
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

log = logging.getLogger(__name__)

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)
from core.database import was_recommended

SPOTIFY_SERVER = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "mcp_servers", "spotify_server.py")

MODEL = "claude-sonnet-4-6"
MAX_TURNS = 10
MAX_DEDUP_RETRIES = 3

# Tools the agent is allowed to call. The SDK exposes MCP tools to Claude as
# `mcp__<server-name>__<tool-name>`; the server name below ("spotify") must
# match the key in ClaudeAgentOptions.mcp_servers.
ALLOWED_TOOLS = [
    "mcp__spotify__get_liked_songs",
    "mcp__spotify__get_top_artists",
    "mcp__spotify__get_artists",
    "mcp__spotify__search_tracks",
    "mcp__spotify__get_recommendations",
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a music recommendation agent. Your mission is to recommend ONE song that is
a great fit for this user based on their taste — balancing songs that expand on what
they already love with occasional ventures into adjacent musical territory.

STRATEGY:
1. Study the user's profile:
   - comfort_zone_genres = genres they listen to most
   - avg_audio_features = their typical sound signature
   - top_artists = artists they already know well

2. Identify 3–5 recommendation angles. Prioritize a mix of:
   - CORE recommendations: Songs within their comfort zone (rock, blues, jazz, indie)
     that match their audio signature
   - ADJACENT recommendations: Styles that blend their known genres or sit at the
     intersection (e.g., blues-rock, indie-rock, jazz fusion, alt-country)
   - EXPLORATION recommendations: Related genres they might enjoy (e.g., if they like
     rock, try folk-rock or psychedelic rock; if they like blues, try soul or R&B).

   Key genres to consider for this user:
   - Rock and its adjacent styles: rock, indie-rock, alternative, punk, post-rock
   - Blues and blues-adjacent: blues, soul, r-b, roots, country-blues
   - Jazz and jazz-adjacent: jazz, jazz-fusion, acid-jazz, smooth-jazz, bebop

   CRITICAL: Use ONLY valid Spotify genre slugs with hyphens, lowercase, no spaces.
   Examples: 'psychedelic-rock' ✓, 'blues-rock' ✓
   WRONG: 'Indie Rock' ✗, 'indie rock' ✗, 'psychedelic rock' ✗

3. Call get_recommendations with multiple diverse genre seeds. ALWAYS provide at least
   one seed (genres, artists, or tracks). Mix genres from the identified angles to create
   interesting combinations that bridge their existing taste. You may optionally adjust
   target_energy / target_valence to find songs with similar feel to what they enjoy.

   IMPORTANT: Never call get_recommendations without explicit seeds. Always select specific
   genres from the profile or your identified angles.

4. From the results, filter out:
   - Any track_id present in the EXCLUDED_IDS list (liked songs + past recs)

5. Pick the single best candidate and return a JSON object with these exact keys:
   {
     "track_id":    "...",
     "track_name":  "...",
     "artist":      "...",
     "spotify_url": "...",
     "genre":       "...",   ← the genre or blend you used as a seed
     "explanation": "..."    ← 2–3 sentences on WHY this is a good pick
                                for THIS specific user (reference their taste)
   }

Aim for songs that feel natural and rewarding — either because they belong in their
comfort zone but are new to them, or because they offer a satisfying musical bridge
to something adjacent they might already appreciate.
"""

REQUIRED_KEYS = {"track_id", "track_name", "artist",
                 "spotify_url", "genre", "explanation"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_user_prompt(profile: dict) -> str:
    """Render the initial user message from the taste profile."""
    excluded_ids = profile["liked_song_ids"][:500]
    return f"""\
Here is the user's music taste profile:

COMFORT ZONE GENRES (most frequent, use these along with some risky, non-comfort zone genres as seed):
{profile["comfort_zone_genres"]}

TOP GENRES ranked by frequency:
{profile["top_genres"][:15]}

GENRE DISTRIBUTION (top 30):
{json.dumps(profile["genre_distribution"], indent=2)}

AVERAGE AUDIO FEATURES (their typical sound signature):
{json.dumps(profile["avg_audio_features"], indent=2)}

TOP ARTISTS (already well-known to this user):
{[a["name"] for a in profile["top_artists"]]}

TOTAL LIKED SONGS: {profile["liked_song_count"]}

EXCLUDED_IDS (liked songs + past recommendations — do not recommend these):
{json.dumps(excluded_ids)}

Find me one novel, risky-but-rewarding song recommendation following the
strategy in your system prompt. Return your final answer as a JSON object
with the exact keys specified."""


def _extract_json_from_text(text: str) -> dict | None:
    """Pull the first {...} JSON object out of Claude's final text reply."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse JSON: {e}. Text: {text[start:end]}")
        return None


async def _collect_final_text(client: ClaudeSDKClient) -> str:
    """Drain one response from the SDK, returning Claude's final text reply.

    Logs each turn and each tool call so a slow run shows progress.
    """
    final_text_parts: list[str] = []
    turn = 0
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            turn += 1
            for b in msg.content:
                if isinstance(b, ToolUseBlock):
                    log.info(f"  turn {turn} tool call: {b.name}({list(b.input.keys())})")
            text_in_this_turn = [
                b.text for b in msg.content
                if isinstance(b, TextBlock) and b.text
            ]
            if text_in_this_turn:
                final_text_parts = text_in_this_turn
        elif isinstance(msg, ResultMessage):
            log.info(f"Agent finished in {turn} turn(s)")
            break
    return "\n".join(final_text_parts)


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

async def find_novel_recommendation(profile: dict) -> dict:
    """Run the Claude tool-use loop to find a novel song recommendation.

    Returns a dict with keys: track_id, track_name, artist, spotify_url,
    genre, explanation.
    """
    options = ClaudeAgentOptions(
        model=MODEL,
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={
            "spotify": {
                "type": "stdio",
                "command": "uv",
                "args": ["run", "python", SPOTIFY_SERVER],
            },
        },
        allowed_tools=ALLOWED_TOOLS,
        max_turns=MAX_TURNS,
        permission_mode="bypassPermissions",
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(_build_user_prompt(profile))

        for attempt in range(MAX_DEDUP_RETRIES + 1):
            log.info(f"Awaiting recommendation (attempt {attempt + 1}/{MAX_DEDUP_RETRIES + 1})")
            text = await _collect_final_text(client)
            rec = _extract_json_from_text(text)

            if rec is None:
                log.error(f"Agent finished without valid JSON. Last text: {text!r}")
                raise RuntimeError("Agent finished but produced no valid recommendation JSON.")

            missing = REQUIRED_KEYS - set(rec.keys())
            if missing:
                log.warning(f"Incomplete recommendation; missing fields: {missing}. Got: {rec}")
                raise RuntimeError(f"Recommendation missing required fields: {missing}")

            if not was_recommended(rec["track_id"]):
                return rec

            log.info(f"Track {rec['track_id']} already in history; asking Claude to retry.")
            await client.query(
                f"Track {rec['track_id']} was already recommended previously. "
                "Please find a different one and return the same JSON shape."
            )

    raise RuntimeError(
        f"Agent could not produce a novel recommendation after {MAX_DEDUP_RETRIES + 1} attempts."
    )


if __name__ == "__main__":
    # Quick smoke-test: load a minimal fake profile and run the agent.
    # Requires the `claude` CLI to be logged in (subscription auth) and a
    # valid Spotify cache.
    from agents.profiler import build_profile

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async def smoke_test():
        profile = await build_profile(max_liked_songs=100)
        rec = await find_novel_recommendation(profile)
        print("\n--- Recommendation ---")
        print(json.dumps(rec, indent=2))

    asyncio.run(smoke_test())
