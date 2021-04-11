import spotipy
import os
from spotipy.oauth2 import SpotifyOAuth

desired_audio_features = ['danceability', 'energy', 'loudness', 'speechiness', 'acousticness', 'instrumentalness', 'liveness',
                          'valence', 'tempo']
def dictionary_average(dict_list):
    dict_avg = {}
    for key in desired_audio_features:
        dict_avg[key] = float(sum(d[key] for d in dict_list)) / len(dict_list)
    return dict_avg

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.environ['SPOTIFY_CLIENT_ID'],
                                                           client_secret=os.environ['SPOTIFY_CLIENT_SECRET'],
                                                           redirect_uri="http://example.com",
                                                           scope="user-top-read"))
results = sp.current_user_top_tracks(limit=20, time_range='long_term')

song_id_list = []
for idx, item in enumerate(results['items']):
    song_id_list.append(item['id'])

audio_features = sp.audio_features(tracks = song_id_list)
dict_avg = dictionary_average(audio_features)
print(dict_avg)
