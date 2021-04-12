import spotipy
import os
from spotipy.oauth2 import SpotifyOAuth

DESIRED_AUDIO_FEATURES = ['danceability', 'energy', 'loudness', 'speechiness', 'acousticness', 'instrumentalness', 'liveness',
                          'valence', 'tempo']

def dictionary_average(dict_list):
    dict_avg = {}
    for key in DESIRED_AUDIO_FEATURES:
        dict_avg[key] = float(sum(d[key] for d in dict_list)) / len(dict_list)
    return dict_avg

def get_eligible_songs(user_top_genres, sp):
    eligible_songs_ids = []
    for idx, item in enumerate(user_top_genres):
        query = "genre:"+ "\"" + item + "\"" 
        genre_search_result = sp.search(q=query, limit = 2, type = "track")
        for idx, item in enumerate(genre_search_result['tracks']['items']):
            eligible_songs_ids.append(item['id'])
    return eligible_songs_ids

def extract_song_ids(tracks_list):
    song_id_list = []
    for idx, item in enumerate(tracks_list['items']):
        song_id_list.append(item['id'])
    return song_id_list

def main():   
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.environ['SPOTIFY_CLIENT_ID'],
                                                            client_secret=os.environ['SPOTIFY_CLIENT_SECRET'],
                                                            redirect_uri="http://example.com",
                                                            scope="user-top-read"))
    user_top_tracks = sp.current_user_top_tracks(limit=5, time_range='long_term')

    song_id_list = extract_song_ids(user_top_tracks)

    user_audio_features = sp.audio_features(tracks = song_id_list)
    user_avg_audio_features = dictionary_average(user_audio_features)


    user_top_artists = sp.current_user_top_artists(limit=1, time_range='long_term')
    user_top_genres = set()
    for idx, artist in enumerate(user_top_artists['items']):
        this_artist_genres = artist['genres']
        user_top_genres.update(this_artist_genres)

    print("User's average audio features rating \n\n", user_avg_audio_features)
    print("\nUser's top genres \n\n", user_top_genres)

    """
    Now that we have user's audio features and user's top genres (genres that user's top artists play)
    we will search for songs that belong to that genre and then extract the audio features of those songs.
    We will then recommend songs from this list that have a high audio features similarity with user's preferred audio features
    """     

    # Reducing search space by filtering based on user's top genres
    eligible_songs_ids = get_eligible_songs(user_top_genres, sp)
    # Extracting audio features from this search space
    search_space_audio_features = sp.audio_features(tracks = eligible_songs_ids)
    print("\n Search space audio features\n\n",search_space_audio_features)
    
    #TODO
    #Find similarity between user's preferred audio features and search space audio features
    
if __name__ == "__main__":
    main()
