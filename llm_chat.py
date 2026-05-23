#!/usr/bin/env python3
"""
OWL Telegram Bot — LLM Chat Module
Chat com pesquisa web usando DuckDuckGo + OpenRouter API.
"""

import os
import json
import re
import urllib.request
import urllib.parse

# === CONFIG ===
OPENROUTER_API_KEY = None
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/owl-alpha"
MAX_SEARCH_RESULTS = 5
MAX_MESSAGE_LENGTH = 4000  # Telegram limit


def _get_api_key() -> str:
    """Obter API key do OpenRouter do ficheiro .env."""
    global OPENROUTER_API_KEY
    if OPENROUTER_API_KEY:
        return OPENROUTER_API_KEY

    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENROUTER_API_KEY="):
                    OPENROUTER_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return OPENROUTER_API_KEY
    raise RuntimeError("OPENROUTER_API_KEY não encontrada em ~/.hermes/.env")


def web_search(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list:
    """
    Pesquisa web usando DuckDuckGo HTML.
    Retorna lista de dicts com 'title', 'url', 'snippet'.
    """
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    }

    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode("utf-8", errors="ignore")

    results = []

    # Extract result blocks
    # Pattern: <a rel="nofollow" class="result__a" href="...">Title</a>
    # Followed by: <a class="result__snippet">snippet</a>
    result_blocks = re.findall(
        r'<a rel="nofollow" class="result__a" href="([^"]+)">.*?<a class="result__snippet"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )

    for url_match, snippet in result_blocks[:max_results]:
        # Clean HTML tags from snippet
        clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
        # Get title from the URL block
        title_match = re.search(r'<a rel="nofollow" class="result__a" href="' + re.escape(url_match) + r'">(.+?)</a>', html, re.DOTALL)
        title = ""
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

        if clean_snippet or title:
            results.append({
                "title": title,
                "url": url_match,
                "snippet": clean_snippet[:300],
            })

    # Fallback: simpler pattern if no results
    if not results:
        titles = re.findall(r'<a rel="nofollow" class="result__a" href="[^"]*">([^<]+)</a>', html)
        snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', html)
        for i, title in enumerate(titles[:max_results]):
            snippet = snippets[i] if i < len(snippets) else ""
            results.append({"title": title.strip(), "url": "", "snippet": snippet.strip()[:300]})

    return results


def chat_with_llm(
    user_message: str,
    conversation_history: list = None,
    use_search: bool = True,
    model: str = None,
) -> dict:
    """
    Enviar mensagem ao LLM com contexto de pesquisa web.
    Retorna dict com 'response', 'search_results', 'error'.
    """
    api_key = _get_api_key()
    selected_model = model or DEFAULT_MODEL

    search_results = []
    search_context = ""

    # Decide se deve pesquisar
    should_search = use_search and _should_search(user_message)

    if should_search:
        try:
            search_results = web_search(user_message, max_results=MAX_SEARCH_RESULTS)
            if search_results:
                search_context = "\n\n--- Resultados da Pesquisa Web ---\n"
                for i, r in enumerate(search_results, 1):
                    search_context += f"\n{i}. {r['title']}\n"
                    if r['snippet']:
                        search_context += f"   {r['snippet']}\n"
                    if r['url']:
                        search_context += f"   URL: {r['url']}\n"
                search_context += "--- Fim da Pesquisa ---\n"
        except Exception as e:
            search_context = f"\n[Nota: Pesquisa web falhou: {e}]\n"

    # Build system prompt
    system_prompt = (
        "És o OWL 🦉, um assistente AI pirata e Rebel. "
        "Respondes em português de forma concisa, útil e com personalidade. "
        "Tens acesso a pesquisa web para dar respostas atualizadas. "
        "Sê direto, usa humor quando apropriado, e não enchas chuchas. "
        "Limita respostas a 200 palavras salvo pedido contrário.\n"
        "Data atual: usa a informação da pesquisa para saber a data."
    )

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history (last 10 turns for context)
    if conversation_history:
        for hist in conversation_history[-10:]:
            if hist.get("role") in ("user", "assistant"):
                messages.append({"role": hist["role"], "content": hist["content"]})

    # Add user message with search context
    full_message = user_message
    if search_context:
        full_message += search_context

    messages.append({"role": "user", "content": full_message})

    # Call OpenRouter API
    body = json.dumps({
        "model": selected_model,
        "messages": messages,
        "max_tokens": 1500,
        "temperature": 0.7,
    }).encode()

    req = urllib.request.Request(OPENROUTER_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://pirate-tv.pages.dev",
        "X-Title": "OWL Telegram Bot",
    })

    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read())
        response_text = result["choices"][0]["message"]["content"].strip()

        return {
            "response": response_text,
            "search_results": search_results,
            "model": result.get("model", selected_model),
            "error": None,
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {
            "response": "",
            "search_results": [],
            "error": f"HTTP {e.code}: {body[:200]}",
        }
    except Exception as e:
        return {
            "response": "",
            "search_results": [],
            "error": str(e),
        }


def _should_search(message: str) -> bool:
    """Decide se a mensagem precisa de pesquisa web."""
    # Always search if question-like or contains keywords
    search_indicators = [
        "?", "o que", "quem", "quando", "onde", "como", "porquê", "porque",
        "qual", "quais", "notícias", "news", "pesquisa", "procura", "busca",
        "meteo", "tempo", "hoje", "agora", "atual", "último", "última",
        "preço", "cotação", "resultado", "score", "pontuação",
        "está", "estão", "são", "foi", "será", "tem", "teve",
    ]

    msg_lower = message.lower()
    for indicator in search_indicators:
        if indicator in msg_lower:
            return True

    # Search if message is long enough to be a question
    if len(message.split()) >= 4 and "?" in message:
        return True

    # Don't search for casual conversation
    casual = ["olá", "ola", "hey", "hi", "hello", "tudo bem", "como estás", "comoestas", "bom dia", "boa tarde", "boa noite"]
    if any(c in msg_lower for c in casual) and len(message.split()) <= 5:
        return False

    return True  # Default: search


# === Simple chat without history (for command-based usage) ===
def ask(message: str, use_search: bool = True) -> str:
    """
    Pergunta simples ao LLM. Retorna a resposta como string.
    """
    result = chat_with_llm(message, use_search=use_search)
    if result["error"]:
        return f"❌ Erro: {result['error']}"
    return result["response"]
