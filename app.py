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
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'v12-final-feed-fix')

# --- DB CONNECTION (Auto-Detect Vercel/Redis Labs) ---
redis_client = None
last_error = "None"
search_vars = ['gmail_gss_REDIS_URL', 'gmail_gsss_REDIS_URL', 'REDIS_URL', 'KV_URL', 'KV_REST_API_URL']

found_url = None
for v in search_vars:
    if os.environ.get(v):
        found_url = os.environ.get(v)
        break

if found_url:
    try:
        target_url = found_url.replace('redis://', 'rediss://', 1) if 'localhost' not in found_url and found_url.startswith('redis://') else found_url
        redis_client = pyredis.from_url(target_url, decode_responses=True, socket_timeout=3, ssl_cert_reqs=None)
        redis_client.ping()
        last_error = "CONNECTED"
    except Exception as e1:
        try:
            redis_client = pyredis.from_url(found_url, decode_responses=True, socket_timeout=3)
            redis_client.ping()
            last_error = "CONNECTED_STD"
        except Exception as e2:
            last_error = f"ERR: {str(e2)[:50]}"
            redis_client = None
else:
    last_error = "NO_URL_FOUND"

def get_client_config():
    return {
        "web": {
            "client_id": os.environ.get('GOOGLE_CLIENT_ID', '').strip(),
            "project_id": os.environ.get('GOOGLE_PROJECT_ID', ''),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET', '').strip(),
            "redirect_uris": [os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/callback')]
        }
    }

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
        flow = Flow.from_client_config(get_client_config(), scopes=['https://www.googleapis.com/auth/gmail.readonly'], redirect_uri=redirect_uri)
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        session['code_verifier'] = flow.code_verifier
        return redirect(auth_url)
    except Exception as e:
        return f"<h1>Auth Error</h1><pre>{traceback.format_exc()}</pre>"

@app.route('/callback')
def callback():
    try:
        redirect_uri = url_for('callback', _external=True)
        if 'localhost' not in redirect_uri: redirect_uri = redirect_uri.replace('http://', 'https://')
        flow = Flow.from_client_config(get_client_config(), scopes=['https://www.googleapis.com/auth/gmail.readonly'], redirect_uri=redirect_uri)
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

@app.route('/api/delete', methods=['DELETE'])
def api_delete():
    email = request.args.get('email')
    if redis_client and email:
        redis_client.hdel("connected_accounts", email)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html') if 'logged_in' in session else redirect(url_for('index'))

@app.route('/api/scan')
def api_scan():
    results = []
    if redis_client:
        try:
            accounts = redis_client.hgetall("connected_accounts")
            for email, json_data in accounts.items():
                try:
                    creds = Credentials.from_json(json_data)
                    if creds.expired and creds.refresh_token: creds.refresh(Request())
                    service = build('gmail', 'v1', credentials=creds)
                    msgs = service.users().messages().list(userId='me', maxResults=6).execute().get('messages', [])
                    emails_data = []
                    for msg in msgs:
                        m = service.users().messages().get(userId='me', id=msg['id']).execute()
                        headers = m.get('payload', {}).get('headers', [])
                        emails_data.append({
                            "id": msg['id'],
                            "subject": next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject'),
                            "from": next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown'),
                            "folder": "Spam" if "SPAM" in m.get('labelIds', []) else "Inbox",
                            "timestamp": m.get('internalDate')
                        })
                    results.append({"email": email, "status": "online", "emails": emails_data})
                except: results.append({"email": email, "status": "error", "emails": []})
        except: pass
    return jsonify({"db_status": "connected" if redis_client else "disconnected", "db_error": last_error, "results": results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
