"""Модуль подключения к базе данных"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from config import Config

engine = None
SessionLocal = None
db_session = None
Base = declarative_base()


def init_database(db_file_path: str):
    """
    Инициализация подключения к базе данных

    Args:
        db_file_path: Путь к файлу SQLite базы данных
    """
    global engine, SessionLocal, db_session

    if not db_file_path.startswith('sqlite:///'):
        db_file_path = f'sqlite:///{db_file_path}'

    Config.DATABASE_URL = db_file_path

    engine = create_engine(
        db_file_path,
        echo=False,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False}
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = scoped_session(SessionLocal)
    Base.query = db_session.query_property()

    print(f"✓ Подключено к БД: {db_file_path}")


def get_session():
    """Получение сессии базы данных"""
    if db_session is None:
        raise RuntimeError("База данных не инициализирована")
    return db_session


def close_database():
    """Закрытие подключения"""
    global db_session
    if db_session:
        db_session.remove()
        print("✓ Подключение закрыто")