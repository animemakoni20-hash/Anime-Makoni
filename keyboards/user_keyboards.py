"""Foydalanuvchi klaviaturalari"""
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional
from database.models import Category, Channel, Movie


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Asosiy menyu"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎬 Kategoriyalar"),
                KeyboardButton(text="🔍 Nomi bo'yicha qidirish"),
                KeyboardButton(text="🔍 Kod orqali")
            ],
            [
                KeyboardButton(text="ℹ️ Yordam")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyudan tanlang..."
    )
    return keyboard


def categories_kb(
    categories: List[Category],
    parent_id: Optional[int] = None,
    page: int = 1,
    total_pages: int = 1
) -> InlineKeyboardMarkup:
    """Istalgan darajadagi Kategoriyalar/Ost-kategoriyalar klaviaturasi (Paginatsiya bilan)"""
    builder = InlineKeyboardBuilder()

    for category in categories:
        builder.button(
            text=f"📁 {category.name}",
            callback_data=f"category_{category.id}"
        )

    builder.adjust(2)  # 2 tadan qatorda

    # 10 tadan ko'p bo'lsa Paginatsiya (Keyingi/Oldingi) tugmalari
    nav_buttons = []
    cb_prefix = f"subcatpage_{parent_id}" if parent_id else "maincatpage"

    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"{cb_prefix}_{page-1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{cb_prefix}_{page+1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    # Ortga qaytish tugmalari
    if parent_id is not None:
        builder.row(
            InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"back_to_parent_{parent_id}"),
            InlineKeyboardButton(text="🏠 Bosh kategoriyalar", callback_data="back_to_categories")
        )

    return builder.as_markup()


def movies_list_kb(
    movies: List[Movie],
    category_id: int,
    page: int = 1,
    total_pages: int = 1,
    parent_id: Optional[int] = None
) -> InlineKeyboardMarkup:
    """Kinolar ro'yxati (Paginatsiya bilan)"""
    builder = InlineKeyboardBuilder()

    for movie in movies:
        quality_lang = ""
        if hasattr(movie, 'quality') and movie.quality:
            quality_lang += f" [{movie.quality}]"
        if hasattr(movie, 'language') and movie.language:
            quality_lang += f" {movie.language}"

        title = getattr(movie, 'title', getattr(movie, 'name', 'Kino'))
        builder.button(
            text=f"🎬 {title}{quality_lang}",
            callback_data=f"movie_{movie.id}"
        )

    builder.adjust(1)  # Har qatorda 1 ta kino

    # Kinolar uchun Paginatsiya
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"catpage_{category_id}_{page-1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"catpage_{category_id}_{page+1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    # Ortga tugmasi
    builder.row(
        InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"category_{category_id}"),
        InlineKeyboardButton(text="🏠 Bosh kategoriyalar", callback_data="back_to_categories")
    )

    return builder.as_markup()


def movie_detail_kb(movie_id: int, category_id: int) -> InlineKeyboardMarkup:
    """Kino ko'rilayotganda ortga qaytish"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="⬅️ Ortga (Ro'yxatga)", callback_data=f"category_{category_id}"),
        InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")
    )

    return builder.as_markup()


def subscription_kb(channels: List[Channel]) -> InlineKeyboardMarkup:
    """Obuna tekshirish klaviaturasi"""
    builder = InlineKeyboardBuilder()

    for channel in channels:
        if channel.channel_type == "public":
            button_text = f"📢 {channel.channel_title}"
            channel_url = f"https://t.me/{channel.channel_username}"
        elif channel.channel_type == "private":
            button_text = f"🔒 {channel.channel_title}"
            channel_url = channel.invite_link
        else:
            button_text = f"✅ {channel.channel_title}"
            channel_url = channel.invite_link if channel.invite_link else f"https://t.me/{channel.channel_username}"

        builder.button(text=button_text, url=channel_url)

    builder.adjust(1)

    builder.row(
        InlineKeyboardButton(text="♻️ Obunani Tekshirish", callback_data="check_subscription")
    )

    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    """Menyuga qaytish"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Bosh menyu", callback_data="main_menu")
    return builder.as_markup()


# =====================================================================
# 1-BOSQICH: AQLLI QIDIRUV VA KINO SO'RASH KLAVIATURALARI
# =====================================================================

def search_results_kb(movies: List[Movie], search_query: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Aqlli qidiruv natijalari uchun paginatsiyali klaviatura"""
    builder = InlineKeyboardBuilder()

    for movie in movies:
        quality_lang = f" [{movie.quality}]" if movie.quality else ""
        builder.button(
            text=f"🎬 {movie.title}{quality_lang}",
            callback_data=f"movie_{movie.id}"
        )

    builder.adjust(1)

    # Paginatsiya tugmalari
    nav_buttons = []
    # Qidiruv so'zini callback ichida sig'ishi uchun qisqartirib olamiz
    safe_query = search_query[:20]

    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"ssearch_{safe_query}_{page-1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"ssearch_{safe_query}_{page+1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"))
    return builder.as_markup()


def missing_movie_kb(search_query: str) -> InlineKeyboardMarkup:
    """Kino topilmaganda chiqadigan 'Kino so'rash' klaviaturasi"""
    builder = InlineKeyboardBuilder()
    safe_query = search_query[:30]

    builder.button(text="➕ Kino qo'shilishini so'rash", callback_data=f"req_movie_{safe_query}")
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"))

    return builder.as_markup()

