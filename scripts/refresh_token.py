#!/usr/bin/env python3
"""
Gera um refresh_token do Google OAuth para o Bimbo.

Uso:
    python scripts/refresh_token.py

O script abre o navegador para autorização OAuth. Se falhar,
mostra a URL para abrir manualmente e cola o código de volta.

Depois de gerar, copie o refresh_token para a variável
GOOGLE_REFRESH_TOKEN no arquivo .env.
"""

import os
import sys

# Permite rodar como script standalone de qualquer diretório
# Adiciona a raiz do projeto ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carrega .env (tenta dotenv, fallback manual)
from config import load_env
load_env()

from google_auth_oauthlib.flow import InstalledAppFlow

from config import CALENDAR_SCOPES, build_oauth_client_config, log


def main():
    """Executa o fluxo OAuth e exibe os tokens gerados."""
    log.info("Iniciando fluxo de autorização OAuth do Google...")

    # Usa a configuração OAuth compartilhada (config.py)
    # Elimina a duplicata que existia entre calendar_service.py e refresh_token.py
    client_config = build_oauth_client_config()
    flow = InstalledAppFlow.from_client_config(client_config, CALENDAR_SCOPES)

    # Tenta abrir navegador automaticamente
    # Se falhar (ex: sem DISPLAY), mostra URL para copiar/colar
    try:
        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message="\nAbra esta URL no navegador:\n{url}\n",
        )
    except Exception:
        auth_url, _ = flow.authorization_url(
            prompt="consent", access_type="offline"
        )
        print(
            f"\nNão foi possível abrir o navegador."
            f"\nAcesse esta URL:\n\n{auth_url}\n"
        )
        code = input("Cole o código de autorização: ").strip()
        flow.fetch_token(code=code)
        creds = flow.credentials

    print("\n✅ Autorização concluída!")
    print(f"\nAccess Token:  {creds.token}")
    print(f"Refresh Token: {creds.refresh_token}")
    print(f"Expira em:     {creds.expiry}")

    print("\n--- Cole no .env (descomente se necessário): ---")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print(f"GOOGLE_ACCESS_TOKEN={creds.token}")


if __name__ == "__main__":
    main()
