"""Admin FSM holatlari"""
from aiogram.fsm.state import State, StatesGroup


class AddMovieStates(StatesGroup):
    """Kino qo'shish holatlari"""
    waiting_code = State()
    waiting_title = State()
    waiting_category = State()
    waiting_file = State()
    waiting_quality = State()
    waiting_language = State()
    waiting_year = State()
    waiting_description = State()


from aiogram.fsm.state import State, StatesGroup

class AddCategoryStates(StatesGroup):
    waiting_name = State()
    waiting_description = State()
    waiting_parent_id = State()  # <-- SHU QATORNI QO'SHING

class EditCategoryStates(StatesGroup):
    waiting_new_name = State()

class AddChannelStates(StatesGroup):
    """Kanal qo'shish"""
    waiting_type = State()         # Yangi: kanal turini tanlash
    waiting_username = State()     # Public uchun
    waiting_invite_link = State()  # Yangi: Private uchun invite link
    waiting_channel_id = State()   # Yangi: Private uchun channel ID


class BroadcastStates(StatesGroup):
    """Reklama yuborish"""
    waiting_content = State()


class DeleteMovieStates(StatesGroup):
    """Kino o'chirish"""
    waiting_code = State()

class CreatePostStates(StatesGroup):
    waiting_for_photo = State()        # Rasm kutish
    waiting_for_movie = State()        # Ost-kategoriyani tanlash