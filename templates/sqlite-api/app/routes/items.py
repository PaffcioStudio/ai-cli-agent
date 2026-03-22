from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.item import Item

router = APIRouter(prefix="/items", tags=["items"])

class ItemCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class ItemOut(BaseModel):
    id: int
    name: str
    description: str
    model_config = {"from_attributes": True}

@router.get("/", response_model=list[ItemOut])
def list_items(db: Session = Depends(get_db)):
    return db.query(Item).all()

@router.post("/", response_model=ItemOut, status_code=201)
def create_item(data: ItemCreate, db: Session = Depends(get_db)):
    item = Item(**data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item

@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item: raise HTTPException(404, "Nie znaleziono")
    return item

@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item: raise HTTPException(404, "Nie znaleziono")
    db.delete(item); db.commit()
