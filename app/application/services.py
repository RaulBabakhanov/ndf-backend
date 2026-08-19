from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status

from app.application.schemas import DealerCreate, DealerLogin, OrderCreate
from app.core.exchange_rates import get_exchange_rates
from app.core.security import create_access_token, hash_password, verify_password
from app.infrastructure.models import DealerModel, OrderItemModel, OrderModel
from app.infrastructure.repositories import (
    SqlAlchemyDealerRepository,
    SqlAlchemyOrderRepository,
    SqlAlchemyProductRepository,
)

def product_price_try(product, usd_try: Decimal, eur_try: Decimal) -> Decimal:
    if product.default_currency == "TRY" and product.price_try is not None:
        return Decimal(product.price_try)
    if product.default_currency == "EUR" and product.price_eur is not None:
        return Decimal(product.price_eur) * eur_try
    return Decimal(product.price_usd) * usd_try


class AuthService:
    def __init__(self, repository: SqlAlchemyDealerRepository) -> None:
        self.repository = repository

    async def register(self, data: DealerCreate) -> DealerModel:
        if await self.repository.get_by_email(str(data.email)):
            raise HTTPException(status.HTTP_409_CONFLICT, "Bu e-posta zaten kayıtlı")
        dealer = DealerModel(
            **data.model_dump(exclude={"password", "email"}),
            password_hash=hash_password(data.password),
            email=str(data.email).lower(),
            is_approved=False,
        )
        return await self.repository.add(dealer)

    async def login(self, data: DealerLogin) -> tuple[DealerModel, str]:
        dealer = await self.repository.get_by_email(str(data.email))
        if not dealer or not verify_password(data.password, dealer.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-posta veya şifre hatalı")
        if not dealer.is_approved:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bayi başvurunuz henüz yönetici tarafından onaylanmadı")
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
        rates = await get_exchange_rates()
        usd_try = Decimal(str(rates["usd_try"]))
        eur_try = Decimal(str(rates["eur_try"]))
        multiplier = Decimal("1") - Decimal(dealer.discount_percent or 0) / Decimal("100")
        items = [OrderItemModel(product_id=p.id, quantity=quantities[p.id], unit_price_try=(product_price_try(p, usd_try, eur_try) * multiplier).quantize(Decimal("0.01"))) for p in products]
        total = sum((item.unit_price_try * item.quantity for item in items), Decimal("0"))
        number = f"NDF-{datetime.now(UTC).strftime('%y%m%d%H%M%S%f')[-12:]}"
        return await self.orders.add(OrderModel(order_number=number, dealer_id=dealer.id, note=data.note, shipping_address=data.shipping_address, total_try=total, items=items))
