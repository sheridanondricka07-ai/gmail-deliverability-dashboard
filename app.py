import os
import json
import traceback
import redis as pyredis
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Allow OAuth over HTTP for local development (only if on localhost)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
# Secure secret key
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'v7-ultimate-secure-key-999')

# --- Persistence Logic (Support both Upstash REST and Standard Redis) ---
redis_client = None

# 1. Try Upstash REST variables (Vercel KV)
kv_url = os.environ.get('gmail_gss_REST_API_URL') or os.environ.get('KV_REST_API_URL')
kv_token = os.environ.get('gmail_gss_REST_API_TOKEN') or os.environ.get('KV_REST_API_TOKEN')

# 2. Try Standard Redis URL (Redis Labs, etc.)
standard_redis_url = os.environ.get('gmail_gss_REDIS_URL') or os.environ.get('REDIS_URL')

if kv_url and kv_token:
    try:
        from upstash_redis import Redis
        redis_client = Redis(url=kv_url, token=kv_token)
        print("✅ Connected to Upstash Redis (REST)")
    except Exception as e:
        print(f"❌ Upstash Connection Error: {e}")

if not redis_client and standard_redis_url:
    try:
        # AUTO-FIX: Upgrade redis:// to rediss:// for secure cloud providers
        if standard_redis_url.startswith('redis://') and 'localhost' not in standard_redis_url:
            standard_redis_url = standard_redis_url.replace('redis://', 'rediss://', 1)
            print("💡 Auto-upgraded Redis URL to secure (rediss://)")
        
        is_ssl = standard_redis_url.startswith('rediss://')
        redis_client = pyredis.from_url(
            standard_redis_url, 
            decode_responses=True, 
            socket_timeout=5,
            ssl_cert_reqs=None if is_ssl else 'required'
        )
        redis_client.ping()
        print("✅ Connected to Standard Redis (Direct)")
    except Exception as e:
        print(f"❌ Standard Redis Connection Error: {e}")

# Admin Credentials
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin123')

def get_client_config():
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()
    if not client_id or not client_secret:
        raise ValueError("CRITICAL: GOOGLE_CLIENT_ID or SECRET is missing. Check Vercel Settings.")
    
    return {
        "web": {
            "client_id": client_id,
            "project_id": os.environ.get('GOOGLE_PROJECT_ID', ''),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_secret": client_secret,
            "redirect_uris": [os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/callback')]
        }
    }

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
        session['logged_in'] = True
        return redirect(url_for('dashboard'))
    return render_template('login.html', error='Invalid credentials')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/authorize')
def authorize():
    if 'logged_in' not in session: return redirect(url_for('index'))
    try:
        redirect_uri = url_for('callback', _external=True)
        if 'localhost' not in redirect_uri: redirect_uri = redirect_uri.replace('http://', 'https://')
        
        flow = Flow.from_client_config(get_client_config(), scopes=SCOPES, redirect_uri=redirect_uri)
        auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
        
        # PKCE Fix: Store the verifier
        session['oauth_state'] = state
        session['code_verifier'] = flow.code_verifier
        
        return redirect(auth_url)
    except Exception as e:
        return f"<h1>Authorize Error</h1><pre>{traceback.format_exc()}</pre>"

@app.route('/callback')
def callback():
    try:
        redirect_uri = url_for('callback', _external=True)
        if 'localhost' not in redirect_uri: redirect_uri = redirect_uri.replace('http://', 'https://')
        
        flow = Flow.from_client_config(get_client_config(), scopes=SCOPES, redirect_uri=redirect_uri)
        flow.code_verifier = session.get('code_verifier')
        
        authorization_response = request.url
        if 'localhost' not in authorization_response: authorization_response = authorization_response.replace('http://', 'https://')
        
        flow.fetch_token(authorization_response=authorization_response)
        service = build('gmail', 'v1', credentials=flow.credentials)
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress')
        
        if redis_client:
            # Handle both Upstash and Redis-py interfaces
            if hasattr(redis_client, 'hset'):
                redis_client.hset("connected_accounts", email, flow.credentials.to_json())
            else:
                # Upstash REST might have a different method signature or be handled via redis-py wrapper
                redis_client.hset("connected_accounts", email, flow.credentials.to_json())
            print(f"✅ Successfully saved account: {email}")
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"<h1>Callback Error</h1><pre>{traceback.format_exc()}</pre>"

@app.route('/api/scan')
def api_scan():
    if 'logged_in' not in session: return jsonify({"error": "Unauthorized"}), 401
    results = []
    
    try:
        accounts = {}
        if redis_client:
            raw_accounts = redis_client.hgetall("connected_accounts")
            # Normalize accounts (redis-py returns dict, upstash might return different)
            for email, data in raw_accounts.items():
                # Data might be bytes or string
                val = data if isinstance(data, str) else data.decode('utf-8')
                accounts[email] = val

        for email, json_data in accounts.items():
            try:
                creds = Credentials.from_json(json_data)
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                
                service = build('gmail', 'v1', credentials=creds)
                msgs_result = service.users().messages().list(userId='me', maxResults=5).execute()
                messages = msgs_result.get('messages', [])
                
                emails_data = []
                for msg in messages:
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
            except Exception as inner:
                results.append({"email": email, "status": "error", "error": str(inner)})
                
        return jsonify({
            "db_status": "connected" if redis_client else "local_memory",
            "results": results
        })
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
