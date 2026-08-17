import asyncio

from sqlalchemy import text

from app.infrastructure.database import engine
from app.infrastructure.models import Base


async def init_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("ALTER TABLE dealers ADD COLUMN IF NOT EXISTS discount_percent NUMERIC(5, 2) NOT NULL DEFAULT 0"))


if __name__ == "__main__":
    asyncio.run(init_database())
