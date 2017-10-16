#!/usr/bin/env python3

REDIRECT_URI = "http://localhost:3000/callback"

import requests, requests.auth, json, sys, shutil, subprocess, time
import tty, termios
import argparse
from threading import Thread
from string import ascii_lowercase
from random import choice
from os.path import expanduser, join
from time import strftime, gmtime, localtime, sleep
from math import floor
import interapp, songfmt, webauth, webapi

parser = argparse.ArgumentParser(prog="Ravenglass", description="Spotify CLI")
parser.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output")
parser.add_argument("-c", "--config_dir", default=expanduser("~/.config/ravenglass"), help="Configuration directory")

subparsers = parser.add_subparsers(help="Commands", dest="command")

what_parser = subparsers.add_parser('what', help="Get current song")
what_parser.add_argument("-j", "--json", default=False, action="store_true", help="Output as JSON")

serve_parser = subparsers.add_parser('serve', help="Run web server for personal token")
watch_parser = subparsers.add_parser('watch', help="Interactive mode")

cache_parser = subparsers.add_parser("cache", help="Cache library as JSON")
cache_parser.add_argument("--out", help="Destination file")

playlist_parser = subparsers.add_parser("playlist", help="Create playlist")
playlist_parser.add_argument("--title", help="Playlist title")
playlist_parser.add_argument("--file", help="Filename for list of IDs")

singles_parser = subparsers.add_parser("singles", help="Create playlist of single saved songs")
singles_parser.add_argument("--title", default="Single Songs", help="Playlist title (date is appended)")
singles_parser.add_argument("--limit", default=1, type=int, help="Max saved songs per album")
singles_parser.add_argument("--library", help="Use a cached library instead")
singles_parser.add_argument("--dry", action="store_true", help="Prints song IDs and titles rather than creating the playlist")

save_parser = subparsers.add_parser("save", help="Save the current song")

args = parser.parse_args()

from configparser import ConfigParser

config = ConfigParser()
config.read(join(args.config_dir, "config.ini"))
CLIENT_ID = config['WEB_API']['CLIENT_ID']
CLIENT_SECRET = config['WEB_API']['CLIENT_SECRET']
web_auth = webauth.WebAuth(config, args.config_dir)
api = webapi.WebApi(web_auth)

current_is_saved = False

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

def print_current(current, include_time=True, start_time=localtime(), saved=False, include_newline=False, include_pos=True):
    width = shutil.get_terminal_size().columns
    sys.stdout.write("\r" + songfmt.format_song(current, width, include_time, start_time, saved, include_pos))
    if include_newline:
        sys.stdout.write("\n")
    sys.stdout.flush()

watching = True
known_saved = set()

def configure_terminal_for_single_char_input():
    fd = sys.stdin.fileno()
    global old_terminal_settings
    old_terminal_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
    except:
        restore_terminal_settings()

def watch():
    global current
    global current_is_saved
    t = localtime()
    current_is_saved = api.is_saved(current["id"])
    if current_is_saved:
        known_saved.add(current["id"])
    print_current(current, start_time = t, saved=current_is_saved)
    while watching:
        new_current = interapp.get_current()
        if current != None and new_current != None:
            if current["id"] != new_current["id"]:
                # Print the previous song after it has finished playing
                print_current(current, start_time=t, saved=current["id"] in known_saved, include_pos=False)
                sys.stdout.write("\n")
                t = localtime()
                current_is_saved = api.is_saved(new_current["id"])
                if current_is_saved:
                    known_saved.add(new_current["id"])
                else:
                    known_saved.discard(new_current["id"])

            current = new_current
            print_current(current, start_time=t, saved= current["id"] in known_saved)
            sleep(1 - (current['position'] - floor(current['position'])))
        else:
            sleep(60) # Wait a minute; Spotify may not be open

def restore_terminal_settings():
    fd = sys.stdin.fileno()
    termios.tcsetattr(fd, termios.TCSADRAIN, old_terminal_settings)
    sys.stdout.flush()

current = interapp.get_current()

if __name__ == "__main__":
    if args.command == "serve":
        web_auth.serve()
    elif args.command == "what":
        current = interapp.get_current()
        if args.json:
            print(json.dumps(current, indent=2, sort_keys=True, separators=(',',': ')))
        else:
            print_current(current, include_newline=True)
    elif args.command == "watch":
        configure_terminal_for_single_char_input()
        t = Thread(target=watch)
        t.start()
        while True:
            ch = sys.stdin.read(1)
            if ch == 'x' or ch == 'q':
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                watching = False
                break
            elif ch == ' ':
                interapp.toggle_play_pause()
            elif ch == 'n':
                interapp.play_next()
            elif ch == 'p':
                interapp.play_previous()
            elif ch == 's':
                id_to_save = interapp.get_current()["id"]
                api.save_song(id_to_save)
                known_saved.add(id_to_save)
        restore_terminal_settings()
    elif args.command == "cache":
        api.cache_library(args.out)
    elif args.command == "playlist":
        title = args.title
        with open(args.file, "r") as f:
            ids = f.readlines()
        ids = ["spotify:track:" + x.strip() for x in ids]
        api.create_playlist(title, ids)
    elif args.command == "singles":
        api.create_singles_playlist(args.limit, args.title, args.library, args.dry)
    elif args.command == "save":
        current = interapp.get_current()
        print_current(current)
        api.save_song(current['id'])
    else:
        parser.print_help()
