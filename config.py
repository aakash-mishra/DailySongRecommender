import os
from dotenv import load_dotenv

load_dotenv()

# Spotify
SPOTIFY_CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

# Anthropic
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# Email
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
SUBSCRIBER_LIST = os.environ["SUBSCRIBER_LIST"]

# App
DB_PATH = os.getenv("DB_PATH", "./history.db")
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "9"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))

if __name__ == "__main__":
    # print("Config loaded successfully.")
    print(f"  Spotify client ID: {SPOTIFY_CLIENT_ID[:8]}...")
    print(f"  Anthropic API key: {ANTHROPIC_API_KEY[:8]}...")
    print(f"  Sender email: {SENDER_EMAIL}")
    print(f"  Schedule: {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} daily")
