"""
Import all ORM models here so metadata is registered before create_all.

When adding a new module, import its models in this file.
"""

from app.modules.auth.models import LinkedAccount, LocalCredential, User, UserOtp  # noqa: F401
from app.modules.shop.models import (  # noqa: F401
    Address,
    CartItem,
    Order,
    OrderItem,
    OrderStatusEvent,
    Product,
    ProductLike,
    ProductReview,
    SavedItem,
)

__all__ = [
    "User",
    "LinkedAccount",
    "LocalCredential",
    "UserOtp",
    "Product",
    "ProductReview",
    "ProductLike",
    "SavedItem",
    "CartItem",
    "Address",
    "Order",
    "OrderItem",
    "OrderStatusEvent",
]
