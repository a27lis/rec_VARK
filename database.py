from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
from typing import Generator
import os
from dotenv import load_dotenv
from config import DB_USER, DB_PASS

# Загружаем переменные окружения
load_dotenv()

class Settings(BaseSettings):
    DB_HOST: str = os.getenv("DB_HOST", "0.0.0.0:3306")
    DB_DATABASE: str = os.getenv("DB_DATABASE", "engforyou")
    DB_USER: str = os.getenv("DB_USER", DB_USER)
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", DB_PASS)

settings = Settings()

# Создаем строку подключения к базе данных
DATABASE_URL = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}/{settings.DB_DATABASE}"

# Создаем движок базы данных
engine = create_engine(DATABASE_URL)

# Создаем базовый класс для моделей
Base = declarative_base()

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
