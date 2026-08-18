from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DealerCreate(BaseModel):
    company: str = Field(min_length=2, max_length=180)
    official: str = Field(min_length=2, max_length=120)
    tax_number: str = Field(pattern=r"^\d{10,11}$")
    city: str = Field(min_length=2, max_length=80)
    address: str = Field(default="", max_length=500)
    phone: str = Field(min_length=10, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class DealerRegistration(DealerCreate):
    turnstile_token: str = Field(min_length=1, max_length=2048)
    website: str = Field(default="", max_length=0)


class DealerDiscountUpdate(BaseModel):
    discount_percent: Decimal = Field(ge=0, le=100)


class DealerApprovalUpdate(BaseModel):
    is_approved: bool


class DealerLogin(BaseModel):
    email: EmailStr
    password: str
    turnstile_token: str = Field(min_length=1, max_length=2048)
    website: str = Field(default="", max_length=0)


class DealerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company: str
    official: str
    tax_number: str
    city: str
    address: str
    phone: str
    email: EmailStr
    discount_percent: Decimal
    is_approved: bool


class DealerRegistrationResponse(BaseModel):
    message: str
    dealer: DealerRead


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    dealer: DealerRead


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    price_usd: Decimal
    price_try: Decimal | None
    price_eur: Decimal | None
    default_currency: str
    image_url: str
    external_url: str
    stock: int


class ProductPage(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    size: int


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=999)


class OrderCreate(BaseModel):
    items: list[OrderItemCreate] = Field(min_length=1)
    note: str = Field(default="", max_length=500)
    shipping_address: str = Field(min_length=10, max_length=500)


class OrderStatusUpdate(BaseModel):
    status: Literal["Onaylandı", "Hazırlanıyor", "Kargoda", "Tamamlandı", "İptal"]


class OrderShippingUpdate(BaseModel):
    shipping_company: str = Field(min_length=2, max_length=100)
    tracking_number: str = Field(min_length=3, max_length=150)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    quantity: int
    unit_price_try: Decimal


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_number: str
    status: str
    note: str
    shipping_address: str
    shipping_company: str
    tracking_number: str
    total_try: Decimal
    created_at: datetime
    items: list[OrderItemRead]
