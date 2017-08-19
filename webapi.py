import requests
import urllib
import json
import shutil
import songfmt
from time import strftime, localtime

class WebApi:
    def __init__(self, auth):
        self.auth = auth

    def is_saved(self, trackID, try_again=True):
        params = { "ids": trackID }
        headers = { "Authorization": "Bearer " + self.auth.oauth() }
        uri = "https://api.spotify.com/v1/me/tracks/contains"
        r = requests.get(uri, params=params, headers=headers)
        if r.status_code == 401 and try_again:
            self.auth.update_token()
            return self.is_saved(trackID, False)
        elif r.status_code != 200:
            return False
        else:
            return r.json()[0]

    def save_song(self, trackID, try_again=True):
        params = { "ids": trackID }
        headers = { "Authorization": "Bearer " + self.auth.oauth() }
        uri = 'https://api.spotify.com/v1/me/tracks'
        r = requests.put(uri, params=params, headers=headers)
        if r.status_code == 401:
            if try_again:
                print("Going to try again with a new token")
                self.auth.update_token()
                self.save_song(trackID, False)
            else:
                print("Failed to save; not trying again. Try reauthorisation")
        elif r.status_code != 200:
            print("Failed with code %d:" % r.status_code)
            print(r.json())

    def cache_library(self, destination):
        all_songs = self.fetch_library(True)
        if destination != None:
            with open(destination, 'w') as f:
                json.dump(all_songs, f, indent=4, sort_keys=True)
            print("Wrote to %s" % destination)
        else:
            print(json.dumps(all_songs, indent=4, sort_keys=True))

    def fetch_library(self, log=False, break_early=False):
        headers = { "Authorization": "Bearer " + self.auth.oauth() }
        params = { "offset": 0, "limit": 50 }
        import urllib
        uri = 'https://api.spotify.com/v1/me/tracks?' + urllib.parse.urlencode(params)
        all_songs = []
        while uri != None:
            if log:
                print("Request %s" % uri)
            r = requests.get(uri, headers=headers)
            if r.status_code == 200:
                j = r.json()
                all_songs.extend(j['items'])
                if 'next' in j and j['next'] != None:
                    uri = j['next']
                    params = None
                else:
                    uri = None
            elif r.status_code == 401:
                if log:
                    print("Refreshing token")
                self.auth.update_token()
                headers = { "Authorization": "Bearer " + self.auth.oauth() }
            elif r.status_code == 429:
                if 'Retry-After' in r.headers:
                    if log:
                        print("Sleep for " + str(r.headers['Retry-After']))
                    sleep(int(r.headers['Retry-After']))
            if break_early:
                break
        return all_songs

    def fetch_cached_library(self, library_src):
        with open(library_src, "r") as f:
            return json.load(f)

    def get_user_id(self):
        headers = { "Authorization" : "Bearer " + self.auth.oauth() }
        uri = 'https://api.spotify.com/v1/me'
        j = requests.get(uri, headers=headers).json()
        return j['id']

    def create_playlist(self, title, ids, public=False):
        user_id = self.get_user_id()
        headers = { "Authorization": "Bearer " + self.auth.oauth() }
        uri = 'https://api.spotify.com/v1/users/%s/playlists' % user_id
        playlist_res = requests.post(uri, headers=headers, json = {"name":title,"public":public}).json()
        playlist_id = playlist_res['id']
        print("Created playlist %s with id %s" % (title, playlist_id))
        for ids_chunk in [ids[i:i + 100] for i in range(0, len(ids), 100)]:
            uri = 'https://api.spotify.com/v1/users/%s/playlists/%s/tracks' % (user_id, playlist_id)
            print(requests.post(uri, headers=headers, json={"uris":ids_chunk}).json())
        print("Added all songs")

    def create_singles_playlist(self, limit=1, title="Single Songs", library_src = None, dry_run=False):
        all_songs = self.fetch_cached_library(library_src) if library_src != None else self.fetch_library(True, library_src)
        album_to_songs = {}
        song_id_to_song = {}
        for song in all_songs:
            song_id = song['track']['id']
            song_id_to_song[song_id] = song
            album_id = song['track']['album']['id']

            if album_id not in album_to_songs:
                album_to_songs[album_id] = set()
            album_to_songs[album_id].add(song_id)

        single_songs = []
        playlist_songs = []

        for album_id in album_to_songs:
            if len(album_to_songs[album_id]) <= limit:
                for song_id in album_to_songs[album_id]:
                    single_songs.append("spotify:track:" + song_id)
                    playlist_songs.append(song_id_to_song[song_id])

        title = title + " " + strftime("%Y-%m-%d", localtime())
        width = shutil.get_terminal_size().columns
        if dry_run:
            print(title)
            for song in playlist_songs:
                print(songfmt.format_song(songfmt.simple_song_obj(song), width, include_time=False, include_pos=False))
        else:
            self.create_playlist(title, single_songs)
