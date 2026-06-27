from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import generate_id
from app.modules.shop.models import Address, Order, OrderItem, OrderStatusEvent, Product


ORDER_STATUS_LABELS = {
    "pending_payment": "Awaiting payment",
    "confirmed": "Order confirmed",
    "processing": "Processing",
    "shipped": "Shipped",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
}


def generate_order_number() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"RI-{stamp}-{generate_id(8).upper()}"


async def add_order_status_event(
    db: AsyncSession,
    *,
    order_id: str,
    status_value: str,
    message: str | None = None,
) -> None:
    db.add(
        OrderStatusEvent(
            id=generate_id(16),
            order_id=order_id,
            status=status_value,
            message=message or ORDER_STATUS_LABELS.get(status_value, status_value),
        )
    )


async def create_pending_order(
    db: AsyncSession,
    *,
    user_id: str,
    address: Address,
    amount_paise: int,
    razorpay_order_id: str,
    cart_rows: list[tuple],
) -> Order:
    existing = (
        await db.execute(select(Order).where(Order.razorpay_order_id == razorpay_order_id))
    ).scalar_one_or_none()
    if existing is not None:
        if existing.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Order access denied.")
        return existing

    order = Order(
        id=generate_id(16),
        user_id=user_id,
        address_id=address.id,
        order_number=generate_order_number(),
        status="pending_payment",
        amount_paise=amount_paise,
        currency="INR",
        razorpay_order_id=razorpay_order_id,
        delivery_full_name=address.full_name,
        delivery_phone=address.phone,
        delivery_line1=address.address_line1,
        delivery_line2=address.address_line2,
        delivery_city=address.city,
        delivery_state=address.state,
        delivery_pincode=address.pincode,
    )
    db.add(order)
    await db.flush()

    for _cart_item, product in cart_rows:
        unit_price = Decimal(str(product.price))
        quantity = _cart_item.quantity
        db.add(
            OrderItem(
                id=generate_id(16),
                order_id=order.id,
                product_id=product.id,
                title=product.title,
                img=product.img,
                unit_price=unit_price,
                quantity=quantity,
                line_total=unit_price * quantity,
            )
        )

    await add_order_status_event(
        db,
        order_id=order.id,
        status_value="pending_payment",
        message="Order created. Complete payment to confirm.",
    )
    return order


async def confirm_paid_order(
    db: AsyncSession,
    *,
    user_id: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
) -> Order:
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.status_events))
        .where(Order.razorpay_order_id == razorpay_order_id, Order.user_id == user_id)
    )
    order = (await db.execute(stmt)).scalar_one_or_none()

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    if order.status != "pending_payment":
        order.razorpay_payment_id = order.razorpay_payment_id or razorpay_payment_id
        return order

    for item in order.items:
        product = (
            await db.execute(select(Product).where(Product.id == item.product_id))
        ).scalar_one_or_none()
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{item.title}' is no longer available.",
            )
        if product.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for '{item.title}'.",
            )
        product.stock_quantity -= item.quantity

    order.status = "confirmed"
    order.razorpay_payment_id = razorpay_payment_id
    await add_order_status_event(
        db,
        order_id=order.id,
        status_value="confirmed",
        message="Payment received. Your order is confirmed.",
    )
    return order


async def get_user_order(
    db: AsyncSession,
    *,
    order_id: str,
    user_id: str,
) -> Order:
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.status_events))
        .where(Order.id == order_id, Order.user_id == user_id)
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


async def get_user_order_by_number(
    db: AsyncSession,
    *,
    order_number: str,
    user_id: str,
) -> Order:
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.status_events))
        .where(Order.order_number == order_number, Order.user_id == user_id)
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


async def list_user_orders(
    db: AsyncSession,
    *,
    user_id: str,
    page: int,
    limit: int,
    status_filter: str | None = None,
) -> tuple[list[Order], int]:
    filters = [Order.user_id == user_id]
    if status_filter:
        filters.append(Order.status == status_filter)

    total = (await db.execute(select(func.count(Order.id)).where(*filters))).scalar_one()

    offset = (page - 1) * limit
    stmt = (
        select(Order)
        .where(*filters)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    orders = (await db.execute(stmt)).scalars().all()
    return list(orders), total
