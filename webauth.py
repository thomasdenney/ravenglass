import requests, requests.auth
from os.path import expanduser, join
from flask import Flask, abort, request

REDIRECT_URI = "http://localhost:3000/callback"

class WebAuth:

    def __init__(self, config, config_dir):
        self.config = config
        self.config_dir = config_dir

    def client_id(self):
        return self.config['WEB_API']['CLIENT_ID']

    def client_secret(self):
        return self.config['WEB_API']['CLIENT_SECRET']

    def serve(self):
        self.app.run(port=3000)

    def get_token(self, code):
        client_auth = requests.auth.HTTPBasicAuth(self.client_id(), self.client_secret())
        post_data = {
                        "code": code,
                        "redirect_uri": REDIRECT_URI,
                        "grant_type": "authorization_code"
                    }
        try:
            response = requests.post("https://accounts.spotify.com/api/token", auth=client_auth, data=post_data)
            token_json = response.json()
            return token_json["access_token"], token_json["refresh_token"]
        except:
            return None

    def token_file_name(self):
        return join(self.config_dir, 'usertoken.txt')

    def update_token(self):
        refresh_token = self.get_refresh_token()
        token = self.get_new_token(refresh_token)
        if token != None:
            f = open(self.token_file_name(), "w")
            f.write(token + '\n')
            f.write(refresh_token)
            f.close()
            return token
        return None

    def get_refresh_token(self):
        return  open(self.token_file_name(), 'r').read().split('\n')[1].strip()

    def oauth(self):
        return open(self.token_file_name(), 'r').read().split('\n')[0].strip()

    def get_new_token(self, refresh_token):
        try:
            client_auth = requests.auth.HTTPBasicAuth(self.client_id(), self.client_secret())
            post_data = {
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_token
                        }
            resp = requests.post("https://accounts.spotify.com/api/token", auth=client_auth, data=post_data)
            token_json = resp.json()
            return token_json["access_token"]
        except:
            return None

    def serve(self):
        from flask import Flask, abort, request
        app = Flask(__name__)

        @app.route('/')
        def homepage():
            return '<a href="{}">Authenticate with Spotify</a>'.format(auth_url())

        def auth_url():
            from uuid import uuid4
            state = str(uuid4())
            # TODO: Store |state| somewhere
            params = {
                        "client_id": self.client_id(),
                        "response_type": "code",
                        "scope": "user-library-modify user-library-read playlist-modify-private playlist-modify-public user-read-email user-read-private user-read-birthdate",
                        "redirect_uri": REDIRECT_URI,
                        "state": state
                     }
            import urllib
            return 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode(params)

        @app.route('/callback')
        def callback():
            error = request.args.get('error', '')
            if error:
                return "Error: " + error
            state = request.args.get('state', '')
            # TODO: Verify the state, if not abort
            code = request.args.get('code')
            f = open(self.token_file_name(), "w")
            token, refresh_token = self.get_token(code)
            f.write(token + '\n')
            f.write(refresh_token)
            f.close()
            return "Thanks! Rerun Ravenglass to interact with the Spotify API"

        print("Open a browser at http://localhost:3000 and follow the instructions")
        app.run(port=3000)
