"""Bot konfiguratsiyasi"""
import os
from dotenv import load_dotenv

load_dotenv()

# Bot sozlamalari
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]

# Database sozlamalari (PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL")