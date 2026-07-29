"""Gera um refresh_token do Google OAuth e exibe no terminal.

Rode no Mac (com navegador): python refresh_token.py
Depois copie o refresh_token para GOOGLE_REFRESH_TOKEN no .env
"""

import os

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]

CLIENT_CONFIG = {
    "installed": {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "auth_uri": os.environ.get("GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": os.environ.get("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
        "redirect_uris": [os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost")],
    }
}

flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
creds = flow.run_local_server(port=0)

print("\n✅ Autorização concluída!")
print(f"\nAccess Token:  {creds.token}")
print(f"Refresh Token: {creds.refresh_token}")
print(f"Expira em:     {creds.expiry}")

print("\n--- Cole no .env (descomente se necessário): ---")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
print(f"GOOGLE_ACCESS_TOKEN={creds.token}")
