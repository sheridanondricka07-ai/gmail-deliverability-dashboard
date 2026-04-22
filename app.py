import os
import json
import time

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Allow OAuth over HTTP for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'super-secret-key-change-this')

# Fixed Admin Credentials
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin123')

# Google OAuth Configuration (loaded from environment variables)
CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get('GOOGLE_CLIENT_ID', ''),
        "project_id": os.environ.get('GOOGLE_PROJECT_ID', ''),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        "redirect_uris": ["http://localhost:5000/callback"]
    }
}

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Global store for connected accounts' tokens (In-memory for this demo)
connected_accounts = {} # format: {email: credentials_obj}

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    if username == ADMIN_USER and password == ADMIN_PASS:
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
    if 'logged_in' not in session:
        return redirect(url_for('index'))
    
    try:
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri='http://localhost:5000/callback'
        )
        
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        return redirect(auth_url)
    except Exception as e:
        return f"<h1>Authorize Error</h1><p>{str(e)}</p><a href='/dashboard'>Go Back</a>"

@app.route('/callback')
def callback():
    # Handle errors sent back by Google (e.g., access_denied)
    auth_error = request.args.get('error')
    if auth_error:
        error_msg = f"Connection failed: {auth_error}"
        if auth_error == 'access_denied':
            error_msg = "Connection Refused: You must add your email to the 'Test Users' list in the Google Cloud Console or click 'Advanced > Go to App' if available."
        return f"<h1>Auth Error</h1><p>{error_msg}</p><a href='/dashboard' class='btn-pro'>Go Back to Dashboard</a>"

    try:
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri='http://localhost:5000/callback'
        )
        
        # Build the full authorization response URL
        # We must use request.url, but ensure it matches the redirect_uri scheme
        authorization_response = request.url
        if authorization_response.startswith('http://'):
            authorization_response = authorization_response.replace('http://', 'https://', 1)
            
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials
        
        # Get user info to identify the account
        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress')
        
        connected_accounts[email] = creds
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"<h1>System Error</h1><p>{str(e)}</p><a href='/dashboard' class='btn-pro'>Go Back</a>"

@app.route('/api/scan')
def api_scan():
    if 'logged_in' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    results = []
    for email, creds in connected_accounts.items():
        try:
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            
            service = build('gmail', 'v1', credentials=creds)
            
            # Fetch last 5 messages
            msgs_result = service.users().messages().list(userId='me', maxResults=5).execute()
            messages = msgs_result.get('messages', [])
            
            emails_data = []
            for msg in messages:
                m_details = service.users().messages().get(userId='me', id=msg['id']).execute()
                headers = m_details.get('payload', {}).get('headers', [])
                
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                from_val = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                
                # Logic for labels
                labels = m_details.get('labelIds', [])
                folder = "Inbox"
                if "SPAM" in labels: folder = "Spam"
                elif "CATEGORY_PROMOTIONS" in labels: folder = "Promotions"
                elif "CATEGORY_FORUMS" in labels: folder = "Forums"
                
                emails_data.append({
                    "id": msg['id'],
                    "subject": subject,
                    "from": from_val,
                    "folder": folder,
                    "timestamp": m_details.get('internalDate')
                })
            
            results.append({
                "email": email,
                "status": "online",
                "emails": emails_data
            })
        except Exception as e:
            results.append({
                "email": email,
                "status": "error",
                "error": str(e),
                "emails": []
            })
            
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
