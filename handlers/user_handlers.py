"""Foydalanuvchi handlerlari"""
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, CommandObject, StateFilter
from aiogram.types import Message, CallbackQuery, ChatJoinRequest
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from database.database import (
    add_user,
    update_user_activity,
    get_all_movies_by_category,
    get_main_categories_paginated,
    get_sub_categories_paginated,
    get_movies_by_category_paginated,
    get_movie_by_code,
    get_movie_by_id,
    increment_movie_views,
    get_category_by_id,
    get_not_subscribed_channels,
    add_pending_request,
    search_movies_smart,
    add_movie_request
)
from keyboards.user_keyboards import (
    main_menu_kb,
    categories_kb,
    movies_list_kb,
    movie_detail_kb,
    subscription_kb,
    search_results_kb,
    missing_movie_kb
)
import logging
from states.user_states import UserStates

logger = logging.getLogger(__name__)
router = Router(name="user_router")


# =====================================================================
# 0. CHAT JOIN REQUEST (ZAYAVKA TUTUVCHI VA AVTOMAT QABUL Qiluvchi HANDLER)
# =====================================================================
@router.chat_join_request()
async def handle_chat_join_request(event: ChatJoinRequest, bot: Bot):
    """Kanalga zayavka yuborilganda bazaga yozadi va avtomatik kanalga qabul qiladi"""
    user_id = event.from_user.id
    chat_id = event.chat.id

    await add_pending_request(user_id=user_id, chat_id=chat_id)

    try:
        await bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
    except Exception as e:
        logger.error(f"Zayavkani avtomatik qabul qilishda xatolik: {e}")


# =====================================================================
# 1. PARAMETRLI START (DEEP-LINK)
# =====================================================================
@router.message(CommandStart(deep_link=True))
async def process_start_deep_link(message: Message, command: CommandObject, bot: Bot):
    """Kanal ostidagi 'Tomosha Qilish' tugmasi (start=KOD) orqali kirganda"""
    await add_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name
    )

    unsubscribed = await get_not_subscribed_channels(bot, message.from_user.id)
    if unsubscribed:
        await message.answer(
            "⚠️ <b>Kino ko'rish uchun quyidagi kanallarga obuna bo'ling:</b>",
            reply_markup=subscription_kb(unsubscribed),
            parse_mode="HTML"
        )
        return

    try:
        movie_code = int(command.args)
    except (ValueError, TypeError):
        await message.answer("❌ Noto'g'ri kod!")
        return

    movie = await get_movie_by_code(movie_code)
    if not movie:
        await message.answer("❌ Kino topilmadi!")
        return

    all_episodes = await get_all_movies_by_category(movie.category_id)

    if all_episodes:
        await message.answer(f"🎬 <b>{len(all_episodes)} ta qism yuborilmoqda...</b>", parse_mode="HTML")
        for ep in all_episodes:
            await message.answer_video(
                video=ep.file_id,
                caption=f"🍿 <b>{ep.title}</b>\n🔑 Kod: <code>{ep.code}</code>",
                parse_mode="HTML",
                protect_content=True  # 🛡️ Forwarddan himoya
            )
            await asyncio.sleep(0.5)
    else:
        await message.answer_video(
            video=movie.file_id,
            caption=f"🍿 <b>{movie.title}</b>\n🔑 Kod: <code>{movie.code}</code>",
            parse_mode="HTML",
            protect_content=True  # 🛡️ Forwarddan himoya
        )


# =====================================================================
# 2. ODDIY START COMMAND
# =====================================================================
@router.message(CommandStart())
async def start_cmd(message: Message, bot: Bot):
    """Oddiy /start bosilganda"""
    await add_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name
    )

    unsubscribed = await get_not_subscribed_channels(bot, message.from_user.id)
    if unsubscribed:
        await message.answer(
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>",
            reply_markup=subscription_kb(unsubscribed),
            parse_mode="HTML"
        )
        return

    text = (
        f"👋 Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n\n"
        "🎬 Kino Bot'ga xush kelibsiz!\n\n"
        "🔍 Kinolarni 2 xil usulda topishingiz mumkin:\n"
        "1️⃣ <b>Kategoriyalar</b> orqali\n"
        "2️⃣ <b>Kod</b> orqali (masalan: 105)\n\n"
        "📱 Quyidagi tugmalardan foydalaning:"
    )

    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


# =====================================================================
# 3. OBUNANI TEKSHIRISH CALLBACK
# =====================================================================
@router.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: CallbackQuery, bot: Bot):
    unsubscribed = await get_not_subscribed_channels(bot, callback.from_user.id)

    if unsubscribed:
        await callback.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        try:
            await callback.message.edit_text(
                "⚠️ <b>Hali barcha kanallarga obuna bo'lmadingiz! Qayta obuna bo'ling:</b>",
                reply_markup=subscription_kb(unsubscribed),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
    else:
        await callback.answer("✅ Rahmat! Barcha kanallarga obuna bo'lgansiz.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "👋 Xush kelibsiz! Quyidagi menyudan foydalaning:",
            reply_markup=main_menu_kb()
        )


# =====================================================================
# 4. KATEGORIYALAR, PAGINATSIYA VA NAVIGATSIYA
# =====================================================================
@router.message(F.text == "🎬 Kategoriyalar")
async def show_categories(message: Message, bot: Bot):
    unsubscribed = await get_not_subscribed_channels(bot, message.from_user.id)
    if unsubscribed:
        await message.answer(
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>",
            reply_markup=subscription_kb(unsubscribed),
            parse_mode="HTML"
        )
        return

    await update_user_activity(message.from_user.id)
    categories, total_pages = await get_main_categories_paginated(page=1, per_page=10)

    if not categories:
        await message.answer("❌ Hozircha kategoriyalar mavjud emas.", reply_markup=main_menu_kb())
        return

    await message.answer(
        f"📁 <b>Kategoriyalardan birini tanlang:</b> (Sahifa: 1/{total_pages})",
        reply_markup=categories_kb(categories, page=1, total_pages=total_pages),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    categories, total_pages = await get_main_categories_paginated(page=1, per_page=10)
    await callback.message.edit_text(
        f"📁 <b>Kategoriyalardan birini tanlang:</b> (Sahifa: 1/{total_pages})",
        reply_markup=categories_kb(categories, page=1, total_pages=total_pages),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("maincatpage_"))
async def handle_main_categories_pagination(callback: CallbackQuery):
    page = int(callback.data.split("_")[1])
    categories, total_pages = await get_main_categories_paginated(page=page, per_page=10)

    await callback.message.edit_text(
        f"📁 <b>Kategoriyalardan birini tanlang:</b> (Sahifa: {page}/{total_pages})",
        reply_markup=categories_kb(categories, page=page, total_pages=total_pages),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("subcatpage_"))
async def handle_subcategories_pagination(callback: CallbackQuery):
    _, parent_id_str, page_str = callback.data.split("_")
    parent_id = int(parent_id_str)
    page = int(page_str)

    parent_category = await get_category_by_id(parent_id)
    subcategories, total_pages = await get_sub_categories_paginated(parent_id, page=page, per_page=10)

    cat_name = parent_category.name if parent_category else "Bo'lim"
    text = f"📂 <b>{cat_name}</b> bo'limi:\n\n<i>Sahifa: {page}/{total_pages}</i>"

    await callback.message.edit_text(
        text,
        reply_markup=categories_kb(
            categories=subcategories,
            parent_id=parent_id,
            page=page,
            total_pages=total_pages
        ),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("back_to_parent_"))
async def back_to_parent_category(callback: CallbackQuery):
    parent_id = int(callback.data.split("_")[-1])
    parent_category = await get_category_by_id(parent_id)

    if not parent_category or parent_category.parent_id is None:
        categories, total_pages = await get_main_categories_paginated(page=1, per_page=10)
        await callback.message.edit_text(
            f"📁 <b>Kategoriyalardan birini tanlang:</b>",
            reply_markup=categories_kb(categories, page=1, total_pages=total_pages),
            parse_mode="HTML"
        )
    else:
        subcategories, total_pages = await get_sub_categories_paginated(parent_category.parent_id, page=1, per_page=10)
        await callback.message.edit_text(
            f"📂 <b>{parent_category.name}</b> bo'limi:",
            reply_markup=categories_kb(subcategories, parent_id=parent_category.parent_id, page=1, total_pages=total_pages),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("category_"))
async def handle_category_click(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    category = await get_category_by_id(category_id)

    if not category:
        await callback.answer("❌ Kategoriya topilmadi!", show_alert=True)
        return

    subcategories, total_sub_pages = await get_sub_categories_paginated(category_id, page=1, per_page=10)

    if subcategories:
        await callback.message.edit_text(
            f"📂 <b>{category.name}</b> bo'limi:\n\n<i>Kerakli bo'limni tanlang (1/{total_sub_pages}):</i>",
            reply_markup=categories_kb(subcategories, parent_id=category_id, page=1, total_pages=total_sub_pages),
            parse_mode="HTML"
        )
    else:
        page = 1
        movies, total_pages = await get_movies_by_category_paginated(category_id, page=page, per_page=10)

        if not movies:
            await callback.answer("❌ Bu bo'limda hozircha kinolar yo'q!", show_alert=True)
            return

        text = f"🎬 <b>{category.name}</b>\n\n"
        if category.description:
            text += f"{category.description}\n\n"
        text += f"📊 Sahifa: <b>{page}/{total_pages}</b>"

        await callback.message.edit_text(
            text,
            reply_markup=movies_list_kb(
                movies=movies,
                category_id=category_id,
                page=page,
                total_pages=total_pages,
                parent_id=category.parent_id
            ),
            parse_mode="HTML"
        )

    await callback.answer()


@router.callback_query(F.data.startswith("catpage_"))
async def handle_category_pagination(callback: CallbackQuery):
    _, category_id_str, page_str = callback.data.split("_")
    category_id = int(category_id_str)
    page = int(page_str)

    category = await get_category_by_id(category_id)
    movies, total_pages = await get_movies_by_category_paginated(category_id, page=page, per_page=10)

    cat_name = category.name if category else "Bo'lim"
    text = f"🎬 <b>{cat_name}</b>\n\n"
    if category and category.description:
        text += f"{category.description}\n\n"
    text += f"📊 Sahifa: <b>{page}/{total_pages}</b>"

    await callback.message.edit_text(
        text,
        reply_markup=movies_list_kb(
            movies=movies,
            category_id=category_id,
            page=page,
            total_pages=total_pages,
            parent_id=category.parent_id if category else None
        ),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """Sahifa raqami bosilganda hech narsa qilmaydi"""
    await callback.answer()


@router.callback_query(F.data.startswith("movie_"))
async def show_movie_detail(callback: CallbackQuery):
    """Kinoni tanlaganda uning ma'lumotlari va videoni chiqarish"""
    movie_id = int(callback.data.split("_")[1])
    movie = await get_movie_by_id(movie_id)

    if not movie:
        await callback.answer("❌ Kino topilmadi!", show_alert=True)
        return

    await increment_movie_views(movie.id, callback.from_user.id)

    text = f"🎬 <b>{movie.title}</b>\n\n"
    if movie.year:
        text += f"📅 Yil: <b>{movie.year}</b>\n"
    if movie.quality:
        text += f"🎞 Sifat: <b>{movie.quality}</b>\n"
    if movie.language:
        text += f"🗣 Til: <b>{movie.language}</b>\n"

    text += f"👁 Ko'rishlar: <b>{movie.views_count}</b>\n"
    text += f"🔢 Kod: <b>#{movie.code}</b>\n"

    if movie.description:
        text += f"\n📝 <i>{movie.description}</i>"

    await callback.message.edit_text(
        text,
        reply_markup=movie_detail_kb(movie.id, movie.category_id),
        parse_mode="HTML"
    )

    try:
        await callback.message.answer_video(
            video=movie.file_id,
            caption=f"🍿 <b>{movie.title}</b>",
            parse_mode="HTML",
            protect_content=True  # 🛡️ Forwarddan himoya
        )
    except Exception as e:
        logger.error(f"Video yuborishda xatolik: {e}")

    await callback.answer()


# =====================================================================
# 5. KOD ORQALI QIDIRUV VA TEKST XANDLERLAR
# =====================================================================
@router.message(F.text == "🔍 Kod orqali")
async def search_by_code_start(message: Message, state: FSMContext, bot: Bot):
    unsubscribed = await get_not_subscribed_channels(bot, message.from_user.id)
    if unsubscribed:
        await message.answer(
            "⚠️ <b>Kino ko'rish uchun quyidagi kanallarga obuna bo'ling:</b>",
            reply_markup=subscription_kb(unsubscribed),
            parse_mode="HTML"
        )
        return

    await update_user_activity(message.from_user.id)
    await message.answer(
        "🔢 <b>Kino kodini yuboring:</b>\n\nMasalan: <code>105</code>\n\n❌ Bekor qilish uchun /cancel",
        parse_mode="HTML"
    )
    await state.set_state(UserStates.waiting_movie_code)


@router.message(StateFilter(UserStates.waiting_movie_code))
async def search_by_code_process(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=main_menu_kb())
        return

    if not message.text.isdigit():
        await message.answer("❌ Iltimos faqat raqam kiriting!\n\nMasalan: <code>105</code>", parse_mode="HTML")
        return

    code = int(message.text)
    movie = await get_movie_by_code(code)

    if not movie:
        await message.answer(f"❌ <b>#{code}</b> kodli kino topilmadi!", parse_mode="HTML")
        return

    await increment_movie_views(movie.id, message.from_user.id)
    await state.clear()

    text = f"🎬 <b>{movie.title}</b>\n\n🔢 Kod: <b>#{movie.code}</b>"
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")

    try:
        await message.answer_video(
            video=movie.file_id,
            caption=f"🎬 <b>{movie.title}</b>",
            parse_mode="HTML",
            protect_content=True  # 🛡️ Forwarddan himoya
        )
    except Exception as e:
        logger.error(f"Video yuborishda xatolik: {e}")


@router.message(F.text.regexp(r'^\d+$'))
async def quick_search_by_code(message: Message, bot: Bot):
    """Oddiy raqam ko'rinishida kod yozib yuborilganda tezkor qidiruv"""
    unsubscribed = await get_not_subscribed_channels(bot, message.from_user.id)
    if unsubscribed:
        await message.answer(
            "⚠️ <b>Kino ko'rish uchun quyidagi kanallarga obuna bo'ling:</b>",
            reply_markup=subscription_kb(unsubscribed),
            parse_mode="HTML"
        )
        return

    await update_user_activity(message.from_user.id)
    code = int(message.text)
    movie = await get_movie_by_code(code)

    if not movie:
        await message.answer(
            f"❌ <b>#{code}</b> kodli kino topilmadi!",
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
        return

    await increment_movie_views(movie.id, message.from_user.id)

    text = f"🎬 <b>{movie.title}</b>\n\n🔢 Kod: <b>#{movie.code}</b>"
    await message.answer(text, parse_mode="HTML")

    try:
        await message.answer_video(
            video=movie.file_id,
            caption=f"🎬 <b>{movie.title}</b>",
            parse_mode="HTML",
            protect_content=True  # 🛡️ Forwarddan himoya
        )
    except Exception as e:
        logger.error(f"Video yuborishda xatolik: {e}")


@router.message(F.text.contains("Yordam"))
async def show_help(message: Message, bot: Bot):
    unsubscribed = await get_not_subscribed_channels(bot, message.from_user.id)
    if unsubscribed:
        await message.answer(
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>",
            reply_markup=subscription_kb(unsubscribed),
            parse_mode="HTML"
        )
        return

    await update_user_activity(message.from_user.id)
    text = (
        "ℹ️ <b>Botdan foydalanish:</b>\n\n"
        "<b>🎬 Kategoriyalar:</b>\n"
        "├ Kategoriyani tanlang\n"
        "└ Kino ro'yxatidan birini bosing\n\n"
        "<b>🔍 Kod orqali qidirish:</b>\n"
        "├ Kino kodini yuboring (masalan: 105)\n"
        "└ Kino darhol topiladi!\n\n"
        "❓ Savollar bo'lsa: @phantom_mindd"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())

# =====================================================================
# 6. AQLLI QIDIRUV VA KINO SO'RASH HANDLERLARI (1-BOSQICH)
# =====================================================================

@router.message(F.text == "🔍 Nomi bo'yicha qidirish")
async def search_button_handler(message: Message):
    """Foydalanuvchi qidiruv tugmasini bosganda"""
    await message.answer(
        "🔍 <b>Qidirmoqchi bo'lgan kinongiz nomini yozib yuboring:</b>\n\n"
        "<i>Masalan: Spider-Man, Forsaj, Temir odam va hokazo.</i>",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("ssearch_"))
async def handle_smart_search_pagination(callback: CallbackQuery):
    """Aqlli qidiruv sahifalanishi"""
    data_parts = callback.data.split("_")
    search_query = data_parts[1]
    page = int(data_parts[2])

    movies, total_pages = await search_movies_smart(search_query, page=page, per_page=10)

    if not movies:
        await callback.answer("Hech qanday natija topilmadi.", show_alert=True)
        return

    text = f"🔍 <b>'{search_query}'</b> bo'yicha qidiruv natijalari:\n\n📊 Sahifa: <b>{page}/{total_pages}</b>"
    await callback.message.edit_text(
        text,
        reply_markup=search_results_kb(movies, search_query, page, total_pages),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("req_movie_"))
async def handle_movie_request(callback: CallbackQuery):
    """Topilmagan kinoni so'rov sifatida saqlash"""
    search_query = callback.data.replace("req_movie_", "", 1)
    user_id = callback.from_user.id

    success = await add_movie_request(user_id=user_id, query=search_query)

    if success:
        await callback.answer("✅ Sizning so'rovingiz adinlarga yuborildi! Tez orada qo'shiladi.", show_alert=True)
        await callback.message.edit_text(
            f"✅ <b>'{search_query}'</b> bo'yicha so'rovingiz qabul qilindi!\n\nAdminlar tez orada kinoni bazaga qo'shishadi.",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
    else:
        await callback.answer("⚠️ Siz bu kino uchun allaqachon so'rov yuborgansiz!", show_alert=True)


@router.message(F.text & ~F.text.startswith("/") & ~F.text.in_(["🎬 Kategoriyalar", "🔍 Kod orqali", "ℹ️ Yordam"]))
async def text_smart_search_handler(message: Message, bot: Bot):
    """Foydalanuvchi har qanday matn yozganda (kod yoki menyu tugmasidan tashqari) aqlli qidiruvni ishga tushirish"""
    unsubscribed = await get_not_subscribed_channels(bot, message.from_user.id)
    if unsubscribed:
        await message.answer(
            "⚠️ <b>Kino ko'rish uchun quyidagi kanallarga obuna bo'ling:</b>",
            reply_markup=subscription_kb(unsubscribed),
            parse_mode="HTML"
        )
        return

    await update_user_activity(message.from_user.id)
    query = message.text.strip()

    # Agar matn faqat raqam bo'lsa, uni yuqordagi quick_search_by_code ushlaydi
    if query.isdigit():
        return

    movies, total_pages = await search_movies_smart(query, page=1, per_page=10)

    if movies:
        text = f"🔍 <b>'{query}'</b> bo'yicha topilgan kinolar:\n\n📊 Sahifa: <b>1/{total_pages}</b>"
        await message.answer(
            text,
            reply_markup=search_results_kb(movies, query, page=1, total_pages=total_pages),
            parse_mode="HTML"
        )
    else:
        text = (
            f"❌ <b>'{query}'</b> bo'yicha hech qanday kino topilmadi.\n\n"
            "Quyidagi tugmani bosib, kino qo'shilishini so'rashingiz mumkin:"
        )
        await message.answer(
            text,
            reply_markup=missing_movie_kb(query),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu_callback(callback: CallbackQuery):
    """Inline 'Bosh menyu' tugmasi bosilganda asosiy menyuni chiqarish"""
    await callback.message.answer(
        "🏠 <b>Asosiy menyuga qaytdingiz:</b>",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    # Bosilgandan so'ng inline tugmalarni yo'qotish uchun
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()

