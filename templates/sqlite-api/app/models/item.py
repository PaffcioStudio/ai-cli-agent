from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base

class Item(Base):
    __tablename__ = "items"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), nullable=False)
    description= Column(String(500), default="")
    created_at = Column(DateTime, server_default=func.now())
