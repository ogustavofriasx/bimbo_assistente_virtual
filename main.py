"""
Assistente de Voz Bimbo — entry point.

Fluxo principal:
1. Carrega .env e ativa o filtro de ruído ALSA
2. Abre o microfone, calibra e entra no loop principal
3. Aguarda wake word ("oi bimbo") → cumprimenta → entra no chatbot
4. No chatbot: ouve comandos, transcreve, interpreta intenção,
   executa ação (calendar ou conversa), responde por voz
5. Ao sair do chatbot, volta a aguardar a wake word

Este arquivo é apenas orquestração — toda a lógica está nos módulos:
- config.py   → constantes, logger, fábrica OpenAI
- audio.py    → microfone, wake word, TTS
- chat.py     → chatbot, detecção de intenção, dispatcher
- calendar.py → Google Calendar API
"""

import signal
import sys
import time

# ─── 1. Carrega variáveis de ambiente (.env) ─────────────────────────
from config import load_env
load_env()

# ─── 2. Ativa filtro de ruído ALSA/JACK/PortAudio ────────────────────
# O filtro intercepta stderr antes dos imports de áudio, que disparam
# mensagens de diagnóstico do ALSA ao carregar PyAudio/SpeechRecognition.
# Ele roda numa thread daemon e filtra linhas por regex.
from utils import stderr_filter  # noqa: E402 — efeito colateral intencional

# ─── 3. Imports da aplicação ─────────────────────────────────────────
import speech_recognition as sr

from audio import (
    calibrate_microphone,
    create_recognizer,
    is_speaking,
    listen_for_command,
    listen_for_wake_word,
    speak_async,
)
from chat import run_chatbot
from config import WAKE_PAUSE, get_openai_client, log


# ══════════════════════════════════════════════════════════════════════
# Graceful shutdown (SIGINT / SIGTERM)
# ══════════════════════════════════════════════════════════════════════

_running = True


def _shutdown(signum, frame):
    """Handler de sinais para encerramento limpo."""
    global _running
    log.info("Encerrando assistente...")
    _running = False
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)


# ══════════════════════════════════════════════════════════════════════
# Loop principal
# ══════════════════════════════════════════════════════════════════════

def main():
    """Orquestra o ciclo de vida completo do assistente."""
    recognizer = create_recognizer()

    try:
        with sr.Microphone() as source:
            calibrate_microphone(recognizer, source)

            # ── Loop externo: wake word → chatbot → repete ──
            while _running:
                # Aguarda a wake word (bloqueante)
                listen_for_wake_word(source, recognizer)

                # Wake word detectada — cumprimenta e inicia chatbot
                client = get_openai_client()
                greeting = "Olá! Em que posso ajudar?"
                speak_async(greeting, client)  # TTS em background
                log.info("Bimbo: %s", greeting)
                time.sleep(WAKE_PAUSE)

                # ── Loop interno: chatbot (comandos do usuário) ──
                while _running:
                    # Espera o TTS terminar antes de abrir o microfone
                    # (evita que o assistente ouça a própria voz)
                    while is_speaking():
                        time.sleep(0.1)

                    # Captura e transcreve o comando do usuário
                    user_text = listen_for_command(source, recognizer, client)

                    if user_text is None:
                        # Timeout — usuário não falou nada
                        prompt = "Não ouvi nada. Ainda está aí?"
                        speak_async(prompt, client)
                        log.info("Bimbo: %s", prompt)
                        time.sleep(2)
                        continue

                    if not user_text:
                        continue

                    log.info("Você: %s", user_text)

                    # Processa com o chatbot
                    response_text, should_exit = run_chatbot(user_text, client)
                    speak_async(response_text, client)
                    log.info("Bimbo: %s", response_text)

                    if should_exit:
                        break

                # Restaura threshold curto para detecção da wake word
                recognizer.pause_threshold = 0.5
                log.info(
                    "Chatbot encerrado. Diga 'oi bimbo' para ativar novamente."
                )

    except OSError as error:
        if "No Default Input Device" in str(error):
            log.error("Nenhum microfone encontrado.")
            log.error("No macOS, rode fora do Docker: python main.py")
            log.error(
                "No Raspberry Pi, conecte o microfone USB e tente novamente."
            )
            sys.exit(0)
        raise


if __name__ == "__main__":
    main()
