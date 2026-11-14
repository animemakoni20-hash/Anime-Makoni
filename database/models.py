"""Ma'lumotlar bazasi modellari"""
from datetime import datetime
from sqlalchemy import BigInteger, String, Boolean, Integer, Text, DateTime, ForeignKey, Column, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import List, Optional


class Base(DeclarativeBase):
    """Bazaviy model"""
    pass


class PendingRequest(Base):
    __tablename__ = "pending_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    chat_id = Column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_request'),
    )


class MovieRequest(Base):
    """Topilmagan kinolar bo'yicha foydalanuvchi so'rovlari"""
    __tablename__ = "movie_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=False, index=True)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, completed, rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'query', name='uq_user_movie_request'),
    )

    def __repr__(self):
        return f"<MovieRequest user:{self.user_id} query:'{self.query}'>"


class User(Base):
    """Foydalanuvchilar jadvali"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Munosabatlar
    views: Mapped[List["MovieView"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.user_id} {self.full_name}>"


class Channel(Base):
    """Majburiy obuna kanallari"""
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    channel_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Public uchun
    channel_title: Mapped[str] = mapped_column(String(255))
    invite_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Private uchun
    channel_type: Mapped[str] = mapped_column(String(50), default="public")  # "public" yoki "private"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Channel {self.channel_title} ({self.channel_type})>"


class Category(Base):
    """Kino kategoriyalari"""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Bosh kategoriya ID-si (NULL bo'lsa - asosiy kategoriya bo'ladi)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id", ondelete="CASCADE"),
                                                     nullable=True)

    # Munosabatlar (Relationships)
    movies: Mapped[List["Movie"]] = relationship(back_populates="category", cascade="all, delete-orphan")

    # Asosiy kategoriyaga ulanish (parent)
    parent: Mapped[Optional["Category"]] = relationship("Category", remote_side=[id], back_populates="subcategories")

    # Ichki ost-kategoriyalar ro'yxati (subcategories)
    subcategories: Mapped[List["Category"]] = relationship("Category", back_populates="parent",
                                                           cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Category {self.name}>"


class Movie(Base):
    """Kinolar jadvali"""
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_id: Mapped[str] = mapped_column(String(500))
    quality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id", ondelete="CASCADE"))
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Munosabatlar
    category: Mapped["Category"] = relationship(back_populates="movies")
    views: Mapped[List["MovieView"]] = relationship(back_populates="movie", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Movie #{self.code} {self.title}>"


class MovieView(Base):
    """Kino ko'rishlar statistikasi"""
    __tablename__ = "movie_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    movie_id: Mapped[int] = mapped_column(Integer, ForeignKey("movies.id", ondelete="CASCADE"))
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Munosabatlar
    user: Mapped["User"] = relationship(back_populates="views")
    movie: Mapped["Movie"] = relationship(back_populates="views")

    def __repr__(self):
        return f"<MovieView user:{self.user_id} movie:{self.movie_id}>"


class Broadcast(Base):
    """Reklama yuborish tarixi"""
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Broadcast {self.id} {self.success_count}/{self.total_users}>"