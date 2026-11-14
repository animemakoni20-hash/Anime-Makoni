"""Statistika funksiyalari"""
from database.database import (
    get_total_users,
    get_total_movies,
    get_active_users_count,
    get_new_users_count,
    get_total_views,
    get_top_movies
)


async def get_user_statistics() -> str:
    # Jami start bosganlar (bazadagi barcha foydalanuvchilar)
    total_users = await get_total_users()

    # Bugun qo'shilganlar
    new_users_today = await get_new_users_count(days=1)

    # Jami kinolar va ko'rishlar
    total_movies = await get_total_movies()
    total_views = await get_total_views()

    text = (
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Jami obunachilar (Start bosganlar): <b>{total_users} ta</b>\n"
        f"👤 Bugun qo'shilganlar: <b>{new_users_today} ta</b>\n"
        f"🎬 Jami kinolar: <b>{total_movies} ta</b>\n"
        f"👁 Jami ko'rishlar: <b>{total_views} ta</b>"
    )
    return text


async def get_admin_statistics() -> str:
    """Admin uchun kengaytirilgan statistika"""
    total_users = await get_total_users()
    total_movies = await get_total_movies()
    total_views = await get_total_views()

    active_today = await get_active_users_count(days=1)
    active_week = await get_active_users_count(days=7)

    new_today = await get_new_users_count(days=1)
    new_week = await get_new_users_count(days=7)

    text = (
        "📊 <b>Kengaytirilgan Statistika</b>\n\n"

        "<b>👥 Foydalanuvchilar:</b>\n"
        f"├ Jami: <b>{total_users}</b>\n"
        f"├ Bugun faol: <b>{active_today}</b>\n"
        f"├ Haftalik faol: <b>{active_week}</b>\n"
        f"├ Bugun yangi: <b>{new_today}</b>\n"
        f"└ Haftalik yangi: <b>{new_week}</b>\n\n"

        "<b>🎬 Kinolar:</b>\n"
        f"├ Jami kinolar: <b>{total_movies}</b>\n"
        f"└ Jami ko'rishlar: <b>{total_views}</b>\n"
    )

    # Top 5 kinolar
    top_movies = await get_top_movies(limit=5)

    if top_movies:
        text += "\n<b>🔝 Top 5 Kinolar:</b>\n"
        for idx, movie in enumerate(top_movies, 1):
            text += f"{idx}. {movie.title} - <b>{movie.views_count}</b> ko'rish\n"

    return text