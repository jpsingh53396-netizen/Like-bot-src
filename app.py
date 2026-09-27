import asyncio
import html
import logging
import asyncio
import html
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.constants import ChatType, ParseMode

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# ============================================================
#                 DP FREE LIKE BOT
# ============================================================

# IMPORTANT:
# Put your NEW regenerated BotFather token here.
BOT_TOKEN = "8836114667:AAHqJ_bEpzD_WVYJm3awziaRXpj_MizxLvA"


# Your Telegram numeric ID
ADMIN_IDS = {
    8924709154
}


# ============================================================
#                         API
# ============================================================

API_URL = "https://like-bot-mera.vercel.app/like"
API_KEY = "saito"

DEFAULT_REGION = "ind"


# ============================================================
#                    DEFAULT FORCE JOIN
# ============================================================

# Can be changed later from /admin.
#
# You can use:
#
# https://t.me/GuildGloryBots
#
# or:
#
# https://t.me/+xxxxxxxxxxxx
#
# For a public channel, the bot converts the link to @username.
#
# IMPORTANT:
# Private invite links cannot be converted to a chat ID by
# Telegram Bot API unless the bot already knows that chat.
#
DEFAULT_FORCE_JOIN_LINK = "https://t.me/GuildGloryBots"


# ============================================================
#                       BRANDING
# ============================================================

BOT_NAME = "DP Free Like Bot"
BOT_CREDIT = "Bot by Dev"


# ============================================================
#                       DATABASE
# ============================================================

DB_FILE = "dp_free_like_bot.db"


# ============================================================
#                    DAILY RESET
# ============================================================

RESET_HOUR = 4
RESET_MINUTE = 0


# ============================================================
#                    API TIMEOUT
# ============================================================

API_TIMEOUT = 20


# ============================================================
#                       LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# ============================================================
#                       DATABASE
# ============================================================

db = sqlite3.connect(
    DB_FILE,
    check_same_thread=False
)

db.row_factory = sqlite3.Row


def table_exists(table_name):
    row = db.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name=?
        """,
        (table_name,)
    ).fetchone()

    return row is not None


def column_exists(table_name, column_name):

    if not table_exists(table_name):
        return False

    columns = db.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(
        row["name"] == column_name
        for row in columns
    )


def add_column_if_missing(
    table_name,
    column_name,
    definition
):

    if not column_exists(
        table_name,
        column_name
    ):

        db.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {definition}
            """
        )

        db.commit()

        logger.info(
            "Added missing column %s.%s",
            table_name,
            column_name
        )


# ------------------------------------------------------------
# USERS
# ------------------------------------------------------------

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    joined_at TEXT,
    last_seen TEXT,
    banned INTEGER DEFAULT 0
)
""")


# ------------------------------------------------------------
# USAGE
# ------------------------------------------------------------

db.execute("""
CREATE TABLE IF NOT EXISTS usage (
    user_id INTEGER NOT NULL,
    uid TEXT NOT NULL,
    cycle TEXT NOT NULL,
    used_at TEXT NOT NULL,
    PRIMARY KEY(user_id, uid, cycle)
)
""")


# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

db.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")


# ------------------------------------------------------------
# REQUESTS
# ------------------------------------------------------------

db.execute("""
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    uid TEXT,
    region TEXT,
    status TEXT,
    likes_added INTEGER,
    created_at TEXT
)
""")

db.commit()


# ============================================================
#                 DATABASE MIGRATION
# ============================================================

# Fix older DB versions automatically.

add_column_if_missing(
    "users",
    "username",
    "TEXT"
)

add_column_if_missing(
    "users",
    "first_name",
    "TEXT"
)

add_column_if_missing(
    "users",
    "joined_at",
    "TEXT"
)

add_column_if_missing(
    "users",
    "last_seen",
    "TEXT"
)

add_column_if_missing(
    "users",
    "banned",
    "INTEGER DEFAULT 0"
)

add_column_if_missing(
    "requests",
    "user_id",
    "INTEGER"
)

add_column_if_missing(
    "requests",
    "uid",
    "TEXT"
)

add_column_if_missing(
    "requests",
    "region",
    "TEXT"
)

add_column_if_missing(
    "requests",
    "status",
    "TEXT"
)

add_column_if_missing(
    "requests",
    "likes_added",
    "INTEGER"
)

add_column_if_missing(
    "requests",
    "created_at",
    "TEXT"
)


# ============================================================
#                       SETTINGS
# ============================================================

def set_setting(key, value):

    db.execute(
        """
        INSERT INTO settings(key, value)
        VALUES(?, ?)

        ON CONFLICT(key)
        DO UPDATE SET
            value=excluded.value
        """,
        (
            key,
            str(value)
        )
    )

    db.commit()


def get_setting(
    key,
    default=None
):

    row = db.execute(
        """
        SELECT value
        FROM settings
        WHERE key=?
        """,
        (key,)
    ).fetchone()

    if row:
        return row["value"]

    return default


# ------------------------------------------------------------
# DEFAULT SETTINGS
# ------------------------------------------------------------

if get_setting("api_url") is None:
    set_setting(
        "api_url",
        API_URL
    )


if get_setting("api_key") is None:
    set_setting(
        "api_key",
        API_KEY
    )


if get_setting("force_join_link") is None:
    set_setting(
        "force_join_link",
        DEFAULT_FORCE_JOIN_LINK
    )


if get_setting("force_join_chat_id") is None:
    set_setting(
        "force_join_chat_id",
        ""
    )


if get_setting("maintenance") is None:
    set_setting(
        "maintenance",
        "0"
    )


# ============================================================
#                        TIME
# ============================================================

IST = timezone(
    timedelta(hours=5, minutes=30)
)


def now_ist():
    return datetime.now(IST)


def current_cycle():

    now = now_ist()

    if (
        now.hour < RESET_HOUR
        or (
            now.hour == RESET_HOUR
            and now.minute < RESET_MINUTE
        )
    ):
        cycle_date = (
            now - timedelta(days=1)
        ).date()

    else:
        cycle_date = now.date()

    return cycle_date.isoformat()


# ============================================================
#                         UI
# ============================================================

def header(title):

    return (
        f"⚡ <b>{BOT_NAME}</b>\n"
        f"╰─ {html.escape(title)}\n"
        "━━━━━━━━━━━━━━━━━━\n"
    )


def footer():

    return (
        "\n━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 <b>{html.escape(BOT_CREDIT)}</b>"
    )


def main_menu():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💗 Like",
                callback_data="help_like"
            ),
            InlineKeyboardButton(
                "📖 Help",
                callback_data="help"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 Profile",
                callback_data="profile"
            )
        ]
    ])


# ============================================================
#                     USER FUNCTIONS
# ============================================================

def save_user(user):

    if not user:
        return

    now = now_ist().isoformat()

    db.execute(
        """
        INSERT INTO users(
            user_id,
            username,
            first_name,
            joined_at,
            last_seen
        )
        VALUES(?, ?, ?, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_seen=excluded.last_seen
        """,
        (
            user.id,
            user.username or "",
            user.first_name or "",
            now,
            now
        )
    )

    db.commit()


def is_banned(user_id):

    row = db.execute(
        """
        SELECT banned
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    ).fetchone()

    return bool(
        row and row["banned"]
    )


def ban_user(user_id):

    db.execute(
        """
        UPDATE users
        SET banned=1
        WHERE user_id=?
        """,
        (user_id,)
    )

    db.commit()


def unban_user(user_id):

    db.execute(
        """
        UPDATE users
        SET banned=0
        WHERE user_id=?
        """,
        (user_id,)
    )

    db.commit()


def is_admin(user_id):

    return user_id in ADMIN_IDS


# ============================================================
#                     MAINTENANCE
# ============================================================

def maintenance_enabled():

    return (
        get_setting(
            "maintenance",
            "0"
        ) == "1"
    )


# ============================================================
#                 FORCE JOIN LINK PARSER
# ============================================================

def parse_force_join_link(link):

    """
    Converts a Telegram channel link into information
    that the Bot API can use.

    Supported examples:

    https://t.me/MyChannel
    https://telegram.me/MyChannel
    http://t.me/MyChannel

    Public channel:
        chat_id = @MyChannel

    Private invite:
        https://t.me/+AbCdEf...
        cannot be converted into chat_id automatically
        through the normal Bot API.
    """

    link = link.strip()

    if not link:
        return {
            "valid": False,
            "error": "Empty link."
        }

    if not (
        link.startswith("https://")
        or link.startswith("http://")
    ):
        return {
            "valid": False,
            "error": "Please provide a Telegram channel link."
        }

    try:

        parsed = urlparse(link)

        host = parsed.netloc.lower()

        if host not in (
            "t.me",
            "telegram.me",
            "www.t.me",
            "www.telegram.me"
        ):
            return {
                "valid": False,
                "error": "This is not a Telegram link."
            }

        path = parsed.path.strip("/")

        if not path:
            return {
                "valid": False,
                "error": "Channel link is incomplete."
            }

        # Private invite links
        if (
            path.startswith("+")
            or path.startswith("joinchat/")
        ):

            return {
                "valid": True,
                "type": "invite",
                "link": link,
                "chat_id": None
            }

        # Public username
        username = path.split("/")[0]

        # Remove possible @
        username = username.lstrip("@")

        if not username:
            return {
                "valid": False,
                "error": "Channel username not found."
            }

        return {
            "valid": True,
            "type": "public",
            "link": link,
            "chat_id": "@" + username
        }

    except Exception as e:

        return {
            "valid": False,
            "error": str(e)
        }


# ============================================================
#             VALIDATE / ADD FORCE JOIN CHANNEL
# ============================================================

async def validate_force_join_link(
    bot,
    link
):

    parsed = parse_force_join_link(link)

    if not parsed["valid"]:
        return {
            "success": False,
            "message": parsed["error"]
        }

    # --------------------------------------------------------
    # PUBLIC CHANNEL
    # --------------------------------------------------------

    if parsed["type"] == "public":

        chat_id = parsed["chat_id"]

        try:

            chat = await bot.get_chat(
                chat_id=chat_id
            )

            # Only allow channel or supergroup.
            if chat.type not in (
                "channel",
                "supergroup"
            ):

                return {
                    "success": False,
                    "message": (
                        "The link points to a "
                        "group/chat, not a channel."
                    )
                }

            return {
                "success": True,
                "chat_id": chat.id,
                "title": chat.title or "Telegram Channel",
                "username": (
                    "@" + chat.username
                    if chat.username
                    else ""
                ),
                "link": link,
                "type": "public"
            }

        except Exception as e:

            logger.warning(
                "Force join validation failed: %s",
                e
            )

            return {
                "success": False,
                "message": (
                    "Telegram could not find/access "
                    "this channel.\n\n"
                    "Make sure:\n"
                    "• The link is correct\n"
                    "• The channel exists\n"
                    "• The bot is added to the channel"
                )
            }

    # --------------------------------------------------------
    # PRIVATE INVITE LINK
    # --------------------------------------------------------

    if parsed["type"] == "invite":

        return {
            "success": False,
            "message": (
                "This is a private invite link.\n\n"
                "Telegram Bot API cannot identify the "
                "channel from an invite link alone.\n\n"
                "For automatic validation, use the "
                "channel's public link such as:\n"
                "https://t.me/YourChannel"
            )
        }

    return {
        "success": False,
        "message": "Unknown Telegram link."
    }


# ============================================================
#                    FORCE JOIN CHECK
# ============================================================

async def check_force_join(
    update,
    context
):

    link = get_setting(
        "force_join_link",
        ""
    )

    chat_id = get_setting(
        "force_join_chat_id",
        ""
    )

    if not link or not chat_id:
        return True

    user = update.effective_user

    if not user:
        return False

    try:

        try:
            chat_id_value = int(chat_id)
        except Exception:
            chat_id_value = chat_id

        member = await context.bot.get_chat_member(
            chat_id=chat_id_value,
            user_id=user.id
        )

        allowed_status = {
            "member",
            "administrator",
            "creator"
        }

        if member.status in allowed_status:
            return True

    except Exception as e:

        logger.warning(
            "Force join check failed: %s",
            e
        )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=link
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Check Again",
                callback_data="check_join"
            )
        ]
    ])

    await update.effective_message.reply_text(
        header("Join Required")
        + "⚠️ <b>Please join our channel first.</b>\n\n"
        + "After joining, press <b>Check Again</b>."
        + footer(),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )

    return False


# ============================================================
#                       DM BLOCK
# ============================================================

async def dm_block(update):

    if not update.effective_chat:
        return False

    user = update.effective_user

    # ========================================================
    # ADMIN BYPASS
    # ========================================================

    if user and is_admin(user.id):
        return False

    # ========================================================
    # NORMAL USERS
    # ========================================================

    if update.effective_chat.type == ChatType.PRIVATE:

        await update.effective_message.reply_text(
            header("Groups Only")
            + "🚫 <b>This bot cannot be used in DM.</b>\n\n"
            + "Please use the bot inside a group."
            + footer(),
            parse_mode=ParseMode.HTML
        )

        return True

    return False


# ============================================================
#                    DAILY USAGE
# ============================================================

def already_used_today(
    user_id,
    uid
):

    cycle = current_cycle()

    row = db.execute(
        """
        SELECT 1
        FROM usage
        WHERE user_id=?
        AND uid=?
        AND cycle=?
        """,
        (
            user_id,
            str(uid),
            cycle
        )
    ).fetchone()

    return row is not None


def mark_used(
    user_id,
    uid
):

    cycle = current_cycle()

    db.execute(
        """
        INSERT OR IGNORE INTO usage(
            user_id,
            uid,
            cycle,
            used_at
        )
        VALUES(?, ?, ?, ?)
        """,
        (
            user_id,
            str(uid),
            cycle,
            now_ist().isoformat()
        )
    )

    db.commit()


# ============================================================
#                     REQUEST LOG
# ============================================================

def log_request(
    user_id,
    uid,
    region,
    status,
    likes_added=0
):

    db.execute(
        """
        INSERT INTO requests(
            user_id,
            uid,
            region,
            status,
            likes_added,
            created_at
        )
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            str(uid),
            region,
            status,
            likes_added,
            now_ist().isoformat()
        )
    )

    db.commit()


# ============================================================
#                     LIKE API
# ============================================================

def call_like_api(
    uid,
    region
):

    api_url = get_setting(
        "api_url",
        API_URL
    )

    api_key = get_setting(
        "api_key",
        API_KEY
    )

    params = {
        "uid": str(uid),
        "region": region.lower(),
        "key": api_key
    }

    response = requests.get(
        api_url,
        params=params,
        timeout=API_TIMEOUT
    )

    response.raise_for_status()

    return response.json()


# ============================================================
#                  API RESPONSE PARSER
# ============================================================

def parse_api_response(
    data,
    requested_uid
):

    if not isinstance(data, dict):

        return {
            "success": False,
            "message": "Invalid API response.",
            "raw": {}
        }

    status = data.get(
        "status",
        0
    )

    success = (
        str(status) == "1"
    )

    player = data.get(
        "PlayerNickname",
        "N/A"
    )

    uid = data.get(
        "UID",
        requested_uid
    )

    region = data.get(
        "Region",
        "IND"
    )

    level = data.get(
        "Level",
        "N/A"
    )

    likes_before = data.get(
        "LikesbeforeCommand",
        "N/A"
    )

    likes_after = data.get(
        "LikesafterCommand",
        "N/A"
    )

    likes_added = data.get(
        "LikesGivenByAPI",
        0
    )

    daily_limit = data.get(
        "daily_limit",
        "N/A"
    )

    used = data.get(
        "used",
        "N/A"
    )

    remaining = data.get(
        "remaining",
        "N/A"
    )

    return {
        "success": success,
        "player": str(player),
        "uid": str(uid),
        "region": str(region),
        "level": str(level),
        "likes_before": str(likes_before),
        "likes_after": str(likes_after),
        "likes_added": str(likes_added),
        "daily_limit": str(daily_limit),
        "used": str(used),
        "remaining": str(remaining),
        "raw": data
    }


# ============================================================
#                  SUCCESS MESSAGE
# ============================================================

def success_message(info):

    return (
        header("Like Successful")

        + "✅ <b>Request completed successfully!</b>\n\n"

        + "👤 <b>PLAYER</b>\n"
        + f"└─ <code>{html.escape(info['player'])}</code>\n\n"

        + "🆔 <b>UID</b>\n"
        + f"└─ <code>{html.escape(info['uid'])}</code>\n\n"

        + "🌍 <b>REGION</b>\n"
        + f"└─ <code>{html.escape(info['region'])}</code>\n\n"

        + "🎮 <b>LEVEL</b>\n"
        + f"└─ <code>{html.escape(info['level'])}</code>\n\n"

        + "💗 <b>LIKES BEFORE</b>\n"
        + f"└─ <code>{html.escape(info['likes_before'])}</code>\n\n"

        + "💗 <b>LIKES AFTER</b>\n"
        + f"└─ <code>{html.escape(info['likes_after'])}</code>\n\n"

        + "➕ <b>LIKES ADDED</b>\n"
        + f"└─ <code>+{html.escape(info['likes_added'])}</code>\n\n"

        + "📌 <b>STATUS</b>\n"
        + "└─ <code>SUCCESS</code>"

        + footer()
    )


# ============================================================
#                    FAILED MESSAGE
# ============================================================

def failed_message(info):

    raw_status = info["raw"].get(
        "status",
        0
    )

    return (
        header("Like Failed")

        + "❌ <b>Request was not successful.</b>\n\n"

        + "👤 <b>PLAYER</b>\n"
        + f"└─ <code>{html.escape(info['player'])}</code>\n\n"

        + "🆔 <b>UID</b>\n"
        + f"└─ <code>{html.escape(info['uid'])}</code>\n\n"

        + "🌍 <b>REGION</b>\n"
        + f"└─ <code>{html.escape(info['region'])}</code>\n\n"

        + "📌 <b>STATUS</b>\n"
        + f"└─ <code>{html.escape(str(raw_status))}</code>"

        + footer()
    )


# ============================================================
#                       /START
# ============================================================

async def start(
    update,
    context
):

    save_user(
        update.effective_user
    )

    if await dm_block(update):
        return

    user_id = update.effective_user.id

    if is_banned(user_id):

        await update.effective_message.reply_text(
            "🚫 You are banned from using this bot."
        )

        return

    if not await check_force_join(
        update,
        context
    ):
        return

    await update.effective_message.reply_text(
        header("Welcome")

        + "👋 <b>Welcome to DP Free Like Bot!</b>\n\n"

        + "💗 Send likes using:\n"
        + "<code>/like ind UID</code>\n\n"

        + "Example:\n"
        + "<code>/like ind 6475189319</code>\n\n"

        + "⏰ Same UID can be used once per user "
        + "in each daily cycle.\n\n"

        + "🔄 Daily reset: <b>4:00 AM IST</b>"

        + footer(),

        parse_mode=ParseMode.HTML,
        reply_markup=main_menu()
    )


# ============================================================
#                        /HELP
# ============================================================

async def help_command(
    update,
    context
):

    save_user(
        update.effective_user
    )

    if await dm_block(update):
        return

    await update.effective_message.reply_text(
        header("Help")

        + "💗 <b>LIKE COMMAND</b>\n\n"
        + "<code>/like ind UID</code>\n\n"

        + "Example:\n"
        + "<code>/like ind 6475189319</code>\n\n"

        + "📌 <b>Rules</b>\n"
        + "• Same user + same UID: once per day\n"
        + "• Different UIDs: unlimited\n"
        + "• Daily reset: 4:00 AM IST"

        + footer(),

        parse_mode=ParseMode.HTML
    )


# ============================================================
#                      /PROFILE
# ============================================================

async def profile(
    update,
    context
):

    save_user(
        update.effective_user
    )

    if await dm_block(update):
        return

    user_id = update.effective_user.id

    row = db.execute(
        """
        SELECT *
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    ).fetchone()

    used_count = db.execute(
        """
        SELECT COUNT(*)
        FROM usage
        WHERE user_id=?
        AND cycle=?
        """,
        (
            user_id,
            current_cycle()
        )
    ).fetchone()[0]

    username = (
        "@" + row["username"]
        if row and row["username"]
        else "No username"
    )

    await update.effective_message.reply_text(
        header("Profile")

        + f"👤 <b>Name:</b> "
        + html.escape(
            update.effective_user.first_name or "User"
        )
        + "\n"

        + f"🆔 <b>ID:</b> "
        + f"<code>{user_id}</code>\n"

        + f"📛 <b>Username:</b> "
        + html.escape(username)
        + "\n\n"

        + f"💗 <b>UIDs used today:</b> "
        + f"<code>{used_count}</code>\n"

        + "🔄 <b>Reset:</b> 4:00 AM IST"

        + footer(),

        parse_mode=ParseMode.HTML
    )


# ============================================================
#                       /LIKE
# ============================================================

async def like_command(
    update,
    context
):

    save_user(
        update.effective_user
    )

    if await dm_block(update):
        return

    user_id = update.effective_user.id

    if is_banned(user_id):

        await update.effective_message.reply_text(
            "🚫 You are banned from using this bot."
        )

        return

    if (
        maintenance_enabled()
        and not is_admin(user_id)
    ):

        await update.effective_message.reply_text(
            header("Maintenance")
            + "🛠️ <b>Bot is currently under maintenance.</b>\n\n"
            + "Please try again later."
            + footer(),
            parse_mode=ParseMode.HTML
        )

        return

    if not await check_force_join(
        update,
        context
    ):
        return

    args = context.args

    if len(args) != 2:

        await update.effective_message.reply_text(
            header("Wrong Format")
            + "❌ <b>Incorrect command.</b>\n\n"
            + "Use:\n"
            + "<code>/like ind UID</code>\n\n"
            + "Example:\n"
            + "<code>/like ind 6475189319</code>"
            + footer(),
            parse_mode=ParseMode.HTML
        )

        return

    region = args[0].lower()
    uid = args[1].strip()

    if region != "ind":

        await update.effective_message.reply_text(
            header("Invalid Region")
            + "❌ Currently only <b>IND</b> is supported.\n\n"
            + "Use:\n"
            + "<code>/like ind UID</code>"
            + footer(),
            parse_mode=ParseMode.HTML
        )

        return

    if not uid.isdigit():

        await update.effective_message.reply_text(
            header("Invalid UID")
            + "❌ UID must contain numbers only."
            + footer(),
            parse_mode=ParseMode.HTML
        )

        return

    if len(uid) < 5 or len(uid) > 15:

        await update.effective_message.reply_text(
            header("Invalid UID")
            + "❌ Please enter a valid UID."
            + footer(),
            parse_mode=ParseMode.HTML
        )

        return

    if already_used_today(
        user_id,
        uid
    ):

        await update.effective_message.reply_text(
            header("Already Used")

            + "⚠️ <b>This UID has already been used by you today.</b>\n\n"

            + f"🆔 UID: <code>{uid}</code>\n"

            + "🔄 Try again after the daily reset at "
            + "<b>4:00 AM IST</b>.\n\n"

            + "💡 You can still use a different UID."

            + footer(),

            parse_mode=ParseMode.HTML
        )

        return

    processing = await update.effective_message.reply_text(
        header("Processing")

        + "⏳ <b>Sending likes...</b>\n\n"
        + f"🆔 UID: <code>{uid}</code>\n"
        + f"🌍 Region: <code>{region.upper()}</code>\n\n"
        + "Please wait..."

        + footer(),

        parse_mode=ParseMode.HTML
    )

    try:

        data = await asyncio.to_thread(
            call_like_api,
            uid,
            region
        )

        info = parse_api_response(
            data,
            uid
        )

        if info["success"]:

            mark_used(
                user_id,
                uid
            )

            try:
                likes_added = int(
                    info["likes_added"]
                )
            except Exception:
                likes_added = 0

            log_request(
                user_id,
                uid,
                region,
                "SUCCESS",
                likes_added
            )

            await processing.edit_text(
                success_message(info),
                parse_mode=ParseMode.HTML
            )

        else:

            log_request(
                user_id,
                uid,
                region,
                "FAILED",
                0
            )

            await processing.edit_text(
                failed_message(info),
                parse_mode=ParseMode.HTML
            )

    except requests.Timeout:

        log_request(
            user_id,
            uid,
            region,
            "TIMEOUT",
            0
        )

        await processing.edit_text(
            header("Timeout")
            + "⏱️ <b>API request timed out.</b>\n\n"
            + "Please try again later."
            + footer(),
            parse_mode=ParseMode.HTML
        )

    except requests.RequestException as e:

        logger.error(
            "API request error: %s",
            e
        )

        log_request(
            user_id,
            uid,
            region,
            "API_ERROR",
            0
        )

        await processing.edit_text(
            header("API Error")
            + "❌ <b>Could not connect to the API.</b>\n\n"
            + "Please try again later."
            + footer(),
            parse_mode=ParseMode.HTML
        )

    except Exception:

        logger.exception(
            "Unexpected error"
        )

        log_request(
            user_id,
            uid,
            region,
            "ERROR",
            0
        )

        await processing.edit_text(
            header("Error")
            + "❌ <b>Something went wrong.</b>\n\n"
            + "Please try again later."
            + footer(),
            parse_mode=ParseMode.HTML
        )


# ============================================================
#                     ADMIN PANEL
# ============================================================

def admin_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="admin_stats"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 Force Join",
                callback_data="force_join_admin"
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ Bot Settings",
                callback_data="admin_settings"
            )
        ],
        [
            InlineKeyboardButton(
                "🌐 API Status",
                callback_data="api_status"
            ),
            InlineKeyboardButton(
                "🛠 Maintenance",
                callback_data="maintenance"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 User Management",
                callback_data="user_management"
            )
        ]
    ])


async def admin_command(
    update,
    context
):

    save_user(
        update.effective_user
    )

    # IMPORTANT:
    # Admin check happens BEFORE DM block.
    if not is_admin(
        update.effective_user.id
    ):

        await update.effective_message.reply_text(
            "🚫 <b>Admin only.</b>",
            parse_mode=ParseMode.HTML
        )

        return

    await update.effective_message.reply_text(
        header("Admin Panel")

        + "👑 <b>Welcome to the Admin Panel</b>\n\n"
        + "Select a section below:"

        + footer(),

        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard()
    )


# ============================================================
#                       /STATS
# ============================================================

async def stats_command(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    users = db.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    banned = db.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE banned=1
        """
    ).fetchone()[0]

    total_requests = db.execute(
        "SELECT COUNT(*) FROM requests"
    ).fetchone()[0]

    successful = db.execute(
        """
        SELECT COUNT(*)
        FROM requests
        WHERE status='SUCCESS'
        """
    ).fetchone()[0]

    await update.effective_message.reply_text(
        header("Statistics")

        + f"👥 <b>Total Users:</b> "
        + f"<code>{users}</code>\n"

        + f"🚫 <b>Banned:</b> "
        + f"<code>{banned}</code>\n"

        + f"📨 <b>Total Requests:</b> "
        + f"<code>{total_requests}</code>\n"

        + f"✅ <b>Successful:</b> "
        + f"<code>{successful}</code>"

        + footer(),

        parse_mode=ParseMode.HTML
    )


# ============================================================
#                         /BAN
# ============================================================

async def ban_command(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    if len(context.args) != 1:

        await update.effective_message.reply_text(
            "Usage:\n/ban USER_ID"
        )

        return

    try:
        user_id = int(
            context.args[0]
        )
    except ValueError:

        await update.effective_message.reply_text(
            "Invalid user ID."
        )

        return

    ban_user(
        user_id
    )

    await update.effective_message.reply_text(
        f"🚫 User <code>{user_id}</code> banned.",
        parse_mode=ParseMode.HTML
    )


# ============================================================
#                        /UNBAN
# ============================================================

async def unban_command(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    if len(context.args) != 1:

        await update.effective_message.reply_text(
            "Usage:\n/unban USER_ID"
        )

        return

    try:
        user_id = int(
            context.args[0]
        )
    except ValueError:

        await update.effective_message.reply_text(
            "Invalid user ID."
        )

        return

    unban_user(
        user_id
    )

    await update.effective_message.reply_text(
        f"✅ User <code>{user_id}</code> unbanned.",
        parse_mode=ParseMode.HTML
    )


# ============================================================
#                         /RESET
# ============================================================

async def reset_command(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    if len(context.args) != 2:

        await update.effective_message.reply_text(
            "Usage:\n/reset USER_ID UID"
        )

        return

    try:
        user_id = int(
            context.args[0]
        )
    except ValueError:

        await update.effective_message.reply_text(
            "Invalid user ID."
        )

        return

    uid = context.args[1]

    db.execute(
        """
        DELETE FROM usage
        WHERE user_id=?
        AND uid=?
        AND cycle=?
        """,
        (
            user_id,
            uid,
            current_cycle()
        )
    )

    db.commit()

    await update.effective_message.reply_text(
        "✅ Usage reset successfully."
    )


# ============================================================
#                    /MAINTENANCE
# ============================================================

async def maintenance_command(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    current = maintenance_enabled()

    new_value = (
        "0"
        if current
        else "1"
    )

    set_setting(
        "maintenance",
        new_value
    )

    status = (
        "ON 🔴"
        if new_value == "1"
        else "OFF 🟢"
    )

    await update.effective_message.reply_text(
        f"🛠 Maintenance mode: <b>{status}</b>",
        parse_mode=ParseMode.HTML
    )


# ============================================================
#                      /BROADCAST
# ============================================================

async def broadcast_command(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    if not context.args:

        await update.effective_message.reply_text(
            "Usage:\n/broadcast YOUR MESSAGE"
        )

        return

    message = " ".join(
        context.args
    )

    rows = db.execute(
        """
        SELECT user_id
        FROM users
        WHERE banned=0
        """
    ).fetchall()

    sent = 0
    failed = 0

    status_msg = await update.effective_message.reply_text(
        "📢 Broadcasting..."
    )

    for row in rows:

        try:

            await context.bot.send_message(
                chat_id=row["user_id"],
                text=message,
                parse_mode=ParseMode.HTML
            )

            sent += 1

            await asyncio.sleep(
                0.05
            )

        except Exception:

            failed += 1

    await status_msg.edit_text(
        f"📢 <b>Broadcast complete</b>\n\n"
        f"✅ Sent: <code>{sent}</code>\n"
        f"❌ Failed: <code>{failed}</code>",
        parse_mode=ParseMode.HTML
    )


# ============================================================
#                    API STATUS
# ============================================================

async def api_status(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    try:

        url = get_setting(
            "api_url",
            API_URL
        )

        response = await asyncio.to_thread(
            requests.get,
            url,
            params={
                "uid": "6475189319",
                "region": "ind",
                "key": get_setting(
                    "api_key",
                    API_KEY
                )
            },
            timeout=10
        )

        if response.ok:
            status = "🟢 ONLINE"
        else:
            status = (
                f"🟠 HTTP "
                f"{response.status_code}"
            )

    except Exception:

        status = "🔴 OFFLINE"

    await update.effective_message.reply_text(
        header("API Status")
        + f"🌐 API: <b>{status}</b>"
        + footer(),
        parse_mode=ParseMode.HTML
    )


# ============================================================
#                ADD FORCE JOIN BY LINK
# ============================================================

async def set_forcejoin_command(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    if len(context.args) != 1:

        await update.effective_message.reply_text(
            header("Force Join")

            + "❌ Please give a Telegram channel link.\n\n"

            + "Example:\n"
            + "<code>/setforcejoin https://t.me/YourChannel</code>"

            + footer(),

            parse_mode=ParseMode.HTML
        )

        return

    link = context.args[0].strip()

    checking = await update.effective_message.reply_text(
        "🔎 <b>Checking Telegram channel...</b>",
        parse_mode=ParseMode.HTML
    )

    result = await validate_force_join_link(
        context.bot,
        link
    )

    if not result["success"]:

        await checking.edit_text(
            header("Channel Error")

            + "❌ <b>Channel could not be added.</b>\n\n"
            + html.escape(
                result["message"]
            )
            + "\n\n"
            + "Please give another valid channel link."

            + footer(),

            parse_mode=ParseMode.HTML
        )

        return

    # Save link
    set_setting(
        "force_join_link",
        result["link"]
    )

    # Save Telegram chat ID
    set_setting(
        "force_join_chat_id",
        result["chat_id"]
    )

    title = result.get(
        "title",
        "Telegram Channel"
    )

    username = result.get(
        "username",
        ""
    )

    await checking.edit_text(
        header("Channel Added")

        + "✅ <b>Channel found and added!</b>\n\n"

        + f"📢 <b>Channel:</b> "
        + html.escape(title)
        + "\n"

        + (
            f"🔗 <b>Username:</b> "
            f"<code>{html.escape(username)}</code>\n"
            if username
            else ""
        )

        + f"🆔 <b>Chat ID:</b> "
        + f"<code>{result['chat_id']}</code>\n\n"

        + "🔒 Force Join is now <b>ACTIVE</b>."

        + footer(),

        parse_mode=ParseMode.HTML
    )


# ============================================================
#                 DISABLE FORCE JOIN
# ============================================================

async def disable_forcejoin_command(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    set_setting(
        "force_join_link",
        ""
    )

    set_setting(
        "force_join_chat_id",
        ""
    )

    await update.effective_message.reply_text(
        header("Force Join")

        + "✅ <b>Force Join disabled.</b>\n\n"
        + "Users can now use the bot without joining a channel."

        + footer(),

        parse_mode=ParseMode.HTML
    )


# ============================================================
#                         /SETAPI
# ============================================================

async def set_api_command(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    if len(context.args) < 1:

        await update.effective_message.reply_text(
            "Usage:\n/setapi API_URL"
        )

        return

    url = context.args[0].strip()

    set_setting(
        "api_url",
        url
    )

    await update.effective_message.reply_text(
        "✅ API URL updated."
    )


# ============================================================
#                         /SETKEY
# ============================================================

async def set_key_command(
    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.effective_message.reply_text(
            "🚫 Admin only."
        )
        return

    if len(context.args) != 1:

        await update.effective_message.reply_text(
            "Usage:\n/setkey API_KEY"
        )

        return

    key = context.args[0].strip()

    set_setting(
        "api_key",
        key
    )

    await update.effective_message.reply_text(
        "✅ API key updated."
    )


# ============================================================
#                 FORCE JOIN ADMIN PANEL
# ============================================================

async def force_join_admin_panel(
    query,
    context
):

    user_id = query.from_user.id

    if not is_admin(user_id):
        return

    link = get_setting(
        "force_join_link",
        ""
    )

    chat_id = get_setting(
        "force_join_chat_id",
        ""
    )

    if link and chat_id:

        status = (
            "🟢 ACTIVE"
        )

        channel_text = (
            f"🔗 <code>"
            f"{html.escape(link)}"
            f"</code>"
        )

    else:

        status = "🔴 DISABLED"

        channel_text = (
            "No channel configured."
        )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "❌ Remove Force Join",
                callback_data="remove_force_join"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="admin_home"
            )
        ]
    ])

    await query.message.edit_text(
        header("Force Join")

        + f"📌 <b>Status:</b> {status}\n\n"
        + f"📢 <b>Channel:</b>\n{channel_text}\n\n"

        + "To add/change channel use:\n"
        + "<code>/setforcejoin CHANNEL_LINK</code>\n\n"

        + "Example:\n"
        + "<code>/setforcejoin https://t.me/YourChannel</code>\n\n"

        + "The bot will check Telegram first. "
        + "If the channel cannot be found, it will NOT be saved."

        + footer(),

        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


# ============================================================
#                 BOT SETTINGS PANEL
# ============================================================

async def settings_panel(
    query,
    context
):

    user_id = query.from_user.id

    if not is_admin(user_id):
        return

    force_join = get_setting(
        "force_join_link",
        ""
    )

    maintenance = (
        "ON 🔴"
        if maintenance_enabled()
        else "OFF 🟢"
    )

    api_url = get_setting(
        "api_url",
        API_URL
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Force Join",
                callback_data="force_join_admin"
            )
        ],
        [
            InlineKeyboardButton(
                "🛠 Maintenance",
                callback_data="maintenance"
            )
        ],
        [
            InlineKeyboardButton(
                "🌐 API Status",
                callback_data="api_status"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="admin_home"
            )
        ]
    ])

    await query.message.edit_text(
        header("Bot Settings")

        + f"📢 <b>Force Join:</b>\n"
        + (
            f"<code>{html.escape(force_join)}</code>"
            if force_join
            else "<code>OFF</code>"
        )
        + "\n\n"

        + f"🛠 <b>Maintenance:</b> "
        + f"{maintenance}\n\n"

        + "🌐 <b>API:</b>\n"
        + f"<code>{html.escape(api_url)}</code>\n\n"

        + "Commands:\n"
        + "<code>/setforcejoin LINK</code>\n"
        + "<code>/disableforcejoin</code>\n"
        + "<code>/setapi URL</code>\n"
        + "<code>/setkey KEY</code>\n"
        + "<code>/maintenance</code>"

        + footer(),

        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


# ============================================================
#                  UNKNOWN COMMAND
# ============================================================

async def unknown_command(
    update,
    context
):

    if not update.effective_chat:
        return

    # Admins can receive commands in DM.
    # Normal users are silently ignored in DM.
    if (
        update.effective_chat.type
        == ChatType.PRIVATE
        and not is_admin(
            update.effective_user.id
        )
    ):
        return

    await update.effective_message.reply_text(
        header("Unknown Command")

        + "❌ <b>Unknown command.</b>\n\n"

        + "Available commands:\n"
        + "<code>/like ind UID</code>\n"
        + "<code>/help</code>\n"
        + "<code>/profile</code>"

        + footer(),

        parse_mode=ParseMode.HTML
    )


# ============================================================
#                     BUTTON HANDLER
# ============================================================

async def button_handler(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id


    # ========================================================
    # HELP
    # ========================================================

    if query.data == "help":

        await query.message.edit_text(
            header("Help")

            + "💗 <b>LIKE COMMAND</b>\n\n"
            + "<code>/like ind UID</code>\n\n"

            + "Example:\n"
            + "<code>/like ind 6475189319</code>\n\n"

            + "Same UID can be used once per user "
            + "in each daily cycle.\n\n"

            + "🔄 Reset: <b>4:00 AM IST</b>"

            + footer(),

            parse_mode=ParseMode.HTML
        )


    # ========================================================
    # LIKE HELP
    # ========================================================

    elif query.data == "help_like":

        await query.message.edit_text(
            header("Like")

            + "💗 <b>Send this command:</b>\n\n"
            + "<code>/like ind UID</code>\n\n"

            + "Example:\n"
            + "<code>/like ind 6475189319</code>"

            + footer(),

            parse_mode=ParseMode.HTML
        )


    # ========================================================
    # PROFILE
    # ========================================================

    elif query.data == "profile":

        used_count = db.execute(
            """
            SELECT COUNT(*)
            FROM usage
            WHERE user_id=?
            AND cycle=?
            """,
            (
                user_id,
                current_cycle()
            )
        ).fetchone()[0]

        await query.message.edit_text(
            header("Profile")

            + f"🆔 ID: <code>{user_id}</code>\n\n"
            + f"💗 UIDs used today: "
            + f"<code>{used_count}</code>\n"
            + "🔄 Reset: <b>4:00 AM IST</b>"

            + footer(),

            parse_mode=ParseMode.HTML
        )


    # ========================================================
    # CHECK JOIN
    # ========================================================

    elif query.data == "check_join":

        if await check_force_join(
            update,
            context
        ):

            await query.message.edit_text(
                header("Verified")

                + "✅ <b>You are verified!</b>\n\n"
                + "Now use:\n"
                + "<code>/like ind UID</code>"

                + footer(),

                parse_mode=ParseMode.HTML
            )


    # ========================================================
    # ADMIN HOME
    # ========================================================

    elif query.data == "admin_home":

        if not is_admin(user_id):
            return

        await query.message.edit_text(
            header("Admin Panel")

            + "👑 <b>Admin Control Center</b>\n\n"
            + "Select a section below:"

            + footer(),

            parse_mode=ParseMode.HTML,
            reply_markup=admin_keyboard()
        )


    # ========================================================
    # ADMIN STATS
    # ========================================================

    elif query.data == "admin_stats":

        if not is_admin(user_id):
            return

        users = db.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        banned = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE banned=1
            """
        ).fetchone()[0]

        total = db.execute(
            "SELECT COUNT(*) FROM requests"
        ).fetchone()[0]

        successful = db.execute(
            """
            SELECT COUNT(*)
            FROM requests
            WHERE status='SUCCESS'
            """
        ).fetchone()[0]

        await query.message.edit_text(
            header("Statistics")

            + f"👥 Users: <code>{users}</code>\n"
            + f"🚫 Banned: <code>{banned}</code>\n"
            + f"📨 Requests: <code>{total}</code>\n"
            + f"✅ Success: <code>{successful}</code>"

            + footer(),

            parse_mode=ParseMode.HTML,

            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="admin_home"
                    )
                ]
            ])
        )


    # ========================================================
    # FORCE JOIN ADMIN
    # ========================================================

    elif query.data == "force_join_admin":

        await force_join_admin_panel(
            query,
            context
        )


    # ========================================================
    # REMOVE FORCE JOIN
    # ========================================================

    elif query.data == "remove_force_join":

        if not is_admin(user_id):
            return

        set_setting(
            "force_join_link",
            ""
        )

        set_setting(
            "force_join_chat_id",
            ""
        )

        await query.message.edit_text(
            header("Force Join")

            + "✅ <b>Force Join removed.</b>\n\n"
            + "Users no longer need to join a channel."

            + footer(),

            parse_mode=ParseMode.HTML,

            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="admin_home"
                    )
                ]
            ])
        )


    # ========================================================
    # BOT SETTINGS
    # ========================================================

    elif query.data == "admin_settings":

        await settings_panel(
            query,
            context
        )


    # ========================================================
    # MAINTENANCE
    # ========================================================

    elif query.data == "maintenance":

        if not is_admin(user_id):
            return

        current = maintenance_enabled()

        new_value = (
            "0"
            if current
            else "1"
        )

        set_setting(
            "maintenance",
            new_value
        )

        status = (
            "ON 🔴"
            if new_value == "1"
            else "OFF 🟢"
        )

        await query.message.edit_text(
            header("Maintenance")

            + f"Current status: <b>{status}</b>"

            + footer(),

            parse_mode=ParseMode.HTML,

            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="admin_home"
                    )
                ]
            ])
        )


    # ========================================================
    # API STATUS
    # ========================================================

    elif query.data == "api_status":

        if not is_admin(user_id):
            return

        try:

            url = get_setting(
                "api_url",
                API_URL
            )

            response = await asyncio.to_thread(
                requests.get,
                url,
                params={
                    "uid": "6475189319",
                    "region": "ind",
                    "key": get_setting(
                        "api_key",
                        API_KEY
                    )
                },
                timeout=10
            )

            status = (
                "🟢 ONLINE"
                if response.ok
                else
                f"🟠 HTTP {response.status_code}"
            )

        except Exception:

            status = "🔴 OFFLINE"

        await query.message.edit_text(
            header("API Status")
            + f"🌐 <b>{status}</b>"
            + footer(),

            parse_mode=ParseMode.HTML,

            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="admin_home"
                    )
                ]
            ])
        )


    # ========================================================
    # USER MANAGEMENT
    # ========================================================

    elif query.data == "user_management":

        if not is_admin(user_id):
            return

        users = db.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        banned = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE banned=1
            """
        ).fetchone()[0]

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📊 User Stats",
                    callback_data="admin_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="admin_home"
                )
            ]
        ])

        await query.message.edit_text(
            header("User Management")

            + f"👥 Total Users: "
            + f"<code>{users}</code>\n"

            + f"🚫 Banned Users: "
            + f"<code>{banned}</code>\n\n"

            + "Commands:\n\n"
            + "<code>/ban USER_ID</code>\n"
            + "<code>/unban USER_ID</code>\n"
            + "<code>/reset USER_ID UID</code>\n"
            + "<code>/broadcast MESSAGE</code>"

            + footer(),

            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )


# ============================================================
#                     ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context
):

    logger.exception(
        "Unhandled exception:",
        exc_info=context.error
    )


# ============================================================
#                         MAIN
# ============================================================

def main():

    if (
        not BOT_TOKEN
        or BOT_TOKEN
        == "PUT_YOUR_NEW_BOT_TOKEN_HERE"
    ):

        print(
            "ERROR: Put your NEW BotFather token "
            "inside BOT_TOKEN."
        )

        return


    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )


    # ========================================================
    # USER COMMANDS
    # ========================================================

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "like",
            like_command
        )
    )

    application.add_handler(
        CommandHandler(
            "profile",
            profile
        )
    )


    # ========================================================
    # ADMIN COMMANDS
    # ========================================================

    application.add_handler(
        CommandHandler(
            "admin",
            admin_command
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            stats_command
        )
    )

    application.add_handler(
        CommandHandler(
            "ban",
            ban_command
        )
    )

    application.add_handler(
        CommandHandler(
            "unban",
            unban_command
        )
    )

    application.add_handler(
        CommandHandler(
            "reset",
            reset_command
        )
    )

    application.add_handler(
        CommandHandler(
            "maintenance",
            maintenance_command
        )
    )

    application.add_handler(
        CommandHandler(
            "broadcast",
            broadcast_command
        )
    )


    # ========================================================
    # FORCE JOIN
    # ========================================================

    application.add_handler(
        CommandHandler(
            "setforcejoin",
            set_forcejoin_command
        )
    )

    application.add_handler(
        CommandHandler(
            "disableforcejoin",
            disable_forcejoin_command
        )
    )


    # ========================================================
    # API SETTINGS
    # ========================================================

    application.add_handler(
        CommandHandler(
            "setapi",
            set_api_command
        )
    )

    application.add_handler(
        CommandHandler(
            "setkey",
            set_key_command
        )
    )

    application.add_handler(
        CommandHandler(
            "apistatus",
            api_status
        )
    )


    # ========================================================
    # CALLBACK BUTTONS
    # ========================================================

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )


    # ========================================================
    # UNKNOWN COMMANDS
    # ========================================================

    application.add_handler(
        MessageHandler(
            filters.COMMAND,
            unknown_command
        )
    )


    # ========================================================
    # ERROR HANDLER
    # ========================================================

    application.add_error_handler(
        error_handler
    )


    # ========================================================
    # START
    # ========================================================

    print(
        "===================================="
    )

    print(
        "       DP FREE LIKE BOT"
    )

    print(
        "===================================="
    )

    print(
        "Bot is starting..."
    )

    print(
        "Daily reset: 04:00 AM IST"
    )

    print(
        "Same user + same UID: once/day"
    )

    print(
        "Different UIDs: unlimited"
    )

    print(
        "Admin DM: ENABLED"
    )

    print(
        "Force Join: LINK BASED"
    )

    print(
        "===================================="
    )


    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# ============================================================
#                         RUN
# ============================================================

if __name__ == "__main__":
    main()