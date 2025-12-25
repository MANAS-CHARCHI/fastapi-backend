from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from . import views, schemas

router = APIRouter()

@router.post("/", response_model=schemas.UserResponse)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    return await views.create_user_logic(user, db)

@router.get("/", response_model=list[schemas.UserResponse])
async def get_users(db: AsyncSession = Depends(get_db)):
    return await views.get_users_logic(db)
