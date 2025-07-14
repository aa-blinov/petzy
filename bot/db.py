import enum
import os
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

Base = declarative_base()


class AsthmaType(enum.Enum):
    """Перечисление для типа приступа астмы."""

    short = "short"
    long = "long"


class AsthmaAttack(Base):
    """Модель для хранения приступов астмы."""

    __tablename__ = "asthma_attacks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    date_time = Column(DateTime, nullable=False)
    duration = Column(Enum(AsthmaType), nullable=False)
    reason = Column(String(512), nullable=False)
    inhalation = Column(Boolean, nullable=False)
    comment = Column(Text)


class StoolType(enum.Enum):
    """Вид стула."""

    normal = "Обычный"
    hard = "Твердый"
    liquid = "Жидкий"


class Defecation(Base):
    """Модель для хранения данных о дефекации."""

    __tablename__ = "defecations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    date_time = Column(DateTime, nullable=False)
    stool_type = Column(Enum(StoolType), nullable=False)
    comment = Column(Text)


class WhitelistUser(Base):
    """Модель для хранения пользователей из белого списка."""

    __tablename__ = "whitelist_users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(100))


def get_engine():
    """Создаёт и возвращает SQLAlchemy engine для подключения к базе данных."""

    db_url = f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    return create_engine(db_url)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


class CatHealthRepository:
    """Репозиторий для работы с данными о здоровье кота (CRUD-операции)."""

    def __init__(self, session: Session):
        """
        Инициализация репозитория с сессией SQLAlchemy.
        :param session: SQLAlchemy Session
        """
        self.session = session

    # AsthmaAttack CRUD
    def add_asthma_attack(self, attack: AsthmaAttack) -> AsthmaAttack:
        """
        Добавить запись о приступе астмы.
        :param attack: Объект AsthmaAttack
        :return: Сохранённый объект AsthmaAttack
        """
        self.session.add(attack)
        self.session.commit()
        self.session.refresh(attack)
        return attack

    def get_asthma_attacks_by_user(self, user_id: int) -> List[AsthmaAttack]:
        """
        Получить все приступы астмы пользователя.
        :param user_id: Telegram user id
        :return: Список AsthmaAttack
        """
        return self.session.query(AsthmaAttack).filter_by(user_id=user_id).all()

    def add_defecation(self, defe: Defecation) -> Defecation:
        """
        Добавить запись о дефекации.
        :param defe: Объект Defecation
        :return: Сохранённый объект Defecation
        """
        self.session.add(defe)
        self.session.commit()
        self.session.refresh(defe)
        return defe

    def get_defecations_by_user(self, user_id: int) -> List[Defecation]:
        """
        Получить все дефекации пользователя.
        :param user_id: Telegram user id
        :return: Список Defecation
        """
        return self.session.query(Defecation).filter_by(user_id=user_id).all()

    def get_whitelist_user(self, telegram_id: int) -> Optional[WhitelistUser]:
        """
        Получить пользователя из белого списка по Telegram ID.
        :param telegram_id: Telegram user id
        :return: WhitelistUser или None
        """
        return self.session.query(WhitelistUser).filter_by(telegram_id=telegram_id).first()

    def add_whitelist_user(self, telegram_id: int, name: Optional[str] = None) -> WhitelistUser:
        """
        Добавить пользователя в белый список.
        :param telegram_id: Telegram user id
        :param name: Имя пользователя (опционально)
        :return: Сохранённый объект WhitelistUser
        """
        user = WhitelistUser(telegram_id=telegram_id, name=name)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def remove_whitelist_user(self, telegram_id: int) -> bool:
        """
        Удалить пользователя из белого списка по Telegram ID.
        :param telegram_id: Telegram user id
        :return: True если пользователь был удалён, иначе False
        """
        user = self.get_whitelist_user(telegram_id)
        if user:
            self.session.delete(user)
            self.session.commit()
            return True
        return False


def init_db() -> None:
    """
    Инициализация базы данных: создание всех таблиц.
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    import os

    whitelist_path = os.path.join(os.path.dirname(__file__), "whitelist.txt")
    if os.path.exists(whitelist_path):
        with open(whitelist_path, encoding="utf-8") as f:
            ids = [line.strip() for line in f if line.strip() and line.strip().isdigit()]
        from sqlalchemy.orm import Session

        with Session(engine) as session:
            for id_str in ids:
                telegram_id = int(id_str)
                exists = session.query(WhitelistUser).filter_by(telegram_id=telegram_id).first()
                if not exists:
                    session.add(WhitelistUser(telegram_id=telegram_id))
            session.commit()
