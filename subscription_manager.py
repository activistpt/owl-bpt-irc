#!/usr/bin/env python3
"""
OWL Telegram Bot — Subscription Manager
Sistema de assinaturas VIP com códigos de ativação.
"""

import os
import json
import random
import string
from datetime import datetime, timedelta

SUBS_FILE = os.path.expanduser("~/.hermes/telegram_subscriptions.json")

# === Defaults ===
DEFAULT_DURATION_DAYS = 30
CODE_LENGTH = 12  # Ex: VIP-O3KM-409M (sem hífens: 8 chars)


def load_subs() -> dict:
    """Carregar subscrições do ficheiro JSON."""
    if not os.path.exists(SUBS_FILE):
        return {"users": {}, "codes": {}}
    with open(SUBS_FILE, "r") as f:
        return json.load(f)


def save_subs(data: dict):
    """Guardar subscrições no ficheiro JSON."""
    os.makedirs(os.path.dirname(SUBS_FILE), exist_ok=True)
    with open(SUBS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_code(plan: str = "VIP", duration_days: int = DEFAULT_DURATION_DAYS) -> str:
    """
    Gera um código único de ativação.
    Formato: VIP-XXXX (8 chars alfanuméricos aleatórios)
    Garante unicidade contra códigos já existentes.
    """
    data = load_subs()

    while True:
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        # Format: VIP-O3KM-409M
        code = f"{plan.upper()}-{suffix[:4]}-{suffix[4:]}"
        if code not in data.get("codes", {}):
            break

    data.setdefault("codes", {})
    data["codes"][code] = {
        "plan": plan.upper(),
        "duration_days": duration_days,
        "generated_at": datetime.now().isoformat(),
        "used_by": None,
        "used_at": None,
        "active": False,
    }
    save_subs(data)
    return code


def activate_code(code: str, user_id: int, username: str = "") -> dict:
    """
    Ativa um código para um utilizador.
    Retorna dict com status e mensagem.
    """
    data = load_subs()
    codes = data.get("codes", {})

    code_upper = code.strip().upper()

    if code_upper not in codes:
        return {"success": False, "message": "❌ Código inválido. Verifica e tenta novamente."}

    code_data = codes[code_upper]

    if code_data.get("active") and code_data.get("used_by") != user_id:
        return {"success": False, "message": "❌ Este código já foi utilizado por outro utilizador."}

    # Verificar se o utilizador já tem VIP ativo
    users = data.get("users", {})
    if str(user_id) in users:
        existing = users[str(user_id)]
        if existing.get("active"):
            expiry = datetime.fromisoformat(existing["expiry"])
            if expiry > datetime.now():
                return {
                    "success": False,
                    "message": f"❌ Já tens VIP ativo até {expiry.strftime('%d/%m/%Y')}.\nUsa o código quando a assinatura atual expirar."
                }
            else:
                # Expirado — pode reativar com novo código
                pass

    # Calcular expiração
    expires = datetime.now() + timedelta(days=code_data["duration_days"])

    # Ativar
    code_data["active"] = True
    code_data["used_by"] = user_id
    code_data["used_at"] = datetime.now().isoformat()
    codes[code_upper] = code_data

    # Registar utilizador
    users[str(user_id)] = {
        "username": username,
        "plan": code_data["plan"],
        "activated_at": datetime.now().isoformat(),
        "expiry": expires.isoformat(),
        "active": True,
        "code_used": code_upper,
    }

    data["codes"] = codes
    data["users"] = users
    save_subs(data)

    return {
        "success": True,
        "message": f"🎉 Assinatura {code_data['plan']} Ativada!\n\n"
                   f"🟢 Status: Ativo ({code_data['plan']})\n"
                   f"📅 Expira em: {expires.strftime('%d/%m/%Y')} às {expires.strftime('%H:%M')}",
        "expires": expires,
        "plan": code_data["plan"],
    }


def check_vip(user_id: int) -> dict:
    """
    Verifica o status VIP de um utilizador.
    Retorna dict com info do status.
    """
    data = load_subs()
    users = data.get("users", {})

    if str(user_id) not in users:
        return {"active": False, "message": "Sem assinatura."}

    user_data = users[str(user_id)]
    expires = datetime.fromisoformat(user_data["expiry"])

    if expires < datetime.now():
        user_data["active"] = False
        users[str(user_id)] = user_data
        data["users"] = users
        save_subs(data)
        return {"active": False, "message": "Expirou.", "expired": True}

    days_left = (expires - datetime.now()).days
    return {
        "active": True,
        "plan": user_data.get("plan", "VIP"),
        "expires": expires,
        "days_left": days_left,
        "message": f"VIP {user_data.get('plan', 'VIP')} — {days_left} dias restantes",
    }


def revoke_vip(user_id: int) -> bool:
    """Remove VIP de um utilizador (admin)."""
    data = load_subs()
    users = data.get("users", {})
    if str(user_id) in users:
        users[str(user_id)]["active"] = False
        data["users"] = users
        save_subs(data)
        return True
    return False


def list_codes() -> list:
    """Lista todos os códigos gerados."""
    data = load_subs()
    result = []
    for code, info in data.get("codes", {}).items():
        result.append({
            "code": code,
            "plan": info.get("plan", "?"),
            "active": info.get("active", False),
            "used_by": info.get("used_by"),
            "used_at": info.get("used_at"),
            "duration": info.get("duration_days", 30),
        })
    return result


def list_active_users() -> list:
    """Lista utilizadores com VIP ativo."""
    data = load_subs()
    result = []
    for uid, info in data.get("users", {}).items():
        if info.get("active"):
            try:
                expires = datetime.fromisoformat(info["expiry"])
                if expires > datetime.now():
                    result.append({
                        "user_id": uid,
                        "username": info.get("username", "?"),
                        "plan": info.get("plan", "?"),
                        "expires": expires.strftime("%d/%m/%Y"),
                        "days_left": (expires - datetime.now()).days,
                    })
            except (ValueError, KeyError):
                pass
    return result
