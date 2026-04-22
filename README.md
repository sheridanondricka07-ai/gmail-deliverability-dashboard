# Gmail Deliverability Dashboard

A premium, dark-mode Flask application to monitor Gmail inboxes, identify spam/promotion filtering, and track email analytics in real-time.

## Features
- **OAuth 2.0 Integration**: Securely connect multiple Gmail accounts.
- **Real-time Monitoring**: Scan for new messages and their destination folders (Inbox, Spam, Promotions).
- **Executive Dashboard**: Sleek UI with modern glassmorphism and metrics.
- **Multi-Account Support**: Manage several accounts from a single interface.

## Prerequisites
- Python 3.8+
- Google Cloud Console Project with Gmail API enabled.
- OAuth 2.0 Credentials (stored in `app.py` for this demo).

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/gmail-deliverability-dashboard.git
   cd gmail-deliverability-dashboard
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```
   Access the dashboard at `http://localhost:5000`.

## Configuration
- Update the `CLIENT_CONFIG` in `app.py` with your own Google Cloud credentials if deploying.
- Ensure `http://localhost:5000/callback` is added as an Authorized Redirect URI in the Google Cloud Console.

## License
MIT
