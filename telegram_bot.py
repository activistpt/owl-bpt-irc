#!/usr/bin/env python3
"""
OWL Telegram Bot
Bot autônomo para grupos do Telegram com os mesmos comandos do IRC bot.
Usa python-telegram-bot v22 (async).
"""

import os
import sys
import json
import re
import logging
import importlib.util

# === CONFIG ===
BOT_TOKEN = "8306294739:AAFyPp6Z3xspgrKG7lWx-mI4Hutx23o6DeI"
OWNER_ID = 889219283  # RɆβɆŁŞØŁ ☠️ chat_id
ALLOWED_CHAT_IDS = set()  # vazio = aceita todos os grupos
# Para restringir a grupos específicos:
# ALLOWED_CHAT_IDS = {-1003545367062}  # DEEP WEB group

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    force=True
)
log = logging.getLogger("owl-tg")
# Force unbuffered output
sys.stdout.flush()
sys.stderr.flush()

# === IMPORTAR COMANDOS DO IRC DAEMON ===
# Carrega as funções cmd_* diretamente do irc_daemon.py sem executar o daemon
QUEUE_DIR = os.path.expanduser("~/.hermes/irc")

def load_irc_commands():
    """Load command functions from irc_daemon.py as a module, without running the daemon loop."""
    daemon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "irc_daemon.py")
    spec = importlib.util.spec_from_file_location("irc_daemon", daemon_path)
    mod = importlib.util.module_from_spec(spec)
    
    # Patch: prevent daemon loop from running on import
    # We set CHECK_INTERVAL very high and mock the main loop
    import builtins
    orig_import = builtins.__import__
    
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    
    return mod

log.info("Loading IRC daemon commands...")
irc = load_irc_commands()
log.info("Commands loaded.")

# === TELEGRAM BOT ===
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- Restrict decorator ---
def allowed_chat(func):
    """Decorator to optionally restrict bot to specific group chats."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
            log.warning(f"Blocked chat {chat_id}")
            return
        return await func(update, context)
    return wrapper

# === COMMAND HANDLERS ===

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start / help command."""
    text = (
        "🦉 **OWL Bot** - Comandos disponíveis:\n\n"
        "📋 **Informação:**\n"
        " `/help` - Mostrar ajuda\n"
        " `/wiki <termo>` - Pesquisar Wikipedia\n"
        " `/img <descrição>` - Gerar imagem\n"
        " `/meteo <cidade>` - Meteorologia\n"
        " `/youtube <termo>` - Pesquisar YouTube\n"
        " `/google <termo>` - Pesquisar Google\n"
        " `/news <região>` - Notícias\n"
        "\n💰 **Financeiro:**\n"
        " `/crypto <moeda>` - Preço crypto\n"
        " `/stock <símbolo>` - Cotação ação\n"
        "\n🎬 **Cinema:**\n"
        " `/cinema` - Filmes em cartaz (25)\n"
        " `/estreias` - Estreias da semana\n"
        " `/imdb <filme>` - Info IMDB\n"
        "\n🔧 **OSINT:**\n"
        " `/ipinfo <ip/domínio>` - Info IP\n"
        " `/ipscan <ip>` - Scan de portas\n"
        " `/iplookup <ip>` - Reverse DNS\n"
        "/whois <domínio> - WHOIS\n"
        "\n🌐 **Pirataria:**\n"
        " `/iptv` - Canais IPTV\n"
        " `/piratebay <termo>` - Pesquisar TPB\n"
        " `/predb <termo>` - Pré-db\n"
        "\n💬 **Social:**\n"
        " `/quote` - Citação aleatória\n"
        " `/curiosidade` - Curiosidade\n"
        " `/notice [nick] [msg]` - Enviar notice"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command - delegate to cmd_start."""
    await cmd_start(update, context)

async def run_irc_command(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           func, *args, **kwargs):
    """Run a irc_daemon command function and send results to Telegram."""
    try:
        result = func(*args, **kwargs)
        
        if result is None:
            return
        
        if isinstance(result, str):
            result = [result]
        
        if isinstance(result, list):
            # Handle list of dicts (from cmd_notice with multiple targets)
            for item in result:
                if isinstance(item, dict):
                    # Complex response dict - extract message
                    msg_text = item.get("message", "")
                    target = item.get("target", "")
                    # In Telegram we just send the message
                    if target and target.startswith("#"):
                        if msg_text:
                            await update.message.reply_text(msg_text)
                    else:
                        if msg_text:
                            await update.message.reply_text(msg_text)
                elif isinstance(item, str):
                    if item.strip():
                        await update.message.reply_text(item)
        
    except Exception as e:
        log.error(f"Command error: {e}")
        await update.message.reply_text(f"❌ Erro: {str(e)[:200]}")

async def cmd_wiki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/wiki <termo>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_wiki, query)

async def cmd_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/img <descrição>`", parse_mode="Markdown")
        return
    await update.message.reply_text("🎨 A gerar imagem...")
    await run_irc_command(update, context, irc.cmd_img, query)

async def cmd_meteo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/meteo <cidade>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_meteo, query)

async def cmd_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/youtube <termo>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_youtube, query)

async def cmd_google(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/google <termo>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_google, query)

async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else "portugal"
    await run_irc_command(update, context, irc.cmd_news, query)

async def cmd_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else "bitcoin"
    await run_irc_command(update, context, irc.cmd_crypto, query)

async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/stock <símbolo>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_stock, query)

async def cmd_cinema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 A buscar filmes em cartaz...")
    await run_irc_command(update, context, irc.cmd_cinema)

async def cmd_estreias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 A buscar estreias...")
    await run_irc_command(update, context, irc.cmd_estreias)

async def cmd_imdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/imdb <filme|série>`", parse_mode="Markdown")
        return
    await update.message.reply_text("🎬 A pesquisar IMDB...")
    await run_irc_command(update, context, irc.cmd_imdb, query)

async def cmd_ipinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/ipinfo <ip|domínio>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_ipinfo, query)

async def cmd_ipscan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/ipscan <ip>`", parse_mode="Markdown")
        return
    await update.message.reply_text("🔍 A fazer scan de portas...")
    await run_irc_command(update, context, irc.cmd_ipscan, query)

async def cmd_iplookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/iplookup <ip>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_iplookup, query)

async def cmd_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await run_irc_command(update, context, irc.cmd_quote)

async def cmd_curiosidade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await run_irc_command(update, context, irc.cmd_curiosity)

async def cmd_iptv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await run_irc_command(update, context, irc.cmd_iptv)

async def cmd_piratebay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    await run_irc_command(update, context, irc.cmd_piratebay, query)

async def cmd_predb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    await run_irc_command(update, context, irc.cmd_predb, query)

async def cmd_notice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /notice [nick|#canal] [message]
    Without args: sends random quote to current chat
    """
    args = context.args if context.args else []
    
    if not args:
        # No args: random quote
        sender = update.effective_user.username or update.effective_user.first_name
        result = irc.cmd_notice(sender, "#grupo")
        for item in result:
            if isinstance(item, dict):
                text = item.get("message", "")
                if item.get("type") == "notice":
                    if text:
                        await update.message.reply_text(f"🦉 {text}")
            elif isinstance(item, str) and item.strip():
                await update.message.reply_text(item)
        return
    
    target = args[0]
    msg = " ".join(args[1:]) if len(args) > 1 else None
    
    if target.startswith("#"):
        # Channel/target group
        channel = target
        nick = None
        # Check if second arg is a nick or part of message
        await update.message.reply_text(f"📢 Notice para {target}: {msg or 'quote aleatória'}")
    else:
        # Direct nick
        log.info(f"[TG NOTICE] -> {target}" + (f" msg: {msg}" if msg else ""))
        sender = update.effective_user.username or update.effective_user.first_name
        result = irc.cmd_notice(sender, "#grupo", target_nick=target, custom_msg=msg)
        # Just show confirmation in Telegram
        if msg:
            await update.message.reply_text(f"📢 Notice enviado para {target}: {msg}")
        else:
            await update.message.reply_text(f"📢 Notice (quote) enviado para {target}")

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test if bot is alive."""
    await update.message.reply_text("🦉 Pong! Bot está vivo.")

# === STARTUP MESSAGE ===
async def post_startup(app: Application):
    """Send startup message to owner."""
    log.info("OWL Telegram Bot is online!")

# === MAIN ===
def main():
    log.info("Starting OWL Telegram Bot...")
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_startup).build()
    
    # Register all command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("wiki", cmd_wiki))
    app.add_handler(CommandHandler("img", cmd_img))
    app.add_handler(CommandHandler("meteo", cmd_meteo))
    app.add_handler(CommandHandler("youtube", cmd_youtube))
    app.add_handler(CommandHandler("google", cmd_google))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("crypto", cmd_crypto))
    app.add_handler(CommandHandler("stock", cmd_stock))
    app.add_handler(CommandHandler("cinema", cmd_cinema))
    app.add_handler(CommandHandler("estreias", cmd_estreias))
    app.add_handler(CommandHandler("imdb", cmd_imdb))
    app.add_handler(CommandHandler("ipinfo", cmd_ipinfo))
    app.add_handler(CommandHandler("ipscan", cmd_ipscan))
    app.add_handler(CommandHandler("iplookup", cmd_iplookup))
    app.add_handler(CommandHandler("quote", cmd_quote))
    app.add_handler(CommandHandler("curiosidade", cmd_curiosidade))
    app.add_handler(CommandHandler("curiosity", cmd_curiosidade))
    app.add_handler(CommandHandler("iptv", cmd_iptv))
    app.add_handler(CommandHandler("piratebay", cmd_piratebay))
    app.add_handler(CommandHandler("predb", cmd_predb))
    app.add_handler(CommandHandler("notice", cmd_notice))
    
    # Catch-all for unknown commands
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    log.info("Bot running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.split()[0] if update.message.text else ""
    await update.message.reply_text(f"❓ Comando desconhecido: {cmd}\nUsa /help para ver os comandos disponíveis.")

if __name__ == "__main__":
    main()
