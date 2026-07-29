"""
Configuração centralizada do assistente Bimbo.

Todas as constantes e configurações do projeto ficam aqui, carregadas
de variáveis de ambiente com fallback para valores padrão. Isso evita
valores mágicos espalhados pelo código e facilita ajustes sem alterar
a lógica dos módulos.

Também fornece:
- load_env()     → carregamento único do arquivo .env
- get_openai_client() → fábrica única do cliente OpenAI
- build_oauth_client_config() → dicionário OAuth compartilhado
"""

import logging
import os
import sys

# ─── Logger ──────────────────────────────────────────────────────────

# Configura um logger com timestamp para substituir print() em todo o projeto.
# O formato exibe hora, nível e mensagem: [14:30:05] [INFO] Mensagem
_log_handler = logging.StreamHandler(sys.stdout)
_log_handler.setFormatter(
    logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
)

log = logging.getLogger("bimbo")
log.setLevel(logging.INFO)
log.addHandler(_log_handler)


# ══════════════════════════════════════════════════════════════════════
# Carregamento do .env
# ══════════════════════════════════════════════════════════════════════

def load_env(path=".env"):
    """Carrega variáveis de um arquivo .env sem dependências externas.

    Tenta usar python-dotenv primeiro (mais robusto). Se não estiver
    instalado, usa um parser manual simples como fallback.

    Args:
        path: Caminho para o arquivo .env (padrão: .env na raiz).
    """
    # Tenta python-dotenv (instalado no ambiente de dev e no Docker)
    try:
        from dotenv import load_dotenv
        load_dotenv(path, override=False)
        return
    except ImportError:
        pass

    # Fallback: parser manual (sem dependências externas)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


# Carrega o .env imediatamente no import do módulo.
# Isso garante que as constantes abaixo já encontrem as variáveis
# definidas no arquivo .env, mesmo que o caller ainda não tenha
# chamado load_env() explicitamente.
load_env()


# ══════════════════════════════════════════════════════════════════════
# Wake Word
# ══════════════════════════════════════════════════════════════════════

WAKE_WORD: str = os.environ.get("WAKE_WORD", "oi bimbo")

# Variantes aceitas da wake word (para tolerar reconhecimento imperfeito)
WAKE_KEYWORDS: list = ["bimbo", "bimbu", "bimba"]


# ══════════════════════════════════════════════════════════════════════
# Áudio — thresholds e tempos
# ══════════════════════════════════════════════════════════════════════

# Duração da calibração de ruído ambiente (segundos)
AMBIENT_DURATION: float = 0.5

# Tempo máximo de espera por fala durante detecção da wake word (segundos)
PHRASE_TIMEOUT: int = 5

# Pausa após detectar wake word antes de abrir o microfone para o comando
WAKE_PAUSE: float = 0.3

# Limiar de energia inicial para considerar que alguém está falando
ENERGY_THRESHOLD: int = 300

# Idioma usado no reconhecimento de fala (Google Speech Recognition)
RECOGNITION_LANG: str = "pt-BR"


# ══════════════════════════════════════════════════════════════════════
# Chatbot — tempos de escuta / pausa
# ══════════════════════════════════════════════════════════════════════

# Tempo máximo esperando o usuário começar a falar (segundos)
CHAT_TIMEOUT: int = 10

# Pausa mínima para considerar que o usuário terminou de falar (segundos)
# Valores maiores evitam cortar frases no meio quando o usuário hesita
CHAT_PAUSE_THRESHOLD: float = 2.0

# Duração máxima de uma fala contínua (segundos)
CHAT_PHRASE_TIME_LIMIT: int = 30

# Limite de frases da wake word (só precisa capturar "oi bimbo")
WAKE_PHRASE_TIME_LIMIT: int = 3


# ══════════════════════════════════════════════════════════════════════
# Chatbot — contexto e saída
# ══════════════════════════════════════════════════════════════════════

# Número máximo de mensagens no histórico de contexto do chatbot
MAX_CONTEXT: int = 6

# Frases que encerram o chatbot e voltam ao modo de espera da wake word
EXIT_PHRASES: list = [
    "tchau bimbo", "tchau", "adeus", "sair", "encerrar", "até logo"
]


# ══════════════════════════════════════════════════════════════════════
# OpenAI
# ══════════════════════════════════════════════════════════════════════

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

# Modelo de texto (chatbot / intenções)
OPENAI_TEXT_MODEL: str = os.environ.get("OPENAI_TEXT_MODEL", "gpt-5.6-luna")

# Modelo de transcrição (fala → texto)
OPENAI_TRANSCRIBE_MODEL: str = os.environ.get(
    "OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"
)

# Modelo de TTS (texto → fala)
TTS_MODEL: str = os.environ.get("TTS_MODEL", "gpt-4o-mini-tts")

# Voz do TTS (echo, nova, alloy, fable, onyx, shimmer)
TTS_VOICE: str = os.environ.get("TTS_VOICE", "echo")

# Dispositivo de áudio para o TTS (ex: hdmi:CARD=vc4hdmi1)
# Se não definido, o código tenta auto-detectar entre HDMI 0/1, plughw, etc.
TTS_AUDIO_DEVICE: str = os.environ.get("TTS_AUDIO_DEVICE", "")


# ══════════════════════════════════════════════════════════════════════
# Google OAuth 2.0 — Calendar API
# ══════════════════════════════════════════════════════════════════════

GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN: str = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GOOGLE_ACCESS_TOKEN: str = os.environ.get("GOOGLE_ACCESS_TOKEN", "")

# Endpoints OAuth (valores padrão do Google — não alterar)
GOOGLE_TOKEN_URI: str = os.environ.get(
    "GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"
)
GOOGLE_AUTH_URI: str = os.environ.get(
    "GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"
)
GOOGLE_REDIRECT_URI: str = os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost"
)

# Caminho para persistência do token OAuth renovado
# No Docker, o compose.yaml sobrescreve para /data/token.json
GOOGLE_TOKEN_PATH: str = os.environ.get("GOOGLE_TOKEN_PATH", "token.json")

# Escopos da API Google Calendar
CALENDAR_SCOPES: list = ["https://www.googleapis.com/auth/calendar"]

# ID da agenda (padrão: primary = agenda principal do usuário)
CALENDAR_ID: str = os.environ.get("CALENDAR_ID", "primary")

# Número máximo de eventos retornados em buscas por palavra-chave
MAX_CALENDAR_RESULTS: int = int(os.environ.get("MAX_CALENDAR_RESULTS", "20"))


# ══════════════════════════════════════════════════════════════════════
# Fábrica única do cliente OpenAI
# ══════════════════════════════════════════════════════════════════════

def get_openai_client():
    """Retorna uma instância do cliente OpenAI configurada com a API key.

    Centraliza a criação do cliente num único ponto. Antes esta lógica
    estava duplicada em main.py, tts.py e chatbot.py.

    Returns:
        OpenAI: Cliente pronto para uso.

    Raises:
        RuntimeError: Se OPENAI_API_KEY não estiver definida no .env.
    """
    # Lê do os.environ no momento da chamada (não da constante de módulo)
    # porque load_env() pode ter rodado depois do import do config.py
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "Defina OPENAI_API_KEY no arquivo .env. "
            "Copie .env.example para .env e preencha sua chave."
        )
    # Import lazy para não forçar a dependência antes do load_env()
    from openai import OpenAI
    return OpenAI(api_key=api_key)


# ══════════════════════════════════════════════════════════════════════
# Configuração OAuth compartilhada
# ══════════════════════════════════════════════════════════════════════

def build_oauth_client_config():
    """Monta o dicionário de configuração OAuth do Google.

    Usado por calendar_service.py (autenticação) e scripts/refresh_token.py
    (geração de token). Antes essa função existia em google_calendar.py
    e o dicionário era duplicado em refresh_token.py.

    Returns:
        dict: Configuração no formato esperado pelo google-auth-oauthlib.
    """
    return {
        "installed": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }
    }
