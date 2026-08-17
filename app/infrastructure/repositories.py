from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import DealerModel, OrderModel, ProductModel


class SqlAlchemyDealerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> DealerModel | None:
        return await self.session.scalar(select(DealerModel).where(DealerModel.email == email.lower()))

    async def get_by_id(self, dealer_id: int) -> DealerModel | None:
        return await self.session.get(DealerModel, dealer_id)

    async def add(self, dealer: DealerModel) -> DealerModel:
        self.session.add(dealer)
        await self.session.commit()
        await self.session.refresh(dealer)
        return dealer


class SqlAlchemyProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, search: str | None, category: str | None, page: int, size: int) -> tuple[list[ProductModel], int]:
        filters = []
        if search:
            filters.append(ProductModel.name.ilike(f"%{search}%"))
        if category:
            filters.append(ProductModel.category == category)
        count = await self.session.scalar(select(func.count(ProductModel.id)).where(*filters))
        statement = select(ProductModel).where(*filters).order_by(ProductModel.id).offset((page - 1) * size).limit(size)
        return list((await self.session.scalars(statement)).all()), int(count or 0)

    async def get_many(self, product_ids: list[int]) -> list[ProductModel]:
        return list((await self.session.scalars(select(ProductModel).where(ProductModel.id.in_(product_ids)))).all())


class SqlAlchemyOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_dealer(self, dealer_id: int) -> list[OrderModel]:
        statement = select(OrderModel).where(OrderModel.dealer_id == dealer_id).order_by(OrderModel.created_at.desc())
        return list((await self.session.scalars(statement)).all())

    async def add(self, order: OrderModel) -> OrderModel:
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order, attribute_names=["items"])
        return order
