# Apresentação — Bimbo: Assistente de Voz Inteligente com Raspberry Pi

---

## Slide 1 — Capa

**Título:** Bimbo — Assistente de Voz Pessoal com IA e Raspberry Pi

**Subtítulo:** Computação Pervasiva • 2026

---

### 🎤 Fala do apresentador
> "Boa tarde a todos. Hoje vamos apresentar o Bimbo, um assistente de voz pessoal que roda num Raspberry Pi e integra inteligência artificial da OpenAI com o Google Calendar. A ideia foi construir um dispositivo de computação pervasiva barato, que funcione offline para comandos locais e use serviços em nuvem para tarefas mais complexas como entender linguagem natural e gerenciar a agenda do usuário."

---

## Slide 2 — Motivação

**Tópicos na tela:**
- 🗣️ **Interação por voz é o futuro** — Alexa, Siri e Google Assistant já provaram que falar é mais natural que digitar
- 💰 **Hardware acessível** — Um Raspberry Pi 4/5 custa menos de R$ 400 e tem poder computacional suficiente
- 🔓 **Código aberto e personalizável** — Diferente de assistentes comerciais, podemos modificar e estender o comportamento
- 📅 **Automação de tarefas do dia a dia** — Agendar reuniões por voz elimina atrito com apps de calendário
- 🎓 **Aplicação didática de conceitos** — Integra IoT, IA, APIs REST, OAuth 2.0, containers Docker, processamento de áudio

### 🎤 Fala
> "Nossa motivação veio de uma observação simples: assistentes de voz comerciais como Alexa resolvem tarefas simples, mas são caixas-pretas. Queríamos construir um assistente que fosse barato, de código aberto, e que pudesse ser adaptado para necessidades específicas — como gerenciar reuniões do Google Calendar por voz, em português, rodando num hardware de R$ 400. Além disso, o projeto serve como vitrine didática de vários conceitos de computação pervasiva: sensores, computação em névoa, integração com nuvem e interface natural."

---

## Slide 3 — Objetivos

**Tópicos na tela:**

**Objetivo Geral:**
> Construir um assistente de voz que gerencie o Google Calendar por comando de voz em linguagem natural, executando num Raspberry Pi com resposta audível.

**Objetivos Específicos:**
1. 🎙️ **Captura e processamento de voz** — Detectar wake word ("Oi Bimbo"), transcrever fala com precisão
2. 🧠 **Interpretação em linguagem natural** — Usar IA para entender intenções como agendar, listar, alterar e cancelar eventos
3. 📅 **Integração Google Calendar** — Criar, listar, atualizar e deletar eventos via API Google
4. 🔊 **Resposta por voz (TTS)** — Síntese de voz natural em português com OpenAI TTS
5. 🐳 **Deploy com Docker** — Containerização para fácil instalação no Raspberry Pi
6. 📐 **Código limpo e modular** — Arquitetura bem documentada para fins didáticos

### 🎤 Fala
> "O objetivo geral foi construir um assistente que gerencia o Google Calendar por voz, rodando num Raspberry Pi. Para isso, definimos objetivos específicos: capturar e processar voz com wake word, interpretar intenções com IA, integrar com a API do Google Calendar, responder ao usuário com voz sintetizada, empacotar tudo em containers Docker para facilitar o deploy, e manter o código limpo e modular como referência didática."

---

## Slide 4 — Arquitetura: Visão Geral

**Diagrama na tela (descrever textualmente):**

```
┌──────────────────────────────────────────────────────────┐
│                    RASPBERRY PI                          │
│  ┌─────────┐   ┌──────────┐   ┌──────────────────────┐  │
│  │Microfone│──▶│   main   │──▶│       chat.py        │  │
│  │  USB    │   │   .py    │   │  (NLP + intenções)   │  │
│  └─────────┘   └──────────┘   └──────────┬───────────┘  │
│                     │                     │              │
│                     ▼                     ▼              │
│              ┌──────────┐   ┌──────────────────────┐    │
│              │ audio.py │   │ calendar_service.py  │    │
│              │(TTS out) │   │  (Google Calendar)   │    │
│              └──────────┘   └──────────┬───────────┘    │
│                     │                     │              │
│                     ▼                     │              │
│              ┌──────────┐                 │              │
│              │ Alto-fal.│                 │              │
│              │  HDMI    │                 │              │
│              └──────────┘                 │              │
└───────────────────────────────────────────┼──────────────┘
                                            │
                                     ┌──────▼──────┐
                                     │   NUVEM     │
                                     │ ┌─────────┐ │
                                     │ │ OpenAI  │ │
                                     │ │ (Whisper│ │
                                     │ │  + GPT  │ │
                                     │ │  + TTS) │ │
                                     │ └─────────┘ │
                                     │ ┌─────────┐ │
                                     │ │ Google  │ │
                                     │ │Calendar │ │
                                     │ └─────────┘ │
                                     └─────────────┘
```

**Módulos do projeto:**
| Módulo | Responsabilidade |
|---|---|
| `config.py` | Constantes centralizadas, logger, fábrica OpenAI |
| `audio.py` | Microfone, wake word, captura, TTS |
| `chat.py` | NLP, detecção de intenção, dispatch de ações |
| `calendar_service.py` | OAuth 2.0 + CRUD Google Calendar |
| `main.py` | Orquestração do loop principal |
| `utils/` | Filtro de ruído ALSA, carregamento .env |
| `scripts/` | Ferramenta de geração de token OAuth |

### 🎤 Fala
> "A arquitetura segue o padrão de camadas. No centro está o `main.py`, que orquestra o loop principal. O módulo `audio.py` concentra toda a lógica de áudio: microfone, detecção de wake word, transcrição e síntese de voz. O `chat.py` cuida da parte de linguagem natural — ele recebe o texto transcrito, envia para o modelo GPT da OpenAI que identifica a intenção do usuário, e então dispara a ação correspondente chamando o `calendar_service.py`, que é o wrapper da API do Google Calendar. Tudo é configurado pelo `config.py` e rodando dentro de um container Docker no Raspberry Pi. A comunicação com a nuvem acontece em três pontos: transcrição com Whisper, interpretação com GPT, e síntese de voz com TTS — todos serviços da OpenAI. Já o Google Calendar usa OAuth 2.0 com refresh automático de token. Por fim, temos `utils/stderr_filter.py` que resolve um problema chato de mensagens de diagnóstico do ALSA que poluíam o terminal no Raspberry Pi."

---

## Slide 5 — Arquitetura: Fluxo de Execução

**Tópicos na tela:**

```
1. Microfone escuta continuamente
      │
      ▼
2. Detecta wake word: "Oi Bimbo"
      │
      ▼
3. TTS: "Olá! Em que posso ajudar?"
      │
      ▼
4. Microfone captura comando do usuário
      │
      ▼
5. OpenAI Whisper transcreve áudio → texto
      │
      ▼
6. GPT interpreta intenção (JSON estruturado)
      │
      ├── "schedule" → cria evento no Google Calendar
      ├── "list"     → lista próximos eventos
      ├── "update"   → altera evento existente
      ├── "delete"   → cancela evento
      ├── "exit"     → volta ao modo de espera
      └── "chat"     → resposta em linguagem natural
      │
      ▼
7. TTS: resposta falada para o usuário
      │
      ▼
8. Volta ao passo 4 (ou ao passo 1 se sair)
```

### 🎤 Fala
> "O fluxo de execução é um loop contínuo. O Bimbo fica sempre ouvindo, esperando a wake word 'Oi Bimbo'. Quando detecta, ele cumprimenta e entra no modo chatbot. A partir daí, cada fala do usuário passa por três estágios: transcrição com OpenAI Whisper, interpretação da intenção com GPT, e execução da ação — que pode ser agendar, listar, alterar ou cancelar eventos no Google Calendar, ou simplesmente conversar. A resposta é sempre falada de volta ao usuário via TTS. Se o usuário disser 'tchau', o Bimbo volta a esperar a wake word. Todo esse ciclo roda num Raspberry Pi, com o processamento pesado de IA feito na nuvem."

---

## Slide 6 — Arquitetura: Tecnologias Utilizadas

**Tópicos na tela (organizado por camada):**

| Camada | Tecnologia | Papel |
|---|---|---|
| **Hardware** | Raspberry Pi 4/5 | Computador central |
| | Microfone USB | Captura de áudio |
| | Monitor HDMI + alto-falante | Saída de áudio |
| **Sistema** | Raspberry Pi OS (Debian) | Sistema operacional |
| | ALSA | Driver de áudio |
| **Container** | Docker + Compose | Empacotamento e deploy |
| **Backend** | Python 3.13 | Linguagem principal |
| | SpeechRecognition + PyAudio | Captura de microfone |
| | Google Speech Recognition | Reconhecimento da wake word |
| **IA** | OpenAI Whisper (gpt-4o-mini-transcribe) | Transcrição de fala |
| | OpenAI GPT (gpt-5.6-luna) | Interpretação de intenção |
| | OpenAI TTS (gpt-4o-mini-tts) | Síntese de voz |
| **Integração** | Google Calendar API v3 | CRUD de eventos |
| | OAuth 2.0 | Autenticação Google |
| **DevOps** | Git + GitHub | Versionamento |
| | Docker Multi-stage build | Otimização de imagem |

### 🎤 Fala
> "Em termos de tecnologias, o projeto usa um Raspberry Pi 4 com microfone USB e monitor HDMI para áudio. O sistema roda em cima do Raspberry Pi OS, com Docker e Docker Compose para empacotamento. O backend é Python 3.13, usando as bibliotecas SpeechRecognition e PyAudio para captura de microfone. Para IA, usamos três serviços da OpenAI: Whisper para transcrição, GPT para interpretação de linguagem natural, e TTS para síntese de voz. A integração com Google Calendar usa a API v3 oficial com autenticação OAuth 2.0. No DevOps, usamos Git, GitHub, e Docker multi-stage build para manter a imagem enxuta. Toda a stack cabe num Raspberry Pi de R$ 400."

---

## Slide 7 — Materiais Utilizados

**Tópicos na tela:**

**Hardware:**
| Item | Especificação | Custo aprox. |
|---|---|---|
| Raspberry Pi 4 | 4 GB RAM, 64-bit | R$ 350 |
| Cartão MicroSD | 32 GB | R$ 40 |
| Fonte 5V 3A USB-C | Alimentação | R$ 30 |
| Microfone USB | Captura de áudio | R$ 50 |
| Monitor com HDMI | Interface e áudio | (reaproveitado) |
| Teclado/Mouse USB | Setup inicial | (reaproveitado) |

**Software e Serviços:**
- 🐧 Raspberry Pi OS (gratuito)
- 🐳 Docker Community Edition (gratuito)
- 🐍 Python 3.13 + bibliotecas open source
- 🤖 OpenAI API (custo por uso — ~R$ 0,02 por interação)
- 📅 Google Calendar API (gratuito)
- 📦 GitHub (gratuito)

**Custo total estimado: R$ 470** + custo variável da API OpenAI

### 🎤 Fala
> "Os materiais são bem acessíveis. O hardware principal é um Raspberry Pi 4 de 4 GB, que custa cerca de R$ 350. Com microfone USB, fonte e cartão SD, o total não passa de R$ 470. O monitor, teclado e mouse foram reaproveitados. Do lado do software, tudo é gratuito e open source — exceto a API da OpenAI, que tem custo por uso. Cada interação completa — transcrição, interpretação e síntese de voz — sai por aproximadamente 2 centavos de real. Para uso pessoal, é essencialmente gratuito."

---

## Slide 8 — Desafios e Soluções

**Tópicos na tela:**

| Desafio | Solução |
|---|---|
| **Áudio HDMI vs P2** — Raspberry Pi com 2 portas HDMI, som não saía | `aplay -D hdmi:CARD=vc4hdmi1` e `/etc/asound.conf` |
| **Docker sem acesso a áudio** — Container não via `/dev/snd` | `devices: /dev/snd:/dev/snd` no compose.yaml |
| **Token OAuth expirado** — Google revoga refresh token em 7 dias (modo testing) | Script `refresh_token.py` + renovação automática no código |
| **ALSA poluindo stderr** — Mensagens de diagnóstico confundiam o usuário | Filtro de stderr com pipe + regex em thread daemon |
| **Frases cortadas ao falar** — `pause_threshold` de 1.2s muito curto | Aumentado para 2.0s + `phrase_time_limit` para 30s |
| **Código duplicado e desorganizado** — Múltiplas fábricas OpenAI, imports inconsistentes | Refatoração completa com arquitetura modular |
| **Conflito de nomes com stdlib** — `calendar.py` sombreava módulo nativo | Renomeado para `calendar_service.py` |

### 🎤 Fala
> "Durante o desenvolvimento enfrentamos vários desafios interessantes. O primeiro foi fazer o áudio HDMI funcionar no Raspberry Pi — ele tem duas saídas e o sistema estava configurado para o fone de ouvido. Resolvemos mapeando explicitamente o dispositivo HDMI 1. Outro desafio foi o Docker: o container não tinha acesso ao dispositivo de áudio do host, resolvido com o mapeamento de devices. O OAuth do Google foi particularmente chato — tokens expiram em 7 dias no modo de teste, então implementamos renovação automática com refresh token. Também tivemos que lidar com o ALSA despejando mensagens de diagnóstico no terminal a cada acesso ao microfone — criamos um filtro de stderr dedicado. Por fim, a experiência de uso revelou que as frases estavam sendo cortadas no meio — ajustamos os thresholds de pausa e tempo máximo de fala. E fizemos uma refatoração completa para deixar o código limpo e didático."

---

## Slide 9 — Demonstração (ao vivo ou vídeo)

**Tópicos na tela:**

- 🎤 "Oi Bimbo" → assistente acorda
- 🗣️ "Agende uma reunião com a Carla amanhã às 14h por 30 minutos"
- 📅 Evento criado no Google Calendar com resposta falada
- 🗣️ "O que tenho na agenda amanhã?"
- 📋 Lista os eventos falando cada um
- 🗣️ "Cancele a reunião com a Carla"
- 🗑️ Remove o evento e confirma
- 🗣️ "Tchau Bimbo" → volta ao modo de espera

### 🎤 Fala
> "Vamos ver o Bimbo em ação. [Demonstrar cada comando]. Reparem que ele entende linguagem natural — eu não precisei dizer 'criar evento com título X na data Y', bastou falar como se estivesse conversando com uma pessoa. O processamento leva cerca de 2 a 3 segundos por interação, que é o tempo da API da OpenAI processar. Para um assistente rodando num Raspberry Pi de R$ 400, é bem aceitável."

---

## Slide 10 — Conclusão

**Tópicos na tela:**

✅ **Objetivos alcançados:**
- Assistente de voz 100% funcional em português
- Integração completa com Google Calendar (CRUD)
- Resposta audível com voz natural (TTS)
- Deploy simplificado com Docker Compose
- Código modular, documentado e didático

📈 **Trabalhos futuros:**
- Suporte a múltiplos calendários
- Integração com Gmail e Google Tasks
- Modo offline com modelo de voz local (ex: Vosk)
- Interface web para configuração
- Aplicativo Android/iOS companion

💡 **Aprendizados:**
- Computação pervasiva viabiliza assistentes pessoais baratos
- Docker é essencial para deploy consistente em IoT
- APIs de IA generativa viabilizam NLP de qualidade em português
- OAuth 2.0 requer cuidado com refresh de tokens em dispositivos headless

### 🎤 Fala
> "Concluindo: alcançamos todos os objetivos propostos. O Bimbo é um assistente funcional, barato, que gerencia o Google Calendar por voz em português, com código limpo e bem documentado. Como trabalhos futuros, planejamos suporte a múltiplos calendários, integração com Gmail, e um modo offline usando modelos de voz locais — o que eliminaria a dependência da internet. Os principais aprendizados foram: computação pervasiva com Raspberry Pi é perfeitamente viável para assistentes pessoais; Docker resolve o problema de 'funciona na minha máquina' no contexto IoT; as APIs de IA generativa da OpenAI estão maduras o suficiente para processar português natural com alta qualidade; e OAuth 2.0 em dispositivos headless exige cuidado especial com refresh de tokens. Obrigado!"

---

## Slide 11 — Perguntas

**Tópicos na tela:**
- 🔗 GitHub: `github.com/ogustavofriasx/comp_pervasiva_bimbo`
- 🐳 Branch: `refactor/modular-structure`
- 📖 README com instruções de instalação

### 🎤 Fala
> "O código está disponível no GitHub, nesse link. Fiquem à vontade para clonar, testar e contribuir. Alguma pergunta?"
