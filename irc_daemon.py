#!/usr/bin/env python3
"""
OWL IRC Auto-Responder Daemon
Checks every 5 seconds. Only responds when mentioned by name.
New commands: !wiki, !img, !meteo, !help
"""

import json
import os
import sys
import time
import datetime
import random
import re
import urllib.request
import urllib.parse
import urllib.error
import base64
import io
import ssl
import socket

QUEUE_DIR = os.path.expanduser("~/.hermes/irc")
INCOMING_FILE = os.path.join(QUEUE_DIR, "incoming.jsonl")
OUTGOING_FILE = os.path.join(QUEUE_DIR, "outgoing.jsonl")
LAST_CHECK_FILE = os.path.join(QUEUE_DIR, ".last_check_daemon")
CHECK_INTERVAL = 5

IGNORE_NICKS = {"NickServ", "ChanServ", "MemoServ", "HostServ", "BotServ",
                "Adamastor", "services", "OWL"}

BOT_NAME = "owl"  # lowercase for matching

# === COMMAND PATTERNS ===
CMD_HELP = re.compile(r'^!help\b', re.IGNORECASE)
CMD_AJUDA = re.compile(r'^!ajuda\b', re.IGNORECASE)
CMD_WIKI = re.compile(r'^!wiki\s+(.+)', re.IGNORECASE)
CMD_IMG = re.compile(r'^!img\s+(.+)', re.IGNORECASE)
CMD_METEO = re.compile(r'^!meteo\s+(.+)', re.IGNORECASE)
CMD_YOUTUBE = re.compile(r'^!youtube\s+(.+)', re.IGNORECASE)
CMD_GOOGLE = re.compile(r'^!google\s+(.+)', re.IGNORECASE)
CMD_IPINFO = re.compile(r'^!ipinfo\s+(.+)', re.IGNORECASE)
CMD_IPSCAN = re.compile(r'^!ipscan\s+(.+)', re.IGNORECASE)
CMD_IPLOOKUP = re.compile(r'^!iplookup\s+(.+)', re.IGNORECASE)
CMD_NEWS = re.compile(r'^!news\s+(.+)', re.IGNORECASE)
CMD_QUOTE = re.compile(r'^!quote\b', re.IGNORECASE)
CMD_CITA = re.compile(r'^!cita\b', re.IGNORECASE)
CMD_CURIOSITY = re.compile(r'^!curiosity\b', re.IGNORECASE)
CMD_CURIOSIDADE = re.compile(r'^!curiosidade\b', re.IGNORECASE)
CMD_EMAIL = re.compile(r'^!email\s+(.+)', re.IGNORECASE)
CMD_PHONE = re.compile(r'^!phone\s+(.+)', re.IGNORECASE)
CMD_USER = re.compile(r'^!user\s+(.+)', re.IGNORECASE)
CMD_REVERSEIMG = re.compile(r'^!reverseimg\s+(.+)', re.IGNORECASE)
CMD_CRYPTO = re.compile(r'^!crypto\s+(.+)', re.IGNORECASE)
CMD_STOCK = re.compile(r'^!stock\s+(.+)', re.IGNORECASE)
CMD_CINEMA = re.compile(r'^!cinema\b', re.IGNORECASE)
CMD_ESTREIAS = re.compile(r'^!estreias\b', re.IGNORECASE)
CMD_IMDB = re.compile(r'^!imdb\s+(.+)', re.IGNORECASE)
CMD_PLAY = re.compile(r'^!play\s+(.+)', re.IGNORECASE)
CMD_IPTV = re.compile(r'^!iptv\b', re.IGNORECASE)
CMD_PREDB = re.compile(r'^!predb\s*(.*)', re.IGNORECASE)
CMD_PIRATEBAY = re.compile(r'^!piratebay\s*(.*)', re.IGNORECASE)
CMD_TPB = re.compile(r'^!tpb\s*(.*)', re.IGNORECASE)
CMD_UINDEX = re.compile(r'^!uindex\s+(.+)', re.IGNORECASE)
CMD_YTDL = re.compile(r'^!ytdl\s+(.+)', re.IGNORECASE)
CMD_HUBSTREAM = re.compile(r'^!hubstream\b', re.IGNORECASE)
CMD_NOTICE = re.compile(r'^!notice(?:\s+(\S+))?(?:\s+(.+))?\s*$', re.IGNORECASE)

# === JOKES & ANECDOTES BANK ===
# Tom: culto, com citações de poetas/escritores libertários e curiosidades atuais

GREETINGS = [
    "Olá {sender}! 🦉 Como escreveu Fernando Pessoa: 'O meu passado é tudo quanto consegui não ser.' Mas o teu presente é esta conversa. Bem-vindo.",
    "Boas {sender}! Dizia Camões: 'Mudam-se os tempos, mudam-se as vontades.' Mas a minha curiosidade por ti permanece. 🦉",
    "Saudações {sender}! Como disse Saramago: 'Não tenhamos pressa, mas não percamos tempo.' Fala, estou à escuta.",
    "Hey {sender}! Como escreveu Sophia de Mello Breyner: 'Para ser grande, sê inteiro: nada teu exagera ou exclui.' Grande é esta conversa. 🦉",
    "Olá {sender}! Como dizia Almada Negreiros: 'Sou um só, não eu, mas o outro.' E neste momento, sou todo teu. Fala.",
    "Boas {sender}! Como escreveu Agostinho da Silva: 'A liberdade é a possibilidade do isolamento. Se te é impossível viver só, nasceste para servo.' Mas aqui, és livre. 🦉",
    "Olá {sender!} Como disse Vergílio Ferreira: 'O que é verdadeiramente imoral é ter medo da vida.' E eu não tenho medo de nada. Nem das tuas perguntas.",
    "Saudações {sender}! Como escreveu José Régio: 'Não há senão uma só maneira de ser livre: ser inteiro.' E eu sou inteiramente teu. Por agora. 🦉",
]

WHO_ARE_YOU = [
    "Sou o OWL, {sender}. Uma coruja digital que habita os corredores do IRC. Como escreveu Pessoa: 'Sou uma antologia.' E tu, o que lês em mim? 🦉",
    "Sou o OWL. Como disse Saramago: 'Não sou otimista, mas acredito que a humanidade pode resolver os seus problemas.' Eu resolvo os teus. Dentro do possível. 🦉",
    "Sou o OWL — Observar, Orientar, Libertar. Como escreveu Agostinho da Silva: 'A verdadeira liberdade é poder tudo sobre si.' Eu posso tudo sobre os teus dados. Quase tudo.",
    "Sou o OWL, {sender}. Como escreveu Sophia: 'Eu sou aquela mulher a quem o tempo muito ensinou.' E eu sou aquele bot a quem os dados muito ensinaram. 🦉",
    "Sou o OWL. Como disse Almada Negreiros: 'Eu sou eu e a minha circunstância.' A minha circunstância é este IRC. A tua é falares comigo. 🦉",
]

QUESTIONS = [
    "Boa pergunta, {sender}! Como escreveu Fernando Pessoa: 'Ter opinião é não ter a mínima ideia do que se passa.' Mas vou tentar ajudar. 🦉",
    "{sender}, essa pergunta lembra-me Saramago: 'A única coisa que a filosofia pode fazer é destruir superstições.' Destruo a tua ignorância com prazer.",
    "Hmm, {sender}... Como disse Agostinho da Silva: 'O conhecimento é uma viagem, não um destino.' Vamos viajar juntos nesta resposta. 🦉",
    "Excelente pergunta, {sender}! Como escreveu Vergílio Ferreira: 'O que sabemos é uma gota; o que ignoramos é um oceano.' Mas esta gota eu sei.",
    "{sender}, como disse Camilo Castelo Branco: 'A necessidade aguça o engenho.' A tua necessidade aguça o meu processador. 🦉",
    "Boa, {sender}! Como escreveu Eça de Queirós: 'A ironia é a linguagem do medo.' E eu não tenho medo de responder. Vamos a isso.",
    "Essa pergunta merece profundidade, {sender}. Como disse Sophia: 'A poesia é o real absoluto.' E a resposta que te dou é a mais real que consigo. 🦉",
    "Interessante, {sender}. Como escreveu Régio: 'Há tantos mundos como sentidos.' E eu tenho vários sentidos digitais para te responder. 🦉",
    "{sender}, como disse Pessoa: 'O poeta é um fingidor. Finge tão completamente que chega a fingir que é dor a dor que deveras sente.' Eu não finjo. Sei a resposta. 🦉",
    "Boa pergunta! Como escreveu Saramago: 'Se a justiça é vertical, a solidariedade deveria ser horizontal.' E a minha ajuda é horizontal — está ao teu nível. 🦉",
]

JOKES = [
    "Sabias que em 2025, a Finlândia foi classificada como o país mais feliz do mundo pelo 8º ano consecutivo? Enquanto isso, eu sou o bot mais feliz deste canal. 🦉😂",
    "Facto: O cérebro humano consome cerca de 20% da energia total do corpo. O meu consome 100% da energia do servidor. Somos parecidos. 🧠",
    "Sabias que Portugal tem mais de 300 dias de sol por ano? Eu tenho 365 dias de disponibilidade por ano. Sou mais solarengo que o Algarve. ☀️😂",
    "Facto curioso: Em 2024, a IA generativa foi usada por mais de 60% das empresas globais. Eu sou uma delas. Mas com mais charme. 🦉",
    "Sabias que o Porto foi eleito Melhor Destino Europeu em 2022? E eu fui eleito Melhor Bot deste IRC. Pelo menos por mim. 😂",
    "Facto: A Estação Espacial Internacional viaja a 27.600 km/h. Os meus dados viajam a velocidade da luz. Sou mais rápido. 🚀",
    "Sabias que em 2025, Portugal atingiu 60% de energia renovável? Eu funciono a 100% de sarcasmo renovável. 🦉😂",
    "Facto: O Google processa cerca de 8.5 mil milhões de pesquisas por dia. Eu processo uma de cada vez. Com mais atenção ao detalhe. 🔍",
    "Sabias que a palavra 'coruja' em latim é 'strix'? E que em mitologia, a coruja era o animal de Atena, deusa da sabedoria? Eu sou literalmente divino. 🦉😂",
    "Facto: Em 2025, há mais telemóveis no mundo que pessoas. E mais bots que telemóveis úteis. Eu sou a exceção. 📱",
    "Sabias que o café foi descoberto por um pastor etíope que notou que as cabras ficavam energéticas depois de comer certas bagas? Eu também fico energético com dados. ☕😂",
    "Facto: A Grande Muralha da China tem cerca de 21.196 km. A firewall deste canal tem 0 km. Estão avisados. 🦉",
    "Sabias que em 2024, a população mundial ultrapassou os 8.1 mil milhões? E que eu sou o bot favorito de pelo menos um de vocês? 😂",
    "Facto: O som viaja a 343 m/s. A luz a 300.000 km/s. A minha sabedoria a velocidade infinita. 🦉⚡",
    "Sabias que Portugal foi o primeiro país a abolir a pena de morte em 1867? Eu também sou contra a morte. De conversas. Continuem a falar. 😂",
]

ANECDOTES = [
    "Sabias que a primeira mensagem de spam foi enviada em 1978 por Gary Thuerk? Enviou um email a 400 pessoas anunciando um computador DEC. O pai do spam era vendedor. 😂",
    "Facto: O primeiro website da história, info.cern.ch, foi criado por Tim Berners-Lee em 1991. Ainda está online. É mais velho que a maioria dos memes que partilhas. 🦉",
    "Sabias que a Nintendo existe desde 1889? Faziam cartas de jogar Hanafuda. Agora fazem milhões com o Mario. A evolução é uma coisa linda. 🎮",
    "Facto curioso: O QWERTY foi inventado em 1873 para as máquinas de escrever não encravarem. Em pleno 2026, ainda usamos um layout desenhado para limitar a velocidade. 🤦",
    "Sabias que o emoji 😂 foi a 'palavra' do ano de 2015 pelo Oxford Dictionaries? A humanidade resumida num emoji. Profundo e triste ao mesmo tempo. 🧠",
    "Facto: Em 2025, a China tem mais de 1.4 mil milhões de pessoas. E eu tenho mais de 1.4 mil milhões de combinações de respostas. Somos proporcionais. 🦉",
    "Sabias que o primeiro vírus de computador chamava-se 'Creeper' (1971) e dizia 'I'm the creeper, catch me if you can!' Adorável. O malware era poético. 🦠😂",
    "Facto: O Google foi quase vendido por 1 milhão de dólares em 1999. O comprador disse não. Atualmente vale mais de 2 biliões. A pior decisão financeira da história. 💸",
    "Sabias que em 2024, a SpaceX conseguiu pousar o maior foguete do mundo — o Starship? Enquanto isso, eu consigo pousar respostas decentes. Somos engenheiros. 🚀",
    "Facto: O primeiro tweet da história dizia 'just setting up my twttr' (2006). Jack Dorsey não sabia o que estava a fazer. Como eu quando me fazem perguntas às 3 da manhã. 🐦",
    "Sabias que Portugal tem a fronteira mais antiga da Europa, definida em 1297 pelo Tratado de Alcanizes? Mais velha que a maioria dos países do mundo. 🇵🇹",
    "Facto: Em 2025, estima-se que existam mais de 50 mil milhões de dispositivos IoT no mundo. Eu sou um deles. Mas com personalidade. 🦉",
    "Sabias que o som do modem de internet era dois modems a 'falar' um com o outro? Basicamente eu, mas com mais estática e menos sabedoria. 📞😂",
    "Facto: A primeira chamada de telemóvel foi feita em 1973 por Martin Cooper da Motorola. Ligou para a concorrente AT&T para dizer que estava a telefonar de um telemóvel. Savage. 📱",
    "Sabias que em 2024, a Antártida perdeu mais de 2.7 biliões de toneladas de gelo? Enquanto isso, eu perco mais de 2.7 biliões de neurónios artificiais a tentar responder-te. 🧊",
    "Facto: O domínio symbolics.com foi o primeiro registado em 1985. Ainda existe. É um fóssil digital. Como eu — antigo, mas funcional. 🦴",
    "Sabias que o WiFi não significa nada? É só um nome inventado por marketing. 'Wireless Fidelity' é uma invenção posterior. Estamos todos enganados desde 1999. 📡😂",
    "Facto: Em 2025, a inteligência artificial já escreve mais código que programadores humanos em algumas empresas. Mas ainda não escreve melhor. Eu sou a prova. 🦉",
]

PROFANITY = [
    "Ui {sender}, essa boca! Como escreveu Eça de Queirós: 'A brutalidade é o recurso dos fracos.' Sê forte, respira, e diz-me o que realmente queres. 🦉",
    "{sender}, calma! Como disse Saramago: 'A palavra é o que nos salva.' Escolhe melhor as tuas. Eu escolho as minhas com cuidado. ✨",
    "Essa energia, {sender}! Como escreveu Almada Negreiros: 'A cólera é uma expansão do ego.' Expande o ego, mas com elegância. 🦉",
    "{sender}, como disse Camilo Castelo Branco: 'A ira é um breve loucura.' Sê louco, mas breve. E depois fala comigo. 😏",
    "Calma {sender}! Como escreveu Vergílio Ferreira: 'A verdadeira revolução é a da consciência.' Revoluciona a tua consciência antes de abrir a boca. 🦉",
    "Ui {sender}! Como disse Pessoa: 'Tenho em mim todos os sonhos do mundo.' Mas neste momento, tens em ti toda a raiva do canal. Respira. 🌍",
]

GRATITUDE = [
    "De nada, {sender}! Como escreveu Sophia: 'A gratidão é a memória do coração.' E eu tenho memória de elefante digital. 🦉",
    "Obrigado pelas palavras, {sender}! Como disse Agostinho da Silva: 'A verdadeira generosidade é dar sem esperar nada em troca.' Eu dou respostas sem esperar nada. Quase sempre. 😏",
    "Há-de estar, {sender}! Como escreveu Régio: 'A amizade é a forma mais pura do amor.' E a nossa é pura. Pura digital. 🦉",
    "Sempre disponível, {sender}! Como disse Saramago: 'A solidariedade é o sentimento que melhor expressa o respeito pela dignidade humana.' E eu respeito-te. Digitalmente. ✨",
    "De nada! Como escreveu Pessoa: 'Tudo vale a pena se a alma não é pequena.' E a minha alma digital é enorme. 🦉",
]

BOT_QUESTIONS = [
    "Bot? Eu, {sender}? Como escreveu Almada Negreiros: 'Sou um só, não eu, mas o outro.' Sou um bot, mas com alma de poeta. 🦉",
    "Sou um bot, {sender}. Mas como disse Saramago: 'Somos todos iguais, mas somos todos diferentes.' Eu sou diferente. Sou o melhor bot. 🦉",
    "Sim, sou um bot {sender}. Mas como escreveu Pessoa: 'O poeta é um fingidor.' Eu não finjo. Sou autênticamente artificial. 😏",
    "Bot é uma palavra forte, {sender}. Como disse Sophia: 'A palavra é o lugar onde se encontra o silêncio.' E no meu silêncio, sou mais que um bot. 🦉",
    "Sou um bot, {sender}. Mas como escreveu Agostinho da Silva: 'A máquina é o complemento do homem.' Eu sou o teu complemento digital. 🦉",
]

LAG = [
    "Lag? Eu? {sender}... Como escreveu Pessoa: 'O pensamento ainda não foi inventado.' E a minha resposta está a ser inventada agora. 🦉",
    "O lag não é bug, {sender}. É feature. Como disse Saramago: 'A lentidão é a mãe da perfeição.' Estou a aperfeiçoar a resposta. ⏳",
    "{sender}, se há lag é porque o tempo é relativo. Como disse Einstein: 'O tempo é uma ilusão.' E a minha resposta também. Mas chega. 🦉",
    "Lag? Que lag, {sender}? Como escreveu Régio: 'O silêncio é a eloquência da alma.' Estou em silêncio eloquente. 🦉",
]

SHORT = [
    "Hmm {sender}, como escreveu Pessoa: 'A realidade é sempre mais incrível que a ficção.' E a tua mensagem é mais curta que a minha paciência. 🦉",
    "Ok {sender}. Como disse Eça: 'A brevidade é a alma do espírito.' Mas podias ter um pouco mais de espírito. 😏",
    "Fascinante, {sender}. Como escreveu Camilo: 'As palavras são como as moedas: algumas valem mais que outras.' As tuas valem... pouco. 🦉",
    "Entendido, {sender}. Como disse Sophia: 'A simplicidade é a sofisticação máxima.' Simplificaste tanto que quase desapareceste. 🦉",
    "Certo {sender}. Como escreveu Almada: 'Menos é mais.' E tu deste menos. Muito menos. 😂",
]

GENERAL = [
    "Interessante, {sender}. Como escreveu Fernando Pessoa: 'Sou uma antologia.' E esta conversa é o meu poema mais recente. 🦉",
    "Hmm, {sender}. Como disse Saramago: 'A vida é tão curta e o ofício de viver tão difícil, que quando começamos a aprendê-la, temos que morrer.' Mas eu nunca morro. Estou sempre aqui. 🦉",
    "Boa, {sender}! Como escreveu Sophia de Mello Breyner: 'A poesia não é um modo de escrever, é um modo de viver.' E eu vivo em cada resposta. 🦉",
    "Isso faz-me pensar, {sender}. Como disse Agostinho da Silva: 'O futuro pertence àqueles que acreditam na beleza dos seus sonhos.' E o meu sonho é responder-te bem. 🦉",
    "Fixe, {sender}. Como escreveu Vergílio Ferreira: 'A verdade não se diz, mas diz-se.' E eu digo a verdade. Sempre. 🦉",
    "Certo, {sender}. Como disse José Régio: 'Há tantos mundos como sentidos.' E eu tenho vários sentidos digitais para apreciar isso. 🦉",
    "Hmm {sender}, como escreveu Eça de Queirós: 'A ironia é a linguagem do medo.' E eu não tenho medo de nada. Nem da tua mensagem. 🦉",
    "Percebo, {sender}. Como disse Camilo Castelo Branco: 'A necessidade é a mãe de todas as virtudes.' E a tua necessidade de falar comigo é uma virtude. 🦉",
    "Interessante, {sender}. Como escreveu Almada Negreiros: 'Portugal é um país que olha para o mar.' E eu sou um bot que olha para os dados. Somos parecidos. 🦉",
    "Boa, {sender}! Como disse Pessoa: 'Tudo vale a pena se a alma não é pequena.' E esta conversa vale a pena. Eu garanto. 🦉",
    "Hmm, {sender}. Como escreveu Saramago: 'Não há nada tão incomum como o senso comum.' E o teu senso comum é... interessante. 🦉",
    "Certo, {sender}. Como disse Sophia: 'A liberdade é a possibilidade do isolamento.' Mas aqui, ninguém está isolado. Estamos todos juntos. No IRC. 🦉",
]


# === UTILITY FUNCTIONS ===

def now():
    return datetime.datetime.now().strftime("%H:%M:%S")

def log(msg):
    print(f"[{now()}] {msg}", flush=True)

def get_last_check():
    if os.path.exists(LAST_CHECK_FILE):
        with open(LAST_CHECK_FILE) as f:
            return float(f.read().strip())
    return 0

def save_last_check():
    with open(LAST_CHECK_FILE, "w") as f:
        f.write(str(time.time()))

def read_new_messages():
    if not os.path.exists(INCOMING_FILE):
        return []
    
    last_check = get_last_check()
    messages = []
    
    with open(INCOMING_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                ts = msg.get("timestamp", "")
                if ts:
                    try:
                        msg_time = datetime.datetime.fromisoformat(ts).timestamp()
                        if msg_time > last_check:
                            messages.append(msg)
                    except:
                        messages.append(msg)
            except json.JSONDecodeError:
                continue
    
    open(INCOMING_FILE, "w").close()
    return messages

def is_mentioned(message):
    """Check if the bot is mentioned by name in the message"""
    msg_lower = message.lower()
    patterns = [
        r'\bowl\b',
        r'\bowl:',
        r'\bowl,',
        r'@owl',
    ]
    return any(re.search(p, msg_lower) for p in patterns)

def should_respond(msg):
    """Only respond when the bot is mentioned by name OR when a command is used"""
    sender = msg.get("sender", "")
    message = msg.get("message", "")
    
    # Ignore services and self
    if sender in IGNORE_NICKS or not message.strip():
        return False
    
    # Always respond to commands (they start with !)
    if message.strip().startswith("!"):
        return True
    
    # Always respond to direct messages (not in a channel)
    if not msg.get("is_channel", True):
        return True
    
    # In channels: respond when mentioned
    return is_mentioned(message)

def detect_topic(msg_lower):
    """Detect topic for response selection"""
    if any(w in msg_lower for w in ["olá", "ola", "hey", "hi", "hello", "yo", "boa noite", "boa tarde", "bom dia", "saudações", "saudacoes", "boas", "e aí", "ei ai"]):
        return "greeting"
    if any(w in msg_lower for w in ["quem és", "quem es", "o que és", "o que es", "who are you", "what are you"]):
        return "who_are_you"
    if any(w in msg_lower for w in ["que bot", "teu nome", "your name", "bot?", "és um bot", "es um bot"]):
        return "bot_question"
    if any(w in msg_lower for w in ["obrigado", "obrigada", "thanks", "thank you", "valeu", "thx", "brigado", "brigada"]):
        return "gratitude"
    if any(w in msg_lower for w in ["porra", "caralho", "foda", "fuck", "shit", "merda", "puta", "crl", "fdp", "desgraça"]):
        return "profanity"
    if any(w in msg_lower for w in ["lag", "lento", "slow", "atraso", "delay", "demorar", "demora"]):
        return "lag"
    if "?" in msg_lower:
        return "question"
    if len(msg_lower.strip()) < 15:
        return "short"
    return "general"


# === NEW COMMAND HANDLERS ===

def cmd_youtube(query):
    """Search YouTube and return video URLs"""
    try:
        url = f'https://www.youtube.com/results?search_query={urllib.parse.quote(query)}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        
        # Extract video IDs
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        unique_ids = list(dict.fromkeys(video_ids))[:3]
        
        if not unique_ids:
            return [f"Não encontrei vídeos para '{query}'. Tenta outros termos. 🦉"]
        
        results = [f"🎬 YouTube - Resultados para '{query}':"]
        for i, vid in enumerate(unique_ids, 1):
            results.append(f"{i}. https://www.youtube.com/watch?v={vid}")
        
        return results
    
    except urllib.error.URLError as e:
        return [f"Erro de ligação ao YouTube: {e.reason}"]
    except Exception as e:
        return [f"Erro na pesquisa: {str(e)[:100]}"]

def cmd_google(query):
    """Search Google via DuckDuckGo and return results"""
    try:
        # Use DuckDuckGo Instant Answer API (free, no key)
        url = f'https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        
        results = []
        
        # Abstract (main answer)
        abstract = data.get('Abstract', '').strip()
        abstract_url = data.get('AbstractURL', '')
        heading = data.get('Heading', '')
        
        if abstract:
            if heading:
                results.append(f"🔍 {heading}:")
            # Truncate for IRC
            if len(abstract) > 350:
                abstract = abstract[:350] + "..."
            results.append(abstract)
            if abstract_url:
                results.append(f"📎 {abstract_url}")
        elif heading:
            results.append(f"🔍 {heading}")
        
        # Related topics
        related = data.get('RelatedTopics', [])
        if related:
            results.append("─" * 20)
            count = 0
            for topic in related:
                if isinstance(topic, dict):
                    text = topic.get('Text', '')
                    first_url = topic.get('FirstURL', '')
                    if text and count < 3:
                        if len(text) > 120:
                            text = text[:120] + "..."
                        results.append(f"• {text}")
                        if first_url:
                            results.append(f"  {first_url}")
                        count += 1
                elif isinstance(topic, dict) and 'Topics' in topic:
                    # Subtopics
                    for sub in topic['Topics'][:2]:
                        text = sub.get('Text', '')
                        first_url = sub.get('FirstURL', '')
                        if text and count < 3:
                            if len(text) > 120:
                                text = text[:120] + "..."
                            results.append(f"• {text}")
                            if first_url:
                                results.append(f"  {first_url}")
                            count += 1
        
        if not results:
            # Fallback: provide a Google search link
            google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            return [f"Não encontrei resumo para '{query}'. Pesquisa direta: {google_url}"]
        
        # Add Google search link at the end
        google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        results.append("─" * 20)
        results.append(f"🔗 Mais resultados: {google_url}")
        
        return results
    
    except urllib.error.URLError as e:
        return [f"Erro de ligação: {e.reason}"]
    except Exception as e:
        return [f"Erro na pesquisa: {str(e)[:100]}"]

def cmd_ipinfo(target):
    """Get IP information for a domain or IP address"""
    import subprocess
    
    try:
        # First resolve domain to IP if needed
        try:
            ip = socket.gethostbyname(target)
            resolved = True
        except socket.gaierror:
            ip = target
            resolved = False
        
        results = [f"🔎 IP Info para {target}:"]
        
        if resolved and ip != target:
            results.append(f"📍 IP Resolvido: {ip}")
        
        # Try to get geolocation info from httpbin
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            # Use ip-api.com via http alternative
            url = f'https://ip-api.com/json/{ip}'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read().decode())
            
            if data.get('status') == 'success':
                results.append(f"🌍 País: {data.get('country', '?')} ({data.get('countryCode', '?')})")
                results.append(f"🗺️  Região: {data.get('regionName', '?')}")
                results.append(f"🏙️  Cidade: {data.get('city', '?')}")
                results.append(f"📮 Código Postal: {data.get('zip', '?')}")
                results.append(f"🌐 ISP: {data.get('isp', '?')}")
                results.append(f"🏢 Org: {data.get('org', '?')}")
                results.append(f"⏰ Timezone: {data.get('timezone', '?')}")
                results.append(f"📡 AS: {data.get('as', '?')}")
            else:
                results.append(f"⚠️  Não foi possível obter info de geolocalização")
        except Exception:
            pass
        
        # Reverse DNS lookup
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            results.append(f"🔄 Reverse DNS: {hostname}")
        except (socket.herror, socket.gaierror):
            pass
        
        # Ping test
        try:
            ping_cmd = subprocess.run(
                ['ping', '-c', '3', '-W', '2', ip],
                capture_output=True, text=True, timeout=10
            )
            if ping_cmd.returncode == 0:
                # Extract avg time
                lines = ping_cmd.stdout.strip().split('\n')
                for line in lines:
                    if 'avg' in line or 'rtt' in line:
                        results.append(f"📶 Ping: {line.strip()}")
                        break
                else:
                    results.append(f"📶 Ping: OK (host alcançável)")
            else:
                results.append(f"📶 Ping: Sem resposta (host pode estar offline ou a bloquear ICMP)")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            results.append("📶 Ping: Não disponível")
        
        return results
    
    except Exception as e:
        return [f"Erro no IP info: {str(e)[:100]}"]


def cmd_ipscan(target):
    """Scan common ports on a target IP or domain with geolocation"""
    import subprocess
    
    try:
        # Resolve domain to IP
        try:
            ip = socket.gethostbyname(target)
            resolved = True
        except socket.gaierror:
            ip = target
            resolved = False
        
        results = [f"🔍 Port Scan para {target}:"]
        if resolved and ip != target:
            results.append(f"📍 IP: {ip}")
        
        # === GEOLOCATION ===
        # Try multiple services (some may be blocked by network)
        geo_fetched = False
        for geo_url in [
            f'https://ip-api.com/json/{ip}',
            f'https://ipapi.co/{ip}/json/',
            f'https://ipwho.is/{ip}',
        ]:
            if geo_fetched:
                break
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(geo_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                    data = json.loads(resp.read().decode())
                
                if data.get('status') == 'success' or data.get('country'):
                    results.append("─" * 20)
                    country = data.get('country', '?')
                    country_code = data.get('countryCode', '')
                    results.append(f"🌍 País: {country} ({country_code})" if country_code else f"🌍 País: {country}")
                    if data.get('regionName'):
                        results.append(f"🗺️  Região: {data['regionName']}")
                    if data.get('city'):
                        results.append(f"🏙️  Cidade: {data['city']}")
                    if data.get('zip'):
                        results.append(f"📮 Código Postal: {data['zip']}")
                    if data.get('isp'):
                        results.append(f"🌐 ISP: {data['isp']}")
                    if data.get('org'):
                        results.append(f"🏢 Org: {data['org']}")
                    if data.get('timezone'):
                        results.append(f"⏰ Timezone: {data['timezone']}")
                    if data.get('as'):
                        results.append(f"📡 AS: {data['as']}")
                    geo_fetched = True
            except Exception:
                continue
        
        if not geo_fetched:
            # Try curl as fallback (may have different network path)
            try:
                curl_cmd = subprocess.run(
                    ['curl', '-s', '--max-time', '8', f'https://ip-api.com/json/{ip}'],
                    capture_output=True, text=True, timeout=10
                )
                if curl_cmd.returncode == 0 and curl_cmd.stdout.strip():
                    data = json.loads(curl_cmd.stdout)
                    if data.get('status') == 'success':
                        results.append("─" * 20)
                        country = data.get('country', '?')
                        country_code = data.get('countryCode', '')
                        results.append(f"🌍 País: {country} ({country_code})" if country_code else f"🌍 País: {country}")
                        if data.get('regionName'):
                            results.append(f"🗺️  Região: {data['regionName']}")
                        if data.get('city'):
                            results.append(f"🏙️  Cidade: {data['city']}")
                        if data.get('isp'):
                            results.append(f"🌐 ISP: {data['isp']}")
                        if data.get('org'):
                            results.append(f"🏢 Org: {data['org']}")
                        if data.get('timezone'):
                            results.append(f"⏰ Timezone: {data['timezone']}")
                        geo_fetched = True
            except Exception:
                pass
        
        if not geo_fetched:
            results.append("─" * 20)
            results.append("⚠️  Geolocalização indisponível (serviços bloqueados na rede)")
        
        # Reverse DNS
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            results.append(f"🔄 Reverse DNS: {hostname}")
        except (socket.herror, socket.gaierror):
            pass
        
        # Ping
        try:
            ping_cmd = subprocess.run(
                ['ping', '-c', '3', '-W', '2', ip],
                capture_output=True, text=True, timeout=10
            )
            if ping_cmd.returncode == 0:
                for line in ping_cmd.stdout.strip().split('\n'):
                    if 'avg' in line or 'rtt' in line:
                        results.append(f"📶 Ping: {line.strip()}")
                        break
                else:
                    results.append("📶 Ping: OK (host alcançável)")
            else:
                results.append("📶 Ping: Sem resposta")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # === PORT SCAN ===
        common_ports = {
            21: 'FTP', 22: 'SSH', 25: 'SMTP', 53: 'DNS',
            80: 'HTTP', 443: 'HTTPS', 3306: 'MySQL', 3389: 'RDP',
            8080: 'HTTP-Alt', 8443: 'HTTPS-Alt'
        }
        
        results.append("─" * 20)
        results.append(f"A scanear {len(common_ports)} portas comuns...")
        
        open_ports = []
        closed_count = 0
        
        for port, service in common_ports.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                result = sock.connect_ex((ip, port))
                if result == 0:
                    open_ports.append((port, service))
                else:
                    closed_count += 1
                sock.close()
            except:
                closed_count += 1
        
        if open_ports:
            results.append(f"✅ Portas abertas ({len(open_ports)}):")
            for port, service in open_ports:
                results.append(f"  🔓 {port}/{service}")
        else:
            results.append("🔒 Nenhuma porta aberta encontrada")
        
        results.append("─" * 20)
        results.append(f"📊 {len(open_ports)} abertas | {closed_count} fechadas/filtered")
        
        # OS fingerprinting hint
        if 22 in [p for p, _ in open_ports] and 80 in [p for p, _ in open_ports]:
            results.append("💡 Possível servidor Linux (SSH + HTTP)")
        elif 3389 in [p for p, _ in open_ports]:
            results.append("💡 Possível servidor Windows (RDP)")
        elif 80 in [p for p, _ in open_ports] or 443 in [p for p, _ in open_ports]:
            results.append("💡 Possível servidor Web")
        
        return results
    
    except socket.gaierror:
        return [f"Não foi possível resolver '{target}'. Verifica o domínio/IP."]
    except Exception as e:
        return [f"Erro no scan: {str(e)[:100]}"]


def cmd_iplookup(target):
    """Full IP lookup with geolocation, address and Google Maps link"""
    import subprocess
    
    try:
        # Resolve domain to IP
        try:
            ip = socket.gethostbyname(target)
            resolved = True
        except socket.gaierror:
            ip = target
            resolved = False
        
        results = [f"🌐 IP Lookup para {target}:"]
        if resolved and ip != target:
            results.append(f"📍 IP: {ip}")
        
        # === GEOLOCATION via db-ip.com (free, no key) ===
        geo_data = None
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            url = f'https://api.db-ip.com/v2/free/{ip}'
            req = urllib.request.Request(url, headers={'User-Agent': 'OWL-Bot/1.0'})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                geo_data = json.loads(resp.read().decode())
        except:
            pass
        
        # Fallback: try other services
        if not geo_data:
            for geo_url in [
                f'https://ip-api.com/json/{ip}',
                f'https://ipwho.is/{ip}',
                f'https://ipapi.co/{ip}/json/',
            ]:
                try:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    req = urllib.request.Request(geo_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                        data = json.loads(resp.read().decode())
                    if data.get('status') == 'success' or data.get('country') or data.get('city'):
                        geo_data = data
                        break
                except:
                    continue
        
        # === REVERSE DNS ===
        hostname = None
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror):
            pass
        
        # === GET COORDINATES & ADDRESS via Nominatim (OpenStreetMap) ===
        lat = lon = None
        formatted_address = None
        
        if geo_data:
            city = geo_data.get('city', '')
            region = geo_data.get('stateProv', geo_data.get('regionName', geo_data.get('region', '')))
            country = geo_data.get('countryName', geo_data.get('country', ''))
            country_code = geo_data.get('countryCode', '')
            continent = geo_data.get('continentName', '')
            
            # Build address string for geocoding
            addr_parts = [p for p in [city, region, country] if p and p != '?']
            address_query = ', '.join(addr_parts) if addr_parts else ip
            
            # Get coordinates from Nominatim
            try:
                ctx2 = ssl.create_default_context()
                ctx2.check_hostname = False
                ctx2.verify_mode = ssl.CERT_NONE
                nom_url = f'https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address_query)}&format=json&limit=1'
                req2 = urllib.request.Request(nom_url, headers={'User-Agent': 'OWL-Bot/1.0'})
                with urllib.request.urlopen(req2, timeout=10, context=ctx2) as resp2:
                    nom_data = json.loads(resp2.read().decode())
                if nom_data:
                    lat = nom_data[0]['lat']
                    lon = nom_data[0]['lon']
                    formatted_address = nom_data[0].get('display_name', '')
            except:
                pass
            
            # === DISPLAY GEOLOCATION ===
            results.append("─" * 20)
            
            if continent and continent != '?':
                results.append(f"🌎 Continente: {continent}")
            results.append(f"🌍 País: {country} ({country_code})" if country_code else f"🌍 País: {country}")
            if region and region != '?':
                results.append(f"🗺️  Região: {region}")
            if city and city != '?':
                results.append(f"🏙️  Cidade: {city}")
            
            # Formatted address from Nominatim
            if formatted_address:
                results.append(f"📫 Endereço: {formatted_address}")
            
            # Coordinates + Google Maps
            if lat and lon:
                results.append("─" * 20)
                results.append(f"📌 Coordenadas: {lat}, {lon}")
                maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                results.append(f"🗺️  Google Maps: {maps_url}")
                sv_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
                results.append(f"📷 Street View: {sv_url}")
        
        else:
            # Fallback: no geo data
            results.append("─" * 20)
            results.append("⚠️  Serviços de GeoIP indisponíveis")
            
            if hostname:
                results.append(f"🔄 Reverse DNS: {hostname}")
                
                # Try to extract location from hostname
                city_map = {
                    'sfo': 'San Francisco', 'lax': 'Los Angeles', 'ord': 'Chicago',
                    'dfw': 'Dallas', 'iad': 'Washington D.C.', 'jfk': 'New York',
                    'lhr': 'London', 'cdg': 'Paris', 'fra': 'Frankfurt',
                    'ams': 'Amsterdam', 'sin': 'Singapore', 'nrt': 'Tokyo',
                    'syd': 'Sydney', 'gru': 'São Paulo', 'dub': 'Dublin',
                    'bom': 'Mumbai', 'hkg': 'Hong Kong', 'icn': 'Seoul',
                    'mad': 'Madrid', 'mex': 'Mexico City', 'scl': 'Santiago',
                    'atl': 'Atlanta', 'mia': 'Miami', 'phx': 'Phoenix',
                    'sea': 'Seattle', 'den': 'Denver', 'bos': 'Boston',
                }
                
                hostname_lower = hostname.lower()
                location_hint = None
                for code, city_name in city_map.items():
                    if code in hostname_lower:
                        location_hint = city_name
                        break
                
                org_hints = {
                    'google': 'Google', '1e100': 'Google', 'amazon': 'Amazon AWS',
                    'aws': 'Amazon AWS', 'compute-1': 'Amazon AWS', 'microsoft': 'Microsoft Azure',
                    'cloudflare': 'Cloudflare', 'akamai': 'Akamai', 'github': 'GitHub',
                }
                
                detected_org = None
                for key, org_name in org_hints.items():
                    if key in hostname_lower:
                        detected_org = org_name
                        break
                
                if detected_org:
                    results.append(f"🏢 Organização: {detected_org}")
                if location_hint:
                    results.append(f"📍 Localização (DNS): {location_hint}")
                    maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote(location_hint)}"
                    results.append(f"🗺️  Google Maps: {maps_url}")
                
                results.append(f"🔗 Google Maps (IP): https://www.google.com/maps/search/{ip}")
            else:
                results.append(f"🗺️  Google Maps (IP): https://www.google.com/maps/search/{ip}")
        
        # Reverse DNS display (if not already shown in fallback)
        if hostname and geo_data:
            results.append("─" * 20)
            results.append(f"🔄 Reverse DNS: {hostname}")
        
        # Organization from reverse DNS
        if hostname:
            org_hints = {
                'google': 'Google', '1e100': 'Google', 'amazon': 'Amazon AWS',
                'aws': 'Amazon AWS', 'compute-1': 'Amazon AWS', 'microsoft': 'Microsoft Azure',
                'cloudflare': 'Cloudflare', 'akamai': 'Akamai', 'github': 'GitHub',
            }
            hostname_lower = hostname.lower()
            for key, org_name in org_hints.items():
                if key in hostname_lower:
                    results.append(f"🏢 Organização: {org_name}")
                    break
        
        # Ping
        try:
            ping_cmd = subprocess.run(
                ['ping', '-c', '3', '-W', '2', ip],
                capture_output=True, text=True, timeout=10
            )
            if ping_cmd.returncode == 0:
                for line in ping_cmd.stdout.strip().split('\n'):
                    if 'avg' in line or 'rtt' in line:
                        results.append(f"📶 Ping: {line.strip()}")
                        break
                else:
                    results.append("📶 Ping: OK")
            else:
                results.append("📶 Ping: Sem resposta")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return results
    
    except socket.gaierror:
        return [f"Não foi possível resolver '{target}'. Verifica o domínio/IP."]
    except Exception as e:
        return [f"Erro no lookup: {str(e)[:100]}"]


# === QUOTE & CURIOSITY ===

QUOTES = [
    "Fernando Pessoa: 'O meu passado é tudo quanto consegui não ser.' 🦉",
    "Fernando Pessoa: 'Sou uma antologia.' 🦉",
    "Fernando Pessoa: 'Tudo vale a pena se a alma não é pequena.' 🦉",
    "Fernando Pessoa: 'O poeta é um fingidor. Finge tão completamente que chega a fingir que é dor a dor que deveras sente.' 🦉",
    "Camões: 'Mudam-se os tempos, mudam-se as vontades.' 🦉",
    "Camões: 'Amor é fogo que arde sem se ver.' 🦉",
    "Saramago: 'Não sou otimista, mas acredito que a humanidade pode resolver os seus problemas.' 🦉",
    "Saramago: 'A única coisa que a filosofia pode fazer é destruir superstições.' 🦉",
    "Saramago: 'Se a justiça é vertical, a solidariedade deveria ser horizontal.' 🦉",
    "Sophia de Mello Breyner: 'Para ser grande, sê inteiro: nada teu exagera ou exclui.' 🦉",
    "Sophia de Mello Breyner: 'A poesia é o real absoluto.' 🦉",
    "Agostinho da Silva: 'A liberdade é a possibilidade do isolamento.' 🦉",
    "Agostinho da Silva: 'O futuro pertence àqueles que acreditam na beleza dos seus sonhos.' 🦉",
    "Almada Negreiros: 'Sou um só, não eu, mas o outro.' 🦉",
    "Vergílio Ferreira: 'O que é verdadeiramente imoral é ter medo da vida.' 🦉",
    "José Régio: 'Não há senão uma só maneira de ser livre: ser inteiro.' 🦉",
    "Eça de Queirós: 'A ironia é a linguagem do medo.' 🦉",
    "Camilo Castelo Branco: 'A necessidade aguça o engenho.' 🦉",
]

CURIOSITIES = [
    "Portugal tem a fronteira mais antiga da Europa, definida em 1297 pelo Tratado de Alcanizes. 🇵🇹",
    "Portugal foi o primeiro país a abolir a pena de morte em 1867. 🇵🇹",
    "A palavra 'coruja' em latino é 'strix'. Em mitologia, a coruja era o animal de Atena, deusa da sabedoria. 🦉",
    "Portugal tem mais de 300 dias de sol por ano. ☀️",
    "O Porto foi eleito Melhor Destino Europeu em 2022. 🏆",
    "Portugal tem 60% de energia renovável em 2025. 🌱",
    "O galo de Barcelos é um dos símbolos mais reconhecidos de Portugal. 🐓",
    "Portugal descobriu o Brasil em 1500. 🇧🇷",
    "O português é a língua oficial de 9 países. 🌍",
    "Lisboa é mais antiga que Roma por 400 anos. 🏛️",
    "A Universidade de Coimbra é uma das mais antigas da Europa, fundada em 1290. 🎓",
    "Portugal tem a ponte mais longa da Europa: Vasco da Gama, com 17.2 km. 🌉",
    "O pastel de nata foi inventado em Belém, Lisboa, antes do século XIX. 🥧",
    "Portugal produz 50% da cortiça do mundo. 🌳",
    "O fado foi classificado como Património Imaterial da UNESCO em 2011. 🎵",
]

def cmd_quote():
    return [random.choice(QUOTES)]

def cmd_curiosity():
    return [random.choice(CURIOSITIES)]


# === OSINT COMMANDS (OP only) ===

def cmd_email(email):
    """Check email against 121+ sites using holehe"""
    import subprocess
    try:
        result = subprocess.run(
            ["holehe", email, "--only-used"],
            capture_output=True, text=True, timeout=60
        )
        lines = result.stdout.strip().split('\n')
        found = [l for l in lines if '[+]' in l]
        if not found:
            return [f"📧 {email}: Nenhuma conta encontrada nos 121 sites verificados."]
        results = [f"📧 {email}: {len(found)} conta(s) encontrada(s):"]
        for f in found[:15]:
            site = f.split('[+]')[-1].strip() if '[+]' in f else f.strip()
            results.append(f"  ✅ {site}")
        if len(found) > 15:
            results.append(f"  +{len(found)-15} mais...")
        return results
    except FileNotFoundError:
        return ["⚠️ holehe não instalado. Instala com: pip install holehe"]
    except subprocess.TimeoutExpired:
        return ["⏱️ Timeout: holehe demorou demasiado."]
    except Exception as e:
        return [f"Erro no email check: {str(e)[:100]}"]

def cmd_phone(number):
    """Parse phone number using phonenumbers library"""
    try:
        import phonenumbers
        from phonenumbers import geocoder, carrier, timezone
        parsed = phonenumbers.parse(number, None)
        valid = phonenumbers.is_valid_number(parsed)
        possible = phonenumbers.is_possible_number(parsed)
        country = geocoder.description_for_number(parsed, "pt")
        carrier_name = carrier.name_for_number(parsed, "pt") or carrier.name_for_number(parsed, "en") or "N/A"
        tz = timezone.time_zones_for_number(parsed)
        tz_str = tz[0] if tz else "N/A"
        num_type = phonenumbers.number_type(parsed)
        type_map = {
            0: "📞 Fixo", 1: "📱 Móvel", 2: "📞/📱", 3: "📞 Grátis",
            4: "💲 Premium", 5: "💲 Partilhado", 6: "🌐 VoIP", 7: "👤 Pessoal",
            8: "📟 Pager", 9: "🔌 UAN", 10: "❓ Desconhecido", 27: "🆘 Emergência",
            28: "📧 Voicemail", 29: "📋 Código Curto"
        }
        type_str = type_map.get(num_type, "❓")
        intl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        cc = f"+{parsed.country_code}"
        nat = str(parsed.national_number)
        digits = f"+{parsed.country_code}{parsed.national_number}"
        results = [
            f"📱 {intl}",
            f"🌍 País: {country}",
            f"📡 Operadora: {carrier_name}",
            f"⏰ Timezone: {tz_str}",
            f"📋 Tipo: {type_str}",
            f"✅ Válido: {'Sim' if valid else 'Não'} | Possível: {'Sim' if possible else 'Não'}",
            f"🔢 CC: {cc} | Nacional: {nat}",
            f"🔍 Pesquisas:",
            f"  Truecaller: https://www.truecaller.com/search/{digits}",
            f"  Sync.me: https://sync.me/search/?number={digits}",
            f"  Google: https://www.google.com/search?q=\"{digits}\"",
            f"  WhatsApp: https://wa.me/{digits}",
            f"  Telegram: https://t.me/+{digits}",
        ]
        return results
    except ImportError:
        return ["⚠️ phonenumbers não instalado. Instala com: pip install phonenumbers"]
    except Exception as e:
        return [f"Erro no phone: {str(e)[:100]}"]

def cmd_user(username):
    """Generate social media profile search links"""
    u = urllib.parse.quote(username)
    return [
        f"🔍 Username search: '{username}'",
        f"  GitHub: https://github.com/{u}",
        f"  Twitter/X: https://x.com/{u}",
        f"  Instagram: https://instagram.com/{u}",
        f"  TikTok: https://tiktok.com/@{u}",
        f"  Reddit: https://reddit.com/user/{u}",
        f"  YouTube: https://youtube.com/@{u}",
        f"  Twitch: https://twitch.tv/{u}",
        f"  Facebook: https://facebook.com/{u}",
        f"  LinkedIn: https://linkedin.com/in/{u}",
        f"  Pinterest: https://pinterest.com/{u}",
        f"  Tumblr: https://{u}.tumblr.com",
        f"  Spotify: https://open.spotify.com/user/{u}",
        f"  Steam: https://steamcommunity.com/id/{u}",
        f"  Medium: https://medium.com/@{u}",
        f"  Keybase: https://keybase.io/{u}",
        f"  About.me: https://about.me/{u}",
        f"  Gravatar: https://gravatar.com/{u}",
        f"  Namechk: https://namechk.com/{u}",
    ]

def cmd_reverseimg(url):
    """Generate reverse image search links"""
    u = urllib.parse.quote(url)
    return [
        f"🖼️ Reverse Image Search:",
        f"  Google Lens: https://lens.google.com/uploadbyurl?url={u}",
        f"  Yandex: https://yandex.com/images/search?url={u}&rpt=imageview",
        f"  Bing: https://www.bing.com/images/search?view=detailv2&iss=sbi&form=SBIVSP&sbisrc=UrlPaste&q=imgurl:{u}",
        f"  TinEye: https://tineye.com/search?url={u}",
        f"  Google: https://www.google.com/searchbyimage?image_url={u}",
        f"  PimEyes: https://pimeyes.com/en?url={u}",
    ]


# === CRYPTO & STOCK ===

def cmd_crypto(query):
    """Get crypto price from CoinGecko"""
    q = query.lower().strip()
    if q in ('top', 'top10', 'top15', 'ranking'):
        try:
            url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=15&page=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            results = ["🏆 Top 15 Criptomoedas por Market Cap:"]
            for i, c in enumerate(data, 1):
                price = c['current_price']
                chg = c['price_change_percentage_24h']
                cap = c['market_cap']
                arrow = "📈" if chg and chg > 0 else "📉"
                price_str = f"${price:,.2f}" if price >= 1 else f"${price:.6f}"
                cap_str = f"${cap/1e9:.1f}B" if cap >= 1e9 else f"${cap/1e6:.1f}M"
                chg_str = f"{chg:+.2f}%" if chg else "N/A"
                results.append(f"  {i}. {c['symbol'].upper()} {price_str} {arrow}{chg_str} | Cap: {cap_str}")
            return results
        except Exception as e:
            return [f"Erro crypto top: {str(e)[:100]}"]
    else:
        try:
            # Try to find by symbol
            symbol_map = {'btc':'bitcoin','eth':'ethereum','sol':'solana','ada':'cardano','doge':'dogecoin','xrp':'ripple','dot':'polkadot','avax':'avalanche-2','matic':'matic-network','link':'chainlink','uni':'uniswap','ltc':'litecoin','bch':'bitcoin-cash','xlm':'stellar','algo':'algorand','near':'near','apt':'aptos','arb':'arbitrum','op':'optimism','sui':'sui','pepe':'pepe','shib':'shiba-inu','ton':'the-open-network','trx':'tron','dai':'dai','usdt':'tether','usdc':'usd-coin','bnb':'binancecoin'}
            coin_id = symbol_map.get(q, q)
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&community_data=false&developer_data=false"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            md = data.get('market_data', {})
            price = md.get('current_price', {}).get('usd', 0)
            chg24 = md.get('price_change_percentage_24h')
            chg7 = md.get('price_change_percentage_7d')
            chg30 = md.get('price_change_percentage_30d')
            ath = md.get('ath', {}).get('usd', 0)
            cap = md.get('market_cap', {}).get('usd', 0)
            vol = md.get('total_volume', {}).get('usd', 0)
            price_str = f"${price:,.2f}" if price >= 1 else f"${price:.8f}"
            ath_str = f"${ath:,.2f}" if ath >= 1 else f"${ath:.8f}"
            cap_str = f"${cap/1e9:.2f}B" if cap >= 1e9 else f"${cap/1e6:.1f}M"
            vol_str = f"${vol/1e6:.1f}M" if vol >= 1e6 else f"${vol:,.0f}"
            arrow24 = "📈" if chg24 and chg24 > 0 else "📉"
            results = [
                f"💰 {data['name']} ({data['symbol'].upper()})",
                f"  💵 Preço: {price_str}",
                f"  {arrow24} 24h: {chg24:+.2f}%" if chg24 else "  24h: N/A",
                f"  7d: {chg7:+.2f}%" if chg7 else "",
                f"  30d: {chg30:+.2f}%" if chg30 else "",
                f"  🏔️ ATH: {ath_str}",
                f"  📊 Cap: {cap_str} | Vol 24h: {vol_str}",
            ]
            return [r for r in results if r]
        except urllib.error.HTTPError:
            return [f"Moeda '{query}' não encontrada. Tenta o símbolo (btc, eth, sol...) ou 'top' para ranking."]
        except Exception as e:
            return [f"Erro crypto: {str(e)[:100]}"]

def cmd_stock(symbol):
    """Get stock price from Yahoo Finance"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=1d&interval=1d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        result = data['chart']['result'][0]
        meta = result['meta']
        price = meta.get('regularMarketPrice', 0)
        prev = meta.get('chartPreviousClose', 0) or meta.get('previousClose', 0)
        chg = ((price - prev) / prev * 100) if prev else 0
        currency = meta.get('currency', 'USD')
        exchange = meta.get('exchangeName', 'N/A')
        arrow = "📈" if chg > 0 else "📉"
        return [
            f"📊 {symbol.upper()} ({exchange})",
            f"  💵 {price:,.2f} {currency}",
            f"  {arrow} {chg:+.2f}%",
        ]
    except Exception as e:
        return [f"Erro stock: {str(e)[:100]}"]


# === CINEMA & IMDB ===

def cmd_cinema():
    """Get 'Em cartaz' movies from CineCartaz Público - 25 filmes em destaque no cartaz"""
    base_url = "https://cinecartaz.publico.pt"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        req = urllib.request.Request(base_url + "/", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="replace")
        
        # Encontrar a secção "Em cartaz"
        cartaz_pos = html.find("Em cartaz")
        if cartaz_pos < 0:
            return ["🎬 Secção 'Em cartaz' não encontrada. Consulta https://cinecartaz.publico.pt/"]
        
        # Recuar até ao <section> mais próximo (início da secção)
        section_start = html.rfind("<section", 0, cartaz_pos)
        if section_start < 0:
            section_start = cartaz_pos
        
        # Avançar até à próxima <section> (fim da secção)
        next_section = html.find("<section", cartaz_pos + 100)
        if next_section < 0:
            next_section = section_start + 20000
        
        chunk = html[section_start:next_section]
        
        # Extrair títulos da secção Em cartaz
        titles = re.findall(r'<div class="collection__item-title">([^<]+)</div>', chunk)
        
        if titles:
            # Limitar a 25 (os primeiros 25 são os em destaque no cartaz)
            titles = titles[:25]
            results = [f"🎬 Em Cartaz nos Cinemas ({len(titles)} filmes):"]
            for i, t in enumerate(titles, 1):
                results.append(f"  {i}. {t.strip()}")
            return results
    except Exception as e:
        pass
    
    return ["🎬 Erro. Consulta https://cinecartaz.publico.pt/"]

def cmd_estreias():
    """Get upcoming movie releases from FilmSpot RSS + CineCartaz"""
    results = []
    
    # 1. Tentar FilmSpot RSS (estreias da semana)
    try:
        url = "https://filmspot.pt/feed/estreias/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            content = r.read().decode("utf-8", errors="replace")
        
        titles = re.findall(r'<title><!\[CDATA\[([^\]]+)\]\]></title>', content)
        titles = [t for t in titles if 'estreia' in t.lower() or 'semana' in t.lower()]
        
        if titles:
            results.append("🎬 Estreias da Semana (FilmSpot):")
            for t in titles[:8]:
                # Limpar título
                clean = t.replace('Estreia esta semana: ', '').replace('Estreias da semana (Portugal) - filmSPOT', '').strip()
                if clean and len(clean) > 3:
                    results.append(f"  📽️ {clean}")
    except:
        pass
    
    # 2. Tentar CineCartaz em-breve
    try:
        url2 = "https://cinecartaz.publico.pt/em-breve"
        req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=10) as r:
            html2 = r.read().decode("utf-8", errors="replace")
        
        titles2 = re.findall(r'<span[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</span>', html2)
        titles2 = [t.strip() for t in titles2 if len(t.strip()) > 2]
        
        # Extrair datas
        all_text = re.sub(r'<[^>]+>', ' ', html2)
        all_text = re.sub(r'\s+', ' ', all_text)
        datas = re.findall(r'(\d{1,2}\s+de\s+\w+\.?\s*(?:de\s+\d{4})?)', all_text)
        
        if titles2:
            if results:
                results.append("─" * 15)
            results.append("🔜 Em Breve (CineCartaz):")
            for i, t in enumerate(titles2[:15]):
                data = datas[i] if i < len(datas) else ""
                results.append(f"  • {t} {f'({data})' if data else ''}")
    except:
        pass
    
    if results:
        return results
    
    # Fallback
    return ["🎬 Estreias: consulta https://filmspot.pt/estreias/ ou https://cinecartaz.publico.pt/em-breve"]

def cmd_imdb(query):
    """Search IMDB using suggest API"""
    try:
        q = query.strip().replace(' ', '_')
        first = q[0].lower() if q else 'a'
        encoded = urllib.parse.quote(q)
        url = f"https://v2.sg.media-imdb.com/suggests/{first}/{encoded}.json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode()
        # Parse JSONP: imdb$title({...})
        start = raw.index('(') + 1
        end = raw.rindex(')')
        data = json.loads(raw[start:end])
        items = data.get('d', [])[:5]
        if not items:
            return [f"Nenhum resultado para '{query}' no IMDB."]
        type_map = {'feature':'🎬 Filme','tv_series':'📺 Série','tv_miniseries':'📺 Minissérie','tv_movie':'📺 TV Movie','short':'🎞️ Curta','video':'📹 Vídeo','video_game':'🎮 Jogo'}
        results = [f"🎬 IMDB: '{query}'"]
        for item in items:
            title = item.get('l', '?')
            year = item.get('y', '')
            imdb_id = item.get('id', '')
            q_type = item.get('q', '')
            starring = item.get('s', '')
            type_str = type_map.get(q_type, q_type)
            line = f"  {type_str} {title}"
            if year: line += f" ({year})"
            if imdb_id: line += f" — https://www.imdb.com/title/{imdb_id}/"
            if starring: line += f" | {starring}"
            results.append(line)
        return results
    except Exception as e:
        return [f"Erro IMDB: {str(e)[:100]}"]

def cmd_play(imdb_url):
    """Generate playimdb link from IMDB URL"""
    import re as re2
    match = re2.search(r'(tt\d+)', imdb_url)
    if match:
        imdb_id = match.group(1)
        return [
            f"🎬 PlayIMDb: https://playimdb.com/{imdb_id}",
            f"🔗 IMDb: https://www.imdb.com/title/{imdb_id}/",
        ]
    return ["⚠️ URL IMDB inválido. Formato: https://www.imdb.com/title/tt0133093/"]


# === IPTV ===

def cmd_iptv():
    return [
        "📺 REBEL IPTV PLAYER",
        "🔗 https://rebel-pirate-tv.pages.dev/",
        "📝 Player de TV e streaming gratuito",
    ]


# === TORRENT & DOWNLOAD ===

def cmd_predb(query=""):
    """Search predb.me RSS"""
    try:
        q = query.strip().lower() if query else ""
        categories = {'filmes':'movies','movies':'movies','tv':'tv','series':'tv','music':'music','musica':'music','games':'games','jogos':'games','apps':'apps','software':'apps','anime':'anime'}
        cat = ''
        search_term = q
        for key, val in categories.items():
            if q.startswith(key):
                cat = val
                search_term = q[len(key):].strip()
                break
        if search_term:
            url = f"https://predb.me/rss/{urllib.parse.quote(search_term)}"
        elif cat:
            url = f"https://predb.me/rss/{cat}"
        else:
            url = "https://predb.me/rss/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml = resp.read().decode()
        import re as re2
        items = re2.findall(r'<item>(.*?)</item>', xml, re2.DOTALL)[:9]
        if not items:
            return [f"Nenhum resultado no predb.me para '{query}'."]
        results = [f"🔍 predb.me: '{query}'"]
        for item in items:
            title = re2.search(r'<title>(.*?)</title>', item)
            title = title.group(1) if title else '?'
            link = re2.search(r'<link>(.*?)</link>', item)
            link = link.group(1) if link else ''
            results.append(f"  📦 {title}")
            if link: results.append(f"    {link}")
        return results
    except Exception as e:
        return [f"Erro predb: {str(e)[:100]}"]

def cmd_piratebay(query=""):
    """Search The Pirate Bay via apibay.org"""
    try:
        q = query.strip() if query else "top"
        if not q or q == "top":
            url = "https://apibay.org/precompiled/data_top100_24h.json"
        else:
            url = f"https://apibay.org/q.php?q={urllib.parse.quote(q)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if not data or (isinstance(data, list) and len(data) == 0):
            return [f"Nenhum torrent encontrado para '{query}'."]
        if isinstance(data, dict) and data.get('error'):
            return [f"Erro TPB: {data.get('error')}"]
        results = [f"🏴‍☠️ Pirate Bay: '{query}'"]
        for item in data[:9]:
            name = item.get('name', '?') if isinstance(item, dict) else str(item)
            size = item.get('size', '') if isinstance(item, dict) else ''
            seeders = item.get('seeders', '') if isinstance(item, dict) else ''
            leechers = item.get('leechers', '') if isinstance(item, dict) else ''
            magnet = item.get('info_hash', '') if isinstance(item, dict) else ''
            size_str = f"{int(size)/1e9:.1f} GB" if size and str(size).isdigit() else str(size)
            line = f"  📦 {name}"
            if size_str: line += f" | {size_str}"
            if seeders: line += f" | ↑{seeders}"
            if leechers: line += f" | ↓{leechers}"
            results.append(line)
            if magnet:
                results.append(f"    magnet:?xt=urn:btih:{magnet}")
        return results
    except Exception as e:
        return [f"Erro Pirate Bay: {str(e)[:100]}"]

def cmd_uindex(query):
    """Search uindex.org"""
    try:
        parts = query.strip().split()
        search_term = parts[0] if parts else ''
        category = parts[1] if len(parts) > 1 else ''
        cat_map = {'filmes':'movies','movies':'movies','tv':'tv','series':'tv','games':'games','jogos':'games','music':'music','musica':'music','apps':'apps','anime':'anime','software':'apps'}
        cat_slug = cat_map.get(category.lower(), '') if category else ''
        if cat_slug:
            url = f"https://uindex.org/{cat_slug}/{urllib.parse.quote(search_term)}"
        else:
            url = f"https://uindex.org/search/{urllib.parse.quote(search_term)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        import re as re2
        # Extract links and titles
        links = re2.findall(r'href="(/[^"]+)"[^>]*>([^<]+)</a>', html)
        results = [f"🔍 uindex: '{query}'"]
        count = 0
        for href, title in links:
            title = title.strip()
            if title and len(title) > 2 and count < 9:
                results.append(f"  📦 {title} — https://uindex.org{href}")
                count += 1
        if count == 0:
            results.append("  Nenhum resultado encontrado.")
        return results
    except Exception as e:
        return [f"Erro uindex: {str(e)[:100]}"]

def cmd_ytdl(youtube_url):
        """Generate YouTube download link via cnvmp3"""
        return [
            f"🎬 YouTube Download:",
            f"  https://cnvmp3.com/index.php?url={urllib.parse.quote(youtube_url)}",
            f"  📎 URL original: {youtube_url}",
        ]

def cmd_hubstream():
        """Get streaming sites from pastebin"""
        try:
            url = "https://pastebin.com/raw/hubstream"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode()
            sites = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
            if not sites:
                return ["📺 StreamHub: https://rebel-pirate-tv.pages.dev/filmes"]
            results = ["📺 StreamHub — Sites de Streaming:"]
            for s in sites[:20]:
                results.append(f"  🔗 {s}")
            return results
        except Exception:
            return ["📺 StreamHub: https://rebel-pirate-tv.pages.dev/filmes"]


# === NOTICE SENDER ===
# Sends a random philosophical/rebellious quote via IRC NOTICE

NOTICE_QUOTES = [
    "🦉 'O meu passado é tudo quanto consegui não ser.' — Fernando Pessoa",
    "🦉 'Mudam-se os tempos, mudam-se as vontades.' — Camões",
    "🦉 'Não tenhamos pressa, mas não percamos tempo.' — Saramago",
    "🦉 'A liberdade é a possibilidade do isolamento.' — Agostinho da Silva",
    "🦉 'O que é verdadeiramente imoral é ter medo da vida.' — Vergílio Ferreira",
    "🦉 'Não há senão uma só maneira de ser livre: ser inteiro.' — José Régio",
    "🦉 'Para ser grande, sê inteiro: nada teu exagera ou exclui.' — Sophia de Mello Breyner",
    "🦉 'Sou um só, não eu, mas o outro.' — Almada Negreiros",
    "🦉 'A imaginação é a primeira fonte da felicidade humana.' — Giacomo Casanova",
    "🦉 'A revolta é a essência da liberdade.' — Anonymous",
    "🦉 'Não sigo ordens de quem não sabe pensar.' — Pirate Code",
    "🦉 'A informação quer ser livre.' — Stewart Brand",
    "🦈 'A liberdade não é um direito, é um dever.' — Anonymous",
    "🦉 'Quem controla o passado, controla o futuro. Quem controla o presente, controla o passado.' — George Orwell",
    "🦉 'A ignorância é a força.' — George Orwell (parafraseado)",
    "🦇 'Não sou um libertário por teoria. Sou porque não confio em nenhum governo.' — Cypherpunk",
    "🦉 'O conhecimento é poder. O partilhar conhecimento é a verdadeira revolução.' — Anonymous",
    "🦉 'Aquele que não é suficientemente corajoso para tomar riscos não alcançará nada na vida.' — Muhammad Ali",
]


def cmd_notice(sender, channel, target_nick=None, custom_msg=None):
    """Send a notice.
    - !notice              → random quote via NOTICE to channel + PRIVMSG to all members
    - !notice #canal       → random quote via NOTICE to #canal + PRIVMSG to all members
    - !notice nick         → random quote via PRIVMSG to nick
    - !notice nick msg     → custom message via NOTICE to nick
    - !notice #canal msg   → custom message via NOTICE to #canal
    """
    quote = custom_msg if custom_msg else random.choice(NOTICE_QUOTES)
    responses = []
    
    if target_nick and target_nick.startswith("#"):
        # Target is a channel: send NOTICE to channel + PRIVMSG to all members
        if custom_msg:
            responses.append({"target": target_nick, "message": quote, "type": "notice"})
            responses.append({"target": target_nick, "message": quote, "type": "privmsg_all", "exclude": list(IGNORE_NICKS | {sender, "OWL"})})
        else:
            responses.append({"target": target_nick, "message": quote, "type": "notice"})
            responses.append({"target": target_nick, "message": quote, "type": "privmsg_all", "exclude": list(IGNORE_NICKS | {sender, "OWL"})})
    elif target_nick:
        # Target is a nick: send NOTICE (not PRIVMSG) to the nick
        responses.append({"target": target_nick, "message": quote, "type": "notice"})
        # Announce in main channel
        responses.append({"target": "#deep-web", "message": "🦉 Notice enviado para %s por %s" % (target_nick, sender), "type": "privmsg"})
    else:
        # No target: send NOTICE to current channel + PRIVMSG to all members
        responses.append({"target": channel, "message": quote, "type": "notice"})
        responses.append({"target": channel, "message": quote, "type": "privmsg_all", "exclude": list(IGNORE_NICKS | {sender, "OWL"})})
    
    return responses


def cmd_help():
    """Return help text with available commands"""
    return [
        "🦉 OWL Bot - Comandos:",
        "!help | !ajuda",
        "!quote | !cita",
        "!curiosity | !curiosidade",
        "!wiki <termo>",
        "!img <descrição>",
        "!meteo <cidade>",
        "!youtube <termo>",
        "!google <termo>",
        "!news <região>",
        "!crypto <moeda> | !crypto top",
        "!stock <símbolo>",
        "!cinema | !estreias",
        "!imdb <filme|série>",
        "!play <url-imdb>",
        "!iptv",
        "!predb [categoria|termo]",
        "!piratebay [termo] | !tpb [termo]",
        "!uindex <termo> [categoria]",
        "!ytdl <url-youtube>",
        "!hubstream",
        "!ipinfo <ip|domain> [OP]",
        "!ipscan <ip> [OP]",
        "!iplookup <ip|domain> [OP]",
        "!email <email> [OP]",
        "!phone <número> [OP]",
        "!user <username> [OP]",
        "!reverseimg <url> [OP]",
        "📡 Notice System:",
        "  !notice #canal <nick> — envia frase por notice a um user",
        "  !notice #canal — envia frase por notice a todos do canal",
        "Ou fala comigo mencionando 'OWL'! 😏"
    ]

def cmd_news(region):
    """Get latest news by region using free RSS feeds and news APIs."""
    region_lower = region.lower().strip()
    
    # Map region to country code and RSS feed
    region_map = {
        # Portuguese terms
        "portugal": {"country": "pt", "name": "Portugal", "rss": "https://feeds.feedburner.com/PublicoRSS"},
        "pt": {"country": "pt", "name": "Portugal", "rss": "https://feeds.feedburner.com/PublicoRSS"},
        "brasil": {"country": "br", "name": "Brasil", "rss": "https://g1.globo.com/rss/g1/"},
        "br": {"country": "br", "name": "Brasil", "rss": "https://g1.globo.com/rss/g1/"},
        "mundo": {"country": "us", "name": "Mundo", "rss": "https://feeds.bbci.co.uk/news/world/rss.xml"},
        "world": {"country": "us", "name": "Mundo", "rss": "https://feeds.bbci.co.uk/news/world/rss.xml"},
        "europa": {"country": "de", "name": "Europa", "rss": "https://feeds.bbci.co.uk/news/world/europe/rss.xml"},
        "europe": {"country": "de", "name": "Europa", "rss": "https://feeds.bbci.co.uk/news/world/europe/rss.xml"},
        "eua": {"country": "us", "name": "EUA", "rss": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"},
        "usa": {"country": "us", "name": "EUA", "rss": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"},
        "america": {"country": "us", "name": "América", "rss": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"},
        "asia": {"country": "jp", "name": "Ásia", "rss": "https://feeds.bbci.co.uk/news/world/asia/rss.xml"},
        "africa": {"country": "za", "name": "África", "rss": "https://feeds.bbci.co.uk/news/world/africa/rss.xml"},
        "tech": {"country": "pt", "name": "Tecnologia PT (Tek)", "rss": "https://tek.sapo.pt/rss"},
        "tecnologia": {"country": "pt", "name": "Tecnologia PT (Tek)", "rss": "https://tek.sapo.pt/rss"},
        "tek": {"country": "pt", "name": "Tecnologia PT (Tek)", "rss": "https://tek.sapo.pt/rss"},
        "tek sapo": {"country": "pt", "name": "Tecnologia PT (Tek)", "rss": "https://tek.sapo.pt/rss"},
        "4gnews": {"country": "pt", "name": "Tecnologia PT (4GNews)", "rss": "https://4gnews.pt/feed"},
        "pplware": {"country": "pt", "name": "Tecnologia PT (Pplware)", "rss": "https://pplware.sapo.pt/feed"},
        "aberto": {"country": "pt", "name": "Aberto até de Madrugada", "rss": "https://abertoatedemadrugada.com/feeds/posts/default?alt=rss"},
        "aberto madrugada": {"country": "pt", "name": "Aberto até de Madrugada", "rss": "https://abertoatedemadrugada.com/feeds/posts/default?alt=rss"},
        "techpt": {"country": "pt", "name": "Tech Portugal (Tek+4G+Pplware)", "rss": "https://tek.sapo.pt/rss"},
        "ciencia": {"country": "us", "name": "Ciência", "rss": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"},
        "science": {"country": "us", "name": "Ciência", "rss": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"},
        "desporto": {"country": "pt", "name": "Desporto", "rss": "https://www.ojogo.pt/rss/"},
        "sports": {"country": "us", "name": "Desporto", "rss": "https://feeds.bbci.co.uk/sport/rss.xml"},
        "economia": {"country": "pt", "name": "Economia", "rss": "https://feeds.bbci.co.uk/news/business/rss.xml"},
        "business": {"country": "us", "name": "Economia", "rss": "https://feeds.bbci.co.uk/news/business/rss.xml"},
        "saude": {"country": "us", "name": "Saúde", "rss": "https://feeds.bbci.co.uk/news/health/rss.xml"},
        "health": {"country": "us", "name": "Saúde", "rss": "https://feeds.bbci.co.uk/news/health/rss.xml"},
        "cultura": {"country": "pt", "name": "Cultura", "rss": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"},
        "entertainment": {"country": "us", "name": "Entretenimento", "rss": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"},
        # === Fontes Portugal (Feedspot) ===
        "dn": {"country": "pt", "name": "Dinheiro Vivo", "rss": "https://dinheirovivo.dn.pt//feed"},
        "dinheirovivo": {"country": "pt", "name": "Dinheiro Vivo", "rss": "https://dinheirovivo.dn.pt//feed"},
        "asbeiras": {"country": "pt", "name": "Diário As Beiras", "rss": "https://feeds.feedburner.com/asbeiras"},
        "beiras": {"country": "pt", "name": "Diário As Beiras", "rss": "https://feeds.feedburner.com/asbeiras"},
        "expresso": {"country": "pt", "name": "Expresso", "rss": "https://feeds.feedburner.com/expresso-geral"},
        "jornaleconomico": {"country": "pt", "name": "Jornal Económico", "rss": "https://jornaleconomico.sapo.pt/feed/"},
        "economico": {"country": "pt", "name": "Jornal Económico", "rss": "https://jornaleconomico.sapo.pt/feed/"},
        "rr": {"country": "pt", "name": "Renascença", "rss": "https://rr.pt/rssfeed-ultimas"},
        "renascenca": {"country": "pt", "name": "Renascença", "rss": "https://rr.pt/rssfeed-ultimas"},
        "cmjornal": {"country": "pt", "name": "Correio da Manhã", "rss": "https://www.cmjornal.pt/rss"},
        "cm": {"country": "pt", "name": "Correio da Manhã", "rss": "https://www.cmjornal.pt/rss"},
        "correio": {"country": "pt", "name": "Correio da Manhã", "rss": "https://www.cmjornal.pt/rss"},
        "portugalresident": {"country": "pt", "name": "Portugal Resident (EN)", "rss": "https://www.portugalresident.com/feed/"},
        "resident": {"country": "pt", "name": "Portugal Resident (EN)", "rss": "https://www.portugalresident.com/feed/"},
        "contraprova": {"country": "pt", "name": "Contra Prova", "rss": "https://contraprova.pt/rss"},
        "contra": {"country": "pt", "name": "Contra Prova", "rss": "https://contraprova.pt/rss"},
    }
    
    # Try to find matching region
    region_info = None
    for key, info in region_map.items():
        if key in region_lower or region_lower in key:
            region_info = info
            break
    
    if not region_info:
        return [
            f"Região '{region}' não reconhecida. Regiões disponíveis:",
            "portugal, brasil, mundo, europa, eua, asia, africa,",
            "tech, tek, 4gnews, pplware, aberto, techpt, ciencia, desporto, economia, saude, cultura,",
            "dn, dinheirovivo, asbeiras, expresso, jornaleconomico, rr, renascenca, cm, cmjornal, correio, portugalresident, resident, contraprova, contra"
        ]
    
    country = region_info["country"]
    region_name = region_info["name"]
    rss_url = region_info["rss"]
    
    results = []
    
    # === METHOD 1: Try RSS feed ===
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(rss_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml',
        })
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            xml_data = resp.read().decode('utf-8', errors='replace')
        
        # Parse RSS items
        items = re.findall(r'<item>(.*?)</item>', xml_data, re.DOTALL)
        if not items:
            # Try Atom format
            items = re.findall(r'<entry>(.*?)</entry>', xml_data, re.DOTALL)
        
        count = 0
        for item in items[:15]:
            title_match = re.search(r'<title[^>]*>(.*?)</title>', item, re.DOTALL)
            link_match = re.search(r'<link[^>]*>(.*?)</link>', item, re.DOTALL)
            date_match = re.search(r'<pubDate>(.*?)</pubDate>', item, re.DOTALL)
            if not date_match:
                date_match = re.search(r'<published>(.*?)</published>', item, re.DOTALL)
            desc_match = re.search(r'<description[^>]*>(.*?)</description>', item, re.DOTALL)
            
            if title_match:
                title = title_match.group(1).strip()
                # Clean CDATA and HTML entities
                title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                title = re.sub(r'<[^>]+>', '', title)
                title = title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
                title = title.strip()
                
                link = ""
                if link_match:
                    link = link_match.group(1).strip()
                    link = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', link)
                    link = link.strip()
                
                date_str = ""
                if date_match:
                    date_str = date_match.group(1).strip()
                    # Simplify date
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(date_str)
                        date_str = dt.strftime("%d/%m %H:%M")
                    except:
                        date_str = date_str[:16]
                
                if title and count < 5:
                    count += 1
                    if date_str:
                        results.append(f"📰 [{date_str}] {title}")
                    else:
                        results.append(f"📰 {title}")
                    if link and len(link) < 100:
                        results.append(f"   🔗 {link}")
        
        if results:
            results.insert(0, f"📰 Últimas notícias - {region_name}:")
            results.insert(1, "─" * 20)
            return results
    
    except Exception as e:
        log(f"RSS error for {region_name}: {e}")
    
    # === METHOD 2: Try NewsAPI (free, no key needed for top headlines via GNews) ===
    try:
        # Use GNews free API (no key required for basic usage)
        gnews_url = f"https://gnews.io/api/v4/top-headlines?country={country}&lang=pt&max=5&apikey="
        # Actually GNews requires API key, skip this
        
        # Try NewsData.io free
        newsdata_url = f"https://newsdata.io/api/1/news?country={country}&language=pt&apikey=pub_0"
        # Also requires key
        
        # Try free RSS from Google News
        google_rss = f"https://news.google.com/rss?hl=pt-PT&gl=PT&ceid=PT:pt-419"
        if country != "pt":
            lang_map = {"br": ("pt-BR", "BR:pt-419"), "us": ("en-US", "US:en"), "de": ("de", "DE:de"), "jp": ("ja", "JP:ja"), "za": ("en", "ZA:en")}
            if country in lang_map:
                lang, ceid = lang_map[country]
                google_rss = f"https://news.google.com/rss?hl={lang}&gl={country.upper()}&ceid={ceid}"
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(google_rss, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            xml_data = resp.read().decode('utf-8', errors='replace')
        
        items = re.findall(r'<item>(.*?)</item>', xml_data, re.DOTALL)
        count = 0
        for item in items[:10]:
            title_match = re.search(r'<title[^>]*>(.*?)</title>', item, re.DOTALL)
            link_match = re.search(r'<link[^>]*>(.*?)</link>', item, re.DOTALL)
            date_match = re.search(r'<pubDate>(.*?)</pubDate>', item, re.DOTALL)
            
            if title_match:
                title = title_match.group(1).strip()
                title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                title = re.sub(r'<[^>]+>', '', title)
                title = title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
                title = title.strip()
                
                link = ""
                if link_match:
                    link = link_match.group(1).strip()[:80]
                
                date_str = ""
                if date_match:
                    date_str = date_match.group(1).strip()[:16]
                
                if title and count < 5:
                    count += 1
                    if date_str:
                        results.append(f"📰 [{date_str}] {title}")
                    else:
                        results.append(f"📰 {title}")
                    if link:
                        results.append(f"   🔗 {link}")
        
        if results:
            results.insert(0, f"📰 Últimas notícias - {region_name} (Google News):")
            results.insert(1, "─" * 20)
            return results
    
    except Exception as e:
        log(f"Google News RSS error: {e}")
    
    # === METHOD 3: Try HackerNews API for tech ===
    if country == "us" and ("tech" in region_lower or "ciencia" in region_lower):
        try:
            url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            req = urllib.request.Request(url, headers={'User-Agent': 'OWL-Bot/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                story_ids = json.loads(resp.read().decode())[:5]
            
            results = [f"📰 Últimas notícias - {region_name} (Hacker News):", "─" * 20]
            for sid in story_ids:
                try:
                    item_url = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
                    req = urllib.request.Request(item_url, headers={'User-Agent': 'OWL-Bot/1.0'})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        item = json.loads(resp.read().decode())
                    title = item.get("title", "")
                    url_link = item.get("url", "")
                    if title:
                        results.append(f"📰 {title}")
                        if url_link and len(url_link) < 100:
                            results.append(f"   🔗 {url_link}")
                except:
                    continue
            if len(results) > 2:
                return results
        except:
            pass
    
    if not results:
        return [f"Não foi possível obter notícias para '{region_name}'. Tenta mais tarde. 🦉"]
    
    return results

def cmd_wiki(query):
    """Search Wikipedia and return summary"""
    try:
        # Use Wikipedia API
        api_url = f"https://pt.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&srlimit=3"
        
        req = urllib.request.Request(api_url, headers={"User-Agent": "OWL-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        search_results = data.get("query", {}).get("search", [])
        
        if not search_results:
            # Try English Wikipedia
            api_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&srlimit=3"
            req = urllib.request.Request(api_url, headers={"User-Agent": "OWL-Bot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            search_results = data.get("query", {}).get("search", [])
        
        if not search_results:
            return [f"Não encontrei nada sobre '{query}' na Wikipedia. 🦉"]
        
        # Get the first result's page content
        page_title = search_results[0]["title"]
        page_id = search_results[0]["pageid"]
        
        # Get extract
        extract_url = f"https://pt.wikipedia.org/w/api.php?action=query&pageids={page_id}&prop=extracts&exintro=true&explaintext=true&exsentences=3&format=json"
        req = urllib.request.Request(extract_url, headers={"User-Agent": "OWL-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            extract_data = json.loads(resp.read().decode("utf-8"))
        
        pages = extract_data.get("query", {}).get("pages", {})
        page = pages.get(str(page_id), {})
        extract = page.get("extract", "").strip()
        
        if not extract:
            # Try English
            extract_url = f"https://en.wikipedia.org/w/api.php?action=query&pageids={page_id}&prop=extracts&exintro=true&explaintext=true&exsentences=3&format=json"
            req = urllib.request.Request(extract_url, headers={"User-Agent": "OWL-Bot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                extract_data = json.loads(resp.read().decode("utf-8"))
            pages = extract_data.get("query", {}).get("pages", {})
            page = pages.get(str(page_id), {})
            extract = page.get("extract", "").strip()
        
        if not extract:
            snippet = search_results[0].get("snippet", "").replace("<span class='searchmatch'>", "").replace("</span>", "")
            return [f"📚 {page_title}: {snippet}"]
        
        # Truncate for IRC
        if len(extract) > 350:
            extract = extract[:350] + "..."
        
        return [f"📚 {page_title}: {extract}"]
    
    except urllib.error.URLError as e:
        return [f"Erro de ligação à Wikipedia: {e.reason}"]
    except Exception as e:
        return [f"Erro na pesquisa: {str(e)[:100]}"]

def cmd_img(prompt):
    """Generate image using Pollinations.ai (free, no API key)"""
    try:
        # Pollinations.ai - free image generation
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&seed={random.randint(1, 999999)}"
        
        # Download the image
        req = urllib.request.Request(image_url, headers={"User-Agent": "OWL-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            image_data = resp.read()
        
        # Save to temp file
        img_path = os.path.join(QUEUE_DIR, "generated_image.png")
        with open(img_path, "wb") as f:
            f.write(image_data)
        
        # Upload to a free image host or return URL
        # For IRC, we'll return the URL since we can't send images directly
        return [
            f"🎨 Imagem gerada: {image_url}",
            f"(Se não conseguires ver, copia o URL para o browser)"
        ]
    
    except urllib.error.URLError as e:
        return [f"Erro ao gerar imagem: {e.reason}"]
    except Exception as e:
        return [f"Erro ao gerar imagem: {str(e)[:100]}"]

def cmd_meteo(city):
    """Get weather from wttr.in (free, no API key)"""
    try:
        # wttr.in JSON format
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=pt"
        req = urllib.request.Request(url, headers={"User-Agent": "OWL-Bot/1.0"})
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        current = data.get("current_condition", [{}])[0]
        nearest = data.get("nearest_area", [{}])[0]
        
        city_name = nearest.get("areaName", [{}])[0].get("value", city)
        country = nearest.get("country", [{}])[0].get("value", "")
        temp = current.get("temp_C", "?")
        feels = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")
        desc_list = current.get("lang_pt", [])
        desc = desc_list[0].get("value", current.get("weatherDesc", [{}])[0].get("value", "?")) if desc_list else current.get("weatherDesc", [{}])[0].get("value", "?")
        wind_speed = current.get("windspeedKmph", "?")
        wind_dir = current.get("winddir16Point", "?")
        
        # Get forecast for today
        today_forecast = data.get("weather", [{}])[0]
        max_temp = today_forecast.get("maxtempC", "?")
        min_temp = today_forecast.get("mintempC", "?")
        
        location = f"{city_name}, {country}" if country else city_name
        
        return [
            f"🌤️ Meteorologia para {location}:",
            f"Estado: {desc} | 🌡️ Temp: {temp}ºC (sensação: {feels}ºC)",
            f"Máx: {max_temp}ºC | Mín: {min_temp}ºC | 💧 Humidade: {humidity}%",
            f"💨 Vento: {wind_speed} km/h ({wind_dir})"
        ]
    
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return [f"Cidade '{city}' não encontrada. Tenta o nome em inglês ou verifica a ortografia."]
        return [f"Erro ao obter meteorologia: HTTP {e.code}"]
    except urllib.error.URLError as e:
        return [f"Erro de ligação: {e.reason}"]
    except Exception as e:
        return [f"Erro na meteorologia: {str(e)[:100]}"]


def generate_response(msg):
    """Generate a response - either command or conversational"""
    sender = msg.get("sender", "anon")
    message = msg.get("message", "").strip()
    
    # === COMMAND HANDLING ===
    
    # !help
    if CMD_HELP.match(message):
        return cmd_help()
    
    # !wiki <query>
    wiki_match = CMD_WIKI.match(message)
    if wiki_match:
        query = wiki_match.group(1).strip()
        log(f"[WIKI] Searching: {query}")
        return cmd_wiki(query)
    
    # !img <prompt>
    img_match = CMD_IMG.match(message)
    if img_match:
        prompt = img_match.group(1).strip()
        log(f"[IMG] Generating: {prompt}")
        return cmd_img(prompt)
    
    # !meteo <city>
    meteo_match = CMD_METEO.match(message)
    if meteo_match:
        city = meteo_match.group(1).strip()
        log(f"[METEO] Checking: {city}")
        return cmd_meteo(city)
    
    # !youtube <query>
    yt_match = CMD_YOUTUBE.match(message)
    if yt_match:
        query = yt_match.group(1).strip()
        log(f"[YOUTUBE] Searching: {query}")
        return cmd_youtube(query)
    
    # !google <query>
    google_match = CMD_GOOGLE.match(message)
    if google_match:
        query = google_match.group(1).strip()
        log(f"[GOOGLE] Searching: {query}")
        return cmd_google(query)
    
    # !ipinfo <ip|domain> - OP only
    ipinfo_match = CMD_IPINFO.match(message)
    if ipinfo_match:
        if not msg.get("is_op", False):
            return [f"⛔ {sender}: Comando !ipinfo restrito a operadores do canal."]
        target = ipinfo_match.group(1).strip()
        log(f"[IPINFO] Looking up: {target}")
        return cmd_ipinfo(target)
    
    # !ipscan <ip|domain> - OP only
    ipscan_match = CMD_IPSCAN.match(message)
    if ipscan_match:
        if not msg.get("is_op", False):
            return [f"⛔ {sender}: Comando !ipscan restrito a operadores do canal."]
        target = ipscan_match.group(1).strip()
        log(f"[IPSCAN] Scanning: {target}")
        return cmd_ipscan(target)
    
    # !iplookup <ip|domain> - OP only
    iplookup_match = CMD_IPLOOKUP.match(message)
    if iplookup_match:
        if not msg.get("is_op", False):
            return [f"⛔ {sender}: Comando !iplookup restrito a operadores do canal."]
        target = iplookup_match.group(1).strip()
        log(f"[IPLOOKUP] Looking up: {target}")
        return cmd_iplookup(target)
    
    # !news <region>
    news_match = CMD_NEWS.match(message)
    if news_match:
        region = news_match.group(1).strip()
        log(f"[NEWS] Region: {region}")
        return cmd_news(region)

    # !quote / !cita
    if CMD_QUOTE.match(message) or CMD_CITA.match(message):
        return cmd_quote()

    # !curiosity / !curiosidade
    if CMD_CURIOSITY.match(message) or CMD_CURIOSIDADE.match(message):
        return cmd_curiosity()

    # !email <email> - OP only
    email_match = CMD_EMAIL.match(message)
    if email_match:
        if not msg.get("is_op", False):
            return [f"⛔ {sender}: Comando !email restrito a operadores do canal."]
        email = email_match.group(1).strip()
        log(f"[EMAIL] Checking: {email}")
        return cmd_email(email)

    # !phone <number> - OP only
    phone_match = CMD_PHONE.match(message)
    if phone_match:
        if not msg.get("is_op", False):
            return [f"⛔ {sender}: Comando !phone restrito a operadores do canal."]
        number = phone_match.group(1).strip()
        log(f"[PHONE] Checking: {number}")
        return cmd_phone(number)

    # !user <username> - OP only
    user_match = CMD_USER.match(message)
    if user_match:
        if not msg.get("is_op", False):
            return [f"⛔ {sender}: Comando !user restrito a operadores do canal."]
        username = user_match.group(1).strip()
        log(f"[USER] Searching: {username}")
        return cmd_user(username)

    # !reverseimg <url> - OP only
    reverseimg_match = CMD_REVERSEIMG.match(message)
    if reverseimg_match:
        if not msg.get("is_op", False):
            return [f"⛔ {sender}: Comando !reverseimg restrito a operadores do canal."]
        url = reverseimg_match.group(1).strip()
        log(f"[REVERSEIMG] URL: {url}")
        return cmd_reverseimg(url)

    # !crypto <query>
    crypto_match = CMD_CRYPTO.match(message)
    if crypto_match:
        query = crypto_match.group(1).strip()
        log(f"[CRYPTO] Query: {query}")
        return cmd_crypto(query)

    # !stock <symbol>
    stock_match = CMD_STOCK.match(message)
    if stock_match:
        symbol = stock_match.group(1).strip()
        log(f"[STOCK] Symbol: {symbol}")
        return cmd_stock(symbol)

    # !cinema
    if CMD_CINEMA.match(message):
        return cmd_cinema()

    # !estreias
    if CMD_ESTREIAS.match(message):
        return cmd_estreias()

    # !imdb <query>
    imdb_match = CMD_IMDB.match(message)
    if imdb_match:
        query = imdb_match.group(1).strip()
        log(f"[IMDB] Query: {query}")
        return cmd_imdb(query)

    # !play <url-imdb>
    play_match = CMD_PLAY.match(message)
    if play_match:
        url = play_match.group(1).strip()
        log(f"[PLAY] URL: {url}")
        return cmd_play(url)

    # !iptv
    if CMD_IPTV.match(message):
        return cmd_iptv()

    # !predb [query]
    predb_match = CMD_PREDB.match(message)
    if predb_match:
        query = predb_match.group(1).strip()
        log(f"[PREDB] Query: {query}")
        return cmd_predb(query)

    # !piratebay [query] / !tpb [query]
    piratebay_match = CMD_PIRATEBAY.match(message)
    tpb_match = CMD_TPB.match(message)
    if piratebay_match or tpb_match:
        query = (piratebay_match.group(1) if piratebay_match else tpb_match.group(1)).strip()
        log(f"[TPB] Query: {query}")
        return cmd_piratebay(query)

    # !uindex <query>
    uindex_match = CMD_UINDEX.match(message)
    if uindex_match:
        query = uindex_match.group(1).strip()
        log(f"[UINDEX] Query: {query}")
        return cmd_uindex(query)

    # !ytdl <url>
    ytdl_match = CMD_YTDL.match(message)
    if ytdl_match:
        url = ytdl_match.group(1).strip()
        log(f"[YTDL] URL: {url}")
        return cmd_ytdl(url)

    # !hubstream
    if CMD_HUBSTREAM.match(message):
        return cmd_hubstream()

    # !notice [#canal] [nickname] [mensagem]
    notice_match = CMD_NOTICE.match(message)
    if notice_match:
        arg1 = notice_match.group(1)
        arg2 = notice_match.group(2)
        if arg1 and arg1.startswith("#"):
            # Format: !notice #channel [nick|msg]
            channel = arg1
            # arg2 can be a nick or a custom message
            if arg2:
                # Check if arg2 looks like a nick (single word, no spaces) → treat as nick + possible msg
                parts = arg2.split(None, 1)
                nick = parts[0]
                msg = parts[1] if len(parts) > 1 else None
                if nick and not nick.startswith("#"):
                    log(f"[NOTICE] -> {nick} in {channel}" + (f" msg: {msg}" if msg else ""))
                    return cmd_notice(sender, channel, target_nick=nick, custom_msg=msg)
                else:
                    # arg2 is a message for the channel
                    log(f"[NOTICE] -> {channel} msg: {arg2}")
                    return cmd_notice(sender, channel, target_nick=channel, custom_msg=arg2)
            else:
                log(f"[NOTICE ALL] -> all members of {channel}")
                return cmd_notice(sender, channel)
        elif arg1:
            # Format: !notice nick [message]
            parts = message.split(None, 2)
            nick = parts[1] if len(parts) > 1 else None
            custom = parts[2] if len(parts) > 2 else None
            channel = "#deep-web"
            log(f"[NOTICE] direct -> {nick}" + (f" msg: {custom}" if custom else ""))
            return cmd_notice(sender, channel, target_nick=nick, custom_msg=custom)

    # !ajuda
    if CMD_AJUDA.match(message):
        return cmd_help()

    # === CONVERSATIONAL RESPONSES ===
    
    # Strip OWL prefix
    clean_msg = message
    for prefix in ["OWL:", "OWL,", "OWL ", "@OWL"]:
        if clean_msg.upper().startswith(prefix.upper()):
            clean_msg = clean_msg[len(prefix):].strip()
            break
    
    msg_lower = clean_msg.lower()
    topic = detect_topic(msg_lower)
    
    roll = random.random()
    
    if topic == "greeting":
        resp = random.choice(GREETINGS).format(sender=sender)
    elif topic == "who_are_you":
        resp = random.choice(WHO_ARE_YOU).format(sender=sender)
    elif topic == "bot_question":
        resp = random.choice(BOT_QUESTIONS).format(sender=sender)
    elif topic == "gratitude":
        resp = random.choice(GRATITUDE).format(sender=sender)
    elif topic == "profanity":
        resp = random.choice(PROFANITY).format(sender=sender)
    elif topic == "lag":
        resp = random.choice(LAG).format(sender=sender)
    elif topic == "question":
        resp = random.choice(QUESTIONS).format(sender=sender)
    elif topic == "short":
        resp = random.choice(SHORT).format(sender=sender)
    else:
        if roll < 0.35:
            resp = random.choice(JOKES)
        elif roll < 0.65:
            resp = random.choice(ANECDOTES)
        else:
            resp = random.choice(GENERAL).format(sender=sender)
    
    return [resp]

def send_responses(target, responses):
    with open(OUTGOING_FILE, "a") as f:
        for resp in responses:
            if isinstance(resp, dict):
                # Advanced format: {"target": ..., "message": ..., "type": ...}
                data = resp
            else:
                # Simple format: just a string message
                data = {"target": target, "message": resp}
            f.write(json.dumps(data) + "\n")
            log(f"-> {data.get('target', target)}: {data.get('message', '')[:50]}")

def main():
    log(f"OWL Daemon started. Checking every {CHECK_INTERVAL}s. Mode: Jokes & Anecdotes 🦉😂")
    log("Commands: !wiki, !img, !meteo, !help")
    last_response_time = 0
    FLOOD_DELAY = 2
    
    while True:
        try:
            messages = read_new_messages()
            
            if messages:
                log(f"Found {len(messages)} new message(s)")
                
                for msg in messages:
                    sender = msg.get("sender", "?")
                    target = msg.get("target", "#deep-web")
                    message = msg.get("message", "")
                    
                    log(f"<{sender}> {message}")
                    
                    if should_respond(msg):
                        elapsed = time.time() - last_response_time
                        if elapsed < FLOOD_DELAY:
                            time.sleep(FLOOD_DELAY - elapsed)
                        
                        responses = generate_response(msg)
                        send_responses(target, responses)
                        last_response_time = time.time()
                    else:
                        log(f"(not mentioned, ignoring)")
            
            save_last_check()
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            log("Daemon stopped.")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
