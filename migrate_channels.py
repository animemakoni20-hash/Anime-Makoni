"""
Database Migration - Channels jadvaliga yangi ustunlar qo'shish
PostgreSQL uchun
"""

import asyncio
import sys
from sqlalchemy import text
from database.database import engine


async def migrate_channels():
    """Channels jadvaliga yangi ustunlar qo'shish"""

    print("🔄 Migration boshlandi...\n")

    try:
        async with engine.begin() as conn:

            # 1. invite_link ustuni qo'shish
            print("➕ invite_link ustunini qo'shish...")
            await conn.execute(text(
                """
                ALTER TABLE channels
                    ADD COLUMN IF NOT EXISTS invite_link VARCHAR (500)
                """
            ))
            print("✅ invite_link qo'shildi\n")

            # 2. channel_type ustuni qo'shish
            print("➕ channel_type ustunini qo'shish...")
            await conn.execute(text(
                """
                ALTER TABLE channels
                    ADD COLUMN IF NOT EXISTS channel_type VARCHAR (50) DEFAULT 'public'
                """
            ))
            print("✅ channel_type qo'shildi\n")

            # 3. channel_username ni nullable qilish
            print("🔧 channel_username ni nullable qilish...")
            await conn.execute(text(
                """
                ALTER TABLE channels
                    ALTER COLUMN channel_username DROP NOT NULL
                """
            ))
            print("✅ channel_username nullable qilindi\n")

            # 4. Mavjud ma'lumotlarni yangilash
            print("🔄 Mavjud ma'lumotlarni yangilash...")
            await conn.execute(text(
                """
                UPDATE channels
                SET channel_type = 'public'
                WHERE channel_type IS NULL
                """
            ))
            print("✅ Mavjud ma'lumotlar yangilandi\n")

        print("=" * 50)
        print("✅ Migration muvaffaqiyatli yakunlandi!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Migration xatoligi: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 50)
    print("📊 CHANNELS JADVALI MIGRATION")
    print("=" * 50)
    print()

    asyncio.run(migrate_channels())