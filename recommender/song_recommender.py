import spotipy
import os
from spotipy.oauth2 import SpotifyOAuth
from math import sqrt
from .email_service import send_email
from django.conf import settings

DESIRED_AUDIO_FEATURES = ['danceability', 'energy', 'loudness', 'speechiness', 'acousticness', 'instrumentalness', 'liveness',
                          'valence', 'tempo']
#Max - 50
SONGS_PER_GENRE = 50
#Max - 50
TOP_TRACKS_TO_CONSIDER_COUNT = 50
#Options - short_term, medium_term, long_term
TIME_RANGE = 'long_term'
#Max - 50
TOP_ARTISTS_TO_CONSIDER_COUNT = 50
POPULARITY_THRESHOLD = 60

def chunks(lst, n):
    this_list = []
    final_list = []
    for i in range(0, len(lst), n):
        this_list = lst[i : i + n]
        final_list.append(this_list)
    return final_list

def square_rooted(x):
    return round(sqrt(sum([a*a for a in x])),3)

def cosine_similarity(x,y):
    
    input1 = x
    input2 = y
    vector1 = list(input1.values())
    vector2 = list(input2.values())
   
    numerator = sum(a*b for a,b in zip(vector2,vector1))
    denominator = square_rooted(vector1)*square_rooted(vector2)
    return round(numerator/float(denominator),3)

def dictionary_average(dict_list):
    dict_avg = {}
    for key in DESIRED_AUDIO_FEATURES:
        dict_avg[key] = float(sum(d[key] for d in dict_list)) / len(dict_list)
    return dict_avg

def get_eligible_songs(user_top_genres, sp, song_id_list):
    eligible_songs = []
    for idx, item in enumerate(user_top_genres):
        query = "genre:"+ "\"" + item + "\"" 
        genre_search_result = sp.search(q=query, limit = SONGS_PER_GENRE, type = "track")
        for idx, item in enumerate(genre_search_result['tracks']['items']):
            # Only selecting songs that are below (or equal to) the popularity threshold
            # And discarding songs from the search space that are already present in user's top tracks
            if item['popularity'] <= POPULARITY_THRESHOLD and item['id'] not in song_id_list:
                song_dict = {}
                song_dict['id'] = item['id']
                song_dict['name'] = item['name']
                song_dict['spotify_url'] = item['external_urls']['spotify']
                song_dict['artist'] = item['album']['artists'][0]['name']
                eligible_songs.append(song_dict)

    return eligible_songs

def extract_song_ids(tracks_list):
    song_id_list = []
    for idx, item in enumerate(tracks_list['items']):
        song_id_list.append(item['id'])
    return song_id_list

def get_spotify_client():
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=settings.SPOTIFY_CLIENT_ID,
                                                            client_secret=settings.SPOTIFY_CLIENT_SECRET,
                                                            redirect_uri='http://localhost:8888/callback',
                                                            cache_path='.cache-aakash',
                                                            username=settings.SPOTIFY_USERNAME,
                                                            scope="user-top-read"))
                                                            
    return sp                                                       


def main():
    sp = get_spotify_client()
    # Getting user's top tracks and audio features based on those tracks
    user_top_tracks = sp.current_user_top_tracks(limit=TOP_TRACKS_TO_CONSIDER_COUNT, time_range=TIME_RANGE)
    user_top_tracks_ids = extract_song_ids(user_top_tracks)
    user_avg_audio_features = dictionary_average(sp.audio_features(tracks = user_top_tracks_ids))
    
    # Getting user's top artists to get a list of genres that the user prefers
    user_top_artists = sp.current_user_top_artists(limit=TOP_ARTISTS_TO_CONSIDER_COUNT, time_range=TIME_RANGE)
    user_top_genres = set()
    for idx, artist in enumerate(user_top_artists['items']):
        this_artist_genres = artist['genres']
        user_top_genres.update(this_artist_genres)

    """
    Now that we have user's audio features and user's top genres (genres that user's top artists play)
    we will search for songs that belong to that genre and then extract the audio features of those songs.
    We will then recommend songs from this list that have a high audio features similarity with user's preferred audio features
    """     

    # Creating a search space of eligible songs based on user's preferred genres
    eligible_songs = get_eligible_songs(user_top_genres, sp, user_top_tracks_ids)
    eligible_songs_ids = []
    for idx, item in enumerate(eligible_songs):
        eligible_songs_ids.append(item['id'])
    
    print("\nTotal search space: ", len(eligible_songs_ids))

    # Extracting audio features from this search space
    
    # Max - 100 tracks can be passed at once
    # So creating chunks from the parent list and passing iteratively

    eligible_song_ids_chunks = chunks(eligible_songs_ids, 100)
    for user_top_tracks_ids in eligible_song_ids_chunks:
        search_space_audio_features = sp.audio_features(tracks = user_top_tracks_ids)    
    # Filtering search space to have only desired audio features
    filtered_search_space = []
    for idx, item in enumerate(search_space_audio_features):
        filtered_dict = { key: item[key] for key in DESIRED_AUDIO_FEATURES }
        filtered_search_space.append(filtered_dict)
    
    max_similarity = -1
    max_song_index = -1
    for idx, search_space_dict in enumerate(filtered_search_space):
        score = cosine_similarity(search_space_dict, user_avg_audio_features)
        if score > max_similarity:
            max_similarity = score
            max_song_index = idx
    for idx, item in enumerate(eligible_songs):
        if item['id'] == eligible_songs_ids[max_song_index]:
            message = 'Recommended song: {song_name}\nLink: {song_link}'.format(song_name=item['name'], song_link=item['spotify_url'])
            send_email(message)
            break

if __name__ == "__main__":
    main()
