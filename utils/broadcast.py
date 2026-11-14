"""Reklama yuborish funksiyasi"""
import asyncio
from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest
from typing import List
from database.models import User
from database.database import save_broadcast


async def send_broadcast(
        bot: Bot,
        users: List[User],
        message: Message,
        admin_id: int
) -> dict:
    """
    Barcha foydalanuvchilarga xabar yuborish

    Args:
        bot: Bot instance
        users: Foydalanuvchilar ro'yxati
        message: Yuboriladi xabar
        admin_id: Admin ID

    Returns:
        dict: Statistika
    """
    success = 0
    failed = 0
    total = len(users)

    for user in users:
        try:
            # Xabarni nusxalash va yuborish
            await message.copy_to(chat_id=user.user_id)
            success += 1

            # Flood limitdan qochish uchun
            await asyncio.sleep(0.05)  # 50ms

        except TelegramForbiddenError:
            # Foydalanuvchi botni bloklagan
            failed += 1
        except TelegramRetryAfter as e:
            # Flood wait
            await asyncio.sleep(e.retry_after)
            try:
                await message.copy_to(chat_id=user.user_id)
                success += 1
            except:
                failed += 1
        except TelegramBadRequest:
            # Noto'g'ri user_id
            failed += 1
        except Exception as e:
            print(f"Broadcast xatolik {user.user_id}: {e}")
            failed += 1

    # Statistikani saqlash
    await save_broadcast(
        admin_id=admin_id,
        total=total,
        success=success,
        failed=failed,
        text=message.text or message.caption
    )

    return {
        "total": total,
        "success": success,
        "failed": failed
    }