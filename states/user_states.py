"""Foydalanuvchi FSM holatlari"""
from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    """Oddiy foydalanuvchi holatlari"""
    waiting_movie_code = State()  # Kino kodini kutish