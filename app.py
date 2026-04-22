import os
import json
import traceback
import redis as pyredis
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'v10-mega-final')

# --- DIAGNOSTIC REDIS CONNECTION ---
redis_client = None
last_error = "None"

prefixes = ['', 'gmail_gss_', 'gmail_gsss_']
url_vars = ['REDIS_URL', 'KV_REST_API_URL']

found_url = None
for p in prefixes:
    for v in url_vars:
        if os.environ.get(p + v):
            found_url = os.environ.get(p + v)
            break
    if found_url: break

if found_url:
    try:
        # Try SSL first
        ssl_url = found_url.replace('redis://', 'rediss://', 1) if found_url.startswith('redis://') else found_url
        redis_client = pyredis.from_url(ssl_url, decode_responses=True, socket_timeout=3, ssl_cert_reqs=None)
        redis_client.ping()
        last_error = "CONNECTED_VIA_SSL"
    except Exception as e1:
        try:
            # Fallback to non-SSL
            standard_url = found_url.replace('rediss://', 'redis://', 1) if found_url.startswith('rediss://') else found_url
            redis_client = pyredis.from_url(standard_url, decode_responses=True, socket_timeout=3)
            redis_client.ping()
            last_error = "CONNECTED_VIA_STANDARD"
        except Exception as e2:
            last_error = f"SSL_ERR: {str(e1)[:50]} | STD_ERR: {str(e2)[:50]}"
            redis_client = None
else:
    last_error = "NO_URL_FOUND"

@app.route('/')
def index():
    return redirect(url_for('dashboard')) if 'logged_in' in session else render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    if request.form.get('username') == os.environ.get('ADMIN_USER', 'admin') and \
       request.form.get('password') == os.environ.get('ADMIN_PASS', 'admin123'):
        session['logged_in'] = True
        return redirect(url_for('dashboard'))
    return render_template('login.html', error='Invalid credentials')

@app.route('/authorize')
def authorize():
    try:
        redirect_uri = url_for('callback', _external=True)
        if 'localhost' not in redirect_uri: redirect_uri = redirect_uri.replace('http://', 'https://')
        flow = Flow.from_client_config({
            "web": {
                "client_id": os.environ.get('GOOGLE_CLIENT_ID', '').strip(),
                "project_id": os.environ.get('GOOGLE_PROJECT_ID', ''),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET', '').strip(),
                "redirect_uris": [os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/callback')]
            }
        }, scopes=['https://www.googleapis.com/auth/gmail.readonly'], redirect_uri=redirect_uri)
        auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
        session['code_verifier'] = flow.code_verifier
        return redirect(auth_url)
    except Exception as e:
        return f"<h1>Auth Error</h1><pre>{traceback.format_exc()}</pre>"

@app.route('/callback')
def callback():
    try:
        redirect_uri = url_for('callback', _external=True)
        if 'localhost' not in redirect_uri: redirect_uri = redirect_uri.replace('http://', 'https://')
        flow = Flow.from_client_config({
            "web": {
                "client_id": os.environ.get('GOOGLE_CLIENT_ID', '').strip(),
                "project_id": os.environ.get('GOOGLE_PROJECT_ID', ''),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET', '').strip(),
                "redirect_uris": [os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/callback')]
            }
        }, scopes=['https://www.googleapis.com/auth/gmail.readonly'], redirect_uri=redirect_uri)
        flow.code_verifier = session.get('code_verifier')
        authorization_response = request.url
        if 'localhost' not in authorization_response: authorization_response = authorization_response.replace('http://', 'https://')
        flow.fetch_token(authorization_response=authorization_response)
        service = build('gmail', 'v1', credentials=flow.credentials)
        email = service.users().getProfile(userId='me').execute().get('emailAddress')
        if redis_client:
            redis_client.hset("connected_accounts", email, flow.credentials.to_json())
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"<h1>Callback Error</h1><pre>{traceback.format_exc()}</pre>"

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html') if 'logged_in' in session else redirect(url_for('index'))

@app.route('/api/scan')
def api_scan():
    results = []
    if redis_client:
        try:
            accounts = redis_client.hgetall("connected_accounts")
            for email, data in accounts.items():
                results.append({"email": email, "status": "online", "emails": []})
        except: pass
    return jsonify({
        "db_status": "connected" if redis_client else "disconnected",
        "db_error": last_error,
        "results": results
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
