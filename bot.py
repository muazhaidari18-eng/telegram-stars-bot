import logging
import os
from datetime import datetime
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

PAYMENT_CHANNEL_ID = int(os.getenv("PAYMENT_CHANNEL_ID"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

MAIN_MENU_TEXT = (
    "💎 Megha Shaw Premium Portal 💎\n\n"
    "Megha's private inbox is currently reserved for VIP clients. Choose your VIP experience below."
)
PRIVATE_CHAT_TEXT = (
    "Spend some one-on-one time with Megha. Choose your preferred sexting session below."
)
VOICE_CALL_TEXT = (
    "Hear Megha's voice in a private Telegram call. Pick your preferred duration."
)
VIDEO_CALL_TEXT = (
    "Experience Megha live in a private video call. Choose a Standard session or unlock an exclusive "
    "Custom Outfit experience."
)
OUTFIT_MENU_TEXT = "Choose your preferred outfit for your session."

PRODUCTS = {
    "text_15": {
        "title": "Touch Yourself With Me (10 Min)",
        "description": "Pay 500 Stars for Touch Yourself With Me (10 Min)",
        "amount": 500,
        "label": "💦 Touch Yourself With Me (10 Min) — ⭐500",
        "product_name": "Touch Yourself With Me (10 Min)",
    },
    "text_30": {
        "title": "So Wet & Waiting For You (20 Min)",
        "description": "Pay 900 Stars for So Wet & Waiting For You (20 Min)",
        "amount": 900,
        "label": "❤️ So Wet & Waiting For You (20 Min) — ⭐900",
        "product_name": "So Wet & Waiting For You (20 Min)",
    },
    "text_60": {
        "title": "Total Devotion: My Clothes Come Off (30 Min)",
        "description": "Pay 1300 Stars for Total Devotion: My Clothes Come Off (30 Min)",
        "amount": 1300,
        "label": "🔥 Total Devotion: My Clothes Come Off (30 Min) — ⭐1300",
        "product_name": "Total Devotion: My Clothes Come Off (30 Min)",
    },
    "voice_10": {
        "title": "Sweet Talk (10 Minutes)",
        "description": "Pay 1200 Stars for Sweet Talk (10 Minutes)",
        "amount": 1200,
        "label": "💕 Sweet Talk (10 Minutes) — ⭐1200",
        "product_name": "Sweet Talk (10 Minutes)",
    },
    "voice_20": {
        "title": "Late Night Vibes (20 Minutes)",
        "description": "Pay 2200 Stars for Late Night Vibes (20 Minutes)",
        "amount": 2200,
        "label": "🌙 Late Night Vibes (20 Minutes) — ⭐2200",
        "product_name": "Late Night Vibes (20 Minutes)",
    },
    "voice_30": {
        "title": "VIP Private Call (30 Minutes)",
        "description": "Pay 3200 Stars for VIP Private Call (30 Minutes)",
        "amount": 3200,
        "label": "👑 VIP Private Call (30 Minutes) — ⭐3200",
        "product_name": "VIP Private Call (30 Minutes)",
    },
    "video_classic_10": {
        "title": "Classic Video Call (10 Minutes)",
        "description": "Pay 4000 Stars for Classic Video Call (10 Minutes)",
        "amount": 4000,
        "label": "🎥 Classic Video Call (10 Minutes) — ⭐4000",
        "product_name": "Classic Video Call (10 Minutes)",
    },
    "video_premium_15": {
        "title": "Premium Video Call (15 Minutes)",
        "description": "Pay 6000 Stars for Premium Video Call (15 Minutes)",
        "amount": 6000,
        "label": "💎 Premium Video Call (15 Minutes) — ⭐6000",
        "product_name": "Premium Video Call (15 Minutes)",
    },
    "video_custom_outfit_1_10": {
        "title": "Custom Outfit Experience (10 Minutes) - Outfit #1",
        "description": "Pay 6000 Stars for Custom Outfit Experience (10 Minutes) - Outfit #1",
        "amount": 6000,
        "label": "👗 Outfit #1 - Custom Outfit Experience",
        "product_name": "Custom Outfit Experience (10 Minutes) - Outfit #1",
    },
    "video_custom_outfit_2_10": {
        "title": "Custom Outfit Experience (10 Minutes) - Outfit #2",
        "description": "Pay 6000 Stars for Custom Outfit Experience (10 Minutes) - Outfit #2",
        "amount": 6000,
        "label": "👗 Outfit #2 - Custom Outfit Experience",
        "product_name": "Custom Outfit Experience (10 Minutes) - Outfit #2",
    },
    "video_custom_outfit_3_10": {
        "title": "Custom Outfit Experience (10 Minutes) - Outfit #3",
        "description": "Pay 6000 Stars for Custom Outfit Experience (10 Minutes) - Outfit #3",
        "amount": 6000,
        "label": "👗 Outfit #3 - Custom Outfit Experience",
        "product_name": "Custom Outfit Experience (10 Minutes) - Outfit #3",
    },
    "video_custom_outfit_4_10": {
        "title": "Custom Outfit Experience (10 Minutes) - Outfit #4",
        "description": "Pay 6000 Stars for Custom Outfit Experience (10 Minutes) - Outfit #4",
        "amount": 6000,
        "label": "👗 Outfit #4 - Custom Outfit Experience",
        "product_name": "Custom Outfit Experience (10 Minutes) - Outfit #4",
    },
    "video_ultimate_outfit_1_15": {
        "title": "Ultimate VIP Experience (15 Minutes) - Outfit #1",
        "description": "Pay 8500 Stars for Ultimate VIP Experience (15 Minutes) - Outfit #1",
        "amount": 8500,
        "label": "👗 Outfit #1 - Ultimate VIP Experience",
        "product_name": "Ultimate VIP Experience (15 Minutes) - Outfit #1",
    },
    "video_ultimate_outfit_2_15": {
        "title": "Ultimate VIP Experience (15 Minutes) - Outfit #2",
        "description": "Pay 8500 Stars for Ultimate VIP Experience (15 Minutes) - Outfit #2",
        "amount": 8500,
        "label": "👗 Outfit #2 - Ultimate VIP Experience",
        "product_name": "Ultimate VIP Experience (15 Minutes) - Outfit #2",
    },
    "video_ultimate_outfit_3_15": {
        "title": "Ultimate VIP Experience (15 Minutes) - Outfit #3",
        "description": "Pay 8500 Stars for Ultimate VIP Experience (15 Minutes) - Outfit #3",
        "amount": 8500,
        "label": "👗 Outfit #3 - Ultimate VIP Experience",
        "product_name": "Ultimate VIP Experience (15 Minutes) - Outfit #3",
    },
    "video_ultimate_outfit_4_15": {
        "title": "Ultimate VIP Experience (15 Minutes) - Outfit #4",
        "description": "Pay 8500 Stars for Ultimate VIP Experience (15 Minutes) - Outfit #4",
        "amount": 8500,
        "label": "👗 Outfit #4 - Ultimate VIP Experience",
        "product_name": "Ultimate VIP Experience (15 Minutes) - Outfit #4",
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
        InlineKeyboardButton(text="💬 Sexting Chat", callback_data="private_chat_menu"),
        InlineKeyboardButton(text="📞 Private Voice Call", callback_data="voice_call_menu"),
    )
    keyboard.row(
        InlineKeyboardButton(text="🎥 VIP Video Call", callback_data="video_call_menu"),
    )
    return keyboard


def private_chat_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="� Touch Yourself With Me (10 Min) — ⭐500", callback_data="pay_text_15"),
    )
    keyboard.row(
        InlineKeyboardButton(text="❤️ So Wet & Waiting For You (20 Min) — ⭐900", callback_data="pay_text_30"),
    )
    keyboard.row(
        InlineKeyboardButton(text="🔥 Total Devotion: My Clothes Come Off (30 Min) — ⭐1300", callback_data="pay_text_60"),
    )
    keyboard.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main"),
    )
    return keyboard


def voice_call_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="💕 Sweet Talk (10 Minutes) — ⭐1200", callback_data="pay_voice_10"),
    )
    keyboard.row(
        InlineKeyboardButton(text="🌙 Late Night Vibes (20 Minutes) — ⭐2200", callback_data="pay_voice_20"),
    )
    keyboard.row(
        InlineKeyboardButton(text="👑 VIP Private Call (30 Minutes) — ⭐3200", callback_data="pay_voice_30"),
    )
    keyboard.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main"),
    )
    return keyboard


def video_call_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🎥 Classic Video Call (10 Minutes) — ⭐4000", callback_data="pay_video_classic_10"),
    )
    keyboard.row(
        InlineKeyboardButton(text="✨ Custom Outfit Experience (10 Minutes) — ⭐6000", callback_data="video_custom_menu"),
    )
    keyboard.row(
        InlineKeyboardButton(text="💎 Premium Video Call (15 Minutes) — ⭐6000", callback_data="pay_video_premium_15"),
    )
    keyboard.row(
        InlineKeyboardButton(text="🔥 Ultimate VIP Experience (15 Minutes) — ⭐8500", callback_data="video_ultimate_menu"),
    )
    keyboard.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main"),
    )
    return keyboard


def video_outfit_menu_keyboard(variant: str) -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    if variant == "custom":
        keyboard.row(
            InlineKeyboardButton(text="👗 Outfit #1", callback_data="pay_video_custom_outfit_1_10"),
        )
        keyboard.row(
            InlineKeyboardButton(text="👗 Outfit #2", callback_data="pay_video_custom_outfit_2_10"),
        )
        keyboard.row(
            InlineKeyboardButton(text="👗 Outfit #3", callback_data="pay_video_custom_outfit_3_10"),
        )
        keyboard.row(
            InlineKeyboardButton(text="👗 Outfit #4", callback_data="pay_video_custom_outfit_4_10"),
        )
    else:
        keyboard.row(
            InlineKeyboardButton(text="👗 Outfit #1", callback_data="pay_video_ultimate_outfit_1_15"),
        )
        keyboard.row(
            InlineKeyboardButton(text="👗 Outfit #2", callback_data="pay_video_ultimate_outfit_2_15"),
        )
        keyboard.row(
            InlineKeyboardButton(text="👗 Outfit #3", callback_data="pay_video_ultimate_outfit_3_15"),
        )
        keyboard.row(
            InlineKeyboardButton(text="👗 Outfit #4", callback_data="pay_video_ultimate_outfit_4_15"),
        )
    keyboard.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_video"),
    )
    return keyboard


async def send_main_menu(message: Message) -> None:
    keyboard = main_menu_keyboard().as_markup()
    await message.answer(
        MAIN_MENU_TEXT,
        reply_markup=keyboard,
    )


@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message) -> None:
    await send_main_menu(message)


@dp.callback_query(F.data == "private_chat_menu")
async def callback_private_chat_menu(query: CallbackQuery) -> None:
    keyboard = private_chat_menu_keyboard().as_markup()
    await query.message.edit_text(
        PRIVATE_CHAT_TEXT,
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "voice_call_menu")
async def callback_voice_call_menu(query: CallbackQuery) -> None:
    keyboard = voice_call_menu_keyboard().as_markup()
    await query.message.edit_text(
        VOICE_CALL_TEXT,
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "video_call_menu")
async def callback_video_call_menu(query: CallbackQuery) -> None:
    keyboard = video_call_menu_keyboard().as_markup()
    await query.message.edit_text(
        VIDEO_CALL_TEXT,
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "video_custom_menu")
async def callback_video_custom_menu(query: CallbackQuery) -> None:
    keyboard = video_outfit_menu_keyboard("custom").as_markup()
    image_url = "https://raw.githubusercontent.com/muazhaidari18-eng/telegram-stars-bot/refs/heads/main/Dress-Options.png"
    await query.message.answer_photo(photo=image_url, caption=OUTFIT_MENU_TEXT, reply_markup=keyboard)
    await query.answer()


@dp.callback_query(F.data == "video_ultimate_menu")
async def callback_video_ultimate_menu(query: CallbackQuery) -> None:
    keyboard = video_outfit_menu_keyboard("ultimate").as_markup()
    image_url = "https://raw.githubusercontent.com/muazhaidari18-eng/telegram-stars-bot/refs/heads/main/Dress-Options.png"
    await query.message.answer_photo(photo=image_url, caption=OUTFIT_MENU_TEXT, reply_markup=keyboard)
    await query.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def callback_pay_service(query: CallbackQuery) -> None:
    payload_name = query.data.removeprefix("pay_")
    product_info = get_product_info(payload_name)

    if product_info is None:
        await query.answer("Payment flow for this product is not implemented yet.", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=query.from_user.id,
        title=product_info["title"],
        description=product_info["description"],
        payload=payload_name,
        currency="XTR",
        prices=[LabeledPrice(label=product_info["label"], amount=product_info["amount"])],
    )


@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    stars = message.successful_payment.total_amount

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "No Username"
    )

    user_id = message.from_user.id

    product_name = get_product_name(payload)

    now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M:%S %p IST")

    admin_message = f"""
💰 PAYMENT RECEIVED

👤 User: {username} ({user_id})
🛍️ Product: {product_name}

⭐ Stars: {stars}

📦 Type: one-time
⏱️ Time: {now}
"""

    await bot.send_message(PAYMENT_CHANNEL_ID, admin_message)
    await message.answer("✅ Payment received successfully!")


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
    dp.run_polling(bot)
