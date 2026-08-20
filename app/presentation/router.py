from collections import defaultdict, deque
from hmac import compare_digest
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from pathlib import Path
from uuid import uuid4

from app.application.schemas import (
    AuthResponse,
    AdminLogin,
    DealerApprovalUpdate,
    DealerAdminUpdate,
    DealerCreate,
    DealerDiscountUpdate,
    DealerLogin,
    DealerRegistration,
    DealerRead,
    DealerRegistrationResponse,
    OrderCreate,
    OrderRead,
    OrderShippingUpdate,
    OrderStatusUpdate,
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
from app.core.security import create_access_token, decode_access_token, hash_password
from app.core.turnstile import verify_turnstile
from app.core.exchange_rates import get_exchange_rates
from app.infrastructure.models import DealerModel, OrderItemModel, OrderModel, ProductModel

api_router = APIRouter(prefix="/api/v1")
auth_attempts: dict[str, deque[float]] = defaultdict(deque)


def limit_auth_attempts(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = monotonic()
    attempts = auth_attempts[client_ip]
    while attempts and now - attempts[0] > 300:
        attempts.popleft()
    if len(attempts) >= 12:
        raise HTTPException(status_code=429, detail="Çok fazla deneme yapıldı. 5 dakika sonra tekrar deneyin.")
    attempts.append(now)


def require_admin(
    authorization: str = Header(default=""),
    x_admin_key: str = Header(default=""),
) -> None:
    settings = get_settings()
    if authorization.startswith("Bearer "):
        try:
            subject = decode_access_token(authorization.removeprefix("Bearer ").strip())
            if subject == f"admin:{settings.admin_username}":
                return
        except Exception:
            pass
    if settings.environment == "development" and settings.admin_key and compare_digest(
        x_admin_key.encode("utf-8"), settings.admin_key.encode("utf-8")
    ):
        return
    raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş yönetici oturumu")


@api_router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@api_router.get("/exchange-rates", tags=["system"])
async def exchange_rates() -> dict[str, object]:
    return await get_exchange_rates()


@api_router.post("/auth/register", response_model=DealerRegistrationResponse, status_code=201, tags=["auth"])
async def register(data: DealerRegistration, session: SessionDep, request: Request) -> DealerRegistrationResponse:
    limit_auth_attempts(request)
    await verify_turnstile(data.turnstile_token, request.client.host if request.client else None)
    dealer_data = DealerCreate.model_validate(data.model_dump(exclude={"turnstile_token", "website"}))
    dealer = await AuthService(SqlAlchemyDealerRepository(session)).register(dealer_data)
    return DealerRegistrationResponse(
        message="Başvurunuz alındı. Yönetici onayından sonra giriş yapabilirsiniz.",
        dealer=DealerRead.model_validate(dealer),
    )


@api_router.post("/auth/login", response_model=AuthResponse, tags=["auth"])
async def login(data: DealerLogin, session: SessionDep, request: Request) -> AuthResponse:
    limit_auth_attempts(request)
    await verify_turnstile(data.turnstile_token, request.client.host if request.client else None)
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
            "note": order.note, "shipping_address": order.shipping_address, "shipping_company": order.shipping_company, "tracking_number": order.tracking_number, "total_try": str(order.total_try), "created_at": order.created_at,
            "dealer": {"company": dealer.company, "official": dealer.official, "email": dealer.email, "phone": dealer.phone, "address": dealer.address},
            "items": [],
        })
        entry["items"].append({"name": product.name, "quantity": item.quantity, "unit_price_try": str(item.unit_price_try)})
    return {
        "dealers": [{"id": d.id, "company": d.company, "official": d.official, "tax_number": d.tax_number, "email": d.email, "phone": d.phone, "city": d.city, "address": d.address, "discount_percent": str(d.discount_percent), "is_approved": d.is_approved, "created_at": d.created_at} for d in dealers],
        "orders": list(orders.values()),
        "products": [{"id": p.id, "name": p.name, "category": p.category, "price_usd": str(p.price_usd), "price_try": str(p.price_try) if p.price_try is not None else "", "price_eur": str(p.price_eur) if p.price_eur is not None else "", "default_currency": p.default_currency, "stock": p.stock, "image_url": p.image_url} for p in (await session.scalars(select(ProductModel).order_by(ProductModel.id.desc()))).all()],
    }


@api_router.post("/admin/login", tags=["admin"])
async def admin_login(
    data: AdminLogin,
    request: Request,
    session: SessionDep,
    x_turnstile_token: str = Header(default=""),
) -> dict:
    limit_auth_attempts(request)
    await verify_turnstile(x_turnstile_token, request.client.host if request.client else None)
    settings = get_settings()
    if not settings.admin_key or not (
        compare_digest(data.username.encode("utf-8"), settings.admin_username.encode("utf-8"))
        and compare_digest(data.password.encode("utf-8"), settings.admin_key.encode("utf-8"))
    ):
        raise HTTPException(status_code=401, detail="Yönetici kullanıcı adı veya şifresi hatalı")
    return {
        "access_token": create_access_token(f"admin:{settings.admin_username}"),
        "token_type": "bearer",
        "dashboard": await admin_dashboard(session),
    }


@api_router.patch("/admin/orders/{order_id}/status", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_update_order_status(order_id: int, data: OrderStatusUpdate, session: SessionDep) -> dict:
    order = await session.get(OrderModel, order_id)
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı")
    order.status = data.status
    await session.commit()
    return {"id": order.id, "status": order.status}


@api_router.patch("/admin/orders/{order_id}/shipping", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_update_order_shipping(order_id: int, data: OrderShippingUpdate, session: SessionDep) -> dict:
    order = await session.get(OrderModel, order_id)
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı")
    order.shipping_company = data.shipping_company.strip()
    order.tracking_number = data.tracking_number.strip()
    order.status = "Kargoda"
    await session.commit()
    return {
        "id": order.id,
        "status": order.status,
        "shipping_company": order.shipping_company,
        "tracking_number": order.tracking_number,
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
        image_url = f"/uploads/{filename}"
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


@api_router.delete("/admin/products/{product_id}", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_delete_product(product_id: int, session: SessionDep) -> dict:
    product = await session.get(ProductModel, product_id)
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")
    used_in_order = await session.scalar(
        select(OrderItemModel.id).where(OrderItemModel.product_id == product_id).limit(1)
    )
    if used_in_order:
        raise HTTPException(409, "Sipariş geçmişinde bulunan ürün silinemez")
    await session.delete(product)
    await session.commit()
    return {"ok": True}


@api_router.post("/admin/dealers", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_create_dealer(data: DealerCreate, session: SessionDep) -> dict:
    existing = await session.scalar(select(DealerModel).where((DealerModel.email == data.email.lower()) | (DealerModel.tax_number == data.tax_number)))
    if existing: raise HTTPException(409, "E-posta veya vergi numarası zaten kayıtlı")
    dealer = DealerModel(company=data.company, official=data.official, tax_number=data.tax_number, city=data.city, address=data.address, phone=data.phone, email=data.email.lower(), password_hash=hash_password(data.password), is_approved=True)
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


@api_router.patch("/admin/dealers/{dealer_id}", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_update_dealer(dealer_id: int, data: DealerAdminUpdate, session: SessionDep) -> dict:
    dealer = await session.get(DealerModel, dealer_id)
    if not dealer:
        raise HTTPException(404, "Cari bulunamadı")
    email = data.email.lower()
    duplicate = await session.scalar(
        select(DealerModel.id).where(
            DealerModel.id != dealer_id,
            (DealerModel.email == email) | (DealerModel.tax_number == data.tax_number),
        ).limit(1)
    )
    if duplicate:
        raise HTTPException(409, "E-posta veya vergi numarası başka bir caride kayıtlı")
    dealer.company = data.company
    dealer.official = data.official
    dealer.tax_number = data.tax_number
    dealer.city = data.city
    dealer.address = data.address
    dealer.phone = data.phone
    dealer.email = email
    await session.commit()
    return {"id": dealer.id, "company": dealer.company}


@api_router.patch("/admin/dealers/{dealer_id}/approval", dependencies=[Depends(require_admin)], tags=["admin"])
async def admin_update_dealer_approval(dealer_id: int, data: DealerApprovalUpdate, session: SessionDep) -> dict:
    dealer = await session.get(DealerModel, dealer_id)
    if not dealer:
        raise HTTPException(404, "Cari bulunamadı")
    dealer.is_approved = data.is_approved
    await session.commit()
    return {"id": dealer.id, "is_approved": dealer.is_approved}


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
