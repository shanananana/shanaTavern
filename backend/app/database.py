from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def migrate_schema() -> None:
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        for stmt in (
            "CREATE INDEX IF NOT EXISTS ix_characters_owner ON characters(owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_characters_default ON characters(is_default)",
            "CREATE INDEX IF NOT EXISTS ix_characters_public ON characters(is_public)",
            "CREATE INDEX IF NOT EXISTS ix_chat_sessions_user ON chat_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_session ON chat_messages(session_id)",
            "CREATE INDEX IF NOT EXISTS ix_favorites_user ON favorites(user_id)",
        ):
            conn.execute(text(stmt))
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
