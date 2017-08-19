from time import strftime, localtime

def fixed_length(s, n):
    if len(s) >= n:
        return s[:n - 4] + "... "
    return s.ljust(n)

def format_title(song):
    title = song['name']
    title = title.replace("Beneath Your Beautiful", "Beneath You're Beautiful")
    if "Christina Perri" in song['artist']:
        title = title.title() # Converts to title case
        title = title.replace("(Feat", "(feat") # Looks weird otherwise
    return title

def duration_string(duration):
    duration = int(duration) # for rounding
    return "{:2}:{:02}".format(duration // 60, duration % 60)

def simple_song_obj(track):
    return {
            "id": track["track"]["id"],
            "uri": track["track"]["uri"],
            "name": track["track"]["name"],
            "duration": float(track["track"]["duration_ms"]) / 1000.0,
            "artist": track["track"]["artists"][0]["name"],
            "album": track["track"]["album"]["name"]
            }



def format_song(song, width, include_time=True, start_time=localtime(), saved=False, include_pos=True):
    title_width = width // 3
    artist_width = width // 3

    savedString = u"\u2605 " if saved else "  "

    title = fixed_length(format_title(song), title_width)
    artist = fixed_length(song['artist'], artist_width)

    duration = duration_string(song['duration']) + " "

    time_str = ""
    if include_pos:
        time_str = duration_string(song['position']) + " "
    if include_time:
        time_str += "[{}] ".format(strftime("%H:%M", start_time))
    else:
        time_str += " "
    up_to_album = savedString + time_str + duration + title + artist
    album = fixed_length(song['album'], width - 1 - len(up_to_album))

    return up_to_album + album
