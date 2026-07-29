"""
Filtro de ruído ALSA/JACK/PortAudio no stderr.

Quando o PyAudio é importado no Raspberry Pi, ele dispara mensagens
de diagnóstico do ALSA no stderr. Essas mensagens são inofensivas
mas poluem o terminal e podem confundir o usuário.

Este módulo intercepta o stderr (via dup2 + pipe) e filtra as linhas
que casam com padrões conhecidos de ruído do ALSA/JACK. Linhas que
não são ruído são reenviadas para o stderr original.

Como o PyAudio/SpeechRecognition disparam essas mensagens no momento
do import, este módulo ativa o filtro automaticamente ao ser importado
(efeito colateral intencional). Basta fazer:

    from utils import stderr_filter

antes de importar speech_recognition.
"""

import os
import re
import threading

# Padrões de ruído conhecidos do ALSA, JACK e PortAudio
_NOISE_PATTERN = re.compile(
    r"(ALSA lib|Cannot connect to server|jack server|JackShmReadWrite|"
    r"capture slave|unable to open slave|Unknown PCM|"
    r"Unable to find definition|Evaluate error|"
    r"snd_func_refer|snd_config_expand|snd_pcm_open_noupdate|"
    r"snd_pcm_asym_open|snd_pcm_dmix_open|snd_ctl_open_noupdate|"
    r"Invalid CTL)"
)

# Salva o fd do stderr original (2) e cria um pipe para interceptação
_original_stderr_fd = os.dup(2)
_pipe_read, _pipe_write = os.pipe()
os.dup2(_pipe_write, 2)
os.close(_pipe_write)


def _filter_stderr():
    """Thread que lê o pipe e filtra as mensagens de ruído.

    Linhas que NÃO são ruído são reenviadas ao stderr original.
    Linhas de ruído são descartadas silenciosamente.
    """
    buf = b""
    while True:
        try:
            data = os.read(_pipe_read, 4096)
            if not data:
                # EOF — escreve o que sobrou no buffer
                if buf:
                    text = buf.decode(errors="replace")
                    if not _NOISE_PATTERN.search(text):
                        os.write(_original_stderr_fd, (text + "\n").encode())
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode(errors="replace")
                if not _NOISE_PATTERN.search(text):
                    os.write(_original_stderr_fd, (text + "\n").encode())
        except (OSError, ValueError):
            if buf:
                text = buf.decode(errors="replace")
                if not _NOISE_PATTERN.search(text):
                    os.write(_original_stderr_fd, text.encode())
            break


# Inicia a thread daemon do filtro no momento do import
_stderr_thread = threading.Thread(target=_filter_stderr, daemon=True)
_stderr_thread.start()
