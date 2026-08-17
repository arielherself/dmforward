"""Telegram secretary bot.

Connected to a user's account via Telegram Business (Settings -> Telegram
Business -> Chatbots). For every incoming private message the bot applies the
user's configured behavior: ignore, delete, or forward a summary to the
user's bot DM and delete the original.
"""

import html
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    BusinessConnection,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
)

from db import Database

BOT_TOKEN = os.environ["BOT_TOKEN"]
DB_PATH = os.environ.get("DB_PATH", "secretary.db")

router = Router()
db = Database(DB_PATH)

MODES = {
    "ignore": "Ignore",
    "forward_delete": "Forward & delete",
    "delete": "Delete",
}

# Checked in order; the first present attribute wins. Animation must come
# before document (animations are documents), photo is a list of sizes.
MEDIA_TYPES = [
    ("photo", "Photo"),
    ("animation", "GIF"),
    ("video", "Video"),
    ("video_note", "Video message"),
    ("voice", "Voice message"),
    ("audio", "Audio"),
    ("sticker", "Sticker"),
    ("document", "Document"),
    ("location", "Location"),
    ("venue", "Venue"),
    ("contact", "Contact"),
    ("poll", "Poll"),
    ("dice", "Dice"),
    ("game", "Game"),
    ("invoice", "Invoice"),
    ("story", "Story"),
]


def display_name(user: User) -> str:
    name = " ".join(p for p in (user.first_name, user.last_name) if p)
    return name or (f"@{user.username}" if user.username else str(user.id))


def mode_keyboard(current: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("✅ " if key == current else "") + label,
                    callback_data=f"mode:{key}",
                )
            ]
            for key, label in MODES.items()
        ]
    )


def describe_content(message: Message) -> str:
    text = message.text or message.caption or ""
    for attr, label in MEDIA_TYPES:
        if getattr(message, attr, None):
            return f"[{label}]" + (f" {text}" if text else "")
    return text or "[Unsupported message]"


def format_forward(sender: User, message: Message) -> str:
    return (
        f'Sender: <a href="tg://user?id={sender.id}">{html.escape(display_name(sender))}</a>\n'
        f"Search: #u{sender.id}\n"
        f"Content: {html.escape(describe_content(message))}"
    )


async def delete_business_message(bot: Bot, connection_id: str, message_id: int):
    try:
        await bot.delete_business_messages(connection_id, [message_id])
    except TelegramBadRequest as e:
        logging.warning("Could not delete business message %s: %s", message_id, e)


# ---------------------------------------------------------------------------
# Configuration commands (bot DM)
# ---------------------------------------------------------------------------


@router.message(Command("start"), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: Message):
    await db.upsert_user(message.from_user.id)
    await message.answer(
        "👋 I'm a secretary bot. I screen the private messages sent to your "
        "account — ignoring, deleting, or forwarding them to you right here "
        "in this chat.\n\n"
        "<b>Setup</b>:\n"
        "1. Open <b>Settings → Telegram Business → Chatbots</b> and add me.\n"
        "2. Grant me the permissions to <b>read messages</b> and "
        "<b>delete messages</b>.\n\n"
        "<b>Configuration</b>:\n"
        "/mode — what to do with incoming messages\n"
        "/whitelist — manage whitelisted senders\n"
        "/status — show current configuration",
        parse_mode="HTML",
    )


@router.message(Command("mode"), F.chat.type == ChatType.PRIVATE)
async def cmd_mode(message: Message):
    user = await db.get_user(message.from_user.id)
    current = user["mode"] if user else "ignore"
    await message.answer(
        "What should I do with new incoming messages?",
        reply_markup=mode_keyboard(current),
    )


@router.callback_query(F.data.startswith("mode:"))
async def cb_mode(call: CallbackQuery):
    mode = call.data.split(":", 1)[1]
    if mode not in MODES:
        await call.answer("Unknown mode.", show_alert=True)
        return
    await db.set_mode(call.from_user.id, mode)
    await call.message.edit_text(
        "What should I do with new incoming messages?\n\n"
        f"Current behavior: <b>{MODES[mode]}</b>",
        parse_mode="HTML",
        reply_markup=mode_keyboard(mode),
    )
    await call.answer("Saved.")


@router.message(Command("whitelist"), F.chat.type == ChatType.PRIVATE)
async def cmd_whitelist(message: Message):
    await send_whitelist(message, message.from_user.id)


async def send_whitelist(message: Message, owner_id: int):
    entries = await db.list_whitelist(owner_id)
    if not entries:
        await message.answer(
            "Your whitelist is empty. Whitelisted senders' messages are left "
            "untouched. Use the «Add to whitelist» button on forwarded "
            "messages to add senders."
        )
        return
    await message.answer(
        "Whitelisted senders (their messages are left untouched):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"❌ {e['name']}",
                        callback_data=f"wl_rm:{e['sender_id']}",
                    )
                ]
                for e in entries
            ]
        ),
    )


@router.callback_query(F.data.startswith("wl_rm:"))
async def cb_whitelist_remove(call: CallbackQuery):
    sender_id = int(call.data.split(":", 1)[1])
    await db.remove_from_whitelist(call.from_user.id, sender_id)
    await call.answer("Removed from whitelist.")
    await call.message.delete()
    await send_whitelist(call.message, call.from_user.id)


@router.message(Command("status"), F.chat.type == ChatType.PRIVATE)
async def cmd_status(message: Message):
    user = await db.get_user(message.from_user.id)
    whitelist = await db.list_whitelist(message.from_user.id)
    if not user:
        await message.answer("No configuration yet. See /start.")
        return
    if user["connection_id"]:
        conn = "enabled ✅" if user["connection_enabled"] else "paused ⏸"
    else:
        conn = "not connected ❌ (see /start)"
    await message.answer(
        f"<b>Connection:</b> {conn}\n"
        f"<b>Behavior:</b> {MODES.get(user['mode'], user['mode'])}\n"
        f"<b>Whitelisted senders:</b> {len(whitelist)}",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Business connection
# ---------------------------------------------------------------------------


@router.business_connection()
async def on_connection(conn: BusinessConnection, bot: Bot):
    owner_id = conn.user.id
    await db.upsert_connection(owner_id, conn.id, conn.is_enabled)

    rights = getattr(conn, "rights", None)
    can_read = bool(getattr(rights, "can_read_messages", getattr(conn, "can_read_messages", False)))
    can_delete = bool(getattr(rights, "can_delete_all_messages", False))

    lines = ["🔌 Business connection " + ("enabled." if conn.is_enabled else "paused.")]
    lines.append(f"Read messages: {'✅' if can_read else '❌ missing'}")
    lines.append(f"Delete messages: {'✅' if can_delete else '❌ missing'}")
    if not (can_read and can_delete):
        lines.append(
            "\nI need both permissions to work — check "
            "Settings → Telegram Business → Chatbots."
        )
    try:
        await bot.send_message(owner_id, "\n".join(lines))
    except TelegramBadRequest:
        pass  # user has never started the bot


# ---------------------------------------------------------------------------
# Incoming business messages
# ---------------------------------------------------------------------------


@router.business_message()
async def on_business_message(message: Message, bot: Bot):
    cfg = await db.get_by_connection(message.business_connection_id)
    if not cfg or not cfg["connection_enabled"]:
        return

    owner_id = cfg["user_id"]
    sender = message.from_user
    if sender is None or sender.id == owner_id:
        return  # outgoing message from the account owner

    await db.remember_sender(owner_id, sender.id, display_name(sender))
    if await db.is_whitelisted(owner_id, sender.id):
        return

    mode = cfg["mode"]
    if mode == "ignore":
        return

    if mode == "forward_delete":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Add to whitelist",
                        callback_data=f"wl_add:{owner_id}:{sender.id}",
                    )
                ]
            ]
        )
        try:
            await bot.send_message(
                owner_id,
                format_forward(sender, message),
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=kb,
            )
        except TelegramBadRequest as e:
            # Owner hasn't started the bot (or blocked it) — can't deliver.
            logging.warning("Forward to owner %s failed: %s", owner_id, e)
            return  # keep the original message if forwarding failed

    # mode == "delete", or forward succeeded → delete the original
    await delete_business_message(bot, message.business_connection_id, message.message_id)


# ---------------------------------------------------------------------------
# Whitelist button on forwarded messages
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith("wl_add:"))
async def cb_whitelist_add(call: CallbackQuery):
    _, owner_id, sender_id = call.data.split(":")
    if call.from_user.id != int(owner_id):
        await call.answer(
            "Only the account owner can manage the whitelist.", show_alert=True
        )
        return
    owner_id, sender_id = int(owner_id), int(sender_id)
    name = await db.get_sender_name(owner_id, sender_id) or str(sender_id)
    await db.add_to_whitelist(owner_id, sender_id, name)
    await call.answer(f"✅ {name} added to your whitelist.")
    await call.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Whitelisted", callback_data="wl_noop")]
            ]
        )
    )


@router.callback_query(F.data == "wl_noop")
async def cb_noop(call: CallbackQuery):
    await call.answer("This sender is already whitelisted.")


# ---------------------------------------------------------------------------


async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init()
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "callback_query",
            "business_connection",
            "business_message",
        ],
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
