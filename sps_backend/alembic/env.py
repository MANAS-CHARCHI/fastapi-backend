from logging.config import fileConfig
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import asyncio
# 1. Load your models and metadata
import models  # Ensure this points to your file with "class Base(DeclarativeBase):"
target_metadata = models.Base.metadata

# 2. Setup environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

config = context.config
db_url = os.getenv('DATABASE_URL')
if db_url:
    config.set_main_option('sqlalchemy.url', db_url)


def do_run_migrations(connection):
    """
    This helper function runs migrations in a synchronous context 
    provided by the async connection's 'run_sync' method.
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an AsyncEngine."""
    
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # Use run_sync to execute the synchronous Alembic code
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # Use asyncio.run to execute the async function
    asyncio.run(run_migrations_online())