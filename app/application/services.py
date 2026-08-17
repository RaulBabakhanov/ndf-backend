from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status

from app.application.schemas import DealerCreate, DealerLogin, OrderCreate
from app.core.security import create_access_token, hash_password, verify_password
from app.infrastructure.models import DealerModel, OrderItemModel, OrderModel
from app.infrastructure.repositories import (
    SqlAlchemyDealerRepository,
    SqlAlchemyOrderRepository,
    SqlAlchemyProductRepository,
)

USD_TO_TRY = Decimal("47.7364")
EUR_TO_TRY = Decimal("55.75")


def product_price_try(product) -> Decimal:
    if product.default_currency == "TRY" and product.price_try is not None:
        return Decimal(product.price_try)
    if product.default_currency == "EUR" and product.price_eur is not None:
        return Decimal(product.price_eur) * EUR_TO_TRY
    return Decimal(product.price_usd) * USD_TO_TRY


class AuthService:
    def __init__(self, repository: SqlAlchemyDealerRepository) -> None:
        self.repository = repository

    async def register(self, data: DealerCreate) -> tuple[DealerModel, str]:
        if await self.repository.get_by_email(str(data.email)):
            raise HTTPException(status.HTTP_409_CONFLICT, "Bu e-posta zaten kayıtlı")
        dealer = DealerModel(
            **data.model_dump(exclude={"password", "email"}),
            password_hash=hash_password(data.password),
            email=str(data.email).lower(),
        )
        dealer = await self.repository.add(dealer)
        return dealer, create_access_token(str(dealer.id))

    async def login(self, data: DealerLogin) -> tuple[DealerModel, str]:
        dealer = await self.repository.get_by_email(str(data.email))
        if not dealer or not verify_password(data.password, dealer.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-posta veya şifre hatalı")
        return dealer, create_access_token(str(dealer.id))


class OrderService:
    def __init__(self, orders: SqlAlchemyOrderRepository, products: SqlAlchemyProductRepository) -> None:
        self.orders = orders
        self.products = products

    async def create(self, dealer: DealerModel, data: OrderCreate) -> OrderModel:
        quantities = {item.product_id: item.quantity for item in data.items}
        products = await self.products.get_many(list(quantities))
        if len(products) != len(quantities):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bir veya daha fazla ürün bulunamadı")
        multiplier = Decimal("1") - Decimal(dealer.discount_percent or 0) / Decimal("100")
        items = [OrderItemModel(product_id=p.id, quantity=quantities[p.id], unit_price_try=(product_price_try(p) * multiplier).quantize(Decimal("0.01"))) for p in products]
        total = sum((item.unit_price_try * item.quantity for item in items), Decimal("0"))
        number = f"NDF-{datetime.now(UTC).strftime('%y%m%d%H%M%S%f')[-12:]}"
        return await self.orders.add(OrderModel(order_number=number, dealer_id=dealer.id, note=data.note, total_try=total, items=items))
