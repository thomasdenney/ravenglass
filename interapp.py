from Foundation import NSAppleScript
from AppKit import NSBundle

# Ensures that an app icon doesn't show in the Dock
info = NSBundle.mainBundle().infoDictionary()
info["LSBackgroundOnly"] = "1"

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

def get_property(prop):
    return spotify_command("get the %s of the current track" % prop)

# I've done some experimentation with trying to get the whole of the 'current
# track' object from Spotify, but it seems that this isn't something that is
# actually supported by AppleScript (the language) so I've had to stick to doing
# it this way instead :(
def get_current():
    # Intentionally not all of the properties to ensure this is fast
    properties = [ "id", "name", "artist", "album", "duration" ]
    res = {}
    for prop in properties:
        res[prop] = get_property(prop)
        if res[prop] == None:
            return None
    res["uri"] = res["id"]
    res["id"] = res["uri"].split(":")[2]
    res["duration"] = float(res["duration"]) / 1000.0 # ms to s
    res["position"] = get_position()
    return res

def get_position():
    return float(spotify_command("get the player position"))
