from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DealerModel(Base):
    __tablename__ = "dealers"
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(180))
    official: Mapped[str] = mapped_column(String(120))
    tax_number: Mapped[str] = mapped_column(String(11), unique=True)
    city: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(Text, default="", server_default="")
    phone: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductModel(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_url: Mapped[str] = mapped_column(String(500), unique=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str] = mapped_column(String(180), index=True)
    price_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    price_try: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    price_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    stock: Mapped[int] = mapped_column(default=1)


class OrderModel(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    dealer_id: Mapped[int] = mapped_column(ForeignKey("dealers.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="Hazırlanıyor")
    note: Mapped[str] = mapped_column(Text, default="")
    shipping_address: Mapped[str] = mapped_column(Text, default="", server_default="")
    shipping_company: Mapped[str] = mapped_column(String(100), default="", server_default="")
    tracking_number: Mapped[str] = mapped_column(String(150), default="", server_default="")
    total_try: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    items: Mapped[list["OrderItemModel"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class OrderItemModel(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    quantity: Mapped[int]
    unit_price_try: Mapped[Decimal] = mapped_column(Numeric(14, 2))
