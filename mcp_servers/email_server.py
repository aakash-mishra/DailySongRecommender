"""
Email MCP Server

Exposes a single tool: send_recommendation_email.
Runs as a subprocess; communicates via stdio JSON-RPC.

IMPORTANT: never write to stdout — it is the MCP protocol channel.
"""
import sys
import os
import smtplib
import ssl
import logging
from email.message import EmailMessage

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="[email-server] %(message)s")
log = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP
from config import SENDER_EMAIL, EMAIL_PASSWORD, SUBSCRIBER_LIST

mcp = FastMCP("email")


@mcp.tool()
def send_recommendation_email(
    song_name: str,
    artist: str,
    spotify_url: str,
    explanation: str,
    genre: str,
) -> str:
    """Send the daily song recommendation via email.

    Sends an HTML email with the song details and Claude's explanation of
    why this track was chosen as a novel, risky-but-rewarding pick.

    Args:
        song_name: Name of the recommended track.
        artist: Artist name.
        spotify_url: Direct Spotify link to the track.
        explanation: Claude's reasoning for this recommendation.
        genre: The genre territory this song was sourced from.
    """
    msg = EmailMessage()

    plain = (
        f"{song_name} by {artist}\n\n"
        f"Genre territory: {genre}\n\n"
        f"{explanation}\n\n"
        f"Listen: {spotify_url}"
    )

    html = f"""<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #222;">
  <h2 style="margin-bottom: 4px;">Your Daily Song Recommendation</h2>
  <h3 style="margin-top: 0; color: #1DB954;">{song_name} <span style="color:#888;">—</span> {artist}</h3>
  <p style="font-size: 0.85em; color: #666; margin-top: 0;">
    Genre territory: <strong>{genre}</strong>
  </p>
  <p style="line-height: 1.6;">{explanation}</p>
  <a href="{spotify_url}"
     style="display: inline-block; margin-top: 16px; padding: 10px 20px;
            background: #1DB954; color: white; text-decoration: none;
            border-radius: 24px; font-weight: bold;">
    Listen on Spotify
  </a>
</body>
</html>"""

    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    msg["Subject"] = f"Daily Recommendation: {song_name} by {artist}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = SUBSCRIBER_LIST

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)
        server.send_message(msg)

    log.info(f"Email sent: {song_name} by {artist}")
    return f"Email sent successfully: '{song_name}' by {artist} → {SUBSCRIBER_LIST}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
