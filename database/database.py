"""Database operatsiyalari"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func, delete, update, text, or_, case
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
import config
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from database.models import Base, User, Channel, Category, Movie, MovieView, Broadcast, PendingRequest, MovieRequest
from zoneinfo import ZoneInfo

DATABASE_URL = config.DATABASE_URL
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

connect_args = {}
if DATABASE_URL and "render.com" in DATABASE_URL:
    connect_args["ssl"] = "require"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=connect_args
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Jadvallarni va PostgreSQL fuzzy-search indeksini tayyorlash."""
    async with engine.begin() as conn:
        # Jadvallarni yaratish
        await conn.run_sync(Base.metadata.create_all)

        # Eski bazalarda parent_id ustuni bo'lmasa, qo'shib qo'yish.
        await conn.execute(text("""
            ALTER TABLE categories
            ADD COLUMN IF NOT EXISTS parent_id INTEGER
            REFERENCES categories(id) ON DELETE CASCADE;
        """))

        # pg_trgm faqat PostgreSQL uchun kerak.
        if engine.dialect.name == "postgresql":
            await conn.execute(text(
                "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
            ))
            # Oddiy va probel/tire kabi belgilar olib tashlangan kino nomlari
            # uchun trigram indekslar.
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_movies_title_trgm
                ON movies USING gin (title gin_trgm_ops);
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_movies_title_normalized_trgm
                ON movies USING gin (
                    (regexp_replace(lower(title), '[^[:alnum:]]', '', 'g'))
                    gin_trgm_ops
                );
            """))

# ==================== USER FUNCTIONS ====================

async def add_user(user_id: int, username: str, full_name: str) -> User:
    """Foydalanuvchi qo'shish yoki yangilash"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.username = username
            user.full_name = full_name
            user.last_activity = datetime.utcnow()
        else:
            user = User(
                user_id=user_id,
                username=username,
                full_name=full_name
            )
            session.add(user)

        await session.commit()
        await session.refresh(user)
        return user

async def get_all_users() -> List[User]:
    """Barcha foydalanuvchilar"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.is_blocked == False))
        return result.scalars().all()

async def update_user_activity(user_id: int):
    """Foydalanuvchi faoliyatini yangilash"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.last_activity = datetime.utcnow()
            await session.commit()

async def get_total_users() -> int:
    """Jami foydalanuvchilar soni"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count(User.id)).where(User.is_blocked == False)
        )
        return result.scalar_one()

async def get_active_users_count(days: int = 1) -> int:
    """Faol foydalanuvchilar (oxirgi X kun)"""
    async with AsyncSessionLocal() as session:
        date_from = datetime.utcnow() - timedelta(days=days)
        result = await session.execute(
            select(func.count(User.id)).where(
                User.last_activity >= date_from,
                User.is_blocked == False
            )
        )
        return result.scalar_one()

async def get_new_users_count(days: int = 1) -> int:
    """Yangi foydalanuvchilar (oxirgi X kun)"""
    async with AsyncSessionLocal() as session:
        date_from = datetime.utcnow() - timedelta(days=days)
        result = await session.execute(
            select(func.count(User.id)).where(
                User.created_at >= date_from
            )
        )
        return result.scalar_one()

# ==================== CHANNEL FUNCTIONS ====================

async def add_channel(
        channel_id: int,
        title: str,
        channel_type: str = "public",
        username: str = None,
        invite_link: str = None
) -> Channel:
    """Kanal qo'shish (Public yoki Private)"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Channel).where(Channel.channel_id == channel_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError("Bu kanal allaqachon qo'shilgan!")

        if channel_type not in ["public", "private"]:
            raise ValueError("channel_type 'public' yoki 'private' bo'lishi kerak!")

        if channel_type == "public" and not username:
            raise ValueError("Public kanal uchun username kiritilishi shart!")

        if channel_type == "private" and not invite_link:
            raise ValueError("Private kanal uchun invite_link kiritilishi shart!")

        channel = Channel(
            channel_id=channel_id,
            channel_username=username,
            channel_title=title,
            invite_link=invite_link,
            channel_type=channel_type
        )
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
        return channel

async def get_active_channels() -> List[Channel]:
    """Faol kanallar"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        return result.scalars().all()

async def get_all_channels() -> List[Channel]:
    """Barcha kanallar"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Channel))
        return result.scalars().all()

async def delete_channel(channel_id: int):
    """Kanalni o'chirish"""
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(Channel).where(Channel.channel_id == channel_id)
        )
        await session.commit()

async def check_user_subscription(bot: Bot, user_id: int, channel_id: int) -> bool:
    """Foydalanuvchi kanalda bor-yo'qligini Telegram API orqali tekshirish"""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except (TelegramBadRequest, TelegramForbiddenError):
        return True
    except Exception:
        return False

async def get_not_subscribed_channels(bot, user_id: int):
    channels = await get_active_channels()
    not_subscribed = []

    for ch in channels:
        # 1. Zayavkani tekshiramiz
        if await check_pending_request(user_id, ch.channel_id):
            continue

        # 2. Telegram API orqali tekshiramiz
        try:
            member = await bot.get_chat_member(chat_id=ch.channel_id, user_id=user_id)
            if member.status in ['creator', 'administrator', 'member', 'restricted']:
                continue
        except Exception:
            pass

        # Agar yuqoridagi ikkala shartdan ham o'tmasa, demak obuna bo'lmagan
        not_subscribed.append(ch)

    return not_subscribed

# ==================== CATEGORY FUNCTIONS ====================

async def get_main_categories() -> List[Category]:
    """Faqat Bosh kategoriyalarni olish (parent_id == None bo'lganlar)"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Category).where(Category.parent_id == None).order_by(Category.id.asc())
        )
        return result.scalars().all()


async def get_sub_categories(parent_id: int) -> List[Category]:
    """Ma'lum bir bosh kategoriyaga tegishli ost-kategoriyalarni olish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Category).where(Category.parent_id == parent_id).order_by(Category.id.asc())
        )
        return result.scalars().all()


async def get_sub_categories_paginated(parent_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[Category], int]:
    """Ost-kategoriyalarni sahifalab (paginatsiya bilan) olish"""
    async with AsyncSessionLocal() as session:
        offset = (page - 1) * per_page

        count_stmt = select(func.count(Category.id)).where(Category.parent_id == parent_id)
        total_count = (await session.execute(count_stmt)).scalar_one()

        stmt = (
            select(Category)
            .where(Category.parent_id == parent_id)
            .order_by(Category.id.asc())
            .offset(offset)
            .limit(per_page)
        )
        categories = (await session.execute(stmt)).scalars().all()

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        return categories, total_pages


async def update_category_parent(category_id: int, parent_id: Optional[int] = None) -> bool:
    """Kategoriyaning parent_id sini yangilash (boshqa bo'limga ko'chirish)"""
    async with AsyncSessionLocal() as session:
        try:
            stmt = update(Category).where(Category.id == category_id).values(parent_id=parent_id)
            await session.execute(stmt)
            await session.commit()
            return True
        except Exception as e:
            print(f"Xatolik: {e}")
            await session.rollback()
            return False


async def add_category(name: str, description: str = None, parent_id: Optional[int] = None) -> Category:
    """Kategoriya yoki Ost-kategoriya qo'shish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Category).where(Category.name == name)
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError("Bu kategoriya allaqachon mavjud!")

        category = Category(name=name, description=description, parent_id=parent_id)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category


async def get_categories_with_movies() -> List[Category]:
    """Faqat kino bor kategoriyalar"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Category)
            .join(Movie)
            .where(Category.id == Movie.category_id)
            .distinct()
        )
        return result.scalars().all()


async def get_all_categories() -> List[Category]:
    """Barcha kategoriyalarni olish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Category).order_by(Category.id.asc()))
        return result.scalars().all()


async def get_category_by_id(category_id: int) -> Optional[Category]:
    """ID bo'yicha kategoriya"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Category).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()


async def delete_category_by_id(category_id: int) -> bool:
    """Kategoriyani ID bo'yicha o'chirish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        if category:
            await session.delete(category)
            await session.commit()
            return True
        return False


async def update_category_name(category_id: int, new_name: str) -> bool:
    """Kategoriya nomini yangilash"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        if category:
            category.name = new_name
            await session.commit()
            return True
        return False


# ==================== MOVIE FUNCTIONS ====================

async def add_movie(
    code: int,
    title: str,
    file_id: str,
    category_id: int,
    description: str = None,
    quality: str = None,
    language: str = None,
    year: int = None
) -> Movie:
    """Kino qo'shish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Movie).where(Movie.code == code)
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError(f"#{code} kodli kino allaqachon mavjud!")

        movie = Movie(
            code=code,
            title=title,
            file_id=file_id,
            category_id=category_id,
            description=description,
            quality=quality,
            language=language,
            year=year
        )
        session.add(movie)
        await session.commit()
        await session.refresh(movie)
        return movie

async def get_movie_by_code(code: int) -> Optional[Movie]:
    """Kod bo'yicha kino topish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Movie).where(Movie.code == code)
        )
        return result.scalar_one_or_none()

async def get_movie_by_id(movie_id: int) -> Optional[Movie]:
    """ID bo'yicha kino topish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Movie).where(Movie.id == movie_id)
        )
        return result.scalar_one_or_none()

async def get_movies_by_category(category_id: int, limit: int = 50) -> List[Movie]:
    """Kategoriya bo'yicha kinolar"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Movie)
            .where(Movie.category_id == category_id)
            .order_by(Movie.code.asc())
            .limit(limit)
        )
        return result.scalars().all()

async def delete_movie_by_code(code: int) -> bool:
    """Kod bo'yicha kinoni o'chirish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Movie).where(Movie.code == code)
        )
        movie = result.scalar_one_or_none()

        if movie:
            await session.delete(movie)
            await session.commit()
            return True
        return False

async def delete_movie_by_id(movie_id: int) -> bool:
    """ID bo'yicha kinoni o'chirish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Movie).where(Movie.id == movie_id)
        )
        movie = result.scalar_one_or_none()

        if movie:
            await session.delete(movie)
            await session.commit()
            return True
        return False

async def get_all_movies(limit: int = 100000000000) -> List[Movie]:
    """Barcha kinolar"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Movie)
            .order_by(Movie.code.asc())
            .limit(limit)
        )
        return result.scalars().all()

async def get_total_movies() -> int:
    """Jami kinolar soni"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count(Movie.id)))
        return result.scalar_one()

async def increment_movie_views(movie_id: int, user_id: int):
    """Kino ko'rishni hisoblash"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Movie).where(Movie.id == movie_id)
        )
        movie = result.scalar_one_or_none()

        if movie:
            movie.views_count += 1
            view = MovieView(user_id=user_id, movie_id=movie_id)
            session.add(view)
            await session.commit()

async def get_top_movies():
    """Eng ko'p ko'rilgan top 3 ta kino"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Movie).order_by(Movie.views_count.desc()).limit(3)
        )
        return result.scalars().all()

async def get_total_views() -> int:
    """Jami ko'rishlar soni"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.sum(Movie.views_count))
        )
        total = result.scalar_one()
        return total if total else 0

# ==================== BROADCAST FUNCTIONS ====================

async def save_broadcast(admin_id: int, total: int, success: int, failed: int, text: str = None):
    """Broadcast statistikasini saqlash"""
    async with AsyncSessionLocal() as session:
        broadcast = Broadcast(
            admin_id=admin_id,
            message_text=text,
            total_users=total,
            success_count=success,
            failed_count=failed
        )
        session.add(broadcast)
        await session.commit()

async def get_last_broadcasts(limit: int = 5) -> List[Broadcast]:
    """Oxirgi broadcastlar"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Broadcast)
            .order_by(Broadcast.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

async def get_all_movies_by_category(category_id: int) -> List[Movie]:
    """Ma'lum bir ost-kategoriyaga tegishli BARCHA kinolar/qismlarni kodi bo'yicha tartiblab olish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Movie)
            .where(Movie.category_id == category_id)
            .order_by(Movie.code.asc())
        )
        return result.scalars().all()


async def get_movies_by_category_paginated(category_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[Movie], int]:
    """Kategoriya bo'yicha kinolarni sahifalab olish"""
    async with AsyncSessionLocal() as session:
        offset = (page - 1) * per_page

        count_stmt = select(func.count(Movie.id)).where(Movie.category_id == category_id)
        total_count = (await session.execute(count_stmt)).scalar_one()

        stmt = (
            select(Movie)
            .where(Movie.category_id == category_id)
            .order_by(Movie.code.asc())
            .offset(offset)
            .limit(per_page)
        )
        movies = (await session.execute(stmt)).scalars().all()

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        return movies, total_pages

async def get_main_categories_paginated(page: int = 1, per_page: int = 10):
    """Bosh kategoriyalarni sahifalab olish"""
    async with AsyncSessionLocal() as session:
        offset = (page - 1) * per_page
        count_stmt = select(func.count(Category.id)).where(Category.parent_id == None)
        total_count = (await session.execute(count_stmt)).scalar_one()

        stmt = (
            select(Category)
            .where(Category.parent_id == None)
            .order_by(Category.id.asc())
            .offset(offset)
            .limit(per_page)
        )
        categories = (await session.execute(stmt)).scalars().all()
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        return categories, total_pages


# ==================== PENDING REQUEST (ZAYAVKA) FUNCTIONS ====================

async def add_pending_request(user_id: int, chat_id: int):
    """Foydalanuvchi kanalga zayavka tashlaganda bazaga saqlash (agar oldin bo'lmasa)"""
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                INSERT INTO pending_requests (user_id, chat_id) 
                VALUES (:user_id, :chat_id) 
                ON CONFLICT (user_id, chat_id) DO NOTHING;
            """),
            {"user_id": user_id, "chat_id": chat_id}
        )
        await session.commit()

async def check_pending_request(user_id: int, chat_id: int) -> bool:
    """Foydalanuvchi o'sha kanalga zayavka tashlaganini tekshirish"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT 1 FROM pending_requests 
                WHERE user_id = :user_id AND chat_id = :chat_id;
            """),
            {"user_id": user_id, "chat_id": chat_id}
        )
        return result.scalar_one_or_none() is not None

async def delete_pending_request(user_id: int, chat_id: int):
    """Zayavkani bekor qilgan foydalanuvchini bazadan o'chirish"""
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(PendingRequest).where(
                PendingRequest.user_id == int(user_id),
                PendingRequest.chat_id == int(chat_id)
            )
        )
        await session.commit()


# ==================== SMART SEARCH & MOVIE REQUEST FUNCTIONS ====================

async def search_movies_smart(
    search_query: str,
    page: int = 1,
    per_page: int = 10
) -> Tuple[List[Movie], int]:
    """
    Imlo xatolariga chidamli kino qidiruvi.
    Probel, tire va tinish belgilarini hisobga olmaydi:
    'Mega miya' -> 'megamiya'.
    PostgreSQL pg_trgm orqali o'xshash nomlarni ham topadi.
    """
    async with AsyncSessionLocal() as session:
        # Foydalanuvchi yozgan probel/tire/tinish belgilarini olib tashlaymiz.
        query = " ".join(search_query.strip().split())
        normalized_query = "".join(ch for ch in query.lower() if ch.isalnum())

        if not normalized_query:
            return [], 1

        page = max(1, page)
        per_page = max(1, per_page)
        offset = (page - 1) * per_page

        if engine.dialect.name == "postgresql":
            # Past threshold ko'proq imlo xatolarini ushlaydi.
            # Juda past qiymat aloqasiz natijalarni ham chiqarishi mumkin.
            await session.execute(text(
                "SET LOCAL pg_trgm.similarity_threshold = 0.15"
            ))

            normalized_title = func.regexp_replace(
                func.lower(Movie.title),
                r"[^[:alnum:]]",
                "",
                "g",
            )

            # To'liq nom, probelsiz nom, fuzzy nom va tavsif bo'yicha qidiruv.
            conditions = [
                normalized_title == normalized_query,
                normalized_title.ilike(f"%{normalized_query}%"),
                Movie.title.op("%")(query),
                normalized_title.op("%")(normalized_query),
                Movie.description.ilike(f"%{query}%"),
            ]

            # Tavsifdagi probellar ham qidiruvga xalaqit bermasin.
            if len(normalized_query) >= 3:
                normalized_description = func.regexp_replace(
                    func.lower(func.coalesce(Movie.description, "")),
                    r"[^[:alnum:]]",
                    "",
                    "g",
                )
                conditions.append(
                    normalized_description.ilike(f"%{normalized_query}%")
                )

            condition = or_(*conditions)
            similarity_order = func.similarity(
                normalized_title, normalized_query
            ).desc()

            relevance_order = case(
                (normalized_title == normalized_query, 0),
                (normalized_title.ilike(f"%{normalized_query}%"), 1),
                else_=2,
            )
        else:
            # PostgreSQL bo'lmagan bazalar uchun oddiy qidiruv.
            pattern = f"%{query}%"
            condition = or_(
                Movie.title.ilike(pattern),
                Movie.description.ilike(pattern),
            )
            relevance_order = case(
                (func.lower(Movie.title) == query.lower(), 0),
                (Movie.title.ilike(pattern), 1),
                else_=2,
            )
            similarity_order = Movie.id.desc()

        count_stmt = select(func.count(Movie.id)).where(condition)
        total_count = (await session.execute(count_stmt)).scalar_one()

        stmt = (
            select(Movie)
            .where(condition)
            .order_by(
                relevance_order,
                similarity_order,
                Movie.id.desc(),
            )
            .offset(offset)
            .limit(per_page)
        )

        movies = (await session.execute(stmt)).scalars().all()

        total_pages = (
            (total_count + per_page - 1) // per_page
            if total_count > 0 else 1
        )
        return movies, total_pages


async def add_movie_request(user_id: int, query: str) -> bool:
    """Topilmagan kinoni bazaga saqlash (bir foydalanuvchi bir xil nom bilan qayta so'ray olmasligi uchun)"""
    async with AsyncSessionLocal() as session:
        query_clean = query.strip().lower()

        # Oldin shu user va query mavjudligini tekshiramiz
        result = await session.execute(
            select(MovieRequest).where(
                MovieRequest.user_id == user_id,
                func.lower(MovieRequest.query) == query_clean
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            return False  # Allaqachon so'rov berilgan

        new_request = MovieRequest(
            user_id=user_id,
            query=query.strip(),
            status="pending"
        )
        session.add(new_request)
        await session.commit()
        return True

# ==================== ADMIN MOVIE REQUEST FUNCTIONS ====================

async def get_top_requested_movies(limit: int = 10):
    """Admin uchun: Eng ko'p so'ralgan/ovoz berilgan kinolar ro'yxatini sanab beradi"""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(
                MovieRequest.query,
                func.count(MovieRequest.id).label("votes_count")
            )
            .where(MovieRequest.status == "pending")
            .group_by(MovieRequest.query)
            .order_by(func.count(MovieRequest.id).desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.all()  # [(query_text, count), ...]


async def get_pending_requests_count() -> int:
    """Kutilayotgan jami so'rovlar soni"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count(MovieRequest.id)).where(MovieRequest.status == "pending")
        )
        return result.scalar_one()


async def complete_movie_request(query_text: str):
    """Ma'lum bir so'rovni bajarilgan deb belgilash va uni so'ragan foydalanuvchilar IDlarini qaytarish"""
    async with AsyncSessionLocal() as session:
        query_clean = query_text.strip().lower()

        # Shu nomni so'ragan barcha user_idlarni topamiz
        result = await session.execute(
            select(MovieRequest.user_id).where(
                func.lower(MovieRequest.query) == query_clean,
                MovieRequest.status == "pending"
            )
        )
        user_ids = [row[0] for row in result.all()]

        # Statusini 'completed' ga o'zgartiramiz
        await session.execute(
            update(MovieRequest)
            .where(func.lower(MovieRequest.query) == query_clean)
            .values(status="completed")
        )
        await session.commit()
        return user_ids

# ==================== YANGI STATISTIKA ====================

def get_tashkent_day_start(days_ago=0):
    """Toshkent vaqti bo'yicha kun boshini UTC naive formatida qaytaradi."""
    tashkent_now = datetime.now(ZoneInfo("Asia/Tashkent"))

    day_start = (tashkent_now - timedelta(days=days_ago)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    return day_start.astimezone(timezone.utc).replace(tzinfo=None)


async def get_new_users_today():
    start = get_tashkent_day_start()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.created_at >= start,
                User.is_blocked.is_(False)
            )
        )
        return result.scalar_one()


async def get_new_users_last_7_days():
    start = get_tashkent_day_start(6)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.created_at >= start,
                User.is_blocked.is_(False)
            )
        )
        return result.scalar_one()


async def get_new_users_last_30_days():
    start = get_tashkent_day_start(29)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.created_at >= start,
                User.is_blocked.is_(False)
            )
        )
        return result.scalar_one()


async def get_active_users_today():
    start = get_tashkent_day_start()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.last_activity >= start,
                User.is_blocked.is_(False)
            )
        )
        return result.scalar_one()


async def get_movie_views_today():
    start = get_tashkent_day_start()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(MovieView)
            .where(MovieView.viewed_at >= start)
        )
        return result.scalar_one()