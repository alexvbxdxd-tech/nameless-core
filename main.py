import os
import re
import time
import json
import telebot
from flask import Flask
from threading import Thread
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
RANKS_FILE = "ranks.json"
SETTINGS_FILE = "settings.json"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

GROUP_NAME = os.getenv("GROUP_NAME")
OWNER_URL = os.getenv("OWNER_URL")
GROUP_URL = os.getenv("GROUP_URL")
CHK_BOT_USERNAME = os.getenv("CHK_BOT_USERNAME")

CHK_BOT_URL = f"https://t.me/{CHK_BOT_USERNAME}"

WARNS_FILE = "warns.json"
MAX_WARNS = 3

USERS_FILE = "users_cache.json"

SPAM_FILE = "daily_spam.json"

SPAM_LIMIT = 4
SPAM_SOFT_LIMIT = 6
SPAM_MUTE_LIMIT = 7

SPAM_MIN_LEN = 150

# =========================
# UTILIDADES
# =========================

def load_warns():
    if not os.path.exists(WARNS_FILE):
        return {}
    with open(WARNS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_warns(data):
    with open(WARNS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def is_owner(user_id):
    return user_id == OWNER_ID


def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except:
        return False


def admin_only(m):
    return is_admin(m.chat.id, m.from_user.id)


def owner_only(m):
    return is_owner(m.from_user.id)


def user_text(user):
    name = user.first_name or "Usuario"
    username = f"@{user.username}" if user.username else "Sin username"
    return name, username, user.id


def now_date():
    return time.strftime("%d/%m/%Y %H:%M:%S")


def parse_time(text):
    match = re.match(r"^(\d+)(s|m|h|d)$", text.lower())
    if not match:
        return None

    num = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return num
    if unit == "m":
        return num * 60
    if unit == "h":
        return num * 3600
    if unit == "d":
        return num * 86400

    return None


def get_target(m, args_start=1):
    if m.reply_to_message:
        target = m.reply_to_message.from_user
        cache_user(m.chat.id, target)

        reason = " ".join(m.text.split()[args_start:]) or "Sin motivo"
        return target.id, target.first_name, target.username, reason

    parts = m.text.split()

    if len(parts) <= args_start:
        return None, None, None, None

    raw_target = parts[args_start]
    reason = " ".join(parts[args_start + 1:]) or "Sin motivo"

    cached = get_cached_user(m.chat.id, raw_target)

    if cached:
        user_id = int(cached["id"])
        name = cached["names"][-1] if cached.get("names") else f"ID {user_id}"
        username = cached["usernames"][-1] if cached.get("usernames") else None
        return user_id, name, username, reason

    try:
        user_id = int(raw_target)
        return user_id, f"ID {user_id}", None, reason
    except:
        return None, None, None, None


def ficha(chat_id, accion, user_id, name, username, mod, motivo):
    user_label = f"@{username}" if username else "Sin username"

    text = f"""
<b>💀 NAMELESS CORE</b>

━━━━━━━━━━━━━━
<b>ACCIÓN:</b> <code>{accion}</code>

👤 <b>Usuario:</b> {name}
🔗 <b>Username:</b> <code>{user_label}</code>
🆔 <b>ID:</b> <code>{user_id}</code>

👑 <b>Moderador:</b> {mod.first_name}
📝 <b>Motivo:</b> <code>{motivo}</code>

🕒 <b>Fecha:</b> <code>{now_date()}</code>
━━━━━━━━━━━━━━
<i>Control aplicado.</i>
"""
    bot.send_message(chat_id, text)


def today_key():
    return time.strftime("%Y-%m-%d")


def load_spam():
    if not os.path.exists(SPAM_FILE):
        return {}

    with open(SPAM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_spam(data):
    with open(SPAM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def seconds_until_midnight():
    now = time.localtime()

    tomorrow = time.mktime((
        now.tm_year,
        now.tm_mon,
        now.tm_mday + 1,
        0, 0, 0,
        now.tm_wday,
        now.tm_yday,
        now.tm_isdst
    ))

    return int(tomorrow - time.time())

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def cache_user(chat_id, user):
    data = load_users()

    chat_id = str(chat_id)
    user_id = str(user.id)

    if chat_id not in data:
        data[chat_id] = {}

    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    username = user.username or None

    if user_id not in data[chat_id]:
        data[chat_id][user_id] = {
            "id": user.id,
            "names": [],
            "usernames": [],
            "joined_at": now_date(),
            "last_seen": now_date()
        }

    record = data[chat_id][user_id]

    if full_name and full_name not in record["names"]:
        record["names"].append(full_name)

    if username and username not in record["usernames"]:
        record["usernames"].append(username)

    record["last_seen"] = now_date()

    save_users(data)


def get_cached_user(chat_id, value):
    data = load_users()
    chat_id = str(chat_id)

    if chat_id not in data:
        return None

    value = str(value).replace("@", "").lower()

    for user_id, info in data[chat_id].items():
        if str(user_id) == value:
            return info

        for username in info.get("usernames", []):
            if username.lower() == value:
                return info

    return None


def botones():
    kb = InlineKeyboardMarkup(row_width=2)

    if GROUP_URL:
        kb.add(InlineKeyboardButton("💀 Grupo", url=GROUP_URL))

    if OWNER_URL:
        kb.add(InlineKeyboardButton("👑 Owner", url=OWNER_URL))

    if CHK_BOT_USERNAME:
        kb.add(InlineKeyboardButton("🍪 CHK", url=CHK_BOT_URL))

    return kb


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_rank(chat_id, user_id):
    data = load_json_file(RANKS_FILE, {})
    return data.get(str(chat_id), {}).get(str(user_id))

def set_rank(chat_id, user_id, rank):
    data = load_json_file(RANKS_FILE, {})
    chat_id = str(chat_id)
    user_id = str(user_id)

    if chat_id not in data:
        data[chat_id] = {}

    data[chat_id][user_id] = rank
    save_json_file(RANKS_FILE, data)

def remove_rank(chat_id, user_id):
    data = load_json_file(RANKS_FILE, {})
    chat_id = str(chat_id)
    user_id = str(user_id)

    if chat_id in data and user_id in data[chat_id]:
        del data[chat_id][user_id]
        save_json_file(RANKS_FILE, data)

def fake_closed(chat_id):
    data = load_json_file(SETTINGS_FILE, {})
    return data.get(str(chat_id), {}).get("fake_closed", False)

def set_fake_closed(chat_id, value):
    data = load_json_file(SETTINGS_FILE, {})
    chat_id = str(chat_id)

    if chat_id not in data:
        data[chat_id] = {}

    data[chat_id]["fake_closed"] = value
    save_json_file(SETTINGS_FILE, data)

def can_talk_when_closed(chat_id, user_id):
    if is_admin(chat_id, user_id):
        return True

    rank = get_rank(chat_id, user_id)
    return rank in ["FREE", "SELLER", "VIP", "TRUSTED"]


# =========================
# PÚBLICO
# =========================

@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(m.chat.id, f"""
<b>💀 NAMELESS CORE</b>

━━━━━━━━━━━━━━
<b>{GROUP_NAME}</b>

🛡 Moderación activa
⚡ Sistema privado
👁 Grupo bajo control

━━━━━━━━━━━━━━
Comandos públicos:
/reglas
/owner
/id
/staff
/chk
/checker
""", reply_markup=botones())


@bot.message_handler(commands=["cerrar"])
def cerrar_fake(m):
    if not admin_only(m):
        return

    set_fake_closed(m.chat.id, True)

    bot.send_message(m.chat.id, """
<b>🔒 GRUPO CERRADO</b>

Solo staff y rangos autorizados pueden hablar.
""")

@bot.message_handler(commands=["abrir"])
def abrir_fake(m):
    if not admin_only(m):
        return

    set_fake_closed(m.chat.id, False)

    bot.send_message(m.chat.id, """
<b>🔓 GRUPO ABIERTO</b>

Todos pueden hablar otra vez.
""")


@bot.message_handler(commands=["free"])
def fake_free(m):
    if not admin_only(m):
        return

    if not m.reply_to_message:
        bot.reply_to(m, "Responde al usuario con /free")
        return

    user = m.reply_to_message.from_user
    set_rank(m.chat.id, user.id, "FREE")

    bot.send_message(m.chat.id, f"""
<b>🆓 FREE ACTIVADO</b>

👤 Usuario: <b>{user.first_name}</b>
🆔 ID: <code>{user.id}</code>

Ahora puede hablar cuando el grupo esté cerrado falsamente.
""")


@bot.message_handler(commands=["unfree"])
def fake_unfree(m):
    if not admin_only(m):
        return

    if not m.reply_to_message:
        bot.reply_to(m, "Responde al usuario con /unfree")
        return

    user = m.reply_to_message.from_user
    remove_rank(m.chat.id, user.id)

    bot.send_message(m.chat.id, f"⚠️ FREE removido: <code>{user.id}</code>")



@bot.message_handler(commands=["reglas", "rules"])
def reglas(m):
    bot.send_message(m.chat.id, """
<b>📜 REGLAS DEL GRUPO</b>

━━━━━━━━━━━━━━
✅ Ventas permitidas
✅ Publicidad permitida
✅ Todo debe ser trato Admin

❌ No Spam extremo
❌ No estafas
❌ No contenido enfermo

━━━━━━━━━━━━━━
<b>Respeta o sales.</b>
""")


@bot.message_handler(commands=["owner"])
def owner(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("👑 Contactar Owner", url=OWNER_URL))
    bot.send_message(m.chat.id, "<b>👑 Owner oficial</b>", reply_markup=kb)


@bot.message_handler(commands=["id"])
def get_id(m):
    if m.reply_to_message:
        user = m.reply_to_message.from_user
    else:
        user = m.from_user

    name, username, user_id = user_text(user)

    bot.send_message(m.chat.id, f"""
<b>🆔 INFO USUARIO</b>

👤 Nombre: <b>{name}</b>
🔗 Username: <code>{username}</code>
🆔 ID: <code>{user_id}</code>
""")


@bot.message_handler(commands=["staff", "admins"])
def staff(m):
    try:
        admins_list = bot.get_chat_administrators(m.chat.id)

        text = """
<b>👑 STAFF DEL GRUPO</b>

━━━━━━━━━━━━━━
"""

        count = 0

        for admin in admins_list:
            user = admin.user

            if user.is_bot:
                continue

            title = admin.custom_title or ""

            if title.upper() == "FREE":
                continue

            if admin.status == "creator":
                rango = "Owner"
            elif title.upper() == "SELLER":
                rango = "Seller"
            else:
                rango = "Admin"

            username = f"@{user.username}" if user.username else "Sin username"

            text += f"""
<b>{rango}</b>
👤 {user.first_name}
🔗 <code>{username}</code>
🆔 <code>{user.id}</code>
━━━━━━━━━━━━━━
"""
            count += 1

        if count == 0:
            text += "\nNo hay staff visible."

        bot.send_message(m.chat.id, text)

    except Exception as e:
        bot.reply_to(m, f"❌ Error mostrando staff: <code>{e}</code>")


@bot.message_handler(commands=["chk", "checker"])
def chk_bot(m):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🍪 Abrir Bot CHK", url=CHK_BOT_URL)
    )

    bot.send_message(m.chat.id, f"""
<b>🍪 BOT OFICIAL CHK</b>

━━━━━━━━━━━━━━
🤖 Bot:
<code>@{CHK_BOT_USERNAME}</code>

Este es el bot oficial para:
🍪 Cookies
🎟 Keys
💎 Créditos
⚡ Servicios CHK

━━━━━━━━━━━━━━
<b>Usa únicamente el bot oficial.</b>
""", reply_markup=kb)


@bot.message_handler(content_types=["new_chat_members"])
def welcome(m):

    for user in m.new_chat_members:

        cache_user(m.chat.id, user)

        username = f"@{user.username}" if user.username else "Sin username"

        bot.send_message(m.chat.id, f"""
<b>💀 NAMELESS CORE</b>

━━━━━━━━━━━━━━━━━━
<b>⚡ NUEVO INGRESO DETECTADO</b>

👤 Usuario:
<b>{user.first_name}</b>

🔗 Username:
<code>{username}</code>

🆔 ID:
<code>{user.id}</code>

━━━━━━━━━━━━━━━━━━
🔥 Publica sin miedo
⚠️ Sin flood extremo
🛡 Respeta y vende limpio
🛡 Todo spam debe llevar Trato Admin

🍪 Usa:
<code>/chk</code>
para abrir el bot oficial

━━━━━━━━━━━━━━━━━━
<b>{GROUP_NAME}</b>

<i>El grupo habla solo.</i>
""", reply_markup=botones())


# =========================
# PANEL ADMIN
# =========================

@bot.message_handler(commands=["panel"])
def panel(m):
    if not admin_only(m):
        return

    bot.send_message(m.chat.id, """
<b>⚙️ PANEL NAMELESS</b>

━━━━━━━━━━━━━━
<b>Moderación:</b>

/ban ID motivo
/ban responder motivo

/sban ID motivo
/sban responder motivo

/kick ID motivo
/kick responder motivo

/mute ID motivo
/mute responder motivo

/tmute ID 10m motivo
/tmute responder 10m motivo

/unmute ID
/unmute responder

/unban ID

/warn ID motivo
/warn responder motivo

/warns ID
/warns responder

/resetwarns ID
/resetwarns responder

/del responder
/purge responder
/pin responder
/unpin

<b>Owner:</b>

/promote responder
/demote responder
/seller responder
/unseller responder
/info ID
/info @username
/info responder
━━━━━━━━━━━━━━
<b>Tiempo:</b>
10s = segundos
10m = minutos
2h = horas
7d = días
""")


# =========================
# MODERACIÓN
# =========================

@bot.message_handler(commands=["ban"])
def ban(m):
    if not admin_only(m):
        return

    user_id, name, username, reason = get_target(m)

    if not user_id:
        bot.reply_to(m, "Uso: /ban ID motivo o responde con /ban motivo")
        return

    if is_admin(m.chat.id, user_id):
        bot.reply_to(m, "❌ No puedes moderar otro admin.")
        return
    
    try:
        bot.ban_chat_member(m.chat.id, user_id)
        ficha(m.chat.id, "BAN", user_id, name, username, m.from_user, reason)
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["sban"])
def sban(m):
    if not admin_only(m):
        return

    user_id, name, username, reason = get_target(m)

    if not user_id:
        bot.reply_to(m, "Uso: /sban ID motivo o responde con /sban motivo")
        return

    if is_admin(m.chat.id, user_id):
        bot.reply_to(m, "❌ No puedes moderar otro admin.")
        return

    try:
        bot.ban_chat_member(m.chat.id, user_id)
        try:
            bot.delete_message(m.chat.id, m.message_id)
        except:
            pass
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["unban"])
def unban(m):
    if not admin_only(m):
        return

    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m, "Uso: /unban ID")
        return

    try:
        user_id = int(parts[1])
        bot.unban_chat_member(m.chat.id, user_id)
        bot.send_message(m.chat.id, f"""
<b>✅ USUARIO DESBANEADO</b>

🆔 ID: <code>{user_id}</code>
👑 Admin: {m.from_user.first_name}
🕒 Fecha: <code>{now_date()}</code>
""")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["kick"])
def kick(m):
    if not admin_only(m):
        return

    user_id, name, username, reason = get_target(m)

    if not user_id:
        bot.reply_to(m, "Uso: /kick ID motivo o responde con /kick motivo")
        return

    if is_admin(m.chat.id, user_id):
        bot.reply_to(m, "❌ No puedes moderar otro admin.")
        return
    
    try:
        bot.ban_chat_member(m.chat.id, user_id)
        bot.unban_chat_member(m.chat.id, user_id)
        ficha(m.chat.id, "KICK", user_id, name, username, m.from_user, reason)
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["mute"])
def mute(m):
    if not admin_only(m):
        return

    user_id, name, username, reason = get_target(m)

    if not user_id:
        bot.reply_to(m, "Uso: /mute ID motivo o responde con /mute motivo")
        return

    if is_admin(m.chat.id, user_id):
        bot.reply_to(m, "❌ No puedes moderar otro admin.")
        return

    try:
        bot.restrict_chat_member(
            m.chat.id,
            user_id,
            permissions=ChatPermissions(
                can_send_messages=False
            )
        )
        ficha(m.chat.id, "MUTE", user_id, name, username, m.from_user, reason)
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["tmute"])
def tmute(m):
    if not admin_only(m):
        return

    parts = m.text.split()

    if m.reply_to_message:
        if len(parts) < 2:
            bot.reply_to(m, "Uso: responde con /tmute 10m motivo")
            return

        user = m.reply_to_message.from_user
        user_id = user.id
        name = user.first_name
        username = user.username
        duration_text = parts[1]
        reason = " ".join(parts[2:]) or "Sin motivo"

    else:
        if len(parts) < 3:
            bot.reply_to(m, "Uso: /tmute ID 10m motivo")
            return
        
        try:
            user_id = int(parts[1])
        except:
            bot.reply_to(m, "ID inválido.")
            return

        name = f"ID {user_id}"
        username = None
        duration_text = parts[2]
        reason = " ".join(parts[3:]) or "Sin motivo"

    seconds = parse_time(duration_text)
    
    if is_admin(m.chat.id, user_id):
        bot.reply_to(m, "❌ No puedes moderar otro admin.")
        return

    if not seconds:
        bot.reply_to(m, "Tiempo inválido. Usa 10s, 10m, 2h o 7d")
        return

    until = int(time.time() + seconds)

    try:
        bot.restrict_chat_member(
            m.chat.id,
            user_id,
            until_date=until,
            permissions=ChatPermissions(
                can_send_messages=False
            )
        )

        ficha(
            m.chat.id,
            f"TMUTE {duration_text}",
            user_id,
            name,
            username,
            m.from_user,
            reason
        )
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["unmute"])
def unmute(m):
    if not admin_only(m):
        return

    user_id, name, username, reason = get_target(m)

    if not user_id:
        bot.reply_to(m, "Uso: /unmute ID o responde con /unmute")
        return

    try:
        bot.restrict_chat_member(
            m.chat.id,
            user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )

        ficha(m.chat.id, "UNMUTE", user_id, name, username, m.from_user, reason)
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


# =========================
# WARNS
# =========================

@bot.message_handler(commands=["warn"])
def warn(m):
    if not admin_only(m):
        return

    user_id, name, username, reason = get_target(m)

    if not user_id:
        bot.reply_to(m, "Uso: /warn ID motivo o responde con /warn motivo")
        return

    if is_admin(m.chat.id, user_id):
        bot.reply_to(m, "❌ No puedes moderar otro admin.")
        return

    data = load_warns()
    chat_id = str(m.chat.id)
    uid = str(user_id)

    if chat_id not in data:
        data[chat_id] = {}

    if uid not in data[chat_id]:
        data[chat_id][uid] = []

    data[chat_id][uid].append({
        "reason": reason,
        "admin": m.from_user.id,
        "date": now_date()
    })

    count = len(data[chat_id][uid])
    save_warns(data)

    bot.send_message(m.chat.id, f"""
<b>⚠️ WARN APLICADO</b>

👤 Usuario: {name}
🆔 ID: <code>{user_id}</code>
👑 Admin: {m.from_user.first_name}
📝 Motivo: <code>{reason}</code>

━━━━━━━━━━━━━━
Warns: <code>{count}/{MAX_WARNS}</code>
""")

    if count >= MAX_WARNS:
        try:
            bot.restrict_chat_member(
                m.chat.id,
                user_id,
                until_date=int(time.time() + 3600),
                permissions=ChatPermissions(can_send_messages=False)
            )

            data[chat_id][uid] = []
            save_warns(data)

            bot.send_message(m.chat.id, f"""
<b>🔇 AUTO-MUTE</b>

El usuario alcanzó <code>{MAX_WARNS}</code> warns.
Mute automático: <code>1 hora</code>
""")
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ Error auto-mute: <code>{e}</code>")


@bot.message_handler(commands=["warns"])
def warns(m):
    if not admin_only(m):
        return

    user_id, name, username, reason = get_target(m)

    if not user_id:
        bot.reply_to(m, "Uso: /warns ID o responde con /warns")
        return

    data = load_warns()
    chat_id = str(m.chat.id)
    uid = str(user_id)

    user_warns = data.get(chat_id, {}).get(uid, [])

    if not user_warns:
        bot.send_message(m.chat.id, f"✅ Sin warns para <code>{user_id}</code>")
        return

    lines = ""
    for i, w in enumerate(user_warns, 1):
        lines += f"\n{i}. {w['reason']} — {w['date']}"

    bot.send_message(m.chat.id, f"""
<b>⚠️ WARNS</b>

👤 Usuario: {name}
🆔 ID: <code>{user_id}</code>

{lines}
""")


@bot.message_handler(commands=["resetwarns"])
def resetwarns(m):
    if not admin_only(m):
        return

    user_id, name, username, reason = get_target(m)

    if not user_id:
        bot.reply_to(m, "Uso: /resetwarns ID o responde con /resetwarns")
        return

    data = load_warns()
    chat_id = str(m.chat.id)
    uid = str(user_id)

    if chat_id in data and uid in data[chat_id]:
        data[chat_id][uid] = []
        save_warns(data)

    bot.send_message(m.chat.id, f"""
<b>✅ WARNS LIMPIOS</b>

👤 Usuario: {name}
🆔 ID: <code>{user_id}</code>
""")


# =========================
# MENSAJES
# =========================

@bot.message_handler(commands=["del"])
def delete_msg(m):
    if not admin_only(m):
        return

    if not m.reply_to_message:
        bot.reply_to(m, "Responde al mensaje que quieres borrar.")
        return

    try:
        bot.delete_message(m.chat.id, m.reply_to_message.message_id)
        bot.delete_message(m.chat.id, m.message_id)
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["purge"])
def purge(m):
    if not admin_only(m):
        return

    if not m.reply_to_message:
        bot.reply_to(m, "Responde al primer mensaje desde donde quieres limpiar.")
        return

    start_id = m.reply_to_message.message_id
    end_id = m.message_id

    deleted = 0

    for msg_id in range(start_id, end_id + 1):
        try:
            bot.delete_message(m.chat.id, msg_id)
            deleted += 1
        except:
            pass

    bot.send_message(m.chat.id, f"🧹 Limpieza completada: <code>{deleted}</code> mensajes.")


@bot.message_handler(commands=["pin"])
def pin(m):
    if not can_talk_when_closed(m.chat.id, m.from_user.id):
        return

    if not m.reply_to_message:
        bot.reply_to(m, "Responde al mensaje que quieres fijar.")
        return

    try:
        bot.pin_chat_message(m.chat.id, m.reply_to_message.message_id)
        bot.delete_message(m.chat.id, m.message_id)
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["unpin"])
def unpin(m):
    if not admin_only(m):
        return

    try:
        bot.unpin_chat_message(m.chat.id)
        bot.send_message(m.chat.id, "📍 Mensaje desfijado.")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


# =========================
# ADMINS
# =========================

@bot.message_handler(commands=["admins"])
def admins(m):
    if not admin_only(m):
        return

    try:
        admins_list = bot.get_chat_administrators(m.chat.id)
        text = "<b>👑 ADMINS DEL GRUPO</b>\n\n"

        for admin in admins_list:
            user = admin.user
            username = f"@{user.username}" if user.username else "Sin username"
            text += f"• {user.first_name} — <code>{username}</code> — <code>{user.id}</code>\n"

        bot.send_message(m.chat.id, text)
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["promote"])
def promote(m):
    if not owner_only(m):
        return

    if not m.reply_to_message:
        bot.reply_to(m, "Responde al usuario que quieres hacer admin.")
        return

    user = m.reply_to_message.from_user

    try:
        bot.promote_chat_member(
            m.chat.id,
            user.id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_invite_users=True,
            can_promote_members=False
        )

        bot.send_message(m.chat.id, f"""
<b>👑 ADMIN AGREGADO</b>

👤 Usuario: {user.first_name}
🆔 ID: <code>{user.id}</code>
""")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["demote"])
def demote(m):
    if not owner_only(m):
        return

    if not m.reply_to_message:
        bot.reply_to(m, "Responde al admin que quieres quitar.")
        return

    user = m.reply_to_message.from_user

    try:
        bot.promote_chat_member(
            m.chat.id,
            user.id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_promote_members=False
        )

        bot.send_message(m.chat.id, f"""
<b>⚠️ ADMIN REMOVIDO</b>

👤 Usuario: {user.first_name}
🆔 ID: <code>{user.id}</code>
""")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["seller"])
def seller(m):
    if not owner_only(m):
        return

    if not m.reply_to_message:
        bot.reply_to(m, "Responde al usuario que quieres hacer SELLER.")
        return

    user = m.reply_to_message.from_user

    try:
        bot.promote_chat_member(
            m.chat.id,
            user.id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_invite_users=True,
            can_promote_members=False
        )

        bot.set_chat_administrator_custom_title(
            m.chat.id,
            user.id,
            "SELLER"
        )

        bot.send_message(m.chat.id, f"""
<b>💎 SELLER ACTIVADO</b>

👤 Usuario: <b>{user.first_name}</b>
🆔 ID: <code>{user.id}</code>
🏷 Rango: <code>SELLER</code>

━━━━━━━━━━━━━━
Autorizado dentro de <b>{GROUP_NAME}</b>.
""")

    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


@bot.message_handler(commands=["unseller"])
def unseller(m):
    if not owner_only(m):
        return

    if not m.reply_to_message:
        bot.reply_to(m, "Responde al seller que quieres remover.")
        return

    user = m.reply_to_message.from_user

    try:
        bot.promote_chat_member(
            m.chat.id,
            user.id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_promote_members=False
        )

        bot.send_message(m.chat.id, f"""
<b>⚠️ SELLER REMOVIDO</b>

👤 Usuario: <b>{user.first_name}</b>
🆔 ID: <code>{user.id}</code>
""")

    except Exception as e:
        bot.reply_to(m, f"❌ Error: <code>{e}</code>")


        
@bot.message_handler(commands=["info"])
def info_user(m):
    if not admin_only(m):
        return

    parts = m.text.split()

    if m.reply_to_message:
        user = m.reply_to_message.from_user
        cache_user(m.chat.id, user)
        info = get_cached_user(m.chat.id, user.id)

    else:
        if len(parts) < 2:
            bot.reply_to(m, "Uso: /info ID, /info @username o responde con /info")
            return

        info = get_cached_user(m.chat.id, parts[1])

    if not info:
        bot.reply_to(m, "No tengo registro de ese usuario todavía.")
        return

    user_id = info["id"]
    names = "\n".join([f"• {n}" for n in info.get("names", [])]) or "Sin registros"
    usernames = "\n".join([f"• @{u}" for u in info.get("usernames", [])]) or "Sin username"

    try:
        member = bot.get_chat_member(m.chat.id, user_id)
        status = member.status
    except:
        status = "No disponible"

    bot.send_message(m.chat.id, f"""
<b>🕵️ FICHA DE USUARIO</b>

━━━━━━━━━━━━━━
🆔 <b>ID:</b> <code>{user_id}</code>
📌 <b>Estado:</b> <code>{status}</code>

👤 <b>Nombres registrados:</b>
{names}

🔗 <b>Usernames registrados:</b>
{usernames}

📥 <b>Entró al grupo:</b>
<code>{info.get("joined_at", "No registrado")}</code>

👁 <b>Última vez visto:</b>
<code>{info.get("last_seen", "No registrado")}</code>

━━━━━━━━━━━━━━
<b>Comandos rápidos:</b>
<code>/ban {user_id} motivo</code>
<code>/mute {user_id} motivo</code>
<code>/warn {user_id} motivo</code>
""")


@bot.message_handler(
    func=lambda m: (
        m.chat.type in ["group", "supergroup"]
        and m.text
        and (
            "http://" in m.text.lower()
            or "https://" in m.text.lower()
            or "t.me/" in m.text.lower()
            or "telegram.me/" in m.text.lower()
            or "www." in m.text.lower()
        )
    )
)
def anti_links(m):
    if is_admin(m.chat.id, m.from_user.id):
        return

    try:
        bot.delete_message(m.chat.id, m.message_id)
        bot.send_message(
            m.chat.id,
            f"🚫 {m.from_user.first_name}, links eliminados para evitar estafas."
        )
    except Exception as e:
        print(f"Error anti-links: {e}")


@bot.message_handler(content_types=["text", "photo", "video", "document", "sticker", "audio", "voice", "animation"])
def fake_lock_filter(m):

    if m.chat.type not in ["group", "supergroup"]:
        return

    if m.text and m.text.startswith("/"):
        return

    if not fake_closed(m.chat.id):
        return

    if can_talk_when_closed(m.chat.id, m.from_user.id):
        return

    try:
        bot.delete_message(m.chat.id, m.message_id)
    except Exception as e:
        print(f"Error fake lock: {e}")


@bot.message_handler(content_types=["text"])
def daily_spam_control(m):

    if m.chat.type not in ["group", "supergroup"]:
        return
    
    cache_user(m.chat.id, m.from_user)

    if is_admin(m.chat.id, m.from_user.id):
        return

    text = m.text or ""

    if text.startswith("/"):
        return

    if len(text) < SPAM_MIN_LEN:
        return

    data = load_spam()

    day = today_key()
    chat_id = str(m.chat.id)
    user_id = str(m.from_user.id)

    if day not in data:
        data.clear()
        data[day] = {}

    if chat_id not in data[day]:
        data[day][chat_id] = {}

    if user_id not in data[day][chat_id]:
        data[day][chat_id][user_id] = {
            "count": 0
        }

    data[day][chat_id][user_id]["count"] += 1
    count = data[day][chat_id][user_id]["count"]

    if count <= SPAM_LIMIT:
        save_spam(data)
        return

    save_spam(data)

    try:
        bot.delete_message(m.chat.id, m.message_id)
    except:
        pass

    if count <= SPAM_SOFT_LIMIT:
        bot.send_message(m.chat.id, f"""
<b>⚠️ LÍMITE DIARIO ALCANZADO</b>

━━━━━━━━━━━━━━
👤 Usuario: <b>{m.from_user.first_name}</b>

📢 Spam largos hoy:
<code>{count}/{SPAM_LIMIT}</code>

🕒 Puedes volver a publicar mañana.

━━━━━━━━━━━━━━
🛡 Todo spam debe llevar Trato Admin.
""")
        return

    if count < SPAM_MUTE_LIMIT:
        bot.send_message(m.chat.id, f"""
<b>🚫 PUBLICACIÓN BLOQUEADA</b>

━━━━━━━━━━━━━━
👤 Usuario: <b>{m.from_user.first_name}</b>

📢 Exceso de spam diario:
<code>{count}</code>

⚠️ Siguiente abuso = mute hasta mañana.

━━━━━━━━━━━━━━
🛡 Todo spam debe llevar Trato Admin.
""")
        return

    until = int(time.time() + seconds_until_midnight())

    bot.restrict_chat_member(
        m.chat.id,
        m.from_user.id,
        until_date=until,
        permissions=ChatPermissions(
            can_send_messages=False
        )
    )

    bot.send_message(m.chat.id, f"""
<b>🔇 MUTE DIARIO</b>

━━━━━━━━━━━━━━
👤 Usuario: <b>{m.from_user.first_name}</b>
🆔 ID: <code>{m.from_user.id}</code>

📢 Spam largos hoy:
<code>{count}</code>

🕒 Mute hasta mañana.

━━━━━━━━━━━━━━
🛡 Todo spam debe llevar Trato Admin.
""")

# =========================
# WEB PARA RENDER
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "NAMELESS CORE ACTIVO"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Inicia servidor web falso
Thread(target=run_web).start()

# =========================
# BOT TELEGRAM
# =========================

print("NAMELESS CORE ACTIVO")

try:
    bot.remove_webhook()
    print("Webhook eliminado")
except Exception as e:
    print(f"Error webhook: {e}")

while True:
    try:
        print("Iniciando polling...")

        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            skip_pending=True
        )

    except Exception as e:
        print(f"Error polling: {e}")
        time.sleep(5)
