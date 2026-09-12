import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    raise RuntimeError("BOT_TOKEN environment variable is required to run the bot.")

PAYMENT_CHANNEL_ID = int(os.getenv("PAYMENT_CHANNEL_ID", "0"))
UPI_ID = os.getenv("UPI_ID", "Megha.shaw@ptyes")
UPI_QR_IMAGE_URL = os.getenv(
    "UPI_QR_IMAGE_URL",
    "https://raw.githubusercontent.com/muazhaidari18-eng/telegram-stars-bot/main/Megha-Shaw-UPI.jpeg",
)
CHAT_UPI_PRICE = int(os.getenv("CHAT_UPI_PRICE", "999"))
VIDEO_UPI_PRICE = int(os.getenv("VIDEO_UPI_PRICE", "4999"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "payments.sqlite3")
IST = ZoneInfo("Asia/Kolkata")
SUBSCRIPTION_PERIOD = 30 * 24 * 60 * 60

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

MAIN_MENU_TEXT = "Welcome cutie... select your VIP access below 🤍✨"
PRIVATE_CHAT_TEXT = "💬 Chat with Me\n\nStay connected with private VIP chat access.\n\nChoose your payment method:"
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
        InlineKeyboardButton(text="⭐ Pay 999 Stars / Month", callback_data="pay_chat"),
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
            """
        )


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


@dp.message(Command(commands=["start", "menu"]))
async def cmd_start(message: Message) -> None:
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
            "chat_id": query.from_user.id,
            "title": product_info["title"],
            "description": product_info["description"],
            "payload": "chat_subscription" if payload_name == "chat" else payload_name,
            "provider_token": "",
            "currency": "XTR",
            "prices": [
                LabeledPrice(
                    label="Chat with Me — 30 Days" if payload_name == "chat" else product_info["label"],
                    amount=999 if payload_name == "chat" else product_info["amount"],
                )
            ],
        }

        if payload_name == "chat":
            invoice_kwargs["subscription_period"] = 2592000

        await bot.send_invoice(**invoice_kwargs)
        await query.answer()
    except Exception:
        logging.exception("Failed to create Telegram Stars invoice")
        await query.answer(
            "Unable to open payment right now. Please try again.",
            show_alert=True,
        )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(
        ok=pre_checkout_query.invoice_payload in {"chat_subscription", "video"}
    )


@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    stars = message.successful_payment.total_amount
    product_key = "chat" if payload == "chat_subscription" else payload

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "No Username"
    )

    user_id = message.from_user.id

    product_name = get_product_name(product_key)

    now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M:%S %p IST")

    payment_type = "subscription" if payload == "chat_subscription" else "one-time"
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
        expiration = getattr(message.successful_payment, "subscription_expiration_date", None)
        expires_at = datetime.fromtimestamp(expiration, ZoneInfo("Asia/Kolkata")) if expiration else datetime.now(IST) + timedelta(days=30)
        activate_chat(user_id, "Telegram Stars", expires_at)
        await message.answer("✅ Your VIP chat access is active.")
    else:
        set_flow(user_id, "video_date")
        await message.answer("✅ Payment received successfully.\n\nWhat date works best for you?", reply_markup=back_keyboard().as_markup())


@dp.message(F.text)
async def video_schedule(message: Message) -> None:
    row = db_connect()
    user = row.execute("SELECT * FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    row.close()
    if not user:
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


if __name__ == "__main__":
    init_db()
    dp.run_polling(bot)
