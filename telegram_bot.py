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
from subscription_manager import check_vip, generate_code, activate_code, revoke_vip, list_codes, list_active_users

# === CONFIG ===
BOT_TOKEN = "8306294739:AAFyPp6Z3xspgrKG7lWx-mI4Hutx23o6DeI"
OWNER_ID = 889219283  # RɆβɆŁŞØŁ ☠️ chat_id
ALLOWED_CHAT_IDS = set()  # vazio = aceita todos os grupos
# Para restringir a grupos específicos:
# ALLOWED_CHAT_IDS = {-1003545367062}  # DEEP WEB group

# === COMANDOS QUE NÃO PRECISAM DE VIP ===
FREE_COMMANDS = {"start", "help", "ping", "gerar", "ativar"}

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

# --- Restrict decorator --
def allowed_chat(func):
    """Decorator to optionally restrict bot to specific group chats."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
            log.warning(f"Blocked chat {chat_id}")
            return
        return await func(update, context)
    return wrapper


def vip_required(func):
    """Decorator que verifica se o utilizador tem VIP ativo."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Owner always has access
        user_id = update.effective_user.id
        if user_id == OWNER_ID:
            return await func(update, context)

        # Check if command is free
        command = update.message.text.split()[0].lstrip("/").lower()
        if command in FREE_COMMANDS:
            return await func(update, context)

        # Check VIP status
        status = check_vip(user_id)
        if not status.get("active"):
            await update.message.reply_text(
                "🔒 **Comando VIP**\n\n"
                "Este comando requer uma assinatura VIP ativa.\n"
                "Usa `/ativar <codigo>` para ativar.\n"
                "Não tens um código? Pede a um admin.",
                parse_mode="Markdown",
            )
            return
        return await func(update, context)
    return wrapper

# === COMMAND HANDLERS ===

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start / help command."""
    text = (
        "🦉 **OWL Bot** - Comandos disponíveis:\n\n"
        "📋 **Geral (Grátis):**\n"
        " `/start` - Iniciar bot\n"
        " `/status` - Ver estado VIP\n"
        " `/ativar <codigo>` - Ativar código VIP\n"
        " `/ping` - Testar bot\n\n"
        "💰 **VIP:**\n"
        " `/help` - Mostrar ajuda\n"
        " `/wiki <termo>` - Pesquisar Wikipedia\n"
        " `/img <descrição>` - Gerar imagem\n"
        " `/meteo <cidade>` - Meteorologia\n"
        " `/youtube <termo>` - Pesquisar YouTube\n"
        " `/google <termo>` - Pesquisar Google\n"
        " `/news <região>` - Notícias\n"
        " `/crypto <moeda>` - Preço crypto\n"
        " `/stock <símbolo>` - Cotação ação\n\n"
        "🎬 **Cinema:**\n"
        " `/cinema` - Filmes em cartaz (25)\n"
        " `/estreias` - Estreias da semana\n"
        " `/imdb <filme>` - Info IMDB\n"
        " `/play <url-imdb>` - Gerar link PlayIMDB\n\n"
        "🔧 **OSINT:**\n"
        " `/ipinfo <ip/domínio>` - Info IP\n"
        " `/ipscan <ip>` - Scan de portas\n"
        " `/iplookup <ip>` - Reverse DNS\n\n"
        "🌐 **Pirataria:**\n"
        " `/iptv` - Canais IPTV\n"
        " `/piratebay <termo>` - Pesquisar TPB\n"
        " `/predb <termo>` - Pré-db\n\n"
        "💬 **Social:**\n"
        " `/quote` - Citação aleatória\n"
        " `/curiosidade` - Curiosidade\n"
        " `/notice [nick] [msg]` - Enviar notice\n\n"
        "🔑 **Admin:**\n"
        " `/gerar [VIP|premium] [dias]` - Gerar código\n"
        " `/revoke <user_id>` - Revogar VIP\n"
        " `/vips` - Listar VIPs ativos\n"
        " `/codes` - Listar códigos\n"
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

@vip_required
async def cmd_wiki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/wiki <termo>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_wiki, query)


@vip_required
async def cmd_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/img <descrição>`", parse_mode="Markdown")
        return
    await update.message.reply_text("🎨 A gerar imagem...")
    await run_irc_command(update, context, irc.cmd_img, query)


@vip_required
async def cmd_meteo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/meteo <cidade>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_meteo, query)


@vip_required
async def cmd_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/youtube <termo>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_youtube, query)


@vip_required
async def cmd_google(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/google <termo>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_google, query)


@vip_required
async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else "portugal"
    await run_irc_command(update, context, irc.cmd_news, query)


@vip_required
async def cmd_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else "bitcoin"
    await run_irc_command(update, context, irc.cmd_crypto, query)


@vip_required
async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/stock <símbolo>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_stock, query)


@vip_required
async def cmd_cinema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 A buscar filmes em cartaz...")
    await run_irc_command(update, context, irc.cmd_cinema)


@vip_required
async def cmd_estreias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 A buscar estreias...")
    await run_irc_command(update, context, irc.cmd_estreias)


@vip_required
async def cmd_imdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/imdb <filme|série>`", parse_mode="Markdown")
        return
    await update.message.reply_text("🎬 A pesquisar IMDB...")
    await run_irc_command(update, context, irc.cmd_imdb, query)


@vip_required
async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate playimdb link from IMDB URL or ID."""
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/play <url-imdb>`\nEx: `/play https://www.imdb.com/title/tt0133093/`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_play, query)


@vip_required
async def cmd_ipinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/ipinfo <ip|domínio>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_ipinfo, query)


@vip_required
async def cmd_ipscan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/ipscan <ip>`", parse_mode="Markdown")
        return
    await update.message.reply_text("🔍 A fazer scan de portas...")
    await run_irc_command(update, context, irc.cmd_ipscan, query)


@vip_required
async def cmd_iplookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ Uso: `/iplookup <ip>`", parse_mode="Markdown")
        return
    await run_irc_command(update, context, irc.cmd_iplookup, query)


@vip_required
async def cmd_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await run_irc_command(update, context, irc.cmd_quote)


@vip_required
async def cmd_curiosidade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await run_irc_command(update, context, irc.cmd_curiosity)


@vip_required
async def cmd_iptv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await run_irc_command(update, context, irc.cmd_iptv)


@vip_required
async def cmd_piratebay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    await run_irc_command(update, context, irc.cmd_piratebay, query)


@vip_required
async def cmd_predb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    await run_irc_command(update, context, irc.cmd_predb, query)


@vip_required
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

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verificar status VIP do utilizador."""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "?"
    
    if user_id == OWNER_ID:
        await update.message.reply_text("👑 **ADMIN** — Acesso total (Owner)")
        return
    
    status = check_vip(user_id)
    if status.get("active"):
        expires = status["expires"]
        await update.message.reply_text(
            f"🟢 **Status: VIP Ativo**\n\n"
            f"📋 Plano: {status.get('plan', 'VIP')}\n"
            f"📅 Expira: {expires.strftime('%d/%m/%Y')} às {expires.strftime('%H:%M')}\n"
            f"⏳ Dias restantes: {status.get('days_left', '?')}"
        )
    else:
        if status.get("expired"):
            await update.message.reply_text(
                "🔴 **Status: VIP Expirado**\n\n"
                "A tua assinatura expirou.\n"
                "Usa `/ativar <codigo>` para renovar com um novo código."
            )
        else:
            await update.message.reply_text(
                "⚪ **Status: Sem Assinatura**\n\n"
                "Não tens uma assinatura VIP.\n"
                "Usa `/ativar <codigo>` se tiveres um código."
            )


async def cmd_gerar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    [ADMIN] Gerar um código VIP.
    Uso: /gerar [VIP|premium] [dias]
    Padrão: VIP 30 dias.
    Somente o owner pode gerar códigos.
    """
    user_id = update.effective_user.id
    
    # Verificar se é o owner
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Apenas o admin pode gerar códigos.")
        return
    
    args = context.args if context.args else []
    plan = "VIP"
    days = 30
    
    if args:
        first = args[0].upper()
        if first in ("VIP", "PREMIUM", "TRIAL"):
            plan = first
            args = args[1:]
        # Check if first arg is a number (days)
        if args and args[0].isdigit():
            days = int(args[0])
            args = args[1:]
        elif not plan and first.isdigit():
            days = int(first)
    
    code = generate_code(plan=plan, duration_days=days)
    await update.message.reply_text(
        f"✅ **Código Gerado!**\n\n"
        f"🎫 Código: `{code}`\n"
        f"📋 Plano: {plan}\n"
        f"📅 Duração: {days} dias\n\n"
        f"Para ativar: `/ativar {code}`",
        parse_mode="Markdown",
    )


async def cmd_ativar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ativar um código VIP.
    Uso: /ativar <codigo>
    """
    args = context.args if context.args else []
    if not args:
        await update.message.reply_text(
            "⚠️ Uso: `/ativar <codigo>`\nEx: `/ativar VIP-O3KM-409M`",
            parse_mode="Markdown",
        )
        return
    
    code = args[0].strip().upper()
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "?"
    
    result = activate_code(code, user_id, username)
    await update.message.reply_text(result["message"])


async def cmd_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """[ADMIN] Revogar VIP de um utilizador. Uso: /revoke <user_id>"""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Apenas o admin pode revogar VIP.")
        return
    
    args = context.args if context.args else []
    if not args:
        await update.message.reply_text("⚠️ Uso: `/revoke <user_id>`")
        return
    
    target_id = int(args[0])
    if revoke_vip(target_id):
        await update.message.reply_text(f"✅ VIP revogado do utilizador {target_id}.")
    else:
        await update.message.reply_text(f"❌ Utilizador {target_id} não encontrado.")


async def cmd_vips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """[ADMIN] Listar utilizadores VIP ativos."""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Apenas o admin.")
        return
    
    users = list_active_users()
    if not users:
        await update.message.reply_text("📋 Nenhum VIP ativo.")
        return
    
    lines = ["🟢 **VIPs Ativos:**\n"]
    for u in users:
        lines.append(
            f"👤 `{u['user_id']}` — @{u['username']} | "
            f"{u['plan']} | {u['expiry']} ({u['days_left']}d)"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """[ADMIN] Listar todos os códigos gerados."""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Apenas o admin.")
        return
    
    codes = list_codes()
    if not codes:
        await update.message.reply_text("📋 Nenhum código gerado.")
        return
    
    lines = ["🎫 **Códigos Gerados:**\n"]
    for c in codes:
        status = "🟢 Usado" if c["active"] else "⚪ Livre"
        used = f" (por {c['used_by']})" if c.get("used_by") else ""
        lines.append(f"`{c['code']}` — {c['plan']} {c['duration']}d — {status}{used}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


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
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ativar", cmd_ativar))
    app.add_handler(CommandHandler("gerar", cmd_gerar))
    app.add_handler(CommandHandler("revoke", cmd_revoke))
    app.add_handler(CommandHandler("vips", cmd_vips))
    app.add_handler(CommandHandler("codes", cmd_codes))
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
    app.add_handler(CommandHandler("play", cmd_play))
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
