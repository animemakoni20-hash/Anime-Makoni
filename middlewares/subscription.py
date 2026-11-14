"""Obuna tekshirish middleware - Public va Private kanallar uchun"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from database.database import (
    get_active_channels,
    check_pending_request,
    delete_pending_request,
    add_user  # 📌 Bazaga foydalanuvchi qo'shish funksiyasi
)
from keyboards.user_keyboards import subscription_kb
import config

logger = logging.getLogger(__name__)


class SubscriptionMiddleware(BaseMiddleware):
    """
    Obuna tekshirish middleware
    Public va Private kanallarni qo'llab-quvvatlaydi:
    - Public: @username orqali tekshirish
    - Private: channel_id orqali tekshirish (bot a'zo bo'lishi kerak)
    - Zayavka (Join Request) avtomatik qabul qilingandan keyingi holat
    """

    async def check_user_subscription(self, bot, user_id: int, channel) -> bool:
        """Foydalanuvchi kanalga a'zo yoki yo'qligini tekshirish"""

        try:
            member = await bot.get_chat_member(
                chat_id=channel.channel_id,
                user_id=user_id
            )

            # Agar foydalanuvchi a'zo, admin yoki yaratuvchi bo'lsa -> O'TKAZAMIZ
            if member.status in ['creator', 'administrator', 'member', 'restricted']:
                return True
            else:
                return False

        except (TelegramBadRequest, TelegramForbiddenError, Exception) as e:
            logger.error(f"get_chat_member xatosi: {e}")
            return False

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Middleware asosiy funksiyasi"""

        user_id = event.from_user.id
        bot = data.get("bot") or event.bot

        # ========== 1. FOYDALANUVCHINI DARHOL BAZAGA YOZISH ==========
        # Obuna tekshiruvidan oldin foydalanuvchi statistikaga qo'shib olinadi
        try:
            await add_user(
                user_id=user_id,
                username=event.from_user.username or "",
                full_name=event.from_user.full_name
            )
        except Exception as e:
            logger.error(f"Middleware'da userni bazaga qo'shishda xatolik: {e}")

        # ========== ADMIN TEKSHIRUVI ==========
        # if user_id in config.ADMIN_IDS:
        #     return await handler(event, data)

        # ========== FAOL KANALLARNI OLISH ==========
        channels = await get_active_channels()

        # Faol kanallar bo'lmasa, davom etish
        if not channels:
            return await handler(event, data)

        # ========== OBUNANI TEKSHIRISH ==========
        not_subscribed = []

        for channel in channels:
            is_subscribed = await self.check_user_subscription(
                bot=bot,
                user_id=user_id,
                channel=channel
            )

            if not is_subscribed:
                not_subscribed.append(channel)

        # ========== OBUNA BO'LMAGAN KANALLAR BO'LSA ==========
        if not_subscribed:
            text = (
                "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
            )

            for idx, ch in enumerate(not_subscribed, 1):
                channel_info = f"{idx}. <b>{ch.channel_title}</b>"
                if ch.channel_type == "private":
                    channel_info += " 🔒 (Private/Zayavka)"
                else:
                    channel_info += " 📢 (Public)"
                text += f"{channel_info}\n"

            text += (
                "\n💡 Barcha kanallarga obuna bo'lgandan keyin "
                "<b>♻️ Tekshirish</b> tugmasini bosing!"
            )

            if isinstance(event, Message):
                await event.answer(
                    text,
                    reply_markup=subscription_kb(not_subscribed),
                    parse_mode="HTML"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "❌ Avval barcha kanallarga obuna bo'ling!",
                    show_alert=True
                )

                try:
                    await event.message.edit_text(
                        text,
                        reply_markup=subscription_kb(not_subscribed),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

            # Handlerni to'xtatish (keyingi kodlarga o'tkazmaslik)
            return

        # ========== BARCHA KANALLARGA OBUNA BO'LGAN ==========
        return await handler(event, data)