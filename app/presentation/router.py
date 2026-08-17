from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from sqlalchemy import select
from pathlib import Path
from uuid import uuid4

from app.application.schemas import (
    AuthResponse,
    DealerCreate,
    DealerDiscountUpdate,
    DealerLogin,
    DealerRead,
    OrderCreate,
    OrderRead,
    ProductPage,
    ProductRead,
)
from app.application.services import AuthService, OrderService
from app.infrastructure.repositories import (
    SqlAlchemyDealerRepository,
    SqlAlchemyOrderRepository,
    SqlAlchemyProductRepository,
)
from app.presentation.dependencies import CurrentDealer, SessionDep
from app.core.config import get_settings
from app.core.security import hash_password
from app.infrastructure.models import DealerModel, OrderItemModel, OrderModel, ProductModel

api_router = APIRouter(prefix="/api/v1")


def require_admin(x_admin_key: str = Header(default="")) -> None:
    configured_key = get_settings().admin_key
    if not configured_key or x_admin_key != configured_key:
        raise HTTPException(status_code=401, detail="Geçersiz yönetici anahtarı")


@api_router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@api_router.post("/auth/register", response_model=AuthResponse, status_code=201, tags=["auth"])
async def register(data: DealerCreate, session: SessionDep) -> AuthResponse:
    dealer, token = await AuthService(SqlAlchemyDealerRepository(session)).register(data)
    return AuthResponse(access_token=token, dealer=DealerRead.model_validate(dealer))


@api_router.post("/auth/login", response_model=AuthResponse, tags=["auth"])
async def login(data: DealerLogin, session: SessionDep) -> AuthResponse:
    dealer, token = await AuthService(SqlAlchemyDealerRepository(session)).login(data)
    return AuthResponse(access_token=token, dealer=DealerRead.model_validate(dealer))


@api_router.get("/auth/me", response_model=DealerRead, tags=["auth"])
async def me(dealer: CurrentDealer) -> DealerRead:
    return DealerRead.model_validate(dealer)


@api_router.get("/products", response_model=ProductPage, tags=["products"])
async def list_products(
    session: SessionDep,
    search: str | None = None,
    category: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 24,
) -> ProductPage:
    items, total = await SqlAlchemyProductRepository(session).list(search, category, page, size)
    return ProductPage(items=[ProductRead.model_validate(item) for item in items], total=total, page=page, size=size)


@api_router.get("/orders", response_model=list[OrderRead], tags=["orders"])
async def list_orders(dealer: CurrentDealer, session: SessionDep) -> list[OrderRead]:
    orders = await SqlAlchemyOrderRepository(session).list_for_dealer(dealer.id)
    return [OrderRead.model_validate(order) for order in orders]


@api_router.post("/orders", response_model=OrderRead, status_code=201, tags=["orders"])
async def create_order(data: OrderCreate, dealer: CurrentDealer, session: SessionDep) -> OrderRead:
    service = OrderService(SqlAlchemyOrderRepository(session), SqlAlchemyProductRepository(session))
    return OrderRead.model_validate(await service.create(dealer, data))


@api_router.get("/admin/dashboard", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_dashboard(session: SessionDep) -> dict:
    dealers = (await session.scalars(select(DealerModel).order_by(DealerModel.created_at.desc()))).all()
    rows = (await session.execute(
        select(OrderModel, DealerModel, OrderItemModel, ProductModel)
        .join(DealerModel, DealerModel.id == OrderModel.dealer_id)
        .join(OrderItemModel, OrderItemModel.order_id == OrderModel.id)
        .join(ProductModel, ProductModel.id == OrderItemModel.product_id)
        .order_by(OrderModel.created_at.desc())
    )).all()
    orders: dict[int, dict] = {}
    for order, dealer, item, product in rows:
        entry = orders.setdefault(order.id, {
            "id": order.id, "order_number": order.order_number, "status": order.status,
            "note": order.note, "total_try": str(order.total_try), "created_at": order.created_at,
            "dealer": {"company": dealer.company, "official": dealer.official, "email": dealer.email, "phone": dealer.phone},
            "items": [],
        })
        entry["items"].append({"name": product.name, "quantity": item.quantity, "unit_price_try": str(item.unit_price_try)})
    return {
        "dealers": [{"id": d.id, "company": d.company, "official": d.official, "email": d.email, "phone": d.phone, "city": d.city, "discount_percent": str(d.discount_percent), "created_at": d.created_at} for d in dealers],
        "orders": list(orders.values()),
        "products": [{"id": p.id, "name": p.name, "category": p.category, "price_usd": str(p.price_usd), "price_try": str(p.price_try) if p.price_try is not None else "", "price_eur": str(p.price_eur) if p.price_eur is not None else "", "default_currency": p.default_currency, "stock": p.stock, "image_url": p.image_url} for p in (await session.scalars(select(ProductModel).order_by(ProductModel.id.desc()))).all()],
    }


@api_router.post("/admin/products", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_create_product(session: SessionDep, name: str = Form(...), category: str = Form(...), price_usd: float | None = Form(default=None), price_try: float | None = Form(default=None), price_eur: float | None = Form(default=None), default_currency: str = Form(default="USD"), stock: int = Form(...), image: UploadFile | None = File(default=None)) -> dict:
    prices = {"USD": price_usd, "TRY": price_try, "EUR": price_eur}
    if default_currency not in prices or prices[default_currency] is None:
        raise HTTPException(400, "Varsayılan para birimi için fiyat girilmelidir")
    image_url = ""
    if image and image.filename:
        extension = Path(image.filename).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            raise HTTPException(400, "Geçersiz fotoğraf formatı")
        filename = f"{uuid4().hex}{extension}"
        content = await image.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(400, "Fotoğraf en fazla 5 MB olabilir")
        Path("uploads", filename).write_bytes(content)
        image_url = f"https://api.ndf.allspacesoftware.com/uploads/{filename}"
    product = ProductModel(external_url=f"admin://{uuid4().hex}", name=name, category=category, price_usd=price_usd or 0, price_try=price_try, price_eur=price_eur, default_currency=default_currency, stock=max(0, stock), image_url=image_url)
    session.add(product); await session.commit(); await session.refresh(product)
    return {"id": product.id, "name": product.name}


@api_router.patch("/admin/products/{product_id}", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_update_product(product_id: int, session: SessionDep, stock: int = Form(...), price_usd: float | None = Form(default=None), price_try: float | None = Form(default=None), price_eur: float | None = Form(default=None), default_currency: str = Form(default="USD")) -> dict:
    product = await session.get(ProductModel, product_id)
    if not product: raise HTTPException(404, "Ürün bulunamadı")
    product.stock = max(0, stock)
    prices = {"USD": price_usd, "TRY": price_try, "EUR": price_eur}
    if default_currency not in prices or prices[default_currency] is None:
        raise HTTPException(400, "Varsayılan para birimi için fiyat girilmelidir")
    product.price_usd = price_usd or 0
    product.price_try = price_try
    product.price_eur = price_eur
    product.default_currency = default_currency
    await session.commit()
    return {"ok": True}


@api_router.post("/admin/dealers", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_create_dealer(data: DealerCreate, session: SessionDep) -> dict:
    existing = await session.scalar(select(DealerModel).where((DealerModel.email == data.email.lower()) | (DealerModel.tax_number == data.tax_number)))
    if existing: raise HTTPException(409, "E-posta veya vergi numarası zaten kayıtlı")
    dealer = DealerModel(company=data.company, official=data.official, tax_number=data.tax_number, city=data.city, phone=data.phone, email=data.email.lower(), password_hash=hash_password(data.password))
    session.add(dealer); await session.commit(); await session.refresh(dealer)
    return {"id": dealer.id, "company": dealer.company}


@api_router.patch("/admin/dealers/{dealer_id}/discount", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_update_dealer_discount(dealer_id: int, data: DealerDiscountUpdate, session: SessionDep) -> dict:
    dealer = await session.get(DealerModel, dealer_id)
    if not dealer:
        raise HTTPException(404, "Cari bulunamadı")
    dealer.discount_percent = data.discount_percent
    await session.commit()
    return {"id": dealer.id, "discount_percent": str(dealer.discount_percent)}


@api_router.delete("/admin/dealers/{dealer_id}", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_delete_dealer(dealer_id: int, session: SessionDep) -> dict:
    dealer = await session.get(DealerModel, dealer_id)
    if not dealer:
        raise HTTPException(404, "Cari bulunamadı")
    has_orders = await session.scalar(select(OrderModel.id).where(OrderModel.dealer_id == dealer_id).limit(1))
    if has_orders:
        raise HTTPException(409, "Sipariş geçmişi bulunan cari silinemez")
    await session.delete(dealer)
    await session.commit()
    return {"ok": True}
