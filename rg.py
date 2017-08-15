#!/usr/bin/env python3

REDIRECT_URI = "http://localhost:3000/callback"

import requests, requests.auth, json, sys, shutil, subprocess, time
import tty, termios
from threading import Thread
from string import ascii_lowercase
from random import choice
from os.path import expanduser, join
from time import strftime, gmtime, localtime, sleep
from math import floor

from Foundation import NSAppleScript
import AppKit
info = AppKit.NSBundle.mainBundle().infoDictionary()
info["LSBackgroundOnly"] = "1"

from configparser import ConfigParser

def config_dir():
    return join(expanduser("~"), ".config", "ravenglass")

config = ConfigParser()
config.read(join(config_dir(), "config.ini"))
CLIENT_ID = config['WEB_API']['CLIENT_ID']
CLIENT_SECRET = config['WEB_API']['CLIENT_SECRET']

from flask import Flask, abort, request
app = Flask(__name__)

def apple_script(script):
    try:
        s = NSAppleScript.alloc().initWithSource_(script)
        res, err = s.executeAndReturnError_(None)
        return res.stringValue()
    except:
        return None

def spotify_command(command):
    return apple_script("tell application \"Spotify\" to {}".format(command))

def toggle_play_pause():
    spotify_command("playpause")

def play_next():
    spotify_command("next track")

def play_previous():
    spotify_command("previous track")

def fast_get_id():
    return spotify_command("get the id of the current track")

def fast_get_position():
    return float(spotify_command("get the player position"))

def token_file_name():
    return join(config_dir(), 'usertoken.txt')

@app.route('/')
def homepage():
    text = '<a href="%s">Authenticate with Spotify</a>'
    return text % auth_url()

def auth_url():
    from uuid import uuid4
    state = str(uuid4())
    # TODO: Store |state| somewhere
    params = {
                "client_id": CLIENT_ID,
                "response_type": "code",
                "scope": "user-library-modify user-library-read playlist-modify-private playlist-modify-public user-read-email user-read-private user-read-birthdate",
                "redirect_uri": REDIRECT_URI,
                "state": state
             }
    import urllib
    url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode(params)
    return url

@app.route('/callback')
def callback():
    error = request.args.get('error', '')
    if error:
        return "Error: " + error
    state = request.args.get('state', '')
    # TODO: Verify the state, if not abort
    code = request.args.get('code')
    f = open(token_file_name(), "w")
    token, refresh_token = get_token(code)
    f.write(token + '\n')
    f.write(refresh_token)
    f.close()
    return "Thanks!"

def get_token(code):
    client_auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    post_data = {
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
    try:
        response = requests.post("https://accounts.spotify.com/api/token",
                auth=client_auth, data=post_data)
        token_json = response.json()
        return token_json["access_token"], token_json["refresh_token"]
    except:
        return None

def get_refresh_token():
    return  open(token_file_name(), 'r').read().split('\n')[1].strip()

def get_new_token(refresh_token):
    try:
        client_auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
        post_data = {
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    }
        resp = requests.post("https://accounts.spotify.com/api/token",
                auth=client_auth, data=post_data)
        token_json = resp.json()
        return token_json["access_token"]
    except:
        return None

# Default port that Spotify Web Helper binds to.
PORT = 4370
DEFAULT_RETURN_ON = ['login', 'logout', 'play', 'pause', 'error', 'ap']
ORIGIN_HEADER = {'Origin': 'https://open.spotify.com'}

def get_json(url, params={}, headers={}, timeout=None):
    try:
        if timeout != None:
            return requests.get(url, params=params, headers=headers, timeout=timeout).json()
        else:
            return requests.get(url, params=params, headers=headers).json()
    except:
        return None

def generate_local_hostname():
    """Generate a random hostname under the .spotilocal.com domain"""
    subdomain = ''.join(choice(ascii_lowercase) for x in range(10))
    return subdomain + '.spotilocal.com'

def get_url(url):
    return "https://%s:%d%s" % (generate_local_hostname(), PORT, url)

def get_oauth_token():
    return get_json('http://open.spotify.com/token')['t']

def get_csrf_token():
    # Requires Origin header to be set to generate the CSRF token.
    return get_json(get_url('/simplecsrf/token.json'), headers=ORIGIN_HEADER)['token']

def get_status(oauth_token, csrf_token, return_after_play=False):
    params = { 'oauth': oauth_token, 'csrf': csrf_token }
    if return_after_play:
        while True:
            try:
                params['returnon'] = ['play']
                return get_json(get_url('/remote/status.json'), params=params, headers=ORIGIN_HEADER, timeout=30)
            except: pass
    return get_json(get_url('/remote/status.json'), params=params, headers=ORIGIN_HEADER)

def pause(oauth_token, csrf_token, pause=True):
    params = { 'oauth': oauth_token, 'csrf': csrf_token, 'pause': 'true' if pause else 'false' }
    get_json(get_url('/remote/pause.json'), params=params, headers=ORIGIN_HEADER)

def next_track(oauth_token, csrf_token):
    params = { 'oauth': oauth_token, 'csrf': csrf_token }
    get_json(get_url('/remote/nextTrack'), params=params, headers=ORIGIN_HEADER)

def get_track_id(data):
    trackID = data['track']['track_resource']['uri'].split(':')[2]
    return trackID

def get_web_api_oauth():
    return open(token_file_name(), 'r').read().split('\n')[0].strip()

def is_saved(auth, trackID, try_again=True):
    params = { "ids": trackID }
    headers = { "Authorization": "Bearer " + auth }
    uri = "https://api.spotify.com/v1/me/tracks/contains"
    r = requests.get(uri, params=params, headers=headers)
    if r.status_code == 401 and try_again:
        return is_saved(update_token(), trackID, False)
    elif r.status_code != 200:
        return False
    else:
        return r.json()[0]

current_is_saved = False

def save_song(auth, trackID, try_again=True):
    global current_is_saved
    params = { "ids": trackID }
    headers = { "Authorization": "Bearer " + auth }
    uri = 'https://api.spotify.com/v1/me/tracks'
    r = requests.put(uri, params=params, headers=headers)
    if r.status_code == 401:
        if try_again:
            print("Going to try again with a new token")
            token = update_token()
            save_song(token, trackID, False)
        else:
            print("Failed to save; not trying again. Try reauthorisation")
    elif r.status_code != 200:
        print("Failed with code %d:" % r.status_code)
        print(r.json())
    else:
        if trackID == get_track_id(current):
            current_is_saved = True

def update_token():
    refresh_token = get_refresh_token()
    token = get_new_token(refresh_token)
    if token != None:
        f = open(token_file_name(), "w")
        f.write(token + '\n')
        f.write(refresh_token)
        f.close()
        return token
    return None

def fetch_library(auth, log=False, break_early=False):
    headers = { "Authorization": "Bearer " + auth }
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
            auth = update_token()
            headers = { "Authorization": "Bearer " + auth }
        elif r.status_code == 429:
            if 'Retry-After' in r.headers:
                if log:
                    print("Sleep for " + str(r.headers['Retry-After']))
                sleep(int(r.headers['Retry-After']))
        if break_early:
            break
    return all_songs

def cache_library(auth, destination):
    all_songs = fetch_library(auth, True)
    with open(destination, 'w') as f:
        json.dump(all_songs, f, indent=4, sort_keys=True)
    print("Wrote to %s" % destination)

def get_user_id(auth):
    headers = { "Authorization" : "Bearer " + auth }
    uri = 'https://api.spotify.com/v1/me'
    j = requests.get(uri, headers=headers).json()
    return j['id']

def create_playlist(auth, title, ids, public=False):
    user_id = get_user_id(auth)
    headers = { "Authorization": "Bearer " + auth }
    uri = 'https://api.spotify.com/v1/users/%s/playlists' % user_id
    playlist_res = requests.post(uri, headers=headers, json = {"name":title,"public":public}).json()
    playlist_id = playlist_res['id']
    print("Created playlist %s with id %s" % (title, playlist_id))
    for ids_chunk in [ids[i:i + 100] for i in range(0, len(ids), 100)]:
        uri = 'https://api.spotify.com/v1/users/%s/playlists/%s/tracks' % (user_id, playlist_id)
        print(requests.post(uri, headers=headers, json={"uris":ids_chunk}).json())


def duration_string(duration):
    duration = int(duration) # for rounding
    return "{:2}:{:02}".format(duration // 60, duration % 60)

def fixed_length(s, n):
    if len(s) >= n:
        return s[:n - 4] + "... "
    return s.ljust(n)

def format_title(song):
    title = song['track']['track_resource']['name']
    title = title.replace("Beneath Your Beautiful", "Beneath You're Beautiful")
    if "Christina Perri" in song['track']['artist_resource']['name']:
        title = title.title() # Converts to title case
        title = title.replace("(Feat", "(feat") # Looks weird otherwise
    return title

def print_current(current, include_time=True, start_time=localtime(), saved=False):
    width = shutil.get_terminal_size().columns
    title_width = width // 3
    artist_width = width // 3

    savedString = u"\u2605 " if saved else "  "
    title = fixed_length(format_title(current), title_width)
    artist = fixed_length(current['track']['artist_resource']['name'], artist_width)

    duration = duration_string(current['track']['length']) + " "
    pos = duration_string(current['playing_position']) + " "
    if not include_time:
        pos = " " * len(pos)

    current_time = "[{}] ".format(strftime("%H:%M", start_time))
    up_to_album = savedString + current_time + pos + duration + title + artist
    album = fixed_length(current['track']['album_resource']['name'], width - 1 - len(up_to_album))

    sys.stdout.write("\r" + up_to_album + album)
    sys.stdout.flush()

watching = True

def watch(oauth_token, csrf_token):
    global current
    global current_is_saved
    t = localtime()
    current_is_saved = is_saved(get_web_api_oauth(), get_track_id(current))
    print_current(current, start_time = t, saved=current_is_saved)
    while watching:
        try:
            playback_id = fast_get_id()
            if playback_id != None:
                if playback_id != current['track']['track_resource']['uri']:
                    print_current(current, include_time=False, start_time=t, saved=current_is_saved)
                    sys.stdout.write("\n")
                    t = localtime()
                    current = get_status(oauth_token, csrf_token)
                    current_is_saved = is_saved(get_web_api_oauth(), get_track_id(current))
                current['playing_position'] = fast_get_position()
                print_current(current, include_time=True, start_time=t, saved=current_is_saved)
                time.sleep(1 - (current['playing_position'] - floor(current['playing_position'])))
            else:
                time.sleep(10)
        except: pass

def create_singles_playlist(auth, limit=1, title="Single Songs"):
    all_songs = fetch_library(auth, True)
    album_to_songs = {}
    for song in all_songs:
        song_id = song['track']['id']
        album_id = song['track']['album']['id']

        if album_id not in album_to_songs:
            album_to_songs[album_id] = set()
        album_to_songs[album_id].add(song_id)

    single_songs = []

    for album_id in album_to_songs:
        if len(album_to_songs[album_id]) <= limit:
            for song_id in album_to_songs[album_id]:
                single_songs.append("spotify:track:" + song_id)

    title = title + " " + strftime("%Y-%m-%d", localtime())
    create_playlist(auth, title, single_songs)

def configure_terminal_for_single_char_input():
    fd = sys.stdin.fileno()
    global old_terminal_settings
    old_terminal_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
    except:
        restore_terminal_settings()

def restore_terminal_settings():
    fd = sys.stdin.fileno()
    termios.tcsetattr(fd, termios.TCSADRAIN, old_terminal_settings)
    sys.stdout.flush()

oauth_token = get_oauth_token()
csrf_token = get_csrf_token()
current = get_status(oauth_token, csrf_token)

if len(sys.argv) > 1:
    if sys.argv[1] == "serve":
        print("Open a browser at http://localhost:3000 and follow the instructions")
        app.run(port=3000)
    elif sys.argv[1] == "what":
        print_current(current)
    elif sys.argv[1] == "json":
        print(json.dumps(current, indent=2, sort_keys=True, separators=(',',': ')))
    elif sys.argv[1] == "watch":
        configure_terminal_for_single_char_input()
        t = Thread(target=watch, args=(oauth_token, csrf_token,))
        t.start()
        while True:
            ch = sys.stdin.read(1)
            if ch == 'x' or ch == 'q':
                # p.terminate()
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                watching = False
                break
            elif ch == ' ':
                toggle_play_pause()
            elif ch == 'n':
                play_next()
            elif ch == 'p':
                play_previous()
            elif ch == 's':
                save_song(get_web_api_oauth(), get_track_id(get_status(oauth_token, csrf_token)))
        restore_terminal_settings()
    elif sys.argv[1] == "cache":
        cache_library(get_web_api_oauth(), sys.argv[2])
    elif sys.argv[1] == "playlist":
        title = sys.argv[2]
        with open(sys.argv[3], "r") as f:
            ids = f.readlines()
        ids = ["spotify:track:" + x.strip() for x in ids]
        create_playlist(get_web_api_oauth(), title, ids)
    elif sys.argv[1] == "singles":
        auth = get_web_api_oauth()
        if len(sys.argv) >= 4:
            create_singles_playlist(auth, int(sys.argv[2]), sys.argv[3])
        elif len(sys.argv) >= 3:
            create_singles_playlist(auth, int(sys.argv[2]))
        else:
            create_singles_playlist(get_web_api_oauth())
else:
    track_id = get_track_id(current)
    print_current(current)
    print("Track ID = %s" % track_id)
    save_song(get_web_api_oauth(), track_id)
