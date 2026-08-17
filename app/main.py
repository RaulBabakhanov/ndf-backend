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
    if get_settings().environment == "development":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            # create_all mevcut tabloları değiştirmez; eski kurulumları veri kaybı olmadan yükselt.
            await connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS price_try NUMERIC(14, 2)"))
            await connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS price_eur NUMERIC(12, 2)"))
            await connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS default_currency VARCHAR(3) NOT NULL DEFAULT 'USD'"))
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
