# Ravenglass: A Spotify CLI

Ravenglass allows you to control the Spotify desktop player and interact with
the web API. It currently only supports Python 3 and macOS.

**This is currently in alpha...**

## Installation

Currently you need to clone this repository and install its dependencies -
installation via `pip` is not yet supported. You'll need [Flask][] and
[PyObjC][].

[Flask]: http://flask.pocoo.org
[PyObjC]: https://pythonhosted.org/pyobjc/install.html

In order to use the features that require the [Spotify Web API][api] you'll need
to register an application. When you register you'll need to add
`http://localhost:3000/callback` as a callback URL. Then write the following
file at `~/.config/ravenglass/config.ini`:

```
[WEB_API]
CLIENT_ID = your application client ID
CLIENT_SECRET = your application client secret
```

[api]: https://developer.spotify.com/web-api/

## Usage

Run `./rg.py save` to save the currently playing song. Other options include
caching data on all your songs as JSON, watch Spotify with an interactive UI,
creating playlists from lists of song IDs, and create automatic playlists from
single songs, etc. You can view all the options by running `./rg.py --help`.

## TODO

* [ ] Break up into separate files
* [ ] Rewrite server logic
* [ ] Generalise API access
