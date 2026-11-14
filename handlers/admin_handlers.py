"""Admin handlerlari"""
import re
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramAPIError, TelegramForbiddenError
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import database as db
from states.admin_states import EditCategoryStates

import config
from database.database import (
    add_movie,
    add_category,
    add_channel,
    get_all_categories,
    get_all_channels,
    delete_channel,
    delete_movie_by_code,
    get_all_movies,
    get_top_movies,
    get_all_users,
    get_main_categories,
    update_category_parent,
    delete_category_by_id,
    update_category_name,
    get_all_movies_by_category,
    complete_movie_request,
    get_category_by_id,
    get_total_movies,
    get_total_views,
    get_total_users,
    get_new_users_today,
    get_new_users_last_7_days,
    get_new_users_last_30_days,
    get_active_users_today,
    get_movie_views_today
)

from keyboards.admin_keyboards import (
    admin_main_kb,
    movies_manage_kb,
    categories_manage_kb,
    channels_manage_kb,
    select_category_kb,
    channels_list_kb,
    broadcast_confirm_kb,
    cancel_kb,
    skip_kb,
    confirm_kb, admin_requests_list_kb
)
from keyboards.user_keyboards import main_menu_kb
from utils.statistics import get_admin_statistics
from utils.broadcast import send_broadcast
from states.admin_states import (
    AddMovieStates,
    AddCategoryStates,
    AddChannelStates,
    BroadcastStates,
    DeleteMovieStates
)

router = Router(name="admin_router")

def is_admin(user_id: int) -> bool:
    """Admin ekanligini tekshirish"""
    return user_id in config.ADMIN_IDS


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Admin panel"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Sizda admin huquqi yo'q!")
        return

    text = (
        "👨‍💼 <b>Admin Panel</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )

    await message.answer(
        text,
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )


@router.message(F.text == "👤 User rejim")
async def back_to_user(message: Message):
    """User rejimiga qaytish"""
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "👤 Foydalanuvchi rejimiga o'tdingiz",
        reply_markup=main_menu_kb()
    )

# ==================== STATISTIKA ====================

@router.message(
    F.text.contains("Statistika"),
    F.from_user.id.in_(config.ADMIN_IDS)
)
async def admin_stat_handler(message: Message):
    total_users = await get_total_users()
    total_movies = await get_total_movies()
    total_views = await get_total_views()

    new_today = await get_new_users_today()
    new_7_days = await get_new_users_last_7_days()
    new_30_days = await get_new_users_last_30_days()

    active_today = await get_active_users_today()
    views_today = await get_movie_views_today()

    top_movies = await get_top_movies()

    top_text = ""
    for index, movie in enumerate(top_movies, start=1):
        top_text += (
            f"{index}. {movie.title} — "
            f"👁 {movie.views_count} ta\n"
        )

    if not top_text:
        top_text = "Hozircha top kinolar yo'q.\n"

    text = (
        f"📊 <b>Bot Statistikasi (Admin):</b>\n\n"

        f"👥 <b>Foydalanuvchilar:</b>\n"
        f"├ Jami: <b>{total_users} ta</b>\n"
        f"├ Bugun yangi: <b>{new_today} ta</b>\n"
        f"├ Oxirgi 7 kun: <b>{new_7_days} ta</b>\n"
        f"└ Oxirgi 30 kun: <b>{new_30_days} ta</b>\n\n"

        f"🟢 Bugun faol: <b>{active_today} ta</b>\n\n"

        f"🎬 Kinolar soni: <b>{total_movies} ta</b>\n"
        f"👁 Jami ko'rishlar: <b>{total_views} ta</b>\n"
        f"📅 Bugungi ko'rishlar: <b>{views_today} ta</b>\n\n"

        f"🔥 <b>Top 3 kino:</b>\n"
        f"{top_text}"
    )

    await message.answer(text, parse_mode="HTML")

# ==================== KINOLAR BOSHQARUVI ====================

@router.message(F.text == "🎬 Kinolar")
async def movies_menu(message: Message):
    """Kinolar menyusi"""
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "🎬 <b>Kinolar boshqaruvi</b>\n\n"
        "Kerakli amaliyotni tanlang:",
        reply_markup=movies_manage_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_add_movie")
async def add_movie_start(callback: CallbackQuery, state: FSMContext):
    """Kino qo'shish boshlash"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "🎬 <b>Yangi kino qo'shish</b>\n\n"
        "1️⃣ Kino uchun <b>kod</b> kiriting (faqat raqam):\n\n"
        "Masalan: <code>105</code>\n\n"
        "❌ Bekor qilish: /cancel",
        parse_mode="HTML"
    )

    await state.set_state(AddMovieStates.waiting_code)
    await callback.answer()


@router.message(StateFilter(AddMovieStates.waiting_code))
async def add_movie_code(message: Message, state: FSMContext):
    """Kino kodi"""
    if message.text == "/cancel" or message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Bekor qilindi",
            reply_markup=admin_main_kb()
        )
        return

    if not message.text.isdigit():
        await message.answer(
            "❌ Iltimos faqat raqam kiriting!\n\n"
            "Masalan: <code>105</code>",
            parse_mode="HTML"
        )
        return

    code = int(message.text)
    await state.update_data(code=code)

    await message.answer(
        "2️⃣ Kino <b>nomini</b> kiriting:\n\n"
        "Masalan: <code>Titanik</code>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )

    await state.set_state(AddMovieStates.waiting_title)


@router.message(StateFilter(AddMovieStates.waiting_title))
async def add_movie_title(message: Message, state: FSMContext):
    """Kino nomi"""
    if message.text == "/cancel" or message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return

    await state.update_data(title=message.text)

    # Kategoriyalarni olish
    categories = await get_all_categories()

    if not categories:
        await message.answer(
            "❌ Avval kategoriya qo'shishingiz kerak!\n\n"
            "/admin",
            reply_markup=admin_main_kb()
        )
        await state.clear()
        return

    await message.answer(
        "3️⃣ <b>Kategoriya</b> tanlang:",
        reply_markup=select_category_kb(categories),
        parse_mode="HTML"
    )

    await state.set_state(AddMovieStates.waiting_category)


@router.callback_query(StateFilter(AddMovieStates.waiting_category), F.data.startswith("select_cat_"))
async def add_movie_category(callback: CallbackQuery, state: FSMContext):
    """Kategoriya tanlash"""
    category_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=category_id)

    await callback.message.edit_text(
        "4️⃣ Kino <b>faylini</b> yuboring (video):",
        parse_mode="HTML"
    )

    await state.set_state(AddMovieStates.waiting_file)
    await callback.answer()


@router.message(StateFilter(AddMovieStates.waiting_file), F.video)
async def add_movie_file(message: Message, state: FSMContext):
    """Video fayl"""
    file_id = message.video.file_id
    await state.update_data(file_id=file_id)

    await message.answer(
        "5️⃣ Kino <b>sifati</b>ni kiriting:\n\n"
        "Masalan: <code>720p</code> yoki <code>1080p</code>\n\n"
        "⏭ O'tkazib yuborish mumkin",
        reply_markup=skip_kb(),
        parse_mode="HTML"
    )

    await state.set_state(AddMovieStates.waiting_quality)


@router.message(StateFilter(AddMovieStates.waiting_quality))
async def add_movie_quality(message: Message, state: FSMContext):
    """Sifat"""
    if message.text == "⏭ O'tkazib yuborish":
        quality = None
    elif message.text == "❌ Bekor qilish" or message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return
    else:
        quality = message.text

    await state.update_data(quality=quality)

    await message.answer(
        "6️⃣ Kino <b>tilini</b> kiriting:\n\n"
        "Masalan: <code>O'zbek</code>, <code>Rus</code>\n\n"
        "⏭ O'tkazib yuborish mumkin",
        reply_markup=skip_kb(),
        parse_mode="HTML"
    )

    await state.set_state(AddMovieStates.waiting_language)


@router.message(StateFilter(AddMovieStates.waiting_language))
async def add_movie_language(message: Message, state: FSMContext):
    """Til"""
    if message.text == "⏭ O'tkazib yuborish":
        language = None
    elif message.text == "❌ Bekor qilish" or message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return
    else:
        language = message.text

    await state.update_data(language=language)

    await message.answer(
        "7️⃣ Kino <b>yilini</b> kiriting:\n\n"
        "Masalan: <code>2020</code>\n\n"
        "⏭ O'tkazib yuborish mumkin",
        reply_markup=skip_kb(),
        parse_mode="HTML"
    )

    await state.set_state(AddMovieStates.waiting_year)


@router.message(StateFilter(AddMovieStates.waiting_year))
async def add_movie_year(message: Message, state: FSMContext):
    """Yil"""
    year = None

    if message.text == "⏭ O'tkazib yuborish":
        year = None
    elif message.text == "❌ Bekor qilish" or message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return
    elif message.text.isdigit():
        year = int(message.text)

    await state.update_data(year=year)

    await message.answer(
        "8️⃣ Kino <b>tavsifi</b>ni kiriting:\n\n"
        "⏭ O'tkazib yuborish mumkin",
        reply_markup=skip_kb(),
        parse_mode="HTML"
    )

    await state.set_state(AddMovieStates.waiting_description)


@router.message(StateFilter(AddMovieStates.waiting_description))
async def add_movie_description(message: Message, state: FSMContext):
    """Tavsif va saqlash"""
    if message.text == "⏭ O'tkazib yuborish":
        description = None
    elif message.text == "❌ Bekor qilish" or message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return
    else:
        description = message.text

    # Ma'lumotlarni olish
    data = await state.get_data()

    try:
        # Kinoni saqlash
        movie = await add_movie(
            code=data['code'],
            title=data['title'],
            file_id=data['file_id'],
            category_id=data['category_id'],
            description=description,
            quality=data.get('quality'),
            language=data.get('language'),
            year=data.get('year')
        )

        await message.answer(
            f"✅ Kino muvaffaqiyatli qo'shildi!\n\n"
            f"🎬 <b>{movie.title}</b>\n"
            f"🔢 Kod: <b>#{movie.code}</b>",
            reply_markup=admin_main_kb(),
            parse_mode="HTML"
        )

    except ValueError as e:
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=admin_main_kb()
        )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik yuz berdi: {str(e)}",
            reply_markup=admin_main_kb()
        )

    await state.clear()


@router.callback_query(F.data == "admin_delete_movie")
async def delete_movie_start(callback: CallbackQuery, state: FSMContext):
    """Kino o'chirish"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "🗑 <b>Kino o'chirish</b>\n\n"
        "O'chirmoqchi bo'lgan kino <b>kodini</b> kiriting:\n\n"
        "Masalan: <code>105</code>\n\n"
        "❌ Bekor qilish: /cancel",
        parse_mode="HTML"
    )

    await state.set_state(DeleteMovieStates.waiting_code)
    await callback.answer()


@router.message(StateFilter(DeleteMovieStates.waiting_code))
async def delete_movie_code(message: Message, state: FSMContext):
    """Kino kodini olish va o'chirish"""
    if message.text == "/cancel" or message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return

    # Agar foydalanuvchi matn o'rniga video yoki boshqa media yuborsa
    if not message.text or not message.text.isdigit():
        await message.answer("❌ Faqat raqam kiriting (masalan: 1)!")
        return

    code = int(message.text)

    try:
        # Funksiyadan True yoki False natija olamiz
        deleted = await delete_movie_by_code(code)

        if deleted:
            await message.answer(
                f"✅ #{code} kodli kino muvaffaqiyatli o'chirildi!",
                reply_markup=admin_main_kb()
            )
        else:
            await message.answer(
                f"❌ #{code} kodli kino bazadan topilmadi! Kodni to'g'ri kiritganingizni tekshiring.",
                reply_markup=admin_main_kb()
            )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik yuz berdi: {str(e)}",
            reply_markup=admin_main_kb()
        )

    await state.clear()

@router.callback_query(F.data == "admin_list_movies")
async def list_all_movies_redirect(callback: CallbackQuery):
    """Kinolar tugmasi bosilganda 0-sahifani ochish"""
    if not is_admin(callback.from_user.id):
        return
    await show_movies_page(callback, page=0)


@router.callback_query(F.data.startswith("movies_page_"))
async def list_movies_pagination(callback: CallbackQuery):
    """Kinolar sahifasini almashtirish"""
    if not is_admin(callback.from_user.id):
        return
    page = int(callback.data.split("_")[2])
    await show_movies_page(callback, page=page)


async def show_movies_page(callback: CallbackQuery, page: int):
    PER_PAGE = 20
    movies = await get_all_movies(limit=10000)

    if not movies:
        await callback.answer("❌ Kinolar mavjud emas!", show_alert=True)
        return

    total_movies = len(movies)
    total_pages = (total_movies + PER_PAGE - 1) // PER_PAGE

    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1

    start_idx = page * PER_PAGE
    end_idx = start_idx + PER_PAGE
    current_movies = movies[start_idx:end_idx]

    text = f"📋 <b>Barcha kinolar ro'yxati</b> (Sahifa: {page + 1}/{total_pages}, Jami: {total_movies} ta):\n\n"
    for movie in current_movies:
        text += f"🔹 <code>#{movie.code}</code> — <b>{movie.title}</b>\n"

    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"movies_page_{page - 1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="ignore_page"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Keyingisi ➡️", callback_data=f"movies_page_{page + 1}"))

    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="🏠 Admin Menyu", callback_data="admin_main"))

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()




@router.callback_query(F.data == "admin_top_movies")
async def list_top_movies(callback: CallbackQuery):
    """Top kinolar"""
    if not is_admin(callback.from_user.id):
        return

    movies = await get_top_movies(limit=20)

    if not movies:
        await callback.answer("❌ Kinolar mavjud emas!", show_alert=True)
        return

    text = "🔝 <b>Top 20 Kinolar</b>\n\n"

    for idx, movie in enumerate(movies, 1):
        text += f"{idx}. <b>{movie.title}</b>\n"
        text += f"   └ #{movie.code} | 👁 {movie.views_count}\n\n"

    await callback.message.edit_text(
        text,
        parse_mode="HTML"
    )

    await callback.message.answer(
        "Admin panel:",
        reply_markup=admin_main_kb()
    )
    await callback.answer()

# ==================== KATEGORIYALAR ====================
# --- 1. KATEGORIYALAR RO'YXATI VA BO'LIMGA BIRIKTIRISH (TUSHIRISH) ---
# --- KATEGORIYALARNI SAHIFALAB CHIQARISH VA BOSHQARISH ---

@router.callback_query(F.data == "admin_list_categories")
async def list_categories_redirect(callback: CallbackQuery):
    """Kategoriyalar tugmasi bosilganda bosh kategoriyalar 0-sahifasini ochish"""
    if not is_admin(callback.from_user.id):
        return
    await show_categories_page(callback, page=0)


@router.callback_query(F.data.startswith("cats_page_"))
async def list_categories_pagination(callback: CallbackQuery):
    """Bosh kategoriyalar sahifasini almashtirish"""
    if not is_admin(callback.from_user.id):
        return
    page = int(callback.data.split("_")[2])
    await show_categories_page(callback, page=page)


async def show_categories_page(callback: CallbackQuery, page: int):
    PER_PAGE = 10

    # FAQAT Asosiy (parent_id == None) kategoriyalarni olamiz
    categories = await get_main_categories()

    if not categories:
        await callback.answer("❌ Asosiy kategoriyalar mavjud emas!", show_alert=True)
        return

    # Takrorlanish oldini olish (o'zingiz qo'shgan mantiq)
    seen_names = set()
    unique_categories = []
    for cat in categories:
        clean_name = cat.name.strip().lower()
        if clean_name not in seen_names:
            seen_names.add(clean_name)
            unique_categories.append(cat)
    categories = unique_categories

    total_cats = len(categories)
    total_pages = (total_cats + PER_PAGE - 1) // PER_PAGE

    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1

    start_idx = page * PER_PAGE
    end_idx = start_idx + PER_PAGE
    current_cats = categories[start_idx:end_idx]

    # Matndagi ortiqcha kino/kategoriya yozuvlari olib tashlandi, lekin sarlavha o'z holicha saqlandi
    text = (
        f"📁 <b>Asosiy kategoriyalar</b> (Sahifa: {page + 1}/{total_pages}, Jami: {total_cats} ta):\n"
        f"<i>(Ichidagi kategoriyalarni ko'rish uchun kategoriya ustiga bosing)</i>\n"
    )

    builder = InlineKeyboardBuilder()

    # HAR BIR KATEGORIYA UCHUN TUGMALAR (Faqat 10 tasi chiqadi)
    for cat in current_cats:
        # 1-qator: User menyusi bilan konflikt bo'lmasligi uchun 'adm_cat_' qilindi
        builder.row(
            InlineKeyboardButton(text=f"📂 {cat.name}", callback_data=f"adm_cat_{cat.id}_0")
        )
        # 2-qator: Ixcham amallar tugmalari (Nomini tahrirlash, Ko'chirish, O'chirish)
        builder.row(
            InlineKeyboardButton(text="✏️ Nom", callback_data=f"edit_cat_{cat.id}"),
            InlineKeyboardButton(text="📁 Ko'chirish", callback_data=f"move_cat_{cat.id}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_cat_{cat.id}")
        )

    # SAHIFALASH TUGMALARI
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"cats_page_{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="ignore_page"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Keyingisi ➡️", callback_data=f"cats_page_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🏠 Admin Menyu", callback_data="admin_main"))

    try:
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


# --- KATEGORIYA ICHIGA KIRIB KORISH HANDLERI (SUBKATEGORIYALAR UCHUN 10 TALIK PAGINATION BILAN) ---
@router.callback_query(F.data.startswith("adm_cat_"))
async def view_category_content(callback: CallbackQuery):
    """Tanlangan kategoriya ichidagi subkategoriyalarni ko'rsatish"""
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.split("_")
    cat_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    PER_PAGE = 10

    # Barcha kategoriyalarni olib, shu parent_id ga tegishlilarini va joriy kategoriyani ajratamiz
    all_categories = await get_all_categories()
    current_cat = next((c for c in all_categories if c.id == cat_id), None)
    subcategories = [c for c in all_categories if c.parent_id == cat_id]

    if not current_cat:
        await callback.answer("❌ Kategoriya topilmadi!", show_alert=True)
        return

    total_subs = len(subcategories)
    total_pages = (total_subs + PER_PAGE - 1) // PER_PAGE if total_subs > 0 else 1

    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1

    start_idx = page * PER_PAGE
    end_idx = start_idx + PER_PAGE
    current_subs = subcategories[start_idx:end_idx]

    text = f"📂 <b>{current_cat.name}</b> ichidagi bo'limlar (Sahifa: {page + 1}/{total_pages}, Jami: {total_subs} ta):\n\n"

    builder = InlineKeyboardBuilder()

    if current_subs:
        for sub in current_subs:
            # Subkategoriya uchun alohida nom va ixcham amallar
            builder.row(
                InlineKeyboardButton(text=f"🔹 {sub.name}", callback_data=f"adm_cat_{sub.id}_0")
            )
            builder.row(
                InlineKeyboardButton(text="✏️ Nom", callback_data=f"edit_cat_{sub.id}"),
                InlineKeyboardButton(text="📁 Biriktirish / Ajratish", callback_data=f"move_cat_{sub.id}"),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_cat_{sub.id}")
            )
    else:
        text += "<i>Ushbu kategoriya ichida hozircha subkategoriyalar yo'q.</i>\n"

    # SUBKATEGORIYALAR SAHIFALASH TUGMALARI
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"adm_cat_{cat_id}_{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="ignore_page"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Keyingisi ➡️", callback_data=f"adm_cat_{cat_id}_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="⬅️ Ortga (Asosiy kategoriyalar)", callback_data="admin_list_categories")
    )

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


# --- 1.1 TAYYOR KATEGORIYANI BOSH KATEGORIYA ICHIGA KO'CHIRISH ---
@router.callback_query(F.data.startswith("move_cat_"))
async def move_category_start(callback: CallbackQuery):
    """Mavjud kategoriyani boshqa kategoriyaga biriktirish menyusi"""
    if not is_admin(callback.from_user.id):
        return

    cat_id = int(callback.data.split("_")[2])
    main_categories = await get_main_categories()  # Bazadagi asosiy kategoriyalar

    builder = InlineKeyboardBuilder()

    # Asosiy (mustaqil) kategoriya qilish tugmasi
    builder.button(
        text="🔝 Asosiy Kategoriya (Bosh bo'lim) qilish",
        callback_data=f"setparent_exist_{cat_id}_none"
    )

    # Boshqa kategoriyalar ichiga kirgizish
    if main_categories:
        for m_cat in main_categories:
            if m_cat.id != cat_id:  # O'zining ichiga o'zini joylamaslik uchun
                builder.button(
                    text=f"📁 {m_cat.name} bo'limiga biriktirish",
                    callback_data=f"setparent_exist_{cat_id}_{m_cat.id}"
                )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_list_categories"))

    await callback.message.edit_text(
        "📂 <b>Ushbu kategoriyani qaysi bo'lim ichiga ko'chirmoqchisiz?</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setparent_exist_"))
async def move_category_finish(callback: CallbackQuery):
    """Bazada parent_id ni yangilash va ko'chirishni yakunlash"""
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.split("_")
    cat_id = int(parts[2])
    parent_raw = parts[3]
    parent_id = None if parent_raw == "none" else int(parent_raw)

    # Bazada shu kategoriyaning parent_id sini yangilaymiz
    success = await update_category_parent(cat_id, parent_id)

    if success:
        await callback.answer("✅ Kategoriya muvaffaqiyatli ko'chirildi!", show_alert=True)
        await show_categories_page(callback, page=0)
    else:
        await callback.answer("❌ Ko'chirishda xatolik yuz berdi!", show_alert=True)


# --- 2. KATEGORIYANI O'CHIRISH ---
@router.callback_query(F.data.startswith("del_cat_"))
async def delete_category_handler(callback: CallbackQuery):
    """Kategoriyani o'chirish"""
    if not is_admin(callback.from_user.id):
        return

    cat_id = int(callback.data.split("_")[2])

    success = await delete_category_by_id(cat_id)

    if success:
        await callback.answer("✅ Kategoriya o'chirildi!", show_alert=True)
        await show_categories_page(callback, page=0)
    else:
        await callback.answer("❌ Kategoriya topilmadi!", show_alert=True)


# --- 3. KATEGORIYA NOMINI TAHRIRLASH ---
@router.callback_query(F.data.startswith("edit_cat_"))
async def edit_category_start(callback: CallbackQuery, state: FSMContext):
    """Kategoriya nomini tahrirlashni boshlash"""
    if not is_admin(callback.from_user.id):
        return

    cat_id = int(callback.data.split("_")[2])
    await state.update_data(edit_cat_id=cat_id)

    await callback.message.edit_text(
        "✏️ <b>Kategoriyaning yangi nomini kiriting:</b>\n\n"
        "❌ Bekor qilish: /cancel",
        parse_mode="HTML"
    )
    await state.set_state(EditCategoryStates.waiting_new_name)


@router.message(StateFilter(EditCategoryStates.waiting_new_name))
async def edit_category_name_save(message: Message, state: FSMContext):
    """Yangi nomni saqlash"""
    if message.text in ["/cancel", "❌ Bekor qilish"]:
        await state.clear()
        await message.answer("❌ Tahrirlash bekor qilindi", reply_markup=admin_main_kb())
        return

    data = await state.get_data()
    cat_id = data.get("edit_cat_id")
    new_name = message.text

    success = await update_category_name(cat_id, new_name)

    if success:
        await message.answer(
            f"✅ Kategoriya nomi <b>{new_name}</b> ga o'zgartirildi!",
            reply_markup=admin_main_kb(),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Xatolik yuz berdi!", reply_markup=admin_main_kb())

    await state.clear()


# --- 4. KATEGORIYALAR MENYUSI ---
@router.message(F.text == "📁 Kategoriyalar")
async def categories_menu(message: Message):
    """Kategoriyalar menyusi"""
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "📁 <b>Kategoriyalar boshqaruvi</b>\n\n"
        "Kerakli amaliyotni tanlang:",
        reply_markup=categories_manage_kb(),
        parse_mode="HTML"
    )


# --- 5. YANGI KATEGORIYA QO'SHISH ---
@router.callback_query(F.data == "admin_add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    """Kategoriya qo'shishni boshlash"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "📁 <b>Yangi kategoriya</b>\n\n"
        "1️⃣ Kategoriya <b>nomini</b> kiriting:\n\n"
        "Masalan: <code>Anime</code> yoki <code>Masamune Qasosi</code>\n\n"
        "❌ Bekor qilish: /cancel",
        parse_mode="HTML"
    )

    await state.set_state(AddCategoryStates.waiting_name)
    await callback.answer()


@router.message(StateFilter(AddCategoryStates.waiting_name))
async def add_category_name(message: Message, state: FSMContext):
    """Kategoriya nomini olish"""
    if message.text in ["/cancel", "❌ Bekor qilish"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return

    await state.update_data(name=message.text)

    await message.answer(
        "2️⃣ Kategoriya <b>tavsifi</b>ni kiriting:\n\n"
        "⏭ O'tkazib yuborish mumkin",
        reply_markup=skip_kb(),
        parse_mode="HTML"
    )

    await state.set_state(AddCategoryStates.waiting_description)


@router.message(StateFilter(AddCategoryStates.waiting_description))
async def add_category_description(message: Message, state: FSMContext):
    """Kategoriya tavsifini olish va Bo'lim tanlashni so'rash"""
    if message.text in ["❌ Bekor qilish", "/cancel"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return

    description = None if message.text == "⏭ O'tkazib yuborish" else message.text
    await state.update_data(description=description)

    main_categories = await get_main_categories()

    builder = InlineKeyboardBuilder()

    builder.button(
        text="➕ Asosiy Kategoriya (Bosh bo'lim)",
        callback_data="setparent_none"
    )

    if main_categories:
        for m_cat in main_categories:
            builder.button(
                text=f"📁 {m_cat.name} bo'limiga",
                callback_data=f"setparent_{m_cat.id}"
            )

    builder.adjust(1)

    data = await state.get_data()
    await message.answer(
        f"3️⃣ <b>'{data['name']}'</b> qaysi bo'limga tegishli bo'lsin?",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

    await state.set_state(AddCategoryStates.waiting_parent_id)


@router.callback_query(StateFilter(AddCategoryStates.waiting_parent_id), F.data.startswith("setparent_"))
async def add_category_finish(callback: CallbackQuery, state: FSMContext):
    """Parent ID ni olish va bazaga saqlash"""
    if not is_admin(callback.from_user.id):
        return

    parent_raw = callback.data.split("_")[1]
    parent_id = None if parent_raw == "none" else int(parent_raw)

    data = await state.get_data()

    try:
        category = await add_category(
            name=data['name'],
            description=data['description'],
            parent_id=parent_id
        )

        await callback.message.edit_text(
            f"✅ Kategoriya muvaffaqiyatli saqlandi!\n\n"
            f"📁 Nom: <b>{category.name}</b>\n"
            f"📌 Turi: <b>{'Bosh kategoriya' if parent_id is None else 'Ost-kategoriya'}</b>",
            parse_mode="HTML"
        )
        await callback.message.answer("Admin panel:", reply_markup=admin_main_kb())

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Saqlashda xatolik: {str(e)}"
        )
        await callback.message.answer("Admin panel:", reply_markup=admin_main_kb())

    await state.clear()
    await callback.answer()


# ==================== KANALLAR ====================

@router.message(F.text == "📺 Kanallar")
async def channels_menu(message: Message):
    """Kanallar menyusi"""
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "📺 <b>Kanallar boshqaruvi</b>\n\n"
        "Kerakli amaliyotni tanlang:",
        reply_markup=channels_manage_kb(),
        parse_mode="HTML"
    )


from keyboards.admin_keyboards import select_channel_type_kb  # Yangi keyboard


@router.callback_query(F.data == "admin_add_channel")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    """Kanal qo'shish - tur tanlash"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "📺 <b>Yangi kanal qo'shish</b>\n\n"
        "Qanday turdagi kanal qo'shmoqchisiz?",
        reply_markup=select_channel_type_kb(),
        parse_mode="HTML"
    )

    await state.set_state(AddChannelStates.waiting_type)
    await callback.answer()


@router.callback_query(StateFilter(AddChannelStates.waiting_type), F.data == "channel_type_public")
async def add_public_channel(callback: CallbackQuery, state: FSMContext):
    """Public kanal qo'shish"""
    await state.update_data(channel_type="public")

    await callback.message.edit_text(
        "📢 <b>Public kanal qo'shish</b>\n\n"
        "Kanal <b>username</b>ini kiriting:\n\n"
        "Masalan: <code>@kino_kanal</code>\n\n"
        "⚠️ Bot kanalda admin bo'lishi shart!\n\n"
        "❌ Bekor qilish: /cancel",
        parse_mode="HTML"
    )

    await state.set_state(AddChannelStates.waiting_username)
    await callback.answer()


@router.callback_query(StateFilter(AddChannelStates.waiting_type), F.data == "channel_type_private")
async def add_private_channel(callback: CallbackQuery, state: FSMContext):
    """Private kanal qo'shish"""
    await state.update_data(channel_type="private")

    await callback.message.edit_text(
        "🔒 <b>Private kanal qo'shish</b>\n\n"
        "Kanal <b>taklif havolasini</b> yuboring:\n\n"
        "Masalan: <code>https://t.me/+AbCdEfGhIjKl</code>\n\n"
        "⚠️ Bot kanalda admin bo'lishi va taklif havolasi bo'lishi shart!\n\n"
        "📋 Taklif havolasini qanday olish:\n"
        "1. Kanalga kiring\n"
        "2. Kanal sozlamalariga o'ting\n"
        "3. 'Invite Link' ni toping\n"
        "4. Havolani nusxalang\n\n"
        "❌ Bekor qilish: /cancel",
        parse_mode="HTML"
    )

    await state.set_state(AddChannelStates.waiting_invite_link)
    await callback.answer()


@router.message(StateFilter(AddChannelStates.waiting_username))
async def add_public_channel_username(message: Message, state: FSMContext):
    """Public kanal username"""
    if message.text == "/cancel" or message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return

    username = message.text.replace("@", "").strip()

    try:
        # Kanal ma'lumotlarini olish
        chat = await message.bot.get_chat(f"@{username}")

        # Bot admin ekanligini tekshirish
        bot_member = await message.bot.get_chat_member(
            chat_id=chat.id,
            user_id=message.bot.id
        )

        if bot_member.status not in ['administrator', 'creator']:
            await message.answer(
                "❌ Bot kanalda admin emas!\n\n"
                "Iltimos botni kanalga admin qiling.",
                reply_markup=admin_main_kb()
            )
            await state.clear()
            return

        # Public kanalni saqlash
        channel = await add_channel(
            channel_id=chat.id,
            title=chat.title,
            channel_type="public",
            username=username
        )

        await message.answer(
            f"✅ Public kanal qo'shildi!\n\n"
            f"📢 <b>{channel.channel_title}</b>\n"
            f"👤 @{channel.channel_username}\n"
            f"🆔 ID: <code>{channel.channel_id}</code>",
            reply_markup=admin_main_kb(),
            parse_mode="HTML"
        )

    except TelegramBadRequest as e:
        await message.answer(
            f"❌ Kanal topilmadi yoki bot a'zo emas!\n\n"
            f"Xatolik: {str(e)}",
            reply_markup=admin_main_kb()
        )
    except ValueError as e:
        await message.answer(
            f"❌ {str(e)}",
            reply_markup=admin_main_kb()
        )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=admin_main_kb()
        )

    await state.clear()


@router.message(StateFilter(AddChannelStates.waiting_invite_link))
async def add_private_channel_link(message: Message, state: FSMContext):
    """Private kanal invite link"""
    if message.text == "/cancel" or message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return

    invite_link = message.text.strip()

    # Invite link formatini tekshirish
    if not (invite_link.startswith("https://t.me/+") or invite_link.startswith("https://t.me/joinchat/")):
        await message.answer(
            "❌ Noto'g'ri taklif havolasi formati!\n\n"
            "To'g'ri format:\n"
            "• <code>https://t.me/+AbCdEfGhIjKl</code>\n"
            "• <code>https://t.me/joinchat/AbCdEfGhIjKl</code>",
            parse_mode="HTML"
        )
        return

    try:
        # Invite link orqali kanal ma'lumotlarini olish
        # Birinchi botni kanalga qo'shish kerak

        # Methodlar:
        # 1. Bot allaqachon kanalda bo'lsa - chat_id orqali olish mumkin
        # 2. Invite link orqali join qilish

        # Eng oson yo'l: Admin kanalning chat_id sini qo'lda kiritsin
        await message.answer(
            "🔒 <b>Private kanal uchun qo'shimcha ma'lumot kerak</b>\n\n"
            "Kanal <b>ID raqamini</b> yuboring:\n\n"
            "📋 Kanal ID ni qanday olish:\n"
            "1. @getidsbot ga kanaldan xabar forward qiling\n"
            "2. Yoki @username_to_id_bot dan foydalaning\n\n"
            "Masalan: <code>-1001234567890</code>\n\n"
            "❌ Bekor qilish: /cancel",
            parse_mode="HTML"
        )

        # Invite linkni saqlash
        await state.update_data(invite_link=invite_link)
        await state.set_state(AddChannelStates.waiting_channel_id)

    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=admin_main_kb()
        )
        await state.clear()


# Yangi state qo'shamiz
# states/admin_states.py ga:
# waiting_channel_id = State()

@router.message(StateFilter(AddChannelStates.waiting_channel_id))
async def add_private_channel_id(message: Message, state: FSMContext):
    """Private kanal ID"""
    if message.text == "/cancel" or message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return

    try:
        channel_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format! Faqat raqam kiriting.\n\n"
            "Masalan: <code>-1001234567890</code>",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    invite_link = data.get('invite_link')

    try:
        # Kanal ma'lumotlarini olish
        chat = await message.bot.get_chat(channel_id)

        # Bot admin ekanligini tekshirish
        bot_member = await message.bot.get_chat_member(
            chat_id=channel_id,
            user_id=message.bot.id
        )

        if bot_member.status not in ['administrator', 'creator']:
            await message.answer(
                "❌ Bot kanalda admin emas!\n\n"
                "Iltimos botni kanalga admin qiling.\n\n"
                f"Kanal: <b>{chat.title}</b>",
                reply_markup=admin_main_kb(),
                parse_mode="HTML"
            )
            await state.clear()
            return

        # Private kanalni saqlash
        channel = await add_channel(
            channel_id=channel_id,
            title=chat.title,
            channel_type="private",
            invite_link=invite_link
        )

        await message.answer(
            f"✅ Private kanal qo'shildi!\n\n"
            f"🔒 <b>{channel.channel_title}</b>\n"
            f"🆔 ID: <code>{channel.channel_id}</code>\n"
            f"🔗 Taklif havolasi: <code>{channel.invite_link[:30]}...</code>",
            reply_markup=admin_main_kb(),
            parse_mode="HTML"
        )

    except TelegramBadRequest as e:
        await message.answer(
            f"❌ Kanal topilmadi yoki bot a'zo emas!\n\n"
            f"Xatolik: {str(e)}\n\n"
            f"Botni avval kanalga qo'shing va admin qiling.",
            reply_markup=admin_main_kb()
        )
    except ValueError as e:
        await message.answer(
            f"❌ {str(e)}",
            reply_markup=admin_main_kb()
        )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=admin_main_kb()
        )

    await state.clear()

@router.message(StateFilter(AddChannelStates.waiting_username))
async def add_channel_username(message: Message, state: FSMContext):
    """Kanal username"""
    if message.text == "/cancel" or message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return

    username = message.text.replace("@", "")

    try:
        # Kanal ma'lumotlarini olish
        chat = await message.bot.get_chat(f"@{username}")

        # Bot admin ekanligini tekshirish
        bot_member = await message.bot.get_chat_member(
            chat_id=chat.id,
            user_id=message.bot.id
        )

        if bot_member.status not in ['administrator', 'creator']:
            await message.answer(
                "❌ Bot kanalda admin emas!\n\n"
                "Iltimos botni kanalga admin qiling.",
                reply_markup=admin_main_kb()
            )
            await state.clear()
            return

        # Kanalni saqlash
        channel = await add_channel(
            channel_id=chat.id,
            username=username,
            title=chat.title
        )

        await message.answer(
            f"✅ Kanal qo'shildi!\n\n"
            f"📺 <b>{channel.channel_title}</b>\n"
            f"👤 @{channel.channel_username}",
            reply_markup=admin_main_kb(),
            parse_mode="HTML"
        )

    except TelegramBadRequest:
        await message.answer(
            "❌ Kanal topilmadi yoki bot a'zo emas!",
            reply_markup=admin_main_kb()
        )
    except ValueError as e:
        await message.answer(
            f"❌ {str(e)}",
            reply_markup=admin_main_kb()
        )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=admin_main_kb()
        )

    await state.clear()


@router.callback_query(F.data == "admin_list_channels")
async def list_channels(callback: CallbackQuery):
    """Kanallar ro'yxati"""
    if not is_admin(callback.from_user.id):
        return

    channels = await get_all_channels()

    if not channels:
        await callback.answer("❌ Kanallar mavjud emas!", show_alert=True)
        return

    text = "📺 <b>Barcha kanallar:</b>\n\n"

    for ch in channels:
        status = "✅ Faol" if ch.is_active else "❌ Nofaol"
        text += f"{status}\n"
        text += f"📺 <b>{ch.channel_title}</b>\n"
        text += f"   └ @{ch.channel_username}\n\n"

    await callback.message.edit_text(
        text,
        parse_mode="HTML"
    )

    await callback.message.answer(
        "Admin panel:",
        reply_markup=admin_main_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_delete_channel")
async def delete_channel_menu(callback: CallbackQuery):
    """Kanal o'chirish menyusi"""
    if not is_admin(callback.from_user.id):
        return

    channels = await get_all_channels()

    if not channels:
        await callback.answer("❌ Kanallar mavjud emas!", show_alert=True)
        return

    await callback.message.edit_text(
        "🗑 <b>Kanal o'chirish</b>\n\n"
        "O'chirmoqchi bo'lgan kanalni tanlang:",
        reply_markup=channels_list_kb(channels),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_ch_"))
async def delete_channel_confirm(callback: CallbackQuery):
    """Kanalni o'chirish"""
    if not is_admin(callback.from_user.id):
        return

    channel_id = int(callback.data.split("_")[2])

    try:
        await delete_channel(channel_id)
        await callback.answer("✅ Kanal o'chirildi!", show_alert=True)

        # Yangilangan ro'yxatni ko'rsatish
        channels = await get_all_channels()

        if channels:
            await callback.message.edit_text(
                "🗑 <b>Kanal o'chirish</b>\n\n"
                "O'chirmoqchi bo'lgan kanalni tanlang:",
                reply_markup=channels_list_kb(channels),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "✅ Barcha kanallar o'chirildi!",
                parse_mode="HTML"
            )
            await callback.message.answer(
                "Admin panel:",
                reply_markup=admin_main_kb()
            )

    except Exception as e:
        await callback.answer(f"❌ Xatolik: {str(e)}", show_alert=True)





# ==================== REKLAMA (BROADCAST) ====================
@router.message(F.text == "📢 Reklama")
async def broadcast_start(message: Message, state: FSMContext):
    """Reklama yuborishni boshlash"""
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "📢 <b>Reklama yuborish</b>\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring:\n"
        "- Matn\n"
        "- Rasm + matn\n"
        "- Video + matn\n\n"
        "❌ Bekor qilish: /cancel",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )

    await state.set_state(BroadcastStates.waiting_content)


@router.message(StateFilter(BroadcastStates.waiting_content))
async def broadcast_content(message: Message, state: FSMContext):
    """Reklama mazmunini saqlash"""
    if message.text in ["/cancel", "❌ Bekor qilish"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_main_kb())
        return

    # Xabar ID va Chat ID sin mos nomlar bilan saqlaymiz
    await state.update_data(
        broadcast_message_id=message.message_id,
        broadcast_from_chat_id=message.chat.id
    )

    # Foydalanuvchilar sonini olish
    users = await get_all_users() if asyncio.iscoroutinefunction(get_all_users) else get_all_users()
    total = len(list(users))

    text = (
        "📢 <b>Reklama tayyorlandi!</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total}</b>\n\n"
        "✅ Yuborishni tasdiqlaysizmi?"
    )

    await message.answer(
        text,
        reply_markup=broadcast_confirm_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "broadcast_send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Reklamani barcha foydalanuvchilarga yuborish"""

    data = await state.get_data()
    message_id = data.get("broadcast_message_id")
    from_chat_id = data.get("broadcast_from_chat_id")

    # Agar state'da saqlanmagan bo'lsa, reply qilingan xabardan oladi
    if not message_id and callback.message.reply_to_message:
        message_id = callback.message.reply_to_message.message_id
        from_chat_id = callback.message.chat.id

    if not message_id or not from_chat_id:
        await callback.message.edit_text("❌ Reklama xabari topilmadi. Qaytadan urinib ko'ring.")
        await state.clear()
        return

    await callback.message.edit_text("⏳ Reklama yuborilmoqda, kuting...")

    # Bazadan foydalanuvchilarni olish
    users = await get_all_users() if asyncio.iscoroutinefunction(get_all_users) else get_all_users()
    users_list = list(users)

    count_success = 0
    count_blocked = 0
    count_error = 0

    for user in users_list:
        user_id = user.user_id if hasattr(user, 'user_id') else user[0]

        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=from_chat_id,
                message_id=message_id
            )
            count_success += 1
            await asyncio.sleep(0.04)

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id
                )
                count_success += 1
            except Exception:
                count_error += 1

        except TelegramForbiddenError:
            count_blocked += 1

        except TelegramAPIError:
            count_error += 1

        except Exception:
            count_error += 1

    # Natijani bir marta chiroyli shaklda ko'rsatish
    result_text = (
        "✅ <b>Reklama muvaffaqiyatli yuborildi!</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{len(users_list)}</b>\n"
        f"✅ Yetib bordi: <b>{count_success}</b>\n"
        f"🚫 Botni bloklaganlar: <b>{count_blocked}</b>\n"
        f"❌ Yetib bormadi: <b>{count_error}</b>"
    )

    await callback.message.edit_text(result_text, parse_mode="HTML")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel", StateFilter(BroadcastStates.waiting_content))
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    """Reklamani bekor qilish"""
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi")
    await callback.message.answer(
        "Admin panel:",
        reply_markup=admin_main_kb()
    )
    await callback.answer()

# ==================== CALLBACKS ====================

@router.callback_query(F.data == "admin_main")
async def back_to_admin_main(callback: CallbackQuery):
    """Admin panelga qaytish"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "👨‍💼 <b>Admin Panel</b>",
        parse_mode="HTML"
    )

    await callback.message.answer(
        "Kerakli bo'limni tanlang:",
        reply_markup=admin_main_kb()
    )
    await callback.answer()


PRIVATE_BASE_CHANNEL_ID = -1003584365605
MY_CHANNEL = "@AnimeMakoni_uz"



def clean_and_parse_caption(raw_caption: str):
    if not raw_caption:
        return "Kino", 1, None, ""

    cleaned = raw_caption.replace("\r", "\n")

    # Username va havolalarni olib tashlash
    cleaned = re.sub(r"@\w+|https?://\S+|t\.me/\S+", "", cleaned)

    # Reklama va kanal ma'lumotlarini olib tashlash
    cleaned = re.sub(
        r"(?im)\b(kanal|kanalimiz|manbaa|manba|obuna|admin|tg|link|source)\b\s*[:\-]?\s*.*$",
        "",
        cleaned
    )

    # Kodlarni olib tashlash
    cleaned = re.sub(
        r"(?i)\b(kod|id)\s*[:#\-]?\s*\d+\b",
        "",
        cleaned
    )

    # Fasl / sezon / bo'lim / mavsum aniqlash
    season_patterns = [
        r"\b(\d+)\s*[-:.]?\s*(?:fasl|sezon|season|bo['’`]?lim|mavsum)\b",
        r"\b(?:fasl|sezon|season|bo['’`]?lim|mavsum)\s*[-:.]?\s*(\d+)\b",
        r"\bseason\s*(\d+)\b",
        r"\bs\s*(\d+)\b"
    ]

    season_num = 1

    for pattern in season_patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            season_num = int(match.group(1))
            break

    # Qism / seriya / episode aniqlash
    episode_patterns = [
        r"\b(\d+)\s*[-:.]?\s*(?:qism|seriya|episode|ep)\b",
        r"\b(?:qism|seriya|episode|ep)\s*[-:.]?\s*(\d+)\b",
        r"\be\s*(\d+)\b"
    ]

    episode_num = None

    for pattern in episode_patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            episode_num = int(match.group(1))
            break

    # Anime nomini bildiruvchi belgilar
    title_marker = re.compile(
        r"(?i)^\s*(?:"
        r"anime\s+nomi|kino\s+nomi|film\s+nomi|"
        r"multfilm\s+nomi|serial\s+nomi|"
        r"nomi|nomlanishi|nomlanadi|nom|"
        r"название|наименование|name|title"
        r")\s*[:：\-–—]?\s*(.*)$"
    )

    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]

    title_parts = []
    marker_found = False

    for index, line in enumerate(lines):
        match = title_marker.match(line)

        if match:
            marker_found = True

            if match.group(1).strip():
                title_parts.append(match.group(1).strip())

            for next_line in lines[index + 1:]:
                if re.search(
                    r"(?i)\b(?:\d+\s*[-:.]?\s*(?:fasl|sezon|season|bo['’`]?lim|mavsum|qism|seriya|ep)|"
                    r"(?:fasl|sezon|season|bo['’`]?lim|mavsum|qism|seriya|ep)\s*\d+|"
                    r"kod|id|sifat|quality|til|language|yil|year)\b",
                    next_line
                ):
                    break

                title_parts.append(next_line)

            break

    # Belgilar topilmasa, caption matnidan nomni ajratish
    if not marker_found:
        title_parts = lines

    title = " ".join(title_parts)

    # Nom ichidan fasl va qism ma'lumotlarini olib tashlash
    remove_patterns = [
        r"\b\d+\s*[-:.]?\s*(?:fasl|sezon|season|bo['’`]?lim|mavsum)\b",
        r"\b(?:fasl|sezon|season|bo['’`]?lim|mavsum)\s*[-:.]?\s*\d+\b",
        r"\bseason\s*\d+\b",
        r"\bs\s*\d+\b",
        r"\b\d+\s*[-:.]?\s*(?:qism|seriya|episode|ep)\b",
        r"\b(?:qism|seriya|episode|ep)\s*[-:.]?\s*\d+\b",
        r"\be\s*\d+\b",
        r"(?i)\b(?:kod|id)\s*[:#\-]?\s*\d+\b"
    ]

    for pattern in remove_patterns:
        title = re.sub(pattern, " ", title, flags=re.IGNORECASE)

    # Ortiqcha belgilar va bo'shliqlar
    title = re.sub(r"[{}\[\]()]", " ", title)
    title = re.sub(r"[\/\\\-_🎬📢⭐️🔥]", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" -:|_")

    if not title:
        title = "Kino"

    return title[:255], season_num, episode_num, raw_caption


# Parallel saqlashning oldini olish
channel_post_lock = asyncio.Lock()


@router.channel_post(F.video | F.document)
async def handle_channel_post(message: types.Message):

    if message.chat.id != PRIVATE_BASE_CHANNEL_ID:
        return

    video = message.video or message.document

    if not video:
        return

    async with channel_post_lock:
        try:
            raw_caption = message.caption or ""

            title, season_num, episode_num, _ = clean_and_parse_caption(
                raw_caption
            )

            file_id = video.file_id

            # Kategoriya nomi
            if season_num > 1:
                base_category_name = f"{title} {season_num}-fasl"
            else:
                base_category_name = title

            # Kategoriyani tekshirish
            all_categories = await db.get_all_categories()

            category = next(
                (
                    cat for cat in all_categories
                    if cat.name.strip().casefold()
                    == base_category_name.strip().casefold()
                ),
                None
            )

            # Kategoriya mavjud bo'lmasa yaratish
            if category is None:
                category = await db.add_category(
                    name=base_category_name,
                    description=f"{base_category_name} kategoriyasi"
                )

            category_id = category.id

            # Barcha kinolarni olish
            all_movies = await db.get_all_movies()

            # Qism raqamini avtomatik belgilash
            if episode_num is None:
                category_movies = [
                    m for m in all_movies
                    if m.category_id == category_id
                ]
                episode_num = len(category_movies) + 1

            # Yangi kod
            max_code = max(
                (m.code for m in all_movies if m.code is not None),
                default=0
            )

            next_code = max_code + 1

            # Kino nomi
            movie_title = f"{base_category_name} {episode_num}-qism"

            if season_num > 1:
                caption_info = f"{season_num}-fasl {episode_num}-qism"
            else:
                caption_info = f"{episode_num}-qism"

            formatted_caption = (
                f"🎬 <b>{title}</b> | {caption_info}\n\n"
                f"📢 Rasmiy kanalimiz: {MY_CHANNEL}"
            )

            # Bazaga saqlash
            await db.add_movie(
                code=next_code,
                title=movie_title,
                file_id=file_id,
                category_id=category_id,
                description=formatted_caption
            )

            print(
                f"✅ SAQLANDI: #{next_code} | {movie_title}"
            )

        except Exception as e:
            print(f"❌ Saqlashda xatolik: {e}")


@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    """Bekor qilish"""
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi")
    await callback.message.answer(
        "Admin panel:",
        reply_markup=admin_main_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_channels")
async def back_to_channels(callback: CallbackQuery):
    """Kanallar menyusiga qaytish"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "📺 <b>Kanallar boshqaruvi</b>\n\n"
        "Kerakli amaliyotni tanlang:",
        reply_markup=channels_manage_kb(),
        parse_mode="HTML"
    )
    await callback.answer()



###########################POST####################################
from states.admin_states import CreatePostStates
from keyboards.admin_keyboards import select_movie_for_post_kb, movie_post_inline_kb


@router.message(F.text == "📢 Kanalga post yaratish")
async def start_create_post(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await message.answer("📸 Post uchun rasmni (poster) yuboring:")
    await state.set_state(CreatePostStates.waiting_for_photo)


# 2. Admin rasmni yuborganda -> Ost-kategoriyalar (Anime/Kino nomlari) ro'yxati chiqadi
@router.message(CreatePostStates.waiting_for_photo, F.photo)
async def process_post_photo(message: Message, state: FSMContext):
    try:
        photo_id = message.photo[-1].file_id
        await state.update_data(photo_id=photo_id)

        categories = await get_all_categories()

        # Agar parent_id mantiqida chalkashlik bo'lsa, barcha kategoriyalarni olib turamiz:
        sub_categories = [c for c in categories if c.parent_id is not None] if categories else []

        # Agarda ost-kategoriya topilmasa, shunchaki barcha kategoriyalarni ko'rsatish:
        if not sub_categories:
            sub_categories = categories

        if not sub_categories:
            await message.answer("❌ Bazada kategoriyalar topilmadi! Avval kategoriya yarating.")
            await state.clear()
            return

        await message.answer(
            "🎬 Ushbu rasm qaysi anime/kino papkasiga tegishli? Tanlang:",
            reply_markup=select_movie_for_post_kb(sub_categories, page=0)
        )
        await state.set_state(CreatePostStates.waiting_for_movie)

    except Exception as e:
        print(f"Rasm qabul qilishda xatolik: {e}")
        await message.answer(f"❌ Xatolik yuz berdi: {e}")

# 3. Sahifalash (Oldingi/Keyingi)
@router.callback_query(CreatePostStates.waiting_for_movie, F.data.startswith("post_movie_page_"))
async def process_post_movie_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[-1])
    categories = await get_all_categories()
    sub_categories = [c for c in categories if c.parent_id is not None]

    await callback.message.edit_reply_markup(
        reply_markup=select_movie_for_post_kb(sub_categories, page=page)
    )
    await callback.answer()


# 4. Выбор подкатегории -> Прямая публикация в канал @kinopooisk_uz
@router.callback_query(CreatePostStates.waiting_for_movie, F.data.startswith("post_movie_"))
async def process_select_category_for_post(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[-1])
    category = await get_category_by_id(category_id)

    if not category:
        await callback.message.answer("❌ Категория не найдена!")
        await state.clear()
        return

    movies = await get_all_movies_by_category(category_id)
    if not movies:
        await callback.message.answer("⚠ В этой папке нет видео/серий! Сначала загрузите видео.")
        await state.clear()
        return

    data = await state.get_data()
    photo_id = data.get("photo_id")
    bot_info = await callback.bot.get_me()

    caption_text = (
        f"🍿 <b>{category.name}</b>\n\n"
        f"📂 <b>Количество серий:</b> {len(movies)} шт.\n"
        f"📝 <b>Описание:</b> {category.description if category.description else 'Отсутствует'}\n\n"
        f"⬇ Нажмите кнопку ниже, чтобы посмотреть все серии:"
    )

    first_movie_code = movies[0].code
    target_channel = "@kinopooisk_uz"

    try:
        await callback.bot.send_photo(
            chat_id=target_channel,
            photo=photo_id,
            caption=caption_text,
            reply_markup=movie_post_inline_kb(bot_info.username, first_movie_code),
            parse_mode="HTML"
        )
        await callback.message.delete()
        await callback.message.answer(f"✅ Пост успешно опубликован в канале {target_channel}!")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при отправке в канал: {e}")

    await state.clear()


# Bekor qilish
@router.callback_query(F.data == "cancel_post")
async def cancel_post_process(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Post yaratish bekor qilindi.")
    await callback.answer()

# =====================================================================
# KINO SO'ROVLARI / OVOZLAR STATISTIKASI (ADMIN UCHUN)
# =====================================================================
from database.database import get_top_requested_movies, get_pending_requests_count

@router.message(F.text == "📋 Kino so'rovlari")
async def admin_movie_requests_handler(message: Message):
    top_requests = await get_top_requested_movies(limit=10)
    total_pending = await get_pending_requests_count()

    if not top_requests:
        await message.answer("📭 Hozircha foydalanuvchilardan kino so'rovlari mavjud emas.")
        return

    text = (
        f"📋 <b>Topilmagan kinolar so'rovlari (Ovozlar):</b>\n\n"
        f"📊 Jami kutilayotgan so'rovlar: <b>{total_pending} ta</b>\n\n"
        f"🔥 <b>Eng ko'p so'ralgan kinolar:</b>\n"
    )

    for idx, (query, count) in enumerate(top_requests, start=1):
        text += f"{idx}. 🎬 <b>{query}</b> — 👤 <b>{count} ta</b> foydalanuvchi\n"

    text += "\n✨ <i>Bajarilgan kinoning tugmasini bosing:</i>"

    # 👈 Mana bu yerda klaviatura ulanadi
    await message.answer(
        text,
        reply_markup=admin_requests_list_kb(top_requests),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("req_done_"))
async def mark_request_done(callback: CallbackQuery, bot: Bot):
    query_text = callback.data.replace("req_done_", "", 1)

    # Bazadan o'sha so'rovni yuborgan userlarni olamiz va statusini yopamiz
    user_ids = await complete_movie_request(query_text)

    success_count = 0
    for uid in user_ids:
        try:
            await bot.send_message(
                chat_id=uid,
                text=f"✅ <b>Siz so'ragan '{query_text}' kinoteatrimizga qo'shildi!</b>\n\n🔍 Uni botga qayta yozib topishingiz mumkin.",
                parse_mode="HTML"
            )
            success_count += 1
            await asyncio.sleep(0.3)
        except Exception:
            pass

    await callback.answer(f"Muvaffaqiyatli bajarildi! {success_count} ta foydalanuvchiga xabar yuborildi.",
                          show_alert=True)
    await callback.message.edit_text(
        f"✅ <b>'{query_text}'</b> bo'yicha so'rov yopildi va {success_count} ta foydalanuvchiga xabar berildi.",
        parse_mode="HTML"
    )