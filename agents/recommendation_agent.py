"""
Recommendation Agent

Claude-powered agent that finds one novel, risky-but-rewarding song
recommendation tailored to the user's specific taste profile.

Key concepts demonstrated here:
  1. MCP client ↔ server communication over stdio
  2. Anthropic tool-use agent loop (the core agentic pattern)
  3. Converting MCP tool schemas to Anthropic tool format
  4. Handling parallel tool calls in a single conversation turn
"""
import asyncio
import json
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

log = logging.getLogger(__name__)

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from core.database import was_recommended
from config import ANTHROPIC_API_KEY

SPOTIFY_SERVER = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "mcp_servers", "spotify_server.py")

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
     rock, try folk-rock or psychedelic rock; if they like blues, try soul or R&B)

   Key genres to consider for this user:
   - Rock and its adjacent styles: rock, indie-rock, alternative, punk, post-rock
   - Blues and blues-adjacent: blues, soul, r-b, roots, country-blues
   - Jazz and jazz-adjacent: jazz, jazz-fusion, acid-jazz, smooth-jazz, bebop
   - Indie and indie-adjacent: indie-pop, indie-rock, lo-fi, alternative, indie-folk

   CRITICAL: Use ONLY valid Spotify genre slugs with hyphens, lowercase, no spaces.
   Examples: 'indie-rock' ✓, 'psychedelic-rock' ✓, 'blues-rock' ✓
   WRONG: 'Indie Rock' ✗, 'indie rock' ✗, 'psychedelic rock' ✗
   Feel free to include some Hindi indie songs occasionally.

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mcp_tools_to_anthropic(mcp_tools) -> list[dict]:
    """Convert MCP ListToolsResult to Anthropic tools format.

    Both formats use JSON Schema, but the top-level key name differs:
      MCP:      tool.inputSchema
      Anthropic: tool["input_schema"]
    """
    result = []
    for tool in mcp_tools:
        schema = tool.inputSchema if tool.inputSchema else {
            "type": "object", "properties": {}, "required": []
        }
        result.append({
            "name": tool.name,
            "description": tool.description or f"Call {tool.name}",
            "input_schema": schema,
        })
    return result


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

async def find_novel_recommendation(profile: dict) -> dict:
    """Run the Claude tool-use loop to find a novel song recommendation.

    Returns a dict with keys: track_id, track_name, artist, spotify_url,
    genre, explanation.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", SPOTIFY_SERVER],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=30)

            # Convert MCP tools to Anthropic format
            tools_list = await session.list_tools()
            anthropic_tools = _mcp_tools_to_anthropic(tools_list.tools)

            # Build the initial prompt — include profile + IDs to exclude
            # Limit to 500 IDs to keep the context window manageable
            excluded_ids = profile["liked_song_ids"][:500]

            user_message = f"""\
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

            messages = [{"role": "user", "content": user_message}]

            # ------------------------------------------------------------------
            # Agent loop
            # Each iteration: Claude responds → we execute any tool calls →
            # we return all tool results in a single user message → repeat.
            # Loop ends when stop_reason == "end_turn".
            # ------------------------------------------------------------------
            max_iterations = 10
            for iteration in range(max_iterations):
                log.info(f"Agent iteration {iteration + 1}/{max_iterations}")

                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=anthropic_tools,
                    messages=messages,
                )

                # Append Claude's full response to conversation history
                messages.append({"role": "assistant", "content": response.content})

                # ---- Case 1: Claude is done ----
                if response.stop_reason == "end_turn":
                    for block in response.content:
                        if hasattr(block, "text") and block.text:
                            text = block.text
                            start = text.find("{")
                            end = text.rfind("}") + 1
                            if start >= 0 and end > start:
                                try:
                                    rec = json.loads(text[start:end])
                                except json.JSONDecodeError as e:
                                    log.error(f"Failed to parse JSON: {e}. Text: {text[start:end]}")
                                    continue

                                # Final dedup check against DB history
                                if was_recommended(rec.get("track_id", "")):
                                    log.info(f"Track {rec['track_id']} already in history; asking Claude to retry.")
                                    messages.append({
                                        "role": "user",
                                        "content": (
                                            f"Track {rec['track_id']} was already recommended "
                                            "previously. Please find a different one."
                                        ),
                                    })
                                    continue

                                required = {"track_id", "track_name", "artist",
                                            "spotify_url", "genre", "explanation"}
                                missing = required - set(rec.keys())
                                if missing:
                                    log.warning(f"Incomplete recommendation; missing fields: {missing}. Got: {rec}")
                                if required.issubset(rec.keys()):
                                    return rec

                    log.error(f"Agent finished without valid JSON. Claude's last response: {response.content}")
                    raise RuntimeError("Agent finished but produced no valid recommendation JSON.")

                # ---- Case 2: Claude wants to call tools ----
                elif response.stop_reason == "tool_use":
                    tool_results = []
                    tool_calls = [b for b in response.content if b.type == "tool_use"]
                    for tool_idx, block in enumerate(tool_calls):
                        log.info(f"  Tool call: {block.name}({list(block.input.keys())})")
                        try:
                            mcp_result = await session.call_tool(block.name, block.input)
                            content = (mcp_result.content[0].text
                                       if mcp_result.content else "{}")
                        except Exception as exc:
                            content = json.dumps({"error": str(exc)})

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": content,
                        })

                        # Rate limit: add 0.5s delay between Spotify API calls
                        if tool_idx < len(tool_calls) - 1:
                            await asyncio.sleep(0.5)

                    # All results for one Claude turn → one user message
                    messages.append({"role": "user", "content": tool_results})

                else:
                    raise RuntimeError(
                        f"Unexpected stop_reason: {response.stop_reason}"
                    )

    raise RuntimeError(
        f"Agent did not converge after {max_iterations} iterations."
    )


if __name__ == "__main__":
    # Quick smoke-test: load a minimal fake profile and run the agent.
    # Requires ANTHROPIC_API_KEY and a valid Spotify cache.
    import asyncio
    from agents.profiler import build_profile

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async def smoke_test():
        profile = await build_profile(max_liked_songs=100)
        rec = await find_novel_recommendation(profile)
        print("\n--- Recommendation ---")
        print(json.dumps(rec, indent=2))

    asyncio.run(smoke_test())
