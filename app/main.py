from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import get_settings
from app.infrastructure.database import engine
from app.infrastructure.models import Base
from app.presentation.router import api_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        if get_settings().environment == "development":
            await connection.run_sync(Base.metadata.create_all)
            # create_all mevcut tabloları değiştirmez; eski kurulumları veri kaybı olmadan yükselt.
            await connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS price_try NUMERIC(14, 2)"))
            await connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS price_eur NUMERIC(12, 2)"))
            await connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS default_currency VARCHAR(3) NOT NULL DEFAULT 'USD'"))
        # Mevcut bayiler açık kalır; bu geçişten sonraki yeni başvurular onay bekler.
        await connection.execute(text("ALTER TABLE dealers ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT TRUE"))
        await connection.execute(text("ALTER TABLE dealers ALTER COLUMN is_approved SET DEFAULT FALSE"))
        await connection.execute(text("ALTER TABLE dealers ADD COLUMN IF NOT EXISTS address TEXT NOT NULL DEFAULT ''"))
        await connection.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_address TEXT NOT NULL DEFAULT ''"))
        await connection.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_company VARCHAR(100) NOT NULL DEFAULT ''"))
        await connection.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS tracking_number VARCHAR(150) NOT NULL DEFAULT ''"))
    yield
    await engine.dispose()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
Path("uploads").mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
