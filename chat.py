"""
Chatbot com detecção de intenção para comandos de calendário.

Fluxo de processamento:
1. handle_message() — envia o texto do usuário para o modelo OpenAI,
   que identifica a intenção (agendar/listar/atualizar/cancelar/conversar/sair)
   e retorna um dicionário de ação estruturado.
2. run_chatbot() — recebe a ação, executa a operação correspondente
   no Google Calendar (via calendar.py) e retorna texto de resposta.

O contexto da conversa (ChatContext) mantém as últimas N mensagens
para que o modelo entenda pronomes e referências entre turnos.
"""

import json
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

from calendar_service import (
    create_event,
    delete_event_by_keyword,
    list_events,
    update_event_by_keyword,
)
from config import (
    EXIT_PHRASES,
    MAX_CONTEXT,
    OPENAI_TEXT_MODEL,
    get_openai_client,
    log,
)

# ══════════════════════════════════════════════════════════════════════
# Histórico de conversa
# ══════════════════════════════════════════════════════════════════════

class ChatContext:
    """Histórico leve das últimas mensagens para dar contexto ao modelo.

    Usa um deque com tamanho máximo fixo — quando atinge o limite,
    as mensagens mais antigas são automaticamente descartadas.
    """

    def __init__(self, max_messages=MAX_CONTEXT):
        self._messages = deque(maxlen=max_messages)

    def add(self, role, text):
        """Adiciona uma mensagem ao histórico.

        Args:
            role: "user" para mensagens do usuário, "assistant" para o Bimbo.
            text: Conteúdo da mensagem.
        """
        self._messages.append({"role": role, "content": text})

    def clear(self):
        """Limpa todo o histórico (ex: ao encerrar o chatbot)."""
        self._messages.clear()

    def as_text(self):
        """Formata o histórico como texto para incluir no prompt do modelo.

        Returns:
            str: Histórico formatado, ou string vazia se estiver vazio.
        """
        if not self._messages:
            return ""
        lines = ["[Conversa anterior:]"]
        for msg in self._messages:
            role = "Você" if msg["role"] == "user" else "Bimbo"
            lines.append(f"{role}: {msg['content']}")
        lines.append("")
        return "\n".join(lines)


# Contexto global da sessão (mantido entre turnos do chatbot)
_context = ChatContext()


# ══════════════════════════════════════════════════════════════════════
# Detecção de intenção
# ══════════════════════════════════════════════════════════════════════

def _should_exit(text):
    """Verifica se o texto contém uma frase de despedida.

    Args:
        text: Texto do usuário (case-insensitive).

    Returns:
        bool: True se for uma frase de saída.
    """
    text = text.casefold().strip(".!? ")
    return any(phrase in text for phrase in EXIT_PHRASES)


def _get_system_prompt():
    """Monta o system prompt com a data/hora atual no fuso de São Paulo.

    O prompt instrui o modelo a retornar JSON estruturado para comandos
    de calendário ou texto natural para conversa.

    Returns:
        str: Prompt completo para enviar como instrução ao modelo.
    """
    now_br = datetime.now(ZoneInfo("America/Sao_Paulo"))

    return (
        "Você é o Bimbo, um assistente de voz brasileiro que roda num Raspberry Pi. "
        "Você conversa de forma natural, amigável e objetiva em português.\n\n"
        "REGRAS IMPORTANTES:\n"
        "1. Se o usuário quer MARCAR/AGENDAR/CRIAR uma reunião, evento, compromisso "
        "ou lembrete no calendário, retorne APENAS:\n"
        '{"action":"schedule","event":{'
        '"summary":"Título","description":"Descrição",'
        '"start":{"dateTime":"AAAA-MM-DDTHH:MM:00-03:00","timeZone":"America/Sao_Paulo"},'
        '"end":{"dateTime":"AAAA-MM-DDTHH:MM:00-03:00","timeZone":"America/Sao_Paulo"}'
        '}}\n\n'
        "2. Se o usuário quer VER/LISTAR/CONSULTAR a agenda, eventos, "
        "compromissos ou perguntar 'o que tenho hoje/amanhã/essa semana', "
        "retorne APENAS:\n"
        '{"action":"list"}\n\n'
        "3. Se o usuário quer ALTERAR/MUDAR/EDITAR/REAGENDAR/ADIAR um evento "
        "ou reunião, retorne APENAS o JSON. Inclua APENAS os campos que vão mudar:\n"
        '{"action":"update","keyword":"palavra-chave do título atual"'
        ',"summary":"novo título (opcional)","description":"nova descrição (opcional)"'
        ',"start":"AAAA-MM-DDTHH:MM:00-03:00 (opcional)"'
        ',"end":"AAAA-MM-DDTHH:MM:00-03:00 (opcional)"}\n\n'
        "4. Se o usuário quer CANCELAR/DESMARCAR/REMOVER/DELETAR um evento "
        "ou reunião, retorne APENAS o JSON com a palavra-chave do evento:\n"
        '{"action":"delete","keyword":"palavra-chave do título"}\n\n'
        f"Data/hora atual: {now_br.isoformat()}\n"
        "Use essa data para interpretar 'hoje', 'amanhã', dias da semana.\n"
        "Duração padrão: 30 minutos se não especificada.\n"
        "Descrição padrão: 'Evento criado pelo Bimbo' se não especificada.\n\n"
        "5. Para QUALQUER outra mensagem (conversa, pergunta, saudação), "
        "responda APENAS com texto natural em português.\n\n"
        "6. Se o usuário disser 'tchau bimbo', 'tchau' ou se despedir, "
        "responda APENAS: {\"action\":\"exit\"}\n\n"
        "Use o contexto da conversa anterior para entender pronomes, "
        "referências e manter coerência nas respostas."
    )


def handle_message(user_text, client=None):
    """Processa uma mensagem do usuário e identifica a intenção.

    Envia o texto para a API OpenAI com o system prompt. O modelo
    retorna JSON estruturado para comandos de calendário ou texto
    natural para conversa casual.

    Args:
        user_text: Texto transcrito da fala do usuário.
        client: Cliente OpenAI (se None, cria um novo).

    Returns:
        dict: Sempre contém a chave "type". Os tipos possíveis:
            - {"type": "exit", "text": "..."}
            - {"type": "schedule_event", "event": {...}}
            - {"type": "update_event", "keyword": "...", ...}
            - {"type": "delete_event", "keyword": "..."}
            - {"type": "list_events"}
            - {"type": "chat", "text": "..."}
    """
    if client is None:
        client = get_openai_client()

    # Verificação rápida: frases de saída não precisam chamar o modelo
    if _should_exit(user_text):
        _context.clear()
        return {"type": "exit", "text": "Até mais! Encerrando o assistente."}

    # Monta o input com o histórico da conversa (se houver)
    context_text = _context.as_text()
    full_input = (
        f"{context_text}[Mensagem atual]\n{user_text}"
        if context_text
        else user_text
    )

    # Chama a API OpenAI para interpretar a intenção
    response = client.responses.create(
        model=OPENAI_TEXT_MODEL,
        input=full_input,
        instructions=_get_system_prompt(),
    )
    raw = response.output_text.strip()

    # Tenta interpretar como JSON estruturado
    try:
        data = json.loads(raw)
        action = data.get("action", "")

        if action == "schedule":
            event = data.get("event", {})
            start = event.get("start", {})
            end = event.get("end", {})
            if not start.get("dateTime") or not end.get("dateTime"):
                return {
                    "type": "chat",
                    "text": (
                        "Não consegui entender a data e horário. "
                        "Pode repetir com mais detalhes?"
                    ),
                }
            return {"type": "schedule_event", "event": event}

        if action == "update":
            keyword = data.get("keyword", "")
            if not keyword:
                return {"type": "chat", "text": "Qual evento você quer alterar?"}
            return {
                "type": "update_event",
                "keyword": keyword,
                "start": data.get("start") or None,
                "end": data.get("end") or None,
                "summary": data.get("summary") or None,
                "description": data.get("description") or None,
            }

        if action == "delete":
            keyword = data.get("keyword", "")
            if not keyword:
                return {"type": "chat", "text": "Qual evento você quer cancelar?"}
            return {"type": "delete_event", "keyword": keyword}

        if action == "list":
            return {"type": "list_events"}

        if action == "exit":
            _context.clear()
            return {"type": "exit", "text": "Até mais! Encerrando o assistente."}

        # JSON com ação desconhecida — trata como texto livre
        return {"type": "chat", "text": raw}

    except json.JSONDecodeError:
        # O modelo respondeu em linguagem natural (não é JSON)
        return {"type": "chat", "text": raw}


# ══════════════════════════════════════════════════════════════════════
# Execução de ações
# ══════════════════════════════════════════════════════════════════════

def run_chatbot(user_text, client=None):
    """Executa um turno completo do chatbot.

    1. Adiciona a fala do usuário ao histórico
    2. Chama handle_message() para identificar a intenção
    3. Executa a ação correspondente (calendar CRUD ou resposta textual)
    4. Retorna o texto de resposta + flag de saída

    Args:
        user_text: Texto transcrito da fala do usuário.
        client: Cliente OpenAI (se None, cria um novo).

    Returns:
        tuple[str, bool]: (texto_de_resposta, deve_encerrar_chatbot)
    """
    if client is None:
        client = get_openai_client()

    # Adiciona mensagem do usuário ao contexto da conversa
    _context.add("user", user_text)

    # Identifica a intenção
    result = handle_message(user_text, client)

    # ── Ação: sair ──
    if result["type"] == "exit":
        return result.get("text", "Até mais!"), True

    # ── Ação: agendar evento ──
    if result["type"] == "schedule_event":
        event = result["event"]
        log.info("Agendando evento: %s", event.get("summary"))
        try:
            create_event(event)
            text = (
                f"Prontinho! Reunião '{event.get('summary', 'sem título')}' "
                "agendada com sucesso. Mais alguma coisa?"
            )
        except Exception as e:
            text = f"Erro ao agendar: {e}. Tente novamente."
        _context.add("assistant", text)
        return text, False

    # ── Ação: atualizar evento ──
    if result["type"] == "update_event":
        keyword = result["keyword"]
        changes = [k for k in ["summary", "description", "start"]
                   if result.get(k)]
        log.info("Atualizando '%s': %s", keyword, changes)
        try:
            updated = update_event_by_keyword(
                keyword,
                new_start=result.get("start"),
                new_end=result.get("end"),
                new_summary=result.get("summary"),
                new_description=result.get("description"),
            )
            if updated:
                text = (
                    f"Evento '{updated}' atualizado com sucesso. "
                    "Mais alguma coisa?"
                )
            else:
                text = (
                    f"Não encontrei nenhum evento com '{keyword}'. "
                    "Quer tentar com outro nome?"
                )
        except Exception as e:
            text = f"Erro ao atualizar: {e}."
        _context.add("assistant", text)
        return text, False

    # ── Ação: cancelar evento ──
    if result["type"] == "delete_event":
        keyword = result["keyword"]
        log.info("Cancelando evento com '%s'", keyword)
        try:
            removed = delete_event_by_keyword(keyword)
            if removed:
                text = (
                    f"Evento '{removed}' cancelado com sucesso. "
                    "Mais alguma coisa?"
                )
            else:
                text = (
                    f"Não encontrei nenhum evento com '{keyword}'. "
                    "Quer tentar com outro nome?"
                )
        except Exception as e:
            text = f"Erro ao cancelar: {e}."
        _context.add("assistant", text)
        return text, False

    # ── Ação: listar eventos ──
    if result["type"] == "list_events":
        try:
            events = list_events()
            if not events:
                text = "Você não tem eventos próximos na agenda."
            else:
                lines = ["Aqui estão seus próximos eventos:"]
                for ev in events:
                    summary = ev["summary"]
                    start = ev["start"]
                    try:
                        dt_start = datetime.fromisoformat(start)
                        formatted = dt_start.strftime("%d/%m às %H:%M")
                    except (ValueError, TypeError):
                        formatted = start
                    lines.append(f"  • {summary} — {formatted}")
                text = "\n".join(lines)
        except Exception as e:
            text = f"Erro ao consultar a agenda: {e}."
        _context.add("assistant", text)
        return text, False

    # ── Ação: conversa livre (chat) ──
    text = result.get("text", "Hmm, não entendi. Pode repetir?")
    _context.add("assistant", text)
    return text, False
