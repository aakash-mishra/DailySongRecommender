import spotipy
from spotipy.oauth2 import SpotifyOAuth
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI

# user-library-read: access liked songs (new scope vs old project)
# user-top-read: access top artists and tracks
SCOPES = "user-library-read user-top-read"


def get_spotify_client() -> spotipy.Spotify:
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPES,
        cache_path=".cache-spotipy",
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth_manager)
