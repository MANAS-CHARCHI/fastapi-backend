from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db # Import from your database file
from schemas import UserCreate, UserResponse
from models import Users as User
app = FastAPI()

@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = User(email=user.email, password=user.password)
    db.add(db_user)
    await db.commit()      # Must be awaited in async mode
    await db.refresh(db_user)
    return db_user

@app.get("/users/", response_model=list[UserResponse])
async def get_users(db: AsyncSession = Depends(get_db)):
    # Async queries use select() and execute()
    result = await db.execute(select(User))
    return result.scalars().all()
