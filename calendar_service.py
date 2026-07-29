"""
Integração com a API Google Calendar.

Fornece autenticação OAuth automática com refresh de token e operações
CRUD de eventos (criar, listar, atualizar, deletar) na agenda principal
do usuário.

Fluxo de autenticação:
1. Tenta carregar token salvo em disco (token.json)
2. Se expirado, renova com refresh_token do .env
3. Se não tem credenciais, faz fluxo OAuth completo (abre navegador)

As constantes de configuração (client_id, secret, tokens) são importadas
de config.py, que por sua vez lê de variáveis de ambiente (.env).
"""

import json
import os
import shutil
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import (
    CALENDAR_ID,
    CALENDAR_SCOPES,
    GOOGLE_AUTH_URI,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    GOOGLE_REFRESH_TOKEN,
    GOOGLE_ACCESS_TOKEN,
    GOOGLE_TOKEN_PATH,
    GOOGLE_TOKEN_URI,
    MAX_CALENDAR_RESULTS,
    build_oauth_client_config,
    log,
)


# ══════════════════════════════════════════════════════════════════════
# Gerenciamento de token OAuth
# ══════════════════════════════════════════════════════════════════════

def _save_token(creds):
    """Persiste o token renovado em disco para evitar re-autenticação."""
    token_directory = os.path.dirname(GOOGLE_TOKEN_PATH)
    if token_directory:
        os.makedirs(token_directory, exist_ok=True)
    with open(GOOGLE_TOKEN_PATH, "w", encoding="utf-8") as token_file:
        token_file.write(creds.to_json())


def _credentials_from_env():
    """Cria credenciais OAuth a partir das variáveis de ambiente (.env).

    Returns:
        Credentials ou None se GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
        não estiverem definidos ou não houver token disponível.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None
    if not GOOGLE_REFRESH_TOKEN and not GOOGLE_ACCESS_TOKEN:
        return None

    return Credentials(
        token=GOOGLE_ACCESS_TOKEN or None,
        refresh_token=GOOGLE_REFRESH_TOKEN or None,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=CALENDAR_SCOPES,
    )


def get_calendar_service():
    """Retorna um serviço Google Calendar autenticado e pronto para uso.

    Ordem de resolução das credenciais:
    1. token.json em disco (salvo de uma autenticação anterior)
    2. Variáveis GOOGLE_* do .env (refresh token + access token)
    3. Fluxo OAuth completo com navegador (fallback interativo)

    Se o token estiver expirado mas houver refresh_token, renova
    automaticamente e persiste o novo token em disco.

    Returns:
        googleapiclient.discovery.Resource: Serviço Calendar API v3.

    Raises:
        RuntimeError: Se GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET não
                      estiverem definidos e não houver token em disco.
    """
    creds = None

    # 1. Tenta carregar token salvo em disco (versão mais recente após refresh)
    if os.path.exists(GOOGLE_TOKEN_PATH):
        if os.path.isdir(GOOGLE_TOKEN_PATH):
            # Docker cria diretório vazio pro volume — remove e ignora
            shutil.rmtree(GOOGLE_TOKEN_PATH, ignore_errors=True)
        else:
            creds = Credentials.from_authorized_user_file(
                GOOGLE_TOKEN_PATH, CALENDAR_SCOPES
            )
            # Se expirado e sem refresh_token, descarta — .env pode ter um válido
            if creds and creds.expired and not creds.refresh_token:
                creds = None

    # 2. Fallback: monta credenciais a partir do .env (tem refresh_token)
    if not creds:
        creds = _credentials_from_env()

    # 3. Se expirado, tenta renovar com refresh_token
    if creds and creds.expired and creds.refresh_token:
        log.info("Renovando token OAuth expirado...")
        try:
            creds.refresh(Request())
            _save_token(creds)
            log.info("Token renovado e salvo em %s", GOOGLE_TOKEN_PATH)
        except Exception as e:
            log.error("Falha ao renovar token: %s", e)
            log.info("Token refresh expirado/revogado — execute scripts/refresh_token.py")
            # Descarta credenciais inválidas e remove token.json corrompido
            creds = None
            if os.path.exists(GOOGLE_TOKEN_PATH):
                os.remove(GOOGLE_TOKEN_PATH)

    # 4. Se ainda não tem credenciais válidas, faz o fluxo OAuth completo
    if not creds or not creds.valid:
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            raise RuntimeError(
                "Defina GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no arquivo .env "
                "ou forneça credentials.json."
            )
        # Se não há display (Docker headless), não adianta tentar abrir navegador
        if not os.environ.get("DISPLAY"):
            raise RuntimeError(
                "Credenciais OAuth expiradas ou ausentes e não há display "
                "para reautorizar. Execute 'python scripts/refresh_token.py' "
                "numa máquina com navegador e atualize GOOGLE_REFRESH_TOKEN "
                "no arquivo .env."
            )
        log.info("Iniciando fluxo OAuth (abra o navegador)...")
        flow = InstalledAppFlow.from_client_config(
            build_oauth_client_config(), CALENDAR_SCOPES
        )
        creds = flow.run_local_server(port=0)
        _save_token(creds)
        log.info("Autenticação OAuth concluída.")

    return build("calendar", "v3", credentials=creds)


# ══════════════════════════════════════════════════════════════════════
# Operações CRUD de eventos
# ══════════════════════════════════════════════════════════════════════

def create_event(event):
    """Cria um evento na agenda principal do Google Calendar.

    Args:
        event: Dicionário com a estrutura:
            {
                "summary": "Título do evento",
                "description": "Descrição (opcional)",
                "start": {"dateTime": "AAAA-MM-DDTHH:MM:00-03:00",
                          "timeZone": "America/Sao_Paulo"},
                "end": {"dateTime": "AAAA-MM-DDTHH:MM:00-03:00",
                        "timeZone": "America/Sao_Paulo"},
            }

    Returns:
        dict: O evento criado com todos os campos (incluindo id e htmlLink).

    Raises:
        ValueError: Se start.dateTime ou end.dateTime estiverem ausentes.
    """
    start = event.get("start", {})
    end = event.get("end", {})
    if not start.get("dateTime") or not end.get("dateTime"):
        raise ValueError(
            "Evento sem data/hora definida. "
            "Certifique-se de que o comando de voz incluiu data e horário."
        )

    log.info("Criando evento: %s", event.get("summary"))
    service = get_calendar_service()
    created = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    log.info("Evento criado: %s", created.get("htmlLink"))
    return created


def list_events(max_results=10):
    """Retorna os próximos eventos da agenda principal.

    Args:
        max_results: Número máximo de eventos a retornar (padrão: 10).

    Returns:
        list[dict]: Lista de eventos, cada um com as chaves:
            summary, description, start, end.
    """
    service = get_calendar_service()
    now = datetime.now(timezone.utc).isoformat()
    result = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for item in result.get("items", []):
        start = item["start"].get("dateTime", item["start"].get("date"))
        end = item["end"].get("dateTime", item["end"].get("date"))
        events.append({
            "summary": item.get("summary", "Sem título"),
            "description": item.get("description", ""),
            "start": start,
            "end": end,
        })
    return events


def _find_event_by_keyword(service, keyword, max_results=MAX_CALENDAR_RESULTS):
    """Busca o primeiro evento futuro cujo título contenha a palavra-chave.

    Args:
        service: Serviço Google Calendar autenticado.
        keyword: Palavra ou frase para buscar no título dos eventos.
        max_results: Número máximo de eventos a vasculhar.

    Returns:
        dict ou None: O evento encontrado (com id), ou None.
    """
    now = datetime.now(timezone.utc).isoformat()
    result = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    keyword_lower = keyword.casefold()
    for item in result.get("items", []):
        summary = item.get("summary", "")
        if keyword_lower in summary.casefold():
            return item
    return None


def delete_event_by_keyword(keyword, max_results=MAX_CALENDAR_RESULTS):
    """Remove o primeiro evento futuro que contenha a palavra-chave no título.

    Args:
        keyword: Palavra ou frase para identificar o evento a cancelar.
        max_results: Número máximo de eventos a vasculhar.

    Returns:
        str ou None: Nome do evento removido, ou None se não encontrado.
    """
    service = get_calendar_service()
    log.info("Procurando evento para cancelar: '%s'", keyword)
    event = _find_event_by_keyword(service, keyword, max_results)

    if event:
        service.events().delete(
            calendarId=CALENDAR_ID, eventId=event["id"]
        ).execute()
        log.info("Evento cancelado: %s", event.get("summary"))
        return event.get("summary")

    log.info("Nenhum evento encontrado com '%s'", keyword)
    return None


def update_event_by_keyword(
    keyword,
    new_start=None,
    new_end=None,
    new_summary=None,
    new_description=None,
    max_results=MAX_CALENDAR_RESULTS,
):
    """Atualiza o primeiro evento futuro que contenha a palavra-chave.

    Apenas os campos informados são alterados — os demais permanecem
    como estavam.

    Args:
        keyword: Palavra ou frase para identificar o evento.
        new_start: Nova data/hora de início (ISO 8601) ou None.
        new_end: Nova data/hora de fim (ISO 8601) ou None.
        new_summary: Novo título ou None.
        new_description: Nova descrição ou None.
        max_results: Número máximo de eventos a vasculhar.

    Returns:
        str ou None: Nome do evento atualizado, ou None se não encontrado.
    """
    service = get_calendar_service()
    log.info("Procurando evento para atualizar: '%s'", keyword)
    event = _find_event_by_keyword(service, keyword, max_results)

    if event:
        if new_summary:
            event["summary"] = new_summary
        if new_description:
            event["description"] = new_description
        if new_start:
            event["start"]["dateTime"] = new_start
        if new_end:
            event["end"]["dateTime"] = new_end

        updated = (
            service.events()
            .update(calendarId=CALENDAR_ID, eventId=event["id"], body=event)
            .execute()
        )
        log.info("Evento atualizado: %s", updated.get("summary"))
        return updated.get("summary", event.get("summary"))

    log.info("Nenhum evento encontrado com '%s'", keyword)
    return None
