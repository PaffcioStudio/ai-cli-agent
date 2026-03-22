from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./{{PROJECT_NAME_SLUG}}.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
