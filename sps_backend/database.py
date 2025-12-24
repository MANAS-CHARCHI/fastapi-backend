from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import os, sys
from dotenv import load_dotenv
load_dotenv(".env")
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session