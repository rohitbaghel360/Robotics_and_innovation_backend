from sqlalchemy import (
    DECIMAL,
    TIMESTAMP,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.modules.auth.models import generate_id


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("idx_products_category", "category"),
        Index("idx_products_brand", "brand"),
        Index("idx_products_price", "price"),
        {"schema": "ri_web_auth"},
    )

    id = Column(String(25), primary_key=True, default=lambda: generate_id(16))
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True)
    img = Column(String(512), nullable=True)
    description = Column(Text)
    price = Column(DECIMAL(10, 2), nullable=False)
    compare_at_price = Column(DECIMAL(10, 2))
    stock_quantity = Column(Integer, default=0, nullable=False)
    category = Column(String(100), nullable=False)
    brand = Column(String(100), nullable=False)
    average_rating = Column(DECIMAL(3, 2), default=0.00, nullable=False)
    review_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    tag = Column(String(100), nullable=True)
    tagtype = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    reviews = relationship("ProductReview", back_populates="product", cascade="all, delete-orphan")


class ProductReview(Base):
    __tablename__ = "product_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="unique_user_product_review"),
        {"schema": "ri_web_auth"},
    )

    id = Column(String(25), primary_key=True, default=lambda: generate_id(16))
    product_id = Column(String(25), ForeignKey("ri_web_auth.products.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(25), ForeignKey("ri_web_auth.users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    product = relationship("Product", back_populates="reviews")


class ProductLike(Base):
    __tablename__ = "product_likes"
    __table_args__ = ({"schema": "ri_web_auth"},)

    user_id = Column(String(25), ForeignKey("ri_web_auth.users.id", ondelete="CASCADE"), primary_key=True)
    product_id = Column(String(25), ForeignKey("ri_web_auth.products.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


class SavedItem(Base):
    __tablename__ = "saved_items"
    __table_args__ = ({"schema": "ri_web_auth"},)

    user_id = Column(String(25), ForeignKey("ri_web_auth.users.id", ondelete="CASCADE"), primary_key=True)
    product_id = Column(String(25), ForeignKey("ri_web_auth.products.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = (
        Index("idx_addresses_user", "user_id"),
        {"schema": "ri_web_auth"},
    )

    id = Column(String(25), primary_key=True, default=lambda: generate_id(16))
    user_id = Column(String(25), ForeignKey("ri_web_auth.users.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(50), nullable=True)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    pincode = Column(String(10), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)


class CartItem(Base):
    """Ephemeral cart line item. IDs use VARCHAR(25) to match products/users FKs."""

    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("session_id", "product_id", name="unique_session_product"),
        {"schema": "ri_web_auth"},
    )

    id = Column(String(25), primary_key=True, default=lambda: generate_id(16))
    session_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(25), ForeignKey("ri_web_auth.users.id", ondelete="CASCADE"), nullable=True, index=True)
    product_id = Column(String(25), ForeignKey("ri_web_auth.products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("order_number", name="uq_orders_order_number"),
        UniqueConstraint("razorpay_order_id", name="uq_orders_razorpay_order_id"),
        Index("idx_orders_user", "user_id"),
        Index("idx_orders_status", "status"),
        {"schema": "ri_web_auth"},
    )

    id = Column(String(25), primary_key=True, default=lambda: generate_id(16))
    user_id = Column(String(25), ForeignKey("ri_web_auth.users.id", ondelete="CASCADE"), nullable=False)
    address_id = Column(String(25), ForeignKey("ri_web_auth.addresses.id", ondelete="SET NULL"), nullable=True)
    order_number = Column(String(32), nullable=False)
    status = Column(String(32), default="pending_payment", nullable=False)
    amount_paise = Column(Integer, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    razorpay_order_id = Column(String(64), nullable=True)
    razorpay_payment_id = Column(String(64), nullable=True)
    delivery_full_name = Column(String(255), nullable=False)
    delivery_phone = Column(String(20), nullable=False)
    delivery_line1 = Column(String(255), nullable=False)
    delivery_line2 = Column(String(255), nullable=True)
    delivery_city = Column(String(100), nullable=False)
    delivery_state = Column(String(100), nullable=False)
    delivery_pincode = Column(String(10), nullable=False)
    tracking_number = Column(String(64), nullable=True)
    carrier = Column(String(64), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_events = relationship(
        "OrderStatusEvent",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusEvent.created_at",
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        Index("idx_order_items_order", "order_id"),
        {"schema": "ri_web_auth"},
    )

    id = Column(String(25), primary_key=True, default=lambda: generate_id(16))
    order_id = Column(String(25), ForeignKey("ri_web_auth.orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(String(25), ForeignKey("ri_web_auth.products.id", ondelete="RESTRICT"), nullable=False)
    title = Column(String(255), nullable=False)
    img = Column(String(512), nullable=True)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    line_total = Column(DECIMAL(10, 2), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    order = relationship("Order", back_populates="items")


class OrderStatusEvent(Base):
    __tablename__ = "order_status_events"
    __table_args__ = (
        Index("idx_order_status_events_order", "order_id"),
        {"schema": "ri_web_auth"},
    )

    id = Column(String(25), primary_key=True, default=lambda: generate_id(16))
    order_id = Column(String(25), ForeignKey("ri_web_auth.orders.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(32), nullable=False)
    message = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    order = relationship("Order", back_populates="status_events")
