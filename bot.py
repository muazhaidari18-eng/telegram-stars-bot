import asyncio
import hashlib
import html
import logging
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import aiogram
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)
logging.info("AIROGRAM VERSION: %s", aiogram.__version__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    raise RuntimeError("BOT_TOKEN environment variable is required to run the bot.")

PAYMENT_CHANNEL_ID = int(os.getenv("PAYMENT_CHANNEL_ID", "0"))
PRIVATE_CHAT_GROUP_ID = int(os.getenv("PRIVATE_CHAT_GROUP_ID", "0"))
UPI_ID = os.getenv("UPI_ID", "Megha.shaw@ptyes")
UPI_QR_IMAGE_URL = os.getenv(
    "UPI_QR_IMAGE_URL",
    "https://raw.githubusercontent.com/muazhaidari18-eng/telegram-stars-bot/main/Megha-Shaw-UPI.jpeg",
)
CHAT_UPI_PRICE = int(os.getenv("CHAT_UPI_PRICE", "999"))
VIDEO_UPI_PRICE = int(os.getenv("VIDEO_UPI_PRICE", "4999"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "payments.sqlite3")
OWNER_USER_ID = int(os.getenv("OWNER_USER_ID", "0"))
OWNER_USER_HASH = os.getenv(
    "OWNER_USER_HASH",
    "07067902a287da64338c77b0734dd9e8480da7f6f9ef514762a8e765ee159ce6",
)
BOT_USERNAME = os.getenv("BOT_USERNAME", "iLuvMeghabot").lstrip("@")
IST = ZoneInfo("Asia/Kolkata")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

MAIN_MENU_TEXT = "Welcome cutie... select your VIP access below 🤍✨"
PRIVATE_CHAT_TEXT = (
    "💬 Chat with Me\n\n"
    "Stay connected with private VIP chat access.\n\n"
    "Your one-time payment unlocks a full 30 days of private chat access.\n\n"
    "Choose your payment method:"
)
VIDEO_CALL_TEXT = "📹 Book a Private Video Call\n\nBook your private 1-on-1 video call.\n\nChoose your payment method:"

PRODUCTS = {
    "chat": {
        "title": "Chat with Me",
        "description": "Private VIP chat access for 30 days",
        "amount": 999,
        "label": "Chat with Me",
        "product_name": "Chat with Me",
        "upi_amount": CHAT_UPI_PRICE,
    },
    "video": {
        "title": "Private Video Call",
        "description": "Book a private 1-on-1 video call",
        "amount": 4999,
        "label": "Private Video Call",
        "product_name": "Private Video Call",
        "upi_amount": VIDEO_UPI_PRICE,
    },
}


def get_product_info(payload_name: str) -> dict | None:
    return PRODUCTS.get(payload_name)


def get_product_name(payload_name: str) -> str:
    product_info = get_product_info(payload_name)
    return product_info["product_name"] if product_info else payload_name


def main_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="💬 Chat with Me", callback_data="private_chat_menu"),
        InlineKeyboardButton(text="📹 Book a Private Video Call", callback_data="video_call_menu"),
    )
    return keyboard


def private_chat_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="⭐ Pay 999 Stars", callback_data="pay_chat"),
        InlineKeyboardButton(text="🇮🇳 Pay ₹999 via UPI", callback_data="upi_chat"),
    )
    keyboard.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main"),
    )
    return keyboard


def video_call_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="⭐ Pay 4,999 Stars", callback_data="pay_video"),
        InlineKeyboardButton(text="🇮🇳 Pay ₹4,999 via UPI", callback_data="upi_video"),
    )
    keyboard.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main"),
    )
    return keyboard


def db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with db_connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, username TEXT, flow_state TEXT NOT NULL DEFAULT 'idle',
                flow_context TEXT, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_access (
                user_id INTEGER PRIMARY KEY, active INTEGER NOT NULL DEFAULT 0,
                expires_at TEXT NOT NULL, source TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS upi_payments (
                payment_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, product_key TEXT NOT NULL,
                amount INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected')),
                created_at TEXT NOT NULL, verified_at TEXT
            );
            CREATE TABLE IF NOT EXISTS stars_payments (
                telegram_charge_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, product_key TEXT NOT NULL,
                stars INTEGER NOT NULL, payment_type TEXT NOT NULL, paid_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS video_bookings (
                booking_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, payment_method TEXT NOT NULL,
                paid TEXT NOT NULL, preferred_date TEXT NOT NULL, preferred_time TEXT NOT NULL, submitted_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS private_offers (
                token TEXT PRIMARY KEY, created_by INTEGER NOT NULL,
                stars INTEGER NOT NULL, duration_hours INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('open', 'pending', 'active', 'expired')),
                claimed_by INTEGER, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS private_sessions (
                session_code TEXT PRIMARY KEY, offer_token TEXT UNIQUE NOT NULL,
                customer_id INTEGER NOT NULL, operator_id INTEGER NOT NULL,
                starts_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active', 'expired')),
                expiry_notified INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS topic_offers (
                token TEXT PRIMARY KEY, session_code TEXT NOT NULL,
                customer_id INTEGER NOT NULL, stars INTEGER NOT NULL,
                duration_hours INTEGER NOT NULL DEFAULT 0,
                description TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS relay_messages (
                operator_message_id INTEGER PRIMARY KEY, session_code TEXT NOT NULL,
                customer_id INTEGER NOT NULL
            );
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(private_sessions)")}
        if "topic_thread_id" not in columns:
            connection.execute("ALTER TABLE private_sessions ADD COLUMN topic_thread_id INTEGER")


def ist_text() -> str:
    return datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p IST")


def set_flow(user_id: int, flow_state: str, context: str | None = None) -> None:
    with db_connect() as connection:
        connection.execute(
            """INSERT INTO users (user_id, flow_state, flow_context, updated_at) VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET flow_state=excluded.flow_state,
            flow_context=excluded.flow_context, updated_at=excluded.updated_at""",
            (user_id, flow_state, context, ist_text()),
        )


def activate_chat(user_id: int, source: str, expires_at: datetime | None = None) -> None:
    expires_at = expires_at or datetime.now(IST) + timedelta(days=30)
    with db_connect() as connection:
        connection.execute(
            """INSERT INTO chat_access VALUES (?, 1, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET active=1, expires_at=excluded.expires_at, source=excluded.source""",
            (user_id, expires_at.isoformat(), source),
        )


def active_chat_access(user_id: int) -> sqlite3.Row | None:
    with db_connect() as connection:
        row = connection.execute("SELECT * FROM chat_access WHERE user_id=? AND active=1", (user_id,)).fetchone()
    if row and datetime.fromisoformat(row["expires_at"]) > datetime.now(IST):
        return row
    return None


def is_owner(user_id: int) -> bool:
    if OWNER_USER_ID and user_id == OWNER_USER_ID:
        return True
    fingerprint = hashlib.sha256(str(user_id).encode()).hexdigest()
    return secrets.compare_digest(fingerprint, OWNER_USER_HASH)


def active_private_session(user_id: int) -> sqlite3.Row | None:
    with db_connect() as connection:
        row = connection.execute(
            "SELECT * FROM private_sessions WHERE customer_id=? AND status='active' ORDER BY starts_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row and datetime.fromisoformat(row["expires_at"]) <= datetime.now(IST):
            connection.execute(
                "UPDATE private_sessions SET status='expired' WHERE session_code=?",
                (row["session_code"],),
            )
            return None
    return row


def create_private_session(offer: sqlite3.Row, customer_id: int) -> sqlite3.Row:
    now = datetime.now(IST)
    expires_at = now + timedelta(hours=offer["duration_hours"])
    session_code = f"CHAT-{secrets.randbelow(900000) + 100000}"
    with db_connect() as connection:
        connection.execute(
            "INSERT INTO private_sessions (session_code, offer_token, customer_id, operator_id, starts_at, expires_at, status) VALUES (?, ?, ?, ?, ?, ?, 'active')",
            (session_code, offer["token"], customer_id, offer["created_by"], now.isoformat(), expires_at.isoformat()),
        )
        connection.execute("UPDATE private_offers SET status='active' WHERE token=?", (offer["token"],))
        return connection.execute("SELECT * FROM private_sessions WHERE session_code=?", (session_code,)).fetchone()


def create_standard_chat_session(customer_id: int, source: str) -> sqlite3.Row:
    """Create the operator-side session used after the public 30-day payment."""
    token = f"standard_{source.lower().replace(' ', '_')}_{uuid.uuid4().hex}"
    created_by = OWNER_USER_ID or 0
    with db_connect() as connection:
        connection.execute(
            "INSERT INTO private_offers VALUES (?, ?, 999, 720, 'open', ?, ?)",
            (token, created_by, customer_id, datetime.now(IST).isoformat()),
        )
        offer = connection.execute("SELECT * FROM private_offers WHERE token=?", (token,)).fetchone()
    return create_private_session(offer, customer_id)


async def announce_private_session(session: sqlite3.Row) -> None:
    expiry = datetime.fromisoformat(session["expires_at"]).strftime("%d-%m-%Y %I:%M %p IST")
    await bot.send_message(
        session["customer_id"],
        f"✅ Your private chat is ready.\n\nChat number: <b>{session['session_code']}</b>\nActive until: <b>{expiry}</b>\n\nSend your messages here in the bot.",
    )
    if PRIVATE_CHAT_GROUP_ID:
        user = await bot.get_chat(session["customer_id"])
        label = user.username and f"@{user.username}" or user.full_name or str(session["customer_id"])
        topic = await bot.create_forum_topic(
            PRIVATE_CHAT_GROUP_ID,
            name=f"🟢 {session['session_code']} · {label}"[:128],
        )
        with db_connect() as connection:
            connection.execute(
                "UPDATE private_sessions SET topic_thread_id=? WHERE session_code=?",
                (topic.message_thread_id, session["session_code"]),
            )
        await bot.send_message(
            PRIVATE_CHAT_GROUP_ID,
            f"🟢 <b>{session['session_code']}</b> started\nCustomer: <b>{html.escape(label)}</b>\nUser ID: <code>{session['customer_id']}</code>\nActive until: <b>{expiry}</b>\n\nReply normally in this topic.\n<code>/tip STARS description</code> sends a tip request.\n<code>/extend STARS HOURS description</code> sells more access.",
            message_thread_id=topic.message_thread_id,
        )
    else:
        await bot.send_message(
            session["operator_id"],
            f"🟢 <b>{session['session_code']}</b> started\nUser ID: <code>{session['customer_id']}</code>\nActive until: <b>{expiry}</b>\n\nReply directly to a relayed message to answer this person.",
        )


async def relay_private_message(message: Message) -> bool:
    if PRIVATE_CHAT_GROUP_ID and message.chat.id == PRIVATE_CHAT_GROUP_ID and message.message_thread_id:
        with db_connect() as connection:
            session = connection.execute(
                "SELECT * FROM private_sessions WHERE topic_thread_id=? AND status='active'",
                (message.message_thread_id,),
            ).fetchone()
        if not session:
            return False
        if datetime.fromisoformat(session["expires_at"]) <= datetime.now(IST):
            await message.answer("🔒 This customer access has expired, so the message was not sent.")
            return True
        try:
            await bot.copy_message(session["customer_id"], message.chat.id, message.message_id)
        except TelegramBadRequest as error:
            # Telegram forum service events (topic creation, pinning, etc.) cannot
            # be copied. They are internal group events, not operator messages.
            if "message can't be copied" not in str(error):
                raise
        return True

    if is_owner(message.from_user.id):
        replied = message.reply_to_message
        if not replied:
            return False
        with db_connect() as connection:
            mapping = connection.execute(
                "SELECT * FROM relay_messages WHERE operator_message_id=?",
                (replied.message_id,),
            ).fetchone()
            session = connection.execute(
                "SELECT * FROM private_sessions WHERE session_code=? AND status='active'",
                (mapping["session_code"],),
            ).fetchone() if mapping else None
        if not mapping or not session:
            return False
        if datetime.fromisoformat(session["expires_at"]) <= datetime.now(IST):
            with db_connect() as connection:
                connection.execute("UPDATE private_sessions SET status='expired' WHERE session_code=?", (session["session_code"],))
            await message.answer(f"🔒 {session['session_code']} has expired, so this reply was not sent.")
            return True
        await bot.copy_message(mapping["customer_id"], message.chat.id, message.message_id)
        return True

    session = active_private_session(message.from_user.id)
    if not session:
        return False
    destination = PRIVATE_CHAT_GROUP_ID or session["operator_id"]
    thread_id = session["topic_thread_id"] if PRIVATE_CHAT_GROUP_ID else None
    header = await bot.send_message(
        destination,
        f"💬 <b>{session['session_code']}</b>",
        message_thread_id=thread_id,
    )
    copied = await bot.copy_message(destination, message.chat.id, message.message_id, message_thread_id=thread_id)
    with db_connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO relay_messages VALUES (?, ?, ?)",
            (copied.message_id, session["session_code"], message.from_user.id),
        )
        connection.execute(
            "INSERT OR REPLACE INTO relay_messages VALUES (?, ?, ?)",
            (header.message_id, session["session_code"], message.from_user.id),
        )
    return True


async def expiry_monitor() -> None:
    while True:
        now = datetime.now(IST)
        with db_connect() as connection:
            expired = connection.execute(
                "SELECT * FROM private_sessions WHERE status='active' AND expires_at<=?",
                (now.isoformat(),),
            ).fetchall()
            for session in expired:
                connection.execute(
                    "UPDATE private_sessions SET status='expired', expiry_notified=1 WHERE session_code=?",
                    (session["session_code"],),
                )
        for session in expired:
            try:
                await bot.send_message(session["customer_id"], f"🔒 {session['session_code']} has ended. Messages are no longer forwarded.")
                if PRIVATE_CHAT_GROUP_ID and session["topic_thread_id"]:
                    await bot.send_message(PRIVATE_CHAT_GROUP_ID, f"🔒 {session['session_code']} has expired and is now closed.", message_thread_id=session["topic_thread_id"])
                    await bot.close_forum_topic(PRIVATE_CHAT_GROUP_ID, session["topic_thread_id"])
                else:
                    await bot.send_message(session["operator_id"], f"🔒 {session['session_code']} has expired and is now closed.")
            except Exception:
                logging.exception("Failed to send expiry notice for %s", session["session_code"])
        await asyncio.sleep(60)


def back_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⬅️ Back", callback_data="back_to_main")
    return keyboard


async def send_main_menu(message: Message) -> None:
    keyboard = main_menu_keyboard().as_markup()
    await message.answer(
        MAIN_MENU_TEXT,
        reply_markup=keyboard,
    )


@dp.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(f"Your Telegram user ID is: <code>{message.from_user.id}</code>")


@dp.message(Command("offer"))
async def cmd_offer(message: Message, command: CommandObject) -> None:
    if not is_owner(message.from_user.id):
        await message.answer("This command is not available.")
        return
    try:
        stars_text, hours_text = (command.args or "").split()
        stars, hours = int(stars_text), int(hours_text)
        if stars < 0 or stars > 10000 or hours < 1 or hours > 24 * 365:
            raise ValueError
    except ValueError:
        await message.answer("Use: <code>/offer STARS HOURS</code>\nExample test: <code>/offer 0 48</code>")
        return
    token = secrets.token_urlsafe(18)
    with db_connect() as connection:
        connection.execute(
            "INSERT INTO private_offers VALUES (?, ?, ?, ?, 'open', NULL, ?)",
            (token, message.from_user.id, stars, hours, datetime.now(IST).isoformat()),
        )
    link = f"https://t.me/{BOT_USERNAME}?start=offer_{token}"
    price = "free test" if stars == 0 else f"{stars:,} Stars"
    await message.answer(
        f"🔐 Private offer created\nPrice: <b>{price}</b>\nAccess: <b>{hours} hours</b>\n\n<code>{link}</code>\n\nThis single-use link is not shown in the public menu."
    )


async def create_topic_offer(message: Message, command: CommandObject, extend: bool) -> None:
    if not (is_owner(message.from_user.id) and PRIVATE_CHAT_GROUP_ID and message.chat.id == PRIVATE_CHAT_GROUP_ID and message.message_thread_id):
        await message.answer("This command is only available to the owner inside an active customer topic.")
        return
    parts = (command.args or "").split(maxsplit=2 if extend else 1)
    try:
        stars = int(parts[0])
        hours = int(parts[1]) if extend else 0
        description = parts[2] if extend and len(parts) > 2 else (parts[1] if not extend and len(parts) > 1 else ("Extra private-chat access" if extend else "Tip"))
        if stars < 1 or stars > 10000 or hours < 0 or hours > 24 * 365:
            raise ValueError
    except (ValueError, IndexError):
        usage = "/extend STARS HOURS description" if extend else "/tip STARS description"
        await message.answer(f"Use: <code>{usage}</code>")
        return
    with db_connect() as connection:
        session = connection.execute(
            "SELECT * FROM private_sessions WHERE topic_thread_id=? AND status='active'",
            (message.message_thread_id,),
        ).fetchone()
    if not session:
        await message.answer("This topic does not have an active customer session.")
        return
    token = secrets.token_urlsafe(12)
    with db_connect() as connection:
        connection.execute(
            "INSERT INTO topic_offers VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
            (token, session["session_code"], session["customer_id"], stars, hours, description, datetime.now(IST).isoformat()),
        )
    await bot.send_invoice(
        chat_id=session["customer_id"], title=("Extend Private Access" if extend else "Tip Megha"),
        description=description[:255], payload=f"topicoffer_{token}", currency="XTR",
        prices=[LabeledPrice(label=description[:32], amount=stars)],
    )
    await message.answer(f"✅ Sent <b>{stars:,} Stars</b> request to the customer: {html.escape(description)}")


@dp.message(Command("tip"))
async def cmd_tip(message: Message, command: CommandObject) -> None:
    await create_topic_offer(message, command, extend=False)


@dp.message(Command("extend"))
async def cmd_extend(message: Message, command: CommandObject) -> None:
    await create_topic_offer(message, command, extend=True)


@dp.message(Command(commands=["start", "menu"]))
async def cmd_start(message: Message, command: CommandObject) -> None:
    if command.command == "start" and command.args and command.args.startswith("offer_"):
        token = command.args.removeprefix("offer_")
        with db_connect() as connection:
            offer = connection.execute("SELECT * FROM private_offers WHERE token=?", (token,)).fetchone()
            if not offer or offer["status"] != "open":
                await message.answer("This private link is invalid, expired, or has already been used.")
                return
            claimed = connection.execute(
                "UPDATE private_offers SET status='pending', claimed_by=? WHERE token=? AND status='open'",
                (message.from_user.id, token),
            ).rowcount
        if not claimed:
            await message.answer("This private link has already been used.")
            return
        if offer["stars"] == 0:
            session = create_private_session(offer, message.from_user.id)
            await announce_private_session(session)
        else:
            await bot.send_invoice(
                chat_id=message.from_user.id,
                title="Private Chat Access",
                description=f"Private chat access for {offer['duration_hours']} hours",
                payload=f"offer_{token}", currency="XTR",
                prices=[LabeledPrice(label="Private Chat Access", amount=offer["stars"])],
            )
        return
    set_flow(message.from_user.id, "idle")
    await send_main_menu(message)


@dp.message(Command("status"))
async def cmd_status(message: Message) -> None:
    access = active_chat_access(message.from_user.id)
    if access:
        expires = datetime.fromisoformat(access["expires_at"]).strftime("%d-%m-%Y %I:%M %p IST")
        await message.answer(f"✅ Your Chat with Me access is active until {expires}.")
    else:
        await message.answer("Your Chat with Me access is not currently active. You can renew it from /menu.")


@dp.callback_query(F.data == "private_chat_menu")
async def callback_private_chat_menu(query: CallbackQuery) -> None:
    keyboard = private_chat_menu_keyboard().as_markup()
    await query.message.edit_text(
        PRIVATE_CHAT_TEXT,
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "video_call_menu")
async def callback_video_call_menu(query: CallbackQuery) -> None:
    await query.message.edit_text(
        VIDEO_CALL_TEXT,
        reply_markup=video_call_menu_keyboard().as_markup(),
    )
    await query.answer()


@dp.callback_query(F.data.in_({"upi_chat", "upi_video"}))
async def callback_upi(query: CallbackQuery) -> None:
    service = query.data.removeprefix("upi_")
    product = PRODUCTS[service]
    set_flow(query.from_user.id, f"upi_{service}")
    await query.message.answer_photo(
        photo=UPI_QR_IMAGE_URL,
        caption=(
            "🇮🇳 <b>UPI Payment</b>\n\n"
            f"💰 Amount: ₹{product['upi_amount']:,}\n"
            f"💳 UPI ID: {UPI_ID}\n\n"
            "Scan the QR code or pay directly to the UPI ID.\n\n"
            "After payment, send the screenshot directly to the channel DM for verification."
        ),
        reply_markup=back_keyboard().as_markup(),
    )
    await query.answer()


@dp.message(F.photo)
async def receive_upi_screenshot(message: Message) -> None:
    user = db_connect()
    row = user.execute("SELECT * FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    user.close()
    if not row or not row["flow_state"].startswith("upi_"):
        await relay_private_message(message)
        return
    service = row["flow_state"].removeprefix("upi_")
    product = PRODUCTS.get(service)
    if not product:
        return
    payment_id = uuid.uuid4().hex
    with db_connect() as connection:
        connection.execute(
            "INSERT INTO upi_payments VALUES (?, ?, ?, ?, 'pending', ?, NULL)",
            (payment_id, message.from_user.id, service, product["upi_amount"], ist_text()),
        )
    set_flow(message.from_user.id, "idle")
    username = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    await bot.send_photo(
        PAYMENT_CHANNEL_ID,
        photo=message.photo[-1].file_id,
        caption=(
            "💳 <b>UPI PAYMENT VERIFICATION</b>\n\n"
            f"👤 User: {username}\n🆔 User ID: {message.from_user.id}\n"
            f"🛍️ Product: {product['product_name']}\n💰 Amount: ₹{product['upi_amount']:,}\n"
            f"📦 Payment Method: UPI\n⏱️ Time: {ist_text()}\n🧾 Payment ID: {payment_id}"
        ),
        reply_markup=(InlineKeyboardBuilder()
                      .button(text="✅ Approve Payment", callback_data=f"upi_approve:{payment_id}")
                      .button(text="❌ Reject Payment", callback_data=f"upi_reject:{payment_id}")
                      .adjust(1).as_markup()),
    )
    await message.answer("✅ Screenshot received. Your payment is pending verification.")


@dp.callback_query(F.data.startswith("upi_approve:") | F.data.startswith("upi_reject:"))
async def callback_verify_upi(query: CallbackQuery) -> None:
    action, payment_id = query.data.split(":", 1)
    new_status = "approved" if action == "upi_approve" else "rejected"
    with db_connect() as connection:
        payment = connection.execute("SELECT * FROM upi_payments WHERE payment_id=?", (payment_id,)).fetchone()
        if not payment or payment["status"] != "pending":
            await query.answer("This payment is already processed or does not exist.", show_alert=True)
            return
        connection.execute(
            "UPDATE upi_payments SET status=?, verified_at=? WHERE payment_id=? AND status='pending'",
            (new_status, ist_text(), payment_id),
        )
    await query.answer(f"Payment {new_status}.")
    await query.message.edit_reply_markup(reply_markup=None)
    if new_status == "rejected":
        await bot.send_message(payment["user_id"], "❌ We couldn't verify this payment. Please check the payment details and send a valid payment screenshot again.")
        return
    await bot.send_message(payment["user_id"], "✅ Payment verified successfully!")
    if payment["product_key"] == "chat":
        activate_chat(payment["user_id"], "UPI")
        session = create_standard_chat_session(payment["user_id"], "UPI")
        await announce_private_session(session)
    else:
        set_flow(payment["user_id"], "video_date")
        await bot.send_message(payment["user_id"], "What date works best for you?", reply_markup=back_keyboard().as_markup())


@dp.callback_query(F.data.startswith("pay_"))
async def callback_pay_service(query: CallbackQuery) -> None:
    payload_name = query.data.removeprefix("pay_")
    product_info = get_product_info(payload_name)

    if product_info is None:
        await query.answer("Payment flow for this product is not implemented yet.", show_alert=True)
        return

    try:
        invoice_kwargs = {
            "title": product_info["title"],
            "description": product_info["description"],
            "payload": payload_name,
            "currency": "XTR",
            "prices": [
                LabeledPrice(
                    label=product_info["label"],
                    amount=product_info["amount"],
                )
            ],
        }

        await bot.send_invoice(chat_id=query.from_user.id, **invoice_kwargs)
        await query.answer()
    except Exception:
        logging.exception("Failed to create Telegram Stars invoice")
        await query.answer(
            "Unable to open payment right now. Please try again.",
            show_alert=True,
        )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    payload = pre_checkout_query.invoice_payload
    if payload in {"chat", "video"}:
        await pre_checkout_query.answer(ok=True)
        return
    if payload.startswith("offer_"):
        token = payload.removeprefix("offer_")
        with db_connect() as connection:
            offer = connection.execute("SELECT * FROM private_offers WHERE token=?", (token,)).fetchone()
        valid = bool(offer and offer["status"] == "pending" and offer["claimed_by"] == pre_checkout_query.from_user.id and offer["stars"] == pre_checkout_query.total_amount)
        await pre_checkout_query.answer(ok=valid, error_message=None if valid else "This private offer is no longer available.")
        return
    if payload.startswith("topicoffer_"):
        token = payload.removeprefix("topicoffer_")
        with db_connect() as connection:
            offer = connection.execute("SELECT * FROM topic_offers WHERE token=?", (token,)).fetchone()
        valid = bool(offer and offer["status"] == "pending" and offer["customer_id"] == pre_checkout_query.from_user.id and offer["stars"] == pre_checkout_query.total_amount)
        await pre_checkout_query.answer(ok=valid, error_message=None if valid else "This offer is no longer available.")
        return
    await pre_checkout_query.answer(ok=False, error_message="Unknown payment request.")


@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    stars = message.successful_payment.total_amount
    product_key = payload

    if payload.startswith("offer_"):
        token = payload.removeprefix("offer_")
        with db_connect() as connection:
            offer = connection.execute("SELECT * FROM private_offers WHERE token=?", (token,)).fetchone()
        if not offer or offer["status"] != "pending" or offer["claimed_by"] != message.from_user.id or offer["stars"] != stars:
            logging.error("Paid private offer validation failed for token %s", token)
            await message.answer("Payment received, but the private session needs manual review. Please contact support.")
            return
        with db_connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO stars_payments VALUES (?, ?, ?, ?, ?, ?)",
                (message.successful_payment.telegram_payment_charge_id, message.from_user.id, payload, stars, "one-time", ist_text()),
            )
        session = create_private_session(offer, message.from_user.id)
        await announce_private_session(session)
        await bot.send_message(PAYMENT_CHANNEL_ID, f"💰 PRIVATE OFFER PAID\n\n👤 User ID: {message.from_user.id}\n💬 Chat: {session['session_code']}\n⭐ Stars: {stars}\n⏱️ Time: {ist_text()}")
        return

    if payload.startswith("topicoffer_"):
        token = payload.removeprefix("topicoffer_")
        with db_connect() as connection:
            offer = connection.execute("SELECT * FROM topic_offers WHERE token=?", (token,)).fetchone()
            if not offer or offer["status"] != "pending" or offer["customer_id"] != message.from_user.id or offer["stars"] != stars:
                await message.answer("Payment received, but this offer needs manual review.")
                return
            connection.execute("UPDATE topic_offers SET status='paid' WHERE token=?", (token,))
            session = connection.execute("SELECT * FROM private_sessions WHERE session_code=?", (offer["session_code"],)).fetchone()
            if offer["duration_hours"] and session:
                current_expiry = max(datetime.fromisoformat(session["expires_at"]), datetime.now(IST))
                new_expiry = current_expiry + timedelta(hours=offer["duration_hours"])
                connection.execute("UPDATE private_sessions SET expires_at=? WHERE session_code=?", (new_expiry.isoformat(), session["session_code"]))
            connection.execute(
                "INSERT OR IGNORE INTO stars_payments VALUES (?, ?, ?, ?, ?, ?)",
                (message.successful_payment.telegram_payment_charge_id, message.from_user.id, payload, stars, "one-time", ist_text()),
            )
        await message.answer("✅ Payment received. Thank you!")
        if session and PRIVATE_CHAT_GROUP_ID and session["topic_thread_id"]:
            detail = f" · access extended by {offer['duration_hours']} hours" if offer["duration_hours"] else ""
            await bot.send_message(PRIVATE_CHAT_GROUP_ID, f"💰 <b>{stars:,} Stars paid</b>{detail}\n{html.escape(offer['description'])}", message_thread_id=session["topic_thread_id"])
        return

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "No Username"
    )

    user_id = message.from_user.id

    product_name = get_product_name(product_key)

    now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M:%S %p IST")

    payment_type = "one-time"
    with db_connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO stars_payments VALUES (?, ?, ?, ?, ?, ?)",
            (message.successful_payment.telegram_payment_charge_id, user_id, product_key, stars, payment_type, ist_text()),
        )

    admin_message = f"""
💰 PAYMENT RECEIVED

👤 User: {username} ({user_id})
🛍️ Product: {product_name}

⭐ Stars: {stars}

📦 Type: {payment_type}
💳 Method: Telegram Stars
⏱️ Time: {now}
"""

    await bot.send_message(PAYMENT_CHANNEL_ID, admin_message)
    if product_key == "chat":
        expires_at = datetime.now(IST) + timedelta(days=30)
        activate_chat(user_id, "Telegram Stars", expires_at)
        session = create_standard_chat_session(user_id, "Telegram Stars")
        await announce_private_session(session)
    else:
        set_flow(user_id, "video_date")
        await message.answer("✅ Payment received successfully.\n\nWhat date works best for you?", reply_markup=back_keyboard().as_markup())


@dp.message(F.text)
async def video_schedule(message: Message) -> None:
    row = db_connect()
    user = row.execute("SELECT * FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    row.close()
    if not user:
        await relay_private_message(message)
        return
    if user["flow_state"] == "video_date":
        set_flow(message.from_user.id, "video_time", message.text)
        await message.answer("What time works best for you? Please mention your timezone.")
    elif user["flow_state"] == "video_time":
        with db_connect() as connection:
            upi = connection.execute("SELECT * FROM upi_payments WHERE user_id=? AND product_key='video' AND status='approved' ORDER BY verified_at DESC LIMIT 1", (message.from_user.id,)).fetchone()
            stars = connection.execute("SELECT * FROM stars_payments WHERE user_id=? AND product_key='video' ORDER BY paid_at DESC LIMIT 1", (message.from_user.id,)).fetchone()
            method = "UPI" if upi and (not stars or upi["verified_at"] >= stars["paid_at"]) else "Telegram Stars"
            paid = f"₹{upi['amount']:,}" if method == "UPI" else f"{stars['stars']} Stars"
            connection.execute("INSERT INTO video_bookings VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (uuid.uuid4().hex, message.from_user.id, method, paid, user["flow_context"], message.text, ist_text()))
        username = f"@{message.from_user.username}" if message.from_user.username else "No Username"
        await bot.send_message(PAYMENT_CHANNEL_ID, f"""📹 VIDEO CALL BOOKING

👤 User: {username} ({message.from_user.id})
💳 Payment Method: {method}
💰 Paid: {paid}
📅 Preferred Date: {html.escape(user['flow_context'])}
🕐 Preferred Time: {html.escape(message.text)}
⏱️ Submitted: {ist_text()}""")
        set_flow(message.from_user.id, "idle")
        await message.answer("✅ Your request has been received.")
    else:
        await relay_private_message(message)


@dp.message()
async def relay_other_messages(message: Message) -> None:
    await relay_private_message(message)


@dp.callback_query(F.data == "back_to_main")
async def callback_back_to_main(query: CallbackQuery) -> None:
    keyboard = main_menu_keyboard().as_markup()
    await query.message.edit_text(
        MAIN_MENU_TEXT,
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "back_to_video")
async def callback_back_to_video(query: CallbackQuery) -> None:
    keyboard = video_call_menu_keyboard().as_markup()
    await query.message.edit_text(
        VIDEO_CALL_TEXT,
        reply_markup=keyboard,
    )
    await query.answer()


async def start_background_tasks() -> None:
    asyncio.create_task(expiry_monitor())


if __name__ == "__main__":
    init_db()
    dp.startup.register(start_background_tasks)
    dp.run_polling(bot)
