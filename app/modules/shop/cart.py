from decimal import Decimal

import razorpay
from fastapi import Header, HTTPException, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.auth.models import generate_id
from app.modules.shop.models import Address, CartItem, Product


def get_razorpay_client() -> razorpay.Client:
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway is not configured.",
        )
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def require_session_id(x_session_id: str | None = Header(None, alias="X-Session-ID")) -> str:
    if not x_session_id or not x_session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Session-ID header is required.",
        )
    return x_session_id.strip()


def cart_items_filter(session_id: str, user_id: str | None):
    """Resolve cart rows for guest or authenticated checkout contexts."""
    if user_id:
        return or_(
            CartItem.user_id == user_id,
            and_(CartItem.session_id == session_id, CartItem.user_id.is_(None)),
        )
    return and_(CartItem.session_id == session_id, CartItem.user_id.is_(None))


async def fetch_cart_with_products(
    db: AsyncSession,
    session_id: str,
    user_id: str | None,
) -> list[tuple[CartItem, Product]]:
    stmt = (
        select(CartItem, Product)
        .join(Product, CartItem.product_id == Product.id)
        .where(cart_items_filter(session_id, user_id), Product.is_active.is_(True))
    )
    result = await db.execute(stmt)
    return list(result.all())


async def calculate_cart_total_paise(
    db: AsyncSession,
    session_id: str,
    user_id: str | None,
) -> tuple[int, list[tuple[CartItem, Product]]]:
    rows = await fetch_cart_with_products(db, session_id, user_id)
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty.")

    total = Decimal("0")
    for cart_item, product in rows:
        if product.stock_quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{product.title}' is out of stock.",
            )
        if cart_item.quantity > product.stock_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for product '{product.title}'.",
            )
        total += Decimal(str(product.price)) * cart_item.quantity

    amount_paise = int(total * 100)
    if amount_paise <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cart total.")

    return amount_paise, rows


async def get_user_address(
    db: AsyncSession,
    *,
    address_id: str,
    user_id: str,
) -> Address:
    address = (
        await db.execute(
            select(Address).where(Address.id == address_id, Address.user_id == user_id)
        )
    ).scalar_one_or_none()
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery address not found.",
        )
    return address


async def clear_cart(
    db: AsyncSession,
    session_id: str,
    user_id: str | None,
) -> None:
    await db.execute(delete(CartItem).where(cart_items_filter(session_id, user_id)))


async def upsert_cart_item(
    db: AsyncSession,
    *,
    session_id: str,
    user_id: str | None,
    product_id: str,
    quantity: int,
) -> None:
    product = (
        await db.execute(select(Product).where(Product.id == product_id, Product.is_active.is_(True)))
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    stmt = select(CartItem).where(
        CartItem.session_id == session_id,
        CartItem.product_id == product_id,
    )
    cart_item = (await db.execute(stmt)).scalar_one_or_none()

    if quantity <= 0:
        if cart_item is not None:
            await db.delete(cart_item)
        return

    if product.stock_quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This product is out of stock.",
        )

    if quantity > product.stock_quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {product.stock_quantity} units available.",
        )

    if cart_item is None:
        db.add(
            CartItem(
                id=generate_id(16),
                session_id=session_id,
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
            )
        )
        return

    cart_item.quantity = quantity
    if user_id is not None:
        cart_item.user_id = user_id


async def merge_guest_cart(
    db: AsyncSession,
    *,
    guest_session_id: str,
    user_id: str,
) -> int:
    guest_stmt = select(CartItem).where(
        CartItem.session_id == guest_session_id,
        CartItem.user_id.is_(None),
    )
    guest_items = (await db.execute(guest_stmt)).scalars().all()
    merged = 0

    for guest_item in guest_items:
        user_stmt = select(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.product_id == guest_item.product_id,
        )
        user_item = (await db.execute(user_stmt)).scalar_one_or_none()

        if user_item is not None:
            user_item.quantity += guest_item.quantity
            await db.delete(guest_item)
        else:
            guest_item.user_id = user_id

        merged += 1

    return merged
