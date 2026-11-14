"""Admin klaviaturalari"""
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List
from database.models import Channel, Category, Movie


def admin_main_kb() -> ReplyKeyboardMarkup:
    """Admin asosiy menyu"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="📢 Reklama")
            ],
            [
                KeyboardButton(text="🎬 Kinolar"),
                KeyboardButton(text="📁 Kategoriyalar")
            ],
            [
                KeyboardButton(text="📺 Kanallar"),
                KeyboardButton(text="👤 User rejim")
            ],
            [
                KeyboardButton(text="📢 Kanalga post yaratish"),
                KeyboardButton(text="📋 Kino so'rovlari")  # 👈 Mana bu yerga qo'shildi
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Admin panelidan tanlang..."
    )
    return keyboard


def movies_manage_kb() -> InlineKeyboardMarkup:
    """Kinolar boshqaruvi"""
    builder = InlineKeyboardBuilder()

    builder.button(text="➕ Kino qo'shish", callback_data="admin_add_movie")
    builder.button(text="🗑 Kino o'chirish", callback_data="admin_delete_movie")
    builder.button(text="📋 Barcha kinolar", callback_data="admin_list_movies")
    builder.button(text="🔝 Top kinolar", callback_data="admin_top_movies")
    builder.button(text="◀️ Orqaga", callback_data="admin_main")

    builder.adjust(2, 2, 1)
    return builder.as_markup()


def categories_manage_kb() -> InlineKeyboardMarkup:
    """Kategoriyalar boshqaruvi"""
    builder = InlineKeyboardBuilder()

    builder.button(text="➕ Qo'shish", callback_data="admin_add_category")
    builder.button(text="📋 Ro'yxat", callback_data="admin_list_categories")
    builder.button(text="◀️ Orqaga", callback_data="admin_main")

    builder.adjust(2, 1)
    return builder.as_markup()


def channels_manage_kb() -> InlineKeyboardMarkup:
    """Kanallar boshqaruvi"""
    builder = InlineKeyboardBuilder()

    builder.button(text="➕ Kanal qo'shish", callback_data="admin_add_channel")
    builder.button(text="📋 Barcha kanallar", callback_data="admin_list_channels")
    builder.button(text="🗑 Kanal o'chirish", callback_data="admin_delete_channel")
    builder.button(text="◀️ Orqaga", callback_data="admin_main")

    builder.adjust(2, 2)
    return builder.as_markup()


def select_category_kb(categories: List[Category]) -> InlineKeyboardMarkup:
    """Kategoriya tanlash"""
    builder = InlineKeyboardBuilder()

    for cat in categories:
        builder.button(
            text=f"📁 {cat.name}",
            callback_data=f"select_cat_{cat.id}"
        )

    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")
    )

    return builder.as_markup()


def channels_list_kb(channels: List[Channel]) -> InlineKeyboardMarkup:
    """Kanallar ro'yxati (o'chirish uchun)"""
    builder = InlineKeyboardBuilder()

    for channel in channels:
        status = "✅" if channel.is_active else "❌"
        builder.button(
            text=f"{status} {channel.channel_title}",
            callback_data=f"delete_ch_{channel.channel_id}"
        )

    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_channels")
    )

    return builder.as_markup()


def confirm_kb(action: str) -> InlineKeyboardMarkup:
    """Tasdiqlash klaviaturasi"""
    builder = InlineKeyboardBuilder()

    builder.button(text="✅ Ha", callback_data=f"confirm_{action}")
    builder.button(text="❌ Yo'q", callback_data=f"cancel_{action}")

    builder.adjust(2)
    return builder.as_markup()


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    """Broadcast tasdiqlash"""
    builder = InlineKeyboardBuilder()

    builder.button(text="✅ Yuborish", callback_data="broadcast_send")
    builder.button(text="❌ Bekor qilish", callback_data="broadcast_cancel")

    builder.adjust(2)
    return builder.as_markup()


def cancel_kb() -> ReplyKeyboardMarkup:
    """Bekor qilish tugmasi"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )
    return keyboard


def skip_kb() -> ReplyKeyboardMarkup:
    """O'tkazib yuborish"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ O'tkazib yuborish")],
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True
    )
    return keyboard


def select_channel_type_kb() -> InlineKeyboardMarkup:
    """Kanal turi tanlash"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="📢 Public Kanal",
        callback_data="channel_type_public"
    )
    builder.button(
        text="🔒 Private Kanal",
        callback_data="channel_type_private"
    )
    builder.button(
        text="❌ Bekor qilish",
        callback_data="admin_cancel"
    )

    builder.adjust(2, 1)
    return builder.as_markup()


def select_movie_for_post_kb(categories, page: int = 0):
    """Kanalga post qilish uchun kategoriyalar/animelar ro'yxati"""
    builder = InlineKeyboardBuilder()

    start = page * 8
    end = start + 8
    current_categories = categories[start:end]

    for category in current_categories:
        builder.button(
            text=f"📂 {category.name}",
            callback_data=f"post_movie_{category.id}"
        )

    builder.adjust(1)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"post_movie_page_{page - 1}"))
    if end < len(categories):
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"post_movie_page_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_post"))
    return builder.as_markup()


def movie_post_inline_kb(bot_username: str, movie_code: int):
    """Kanalga tushadigan post ostidagi 'Tomosha Qilish' tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✨ Tomosha Qilish ✨",
        url=f"https://t.me/{bot_username}?start={movie_code}"
    )
    return builder.as_markup()


def admin_requests_list_kb(top_requests):
    """Har bir so'ralgan kino uchun alohida bajarildi tugmasini yaratish"""
    builder = InlineKeyboardBuilder()

    for query, count in top_requests:
        # Callback uzunligi oshib ketmasligi uchun qisqartiramiz
        safe_q = query[:30]
        builder.button(
            text=f"✅ {query} ({count} ta)",
            callback_data=f"req_done_{safe_q}"
        )

    builder.button(text="◀️ Orqaga", callback_data="admin_main")
    builder.adjust(1)  # Har bir qatorda bittadan chiroyli chiqadi
    return builder.as_markup()