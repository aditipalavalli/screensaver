import os
from flask import Flask, session, request, redirect, render_template, url_for
from flask_session import Session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from urllib.request import urlopen
from urllib.error import HTTPError
from PIL import Image
import io

# Initialize Flask app
app = Flask(__name__, static_folder="static", template_folder="templates")

# Configure app settings
app.config['SECRET_KEY'] = os.urandom(64)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'
Session(app)

# Set up Spotify API credentials
SPOTIPY_CLIENT_ID = 'INSERT CLIENT ID'
SPOTIPY_CLIENT_SECRET = 'INSERT CLIENT SECRET'
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:5000/callback'
SCOPE = 'user-read-currently-playing user-modify-playback-state user-read-playback-state'

# Helper function to get Spotify client
def get_spotify_client():
    token_info = session.get('token_info', None)
    if not token_info:
        app.logger.debug("No token info in session")
        return None
    auth_manager = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        cache_handler=spotipy.cache_handler.FlaskSessionCacheHandler(session)
    )
    if auth_manager.is_token_expired(token_info):
        app.logger.debug("Token is expired, attempting refresh")
        token_info = auth_manager.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info
    return spotipy.Spotify(auth=token_info['access_token'])

# Route for home page
@app.route('/')
def index():
    app.logger.debug("Index route accessed")
    spotify = get_spotify_client()
    if not spotify:
        app.logger.debug("No Spotify client, redirecting to login")
        return redirect('/login')
    try:
        user_info = spotify.me()
        app.logger.debug(f"User info retrieved: {user_info}")
        return render_template('home.html', name=user_info['display_name'])
    except Exception as e:
        app.logger.error(f"Error in index: {str(e)}")
        session.clear()  # Clear the session if there's an error
        return redirect('/login')

# Route for login
@app.route('/login')
def login():
    app.logger.debug("Login route accessed")
    auth_manager = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET, redirect_uri=SPOTIPY_REDIRECT_URI, scope=SCOPE)
    auth_url = auth_manager.get_authorize_url()
    app.logger.debug(f"Generated auth_url: {auth_url}")
    print(f"Auth URL: {auth_url}") 
    return render_template('signin.html', auth_url=auth_url)

# Route for Spotify callback
@app.route('/callback')
def callback():
    app.logger.debug("Callback route accessed")
    auth_manager = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET, redirect_uri=SPOTIPY_REDIRECT_URI, scope=SCOPE)
    code = request.args.get("code")
    app.logger.debug(f"Received code: {code}")
    try:
        token_info = auth_manager.get_access_token(code)
        app.logger.debug(f"Token info received: {token_info}")
        session['token_info'] = token_info
        return redirect('/')
    except Exception as e:
        app.logger.error(f"Error in callback: {str(e)}")
        return redirect('/login')


# Route for sign out
@app.route('/signout')
def signout():
    session.clear()
    return redirect('/')

# Route for image upload
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        url = request.form.get('url')
        size = request.form.get('size', 'small')
        
        try:
            # Attempt to open and validate the image
            with urlopen(url) as response:
                image = Image.open(io.BytesIO(response.read()))
                image.verify()  # Verify that it's a valid image
            
            # Store image URL and size preference in session
            session['image_url'] = url
            session['size'] = size
            
            return redirect('/custom')
        except (HTTPError, IOError):
            return render_template('upload.html', error="Invalid image URL. Please try again.")
    
    return render_template('upload.html')

# Route for custom player page
@app.route('/custom')
def custom():
    spotify = get_spotify_client()
    if not spotify:
        return redirect('/login')
    
    # Get current track info
    current_track = spotify.current_user_playing_track()
    if current_track is None:
        track_info = {"name": "No track playing", "artist": ""}
        image_url = url_for('static', filename='default.jpeg')
    else:
        track_info = {
            "name": current_track['item']['name'],
            "artist": current_track['item']['artists'][0]['name']
        }
        image_url = current_track['item']['album']['images'][0]['url']
    
    # Determine which template to use based on user's size preference
    template = 'custom_large.html' if session.get('size') == 'large' else 'custom_small.html'
    
    return render_template(template, 
                           track=track_info, 
                           album_image=image_url, 
                           background_image=session.get('image_url'))

# Error handler for 404 errors
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error="404 - Page Not Found"), 404

if __name__ == '__main__':
    app.run(debug=True)