"""
Captura de áudio do microfone e síntese de voz (TTS).

Este módulo concentra tudo relacionado a áudio:
- Microfone: calibração, detecção de wake word, captura de comandos
- TTS: síntese de voz via OpenAI, reprodução com player nativo do SO

Sincronização:
- is_speaking() → True enquanto o Bimbo está falando
- speak_async() → dispara TTS em background; o caller deve esperar
  is_speaking() == False antes de abrir o microfone (evita feedback)
"""

import io
import os
import subprocess
import sys
import tempfile
import threading
import time

import speech_recognition as sr

from config import (
    AMBIENT_DURATION,
    CHAT_PAUSE_THRESHOLD,
    CHAT_PHRASE_TIME_LIMIT,
    CHAT_TIMEOUT,
    ENERGY_THRESHOLD,
    OPENAI_TRANSCRIBE_MODEL,
    PHRASE_TIMEOUT,
    RECOGNITION_LANG,
    TTS_AUDIO_DEVICE,
    TTS_MODEL,
    TTS_VOICE,
    WAKE_KEYWORDS,
    WAKE_PAUSE,
    WAKE_PHRASE_TIME_LIMIT,
    WAKE_WORD,
    get_openai_client,
    log,
)

# ══════════════════════════════════════════════════════════════════════
# Microfone — configuração, calibração, wake word e captura
# ══════════════════════════════════════════════════════════════════════

def create_recognizer():
    """Cria e configura um Recognizer do speech_recognition.

    Configura thresholds de energia para detecção de fala.
    O dynamic_energy_threshold ajusta automaticamente o limiar
    com base no ruído ambiente.

    Returns:
        speech_recognition.Recognizer: Instância configurada.
    """
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = ENERGY_THRESHOLD
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.5  # pausa padrão para frases curtas
    return recognizer


def calibrate_microphone(recognizer, source):
    """Ajusta o reconhecedor ao ruído ambiente.

    Deve ser chamada uma vez no início, com o microfone aberto.
    A duração da calibração é controlada por AMBIENT_DURATION (0.5s).

    Args:
        recognizer: Instância de speech_recognition.Recognizer.
        source: Microfone aberto (sr.Microphone context manager).
    """
    log.info("Calibrando ruído ambiente...")
    recognizer.adjust_for_ambient_noise(source, duration=AMBIENT_DURATION)
    log.info("Pronto. Energia base: %d", recognizer.energy_threshold)


def contains_wake_word(transcripts):
    """Verifica se algum transcript contém a wake word ou suas variantes.

    Args:
        transcripts: Lista de strings (resultados do reconhecimento).

    Returns:
        bool: True se a wake word foi detectada.
    """
    for text in transcripts:
        text_lower = text.casefold()
        # Verifica frase completa primeiro ("oi bimbo")
        if WAKE_WORD in text_lower:
            return True
        # Depois verifica variantes isoladas (tolerância a ruído)
        for kw in WAKE_KEYWORDS:
            if kw in text_lower:
                return True
    return False


def listen_for_wake_word(source, recognizer):
    """Loop de escuta contínua até detectar a wake word.

    Fica ouvindo indefinidamente. Cada frase capturada é transcrita
    pelo Google Speech Recognition (português). Se a wake word for
    detectada, retorna.

    Args:
        source: Microfone aberto (sr.Microphone context manager).
        recognizer: Instância configurada de Recognizer.

    Returns:
        bool: Sempre True (detectou wake word).
    """
    while True:
        log.info("Estou ouvindo...")
        try:
            # Captura áudio: espera até PHRASE_TIMEOUT segundos,
            # limita frase a WAKE_PHRASE_TIME_LIMIT segundos
            audio = recognizer.listen(
                source,
                timeout=PHRASE_TIMEOUT,
                phrase_time_limit=WAKE_PHRASE_TIME_LIMIT,
            )
            result = recognizer.recognize_google(
                audio, language=RECOGNITION_LANG, show_all=True
            )
            transcripts = []
            if isinstance(result, dict):
                for alt in result.get("alternative", []):
                    transcript = alt.get("transcript", "")
                    if transcript:
                        transcripts.append(transcript)

            if transcripts:
                log.info("  Ouvido: %s", transcripts[0])

            if contains_wake_word(transcripts):
                log.info("Comando de ativação detectado")
                return True

        except sr.WaitTimeoutError:
            # Ninguém falou — volta a escutar
            continue
        except sr.UnknownValueError:
            # Não entendeu o áudio — volta a escutar
            continue


def listen_for_command(source, recognizer, client=None):
    """Captura e transcreve um comando de voz do usuário.

    Usa pausas maiores (CHAT_PAUSE_THRESHOLD) para não cortar
    frases no meio. Espera até CHAT_TIMEOUT segundos pelo início
    da fala. Permite até CHAT_PHRASE_TIME_LIMIT segundos de fala.

    A transcrição é feita pela API OpenAI Whisper (mais precisa
    que o Google Speech Recognition para frases longas).

    Args:
        source: Microfone aberto (sr.Microphone context manager).
        recognizer: Instância configurada de Recognizer.
        client: Cliente OpenAI (se None, cria um novo).

    Returns:
        str ou None: Texto transcrito, ou None se ninguém falou (timeout).
    """
    if client is None:
        client = get_openai_client()

    # Aumenta a pausa para frases longas (descrevendo reuniões, etc.)
    recognizer.pause_threshold = CHAT_PAUSE_THRESHOLD

    try:
        audio = recognizer.listen(
            source,
            timeout=CHAT_TIMEOUT,
            phrase_time_limit=CHAT_PHRASE_TIME_LIMIT,
        )
    except sr.WaitTimeoutError:
        return None

    # Transcreve com OpenAI Whisper (modelo gpt-4o-mini-transcribe)
    audio_file = io.BytesIO(audio.get_wav_data())
    audio_file.name = "comando.wav"

    transcription = client.audio.transcriptions.create(
        model=OPENAI_TRANSCRIBE_MODEL,
        file=audio_file,
        language="pt",
    )
    return transcription.text


# ══════════════════════════════════════════════════════════════════════
# TTS — síntese de voz e reprodução de áudio
# ══════════════════════════════════════════════════════════════════════

# Evento de sincronização: True enquanto o TTS está tocando áudio.
# O caller (main.py) deve esperar is_speaking() == False antes de
# abrir o microfone, para evitar que o assistente ouça a própria voz.
_busy = threading.Event()


def is_speaking():
    """Retorna True se o TTS ainda está tocando áudio."""
    return _busy.is_set()


def wait_silence(timeout=None):
    """Bloqueia a thread atual até o TTS terminar de falar.

    Args:
        timeout: Tempo máximo de espera em segundos (None = infinito).
    """
    _busy.wait(timeout=timeout)


def _get_players():
    """Retorna lista de players de áudio em ordem de preferência.

    A ordem é específica para cada sistema operacional.
    No Raspberry Pi, tenta múltiplos dispositivos HDMI e fallbacks.

    Returns:
        list[list[str]]: Lista de comandos (ex: [["aplay", "-q", "file.wav"]]).
    """
    # macOS: player nativo afplay
    if sys.platform == "darwin":
        return [["afplay"]]

    # Linux: permite fixar dispositivo via TTS_AUDIO_DEVICE (ex: hdmi:CARD=vc4hdmi1)
    if TTS_AUDIO_DEVICE:
        return [
            ["aplay", "-q", "-D", TTS_AUDIO_DEVICE],
            ["aplay", "-q"],
            ["paplay"],
        ]

    # Raspberry Pi: tenta HDMI 1 → HDMI 0 → plughw → default → PulseAudio
    return [
        ["aplay", "-q", "-D", "hdmi:CARD=vc4hdmi1"],   # HDMI 1 (mais comum em RPi 4/5)
        ["aplay", "-q", "-D", "hdmi:CARD=vc4hdmi0"],   # HDMI 0
        ["aplay", "-q", "-D", "plughw:0,0"],            # plughw card 0
        ["aplay", "-q", "-D", "plughw:1,0"],            # plughw card 1
        ["aplay", "-q", "-D", "default"],               # dispositivo default ALSA
        ["aplay", "-q"],                                 # fallback sem device
        ["paplay"],                                      # PulseAudio
    ]


def _play_audio(audio_bytes):
    """Toca áudio em bytes (formato WAV) no player de áudio do sistema.

    Cria um arquivo temporário, tenta cada player da lista em ordem,
    e remove o arquivo ao final (sucesso ou falha).

    Se todos os players falharem, levanta RuntimeError com as mensagens
    de erro de cada tentativa para diagnóstico.

    Args:
        audio_bytes: Conteúdo do arquivo WAV (bytes).

    Raises:
        RuntimeError: Se nenhum player de áudio conseguir tocar.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    errors = []
    try:
        for player in _get_players():
            try:
                result = subprocess.run(
                    player + [tmp_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except FileNotFoundError:
                # Player não instalado (ex: paplay) — pula silenciosamente
                continue

            if result.returncode == 0:
                return  # tocou com sucesso

            # Coleta erro deste player para diagnóstico
            err = result.stderr.decode().strip()
            label = f"{' '.join(player)}: {err}" if err else \
                    f"{' '.join(player)}: exit code {result.returncode}"
            errors.append(label)

        # Todos os players falharam — exibe diagnóstico completo
        raise RuntimeError(
            "\n".join(errors) if errors else "Nenhum player de áudio funcionou"
        )
    finally:
        os.unlink(tmp_path)


def speak(text, client=None):
    """Converte texto em fala (OpenAI TTS) e toca o áudio.

    Esta função é bloqueante — só retorna após o áudio terminar.

    Args:
        text: Texto a ser falado (português).
        client: Cliente OpenAI (se None, cria um novo).
    """
    if not text:
        _busy.clear()
        return

    if client is None:
        client = get_openai_client()

    try:
        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=text,
            response_format="wav",
        )
        _play_audio(response.content)
    except Exception as e:
        log.error("[TTS] Erro: %s", e)
    finally:
        _busy.clear()


def speak_async(text, client=None):
    """Dispara TTS em background (não-bloqueante).

    Enquanto gera/toca áudio, is_speaking() retorna True.
    O caller deve esperar is_speaking() == False antes de abrir
    o microfone — isso evita que o assistente ouça a própria voz
    e entre em loop de feedback.

    Args:
        text: Texto a ser falado (português).
        client: Cliente OpenAI (se None, cria um novo).
    """
    if not text:
        _busy.clear()
        return

    _busy.set()
    thread = threading.Thread(target=speak, args=(text, client), daemon=True)
    thread.start()
