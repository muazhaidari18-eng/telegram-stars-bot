import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()


def main_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardBuilder().button(text="💕 Girlfriend Experience", callback_data="girlfriend_menu"),
        InlineKeyboardBuilder().button(text="📱 FaceTime", callback_data="facetime_menu"),
    )
    return keyboard


def girlfriend_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardBuilder().button(text="💳 Pay 25,000 Stars", callback_data="pay_girlfriend"),
    )
    keyboard.row(
        InlineKeyboardBuilder().button(text="⬅️ Back", callback_data="back_to_main"),
    )
    return keyboard


def facetime_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardBuilder().button(text="☕ Just Catching Up FaceTime ⭐7,999", callback_data="facetime_casual_menu"),
    )
    keyboard.row(
        InlineKeyboardBuilder().button(text="🌙 The Late Night FaceTime ⭐14,999", callback_data="facetime_latenight_menu"),
    )
    keyboard.row(
        InlineKeyboardBuilder().button(text="⬅️ Back", callback_data="back_to_main"),
    )
    return keyboard


def casual_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardBuilder().button(text="💳 Pay 7,999 Stars", callback_data="pay_facetime_casual"),
    )
    keyboard.row(
        InlineKeyboardBuilder().button(text="⬅️ Back", callback_data="back_to_facetime"),
    )
    return keyboard


def latenight_menu_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardBuilder().button(text="💳 Pay 14,999 Stars", callback_data="pay_facetime_latenight"),
    )
    keyboard.row(
        InlineKeyboardBuilder().button(text="⬅️ Back", callback_data="back_to_facetime"),
    )
    return keyboard


async def send_main_menu(message: Message) -> None:
    keyboard = main_menu_keyboard().as_markup()
    await message.answer(
        "💖 Welcome! Choose an experience below.",
        reply_markup=keyboard,
    )


@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message) -> None:
    await send_main_menu(message)


@dp.callback_query(F.data == "girlfriend_menu")
async def callback_girlfriend_menu(query: CallbackQuery) -> None:
    keyboard = girlfriend_menu_keyboard().as_markup()
    await query.message.edit_text(
        "💕 Girlfriend Experience\n\n⭐ Price: 25,000 Stars",
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "facetime_menu")
async def callback_facetime_menu(query: CallbackQuery) -> None:
    keyboard = facetime_menu_keyboard().as_markup()
    await query.message.edit_text(
        "📱 FaceTime\n\nChoose a package:",
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "facetime_casual_menu")
async def callback_facetime_casual_menu(query: CallbackQuery) -> None:
    keyboard = casual_menu_keyboard().as_markup()
    await query.message.edit_text(
        "☕ Just Catching Up FaceTime\n\n⭐ Price: 7,999 Stars",
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "facetime_latenight_menu")
async def callback_facetime_latenight_menu(query: CallbackQuery) -> None:
    keyboard = latenight_menu_keyboard().as_markup()
    await query.message.edit_text(
        "🌙 The Late Night FaceTime\n\n⭐ Price: 14,999 Stars",
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "back_to_main")
async def callback_back_to_main(query: CallbackQuery) -> None:
    keyboard = main_menu_keyboard().as_markup()
    await query.message.edit_text(
        "💖 Welcome! Choose an experience below.",
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "back_to_facetime")
async def callback_back_to_facetime(query: CallbackQuery) -> None:
    keyboard = facetime_menu_keyboard().as_markup()
    await query.message.edit_text(
        "📱 FaceTime\n\nChoose a package:",
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def callback_placeholder_payment(query: CallbackQuery) -> None:
    payload_name = query.data.removeprefix("pay_")
    product_name = {
        "girlfriend": "Girlfriend Experience",
        "facetime_casual": "Just Catching Up FaceTime",
        "facetime_latenight": "The Late Night FaceTime",
    }.get(payload_name, "selected product")

    await query.answer(f"Payment flow for {product_name} is not implemented yet.", show_alert=True)


if __name__ == "__main__":
    dp.run_polling(bot)
