"""
Telegram Kino Bot - Asosiy fayl
Professional Aiogram 3.x + PostgreSQL/SQLAlchemy

Imkoniyatlar:
- Majburiy obuna tekshirish

- Kod va kategoriya orqali qidirish

- Admin panel (statistika, reklama, boshqaruv)

- Kanalga tashlangan kinolarni avtomatik saqlash

- Render.com Free Web Service + UptimeRobot moslashtirilgan

"""

import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import config
from database.database import init_db
from handlers import user_handlers, admin_handlers
from middlewares.subscription import SubscriptionMiddleware




# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


# ==================== WEB SERVER (UptimeRobot / Render uchun) ====================
async def handle_ping(request):
    """Render va UptimeRobot so'rovlariga javob qaytarish"""
    return web.Response(text="Bot is active and running!", status=200)

async def start_web_server():
    """aiohttp web-serverini ishga tushirish"""
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/ping", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()

    # Render taqdim etadigan PORT o'zgaruvchisi (Odatda 10000 yoki 8080)
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Web-server {port}-portda ishga tushirildi (UptimeRobot uchun tayyor)")


# ==================== MAIN FUNKSIYA ====================
async def main():
    """Asosiy funksiya"""

    # Bot va Dispatcher yaratish
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dp = Dispatcher()

    # Middlewarelarni ulash
    user_handlers.router.message.middleware(SubscriptionMiddleware())
    user_handlers.router.callback_query.middleware(SubscriptionMiddleware())

    # Routerlarni ulash: USER BIRINCHI, ADMIN UNDAN KEYIN TURISHI KERAK!
    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)


    # Ma'lumotlar bazasini yaratish
    logger.info("Ma'lumotlar bazasi yaratilmoqda...")
    await init_db()

    # Web serverni async fonda ishga tushirish
    await start_web_server()

    # Bot haqida ma'lumot
    bot_info = await bot.get_me()
    logger.info(f"Bot ishga tushdi: @{bot_info.username}")
    logger.info(f"Bot ID: {bot_info.id}")
    logger.info(f"Adminlar: {config.ADMIN_IDS}")

    # Polling boshlash
    try:
        logger.info("Polling boshlandi...")

        # Routerlardagi barcha update turlarini avtomat aniqlaydi va zayavka (chat_join_request) ni qo'shamiz
        allowed_updates = dp.resolve_used_update_types()
        if "channel_post" not in allowed_updates:
            allowed_updates.append("channel_post")
        if "chat_join_request" not in allowed_updates:
            allowed_updates.append("chat_join_request")

        await dp.start_polling(
            bot,
            allowed_updates=allowed_updates
        )
    except Exception as e:
        logger.error(f"Xatolik yuz berdi: {e}")
    finally:
        await bot.session.close()
        logger.info("Bot to'xtatildi")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal xatolik: {e}")