from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import Users as User
from .schemas import UserCreate

async def create_user_logic(user: UserCreate, db: AsyncSession):
    db_user = User(email=user.email, password=user.password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_users_logic(db: AsyncSession):
    result = await db.execute(select(User))
    return result.scalars().all()
