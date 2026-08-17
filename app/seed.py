import asyncio
import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.infrastructure.database import session_factory
from app.infrastructure.models import ProductModel


async def seed_products() -> None:
    source = Path(__file__).parent.parent / "data" / "products.json"
    payload = source.read_text(encoding="utf-8-sig").strip()
    if payload.startswith("[] = "):
        payload = payload.removeprefix("[] = ")
    products = json.loads(payload)
    async with session_factory() as session:
        existing_urls = set((await session.scalars(select(ProductModel.external_url))).all())
        session.add_all(
            ProductModel(
                external_url=item["url"],
                name=item["name"],
                category=item["category"],
                price_usd=Decimal(str(item["price"])),
                image_url=item["image"],
                stock=item.get("stock", 1),
            )
            for item in products
            if item["url"] not in existing_urls
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_products())
