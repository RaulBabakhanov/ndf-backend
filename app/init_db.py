import asyncio

from sqlalchemy import text

from app.infrastructure.database import engine
from app.infrastructure.models import Base


async def init_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("ALTER TABLE dealers ADD COLUMN IF NOT EXISTS discount_percent NUMERIC(5, 2) NOT NULL DEFAULT 0"))
        # Existing dealers stay active; registrations explicitly set this field to false.
        await connection.execute(text("ALTER TABLE dealers ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT TRUE"))
        await connection.execute(text("ALTER TABLE dealers ALTER COLUMN is_approved SET DEFAULT FALSE"))
        await connection.execute(text("ALTER TABLE dealers ADD COLUMN IF NOT EXISTS address TEXT NOT NULL DEFAULT ''"))
        await connection.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_address TEXT NOT NULL DEFAULT ''"))
        await connection.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_company VARCHAR(100) NOT NULL DEFAULT ''"))
        await connection.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS tracking_number VARCHAR(150) NOT NULL DEFAULT ''"))


if __name__ == "__main__":
    asyncio.run(init_database())
