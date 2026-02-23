import spotipy
from spotipy.oauth2 import SpotifyOAuth
import sys
import os
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI

# user-library-read: access liked songs (new scope vs old project)
# user-top-read: access top artists and tracks
SCOPES = "user-library-read user-top-read"

# Use absolute path for cache so it works in subprocesses with different working directories
CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache-spotipy")


def ensure_spotify_auth() -> None:
    """Ensure Spotify authentication is available (call this from CLI before pipeline)."""
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPES,
        cache_path=CACHE_PATH,
        open_browser=False,
        show_dialog=True,
    )

    # Check if cached token exists and is valid
    cached_token = auth_manager.cache_handler.get_cached_token()
    if cached_token and auth_manager.validate_token(cached_token):
        return  # Token is valid, no need to re-authenticate

    # No valid cached token, need to authenticate
    auth_url = auth_manager.get_authorize_url()

    # Open browser automatically
    webbrowser.open(auth_url)
    print(f"\n✓ Browser opened to authorize the app.\n")
    print(f"If the browser didn't open, visit this URL:\n{auth_url}\n")
    print("After authorizing, you will be redirected to a URL.")
    print("Copy the 'code' parameter from that URL and paste it below.\n")

    # Get the authorization code from the user (stdin is available at CLI level)
    code = input("Enter the authorization code: ").strip()

    # Exchange the code for a token
    token_info = auth_manager.get_access_token(code)
    auth_manager.cache_handler.save_token_to_cache(token_info)
    print("\n✓ Authentication successful!\n")


def get_spotify_client() -> spotipy.Spotify:
    """Get Spotify client (assumes token is already cached via ensure_spotify_auth)."""
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPES,
        cache_path=CACHE_PATH,
        open_browser=False,
        show_dialog=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager)
