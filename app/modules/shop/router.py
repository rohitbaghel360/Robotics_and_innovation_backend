import math
from typing import Literal

import razorpay
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.core.deps import get_current_user_id
from app.modules.auth.models import generate_id
from app.modules.shop.cart import (
    calculate_cart_total_paise,
    clear_cart,
    fetch_cart_with_products,
    get_razorpay_client,
    get_user_address,
    merge_guest_cart,
    require_session_id,
    upsert_cart_item,
)
from app.modules.shop.models import Address, Order, Product, ProductLike, ProductReview, SavedItem
from app.modules.shop.orders import (
    ORDER_STATUS_LABELS,
    confirm_paid_order,
    create_pending_order,
    get_user_order,
    get_user_order_by_number,
    list_user_orders,
)

router = APIRouter(tags=["Shop Core"])


class ProductResponse(BaseModel):
    id: str
    title: str
    slug: str
    img_url: str | None = None
    img: str | None = None
    description: str | None
    price: float
    compare_at_price: float | None
    stock_quantity: int
    in_stock: bool
    category: str
    brand: str
    tag: str | None = None
    tagtype: str | None = None
    average_rating: float
    review_count: int


class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating scale must fall between 1 and 5")
    comment: str | None = None


class ReviewResponse(BaseModel):
    id: str
    product_id: str
    user_id: str
    rating: int
    comment: str | None = None
    created_at: str


class WishlistItemResponse(BaseModel):
    product_id: str
    saved: bool = True
    product: ProductResponse


class WishlistResponse(BaseModel):
    items: list[WishlistItemResponse]


class StorefrontResponse(BaseModel):
    items: list[ProductResponse]
    page: int
    limit: int
    total: int
    total_pages: int
    filters: dict


class CategoriesResponse(BaseModel):
    """Sidebar filter categories: [[label, product_count], ...]"""

    categories: list[list[str | int]]

class BrandsResponse(BaseModel):
    brands: list[str]


class TagTypesResponse(BaseModel):
    tagtypes: list[str]


class CartUpdateRequest(BaseModel):
    product_id: str
    quantity: int = Field(ge=0)


class CartMergeRequest(BaseModel):
    guest_session_id: str = Field(min_length=1, max_length=50)


class CheckoutCreateOrderRequest(BaseModel):
    address_id: str = Field(min_length=1, max_length=25)


class CheckoutVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class CartItemResponse(BaseModel):
    id: str
    product_id: str
    quantity: int
    title: str
    price: float
    img_url: str | None = None
    stock_quantity: int
    in_stock: bool


class AddressBase(BaseModel):
    label: str | None = Field(None, max_length=50)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=10, max_length=20)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    pincode: str = Field(min_length=6, max_length=10)
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    label: str | None = Field(None, max_length=50)
    full_name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, min_length=10, max_length=20)
    address_line1: str | None = Field(None, min_length=1, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, min_length=1, max_length=100)
    state: str | None = Field(None, min_length=1, max_length=100)
    pincode: str | None = Field(None, min_length=6, max_length=10)
    is_default: bool | None = None


class AddressResponse(AddressBase):
    id: str

    model_config = {"from_attributes": True}


OrderStatus = Literal[
    "pending_payment",
    "confirmed",
    "processing",
    "shipped",
    "delivered",
    "cancelled",
]


class OrderItemResponse(BaseModel):
    product_id: str
    title: str
    quantity: int
    unit_price: float
    line_total: float
    img_url: str | None = None


class OrderTimelineEventResponse(BaseModel):
    status: str
    status_label: str
    message: str | None = None
    created_at: str


class DeliveryAddressResponse(BaseModel):
    full_name: str
    phone: str
    address_line1: str
    address_line2: str | None = None
    city: str
    state: str
    pincode: str


class OrderSummaryResponse(BaseModel):
    id: str
    order_number: str
    status: OrderStatus
    status_label: str
    amount: float
    currency: str
    item_count: int
    created_at: str


class OrderDetailResponse(OrderSummaryResponse):
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    tracking_number: str | None = None
    carrier: str | None = None
    delivery_address: DeliveryAddressResponse
    items: list[OrderItemResponse]
    timeline: list[OrderTimelineEventResponse]


class OrderListResponse(BaseModel):
    items: list[OrderSummaryResponse]
    page: int
    limit: int
    total: int
    total_pages: int


SortBy = Literal["popular", "newest", "price_asc", "price_desc", "rating"]


def _tagtype_label(tagtype: str) -> str:
    return tagtype.strip().capitalize()


async def _resolve_product(db: AsyncSession, product_id: str) -> Product:
    """Find product by primary id or slug (for review/detail URLs)."""
    product = (
        await db.execute(select(Product).where(Product.id == product_id))
    ).scalar_one_or_none()
    if product is None:
        product = (
            await db.execute(select(Product).where(Product.slug == product_id))
        ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product


def _product_to_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "slug": p.slug,
        "img_url": p.img,
        "img": p.img,
        "description": p.description,
        "price": float(p.price),
        "compare_at_price": float(p.compare_at_price) if p.compare_at_price else None,
        "stock_quantity": p.stock_quantity,
        "in_stock": p.stock_quantity > 0,
        "category": p.category,
        "brand": p.brand,
        "average_rating": float(p.average_rating),
        "review_count": p.review_count,
        "tag": p.tag,
        "tagtype": p.tagtype,
    }


def _apply_product_filters(
    stmt,
    *,
    categories: list[str] | None = None,
    brands: list[str] | None = None,
    tagtypes: list[str] | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
):
    stmt = stmt.where(Product.is_active.is_(True))
    if categories:
        stmt = stmt.where(Product.category.in_(categories))
    if brands:
        stmt = stmt.where(Product.brand.in_(brands))
    if tagtypes:
        stmt = stmt.where(Product.tagtype.in_(tagtypes))
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    return stmt


def _build_applied_filters(
    *,
    categories: list[str] | None,
    brands: list[str] | None,
    tagtypes: list[str] | None,
    min_price: float | None,
    max_price: float | None,
    sort_by: str,
) -> dict:
    return {
        "category": categories or [],
        "brand": brands or [],
        "tagtype": tagtypes or [],
        "min_price": min_price,
        "max_price": max_price,
        "sort_by": sort_by,
    }


def _apply_sort(stmt, sort_by: SortBy):
    if sort_by == "popular":
        return stmt.order_by(Product.review_count.desc(), Product.average_rating.desc())
    if sort_by == "newest":
        return stmt.order_by(Product.created_at.desc())
    if sort_by == "price_asc":
        return stmt.order_by(Product.price.asc())
    if sort_by == "price_desc":
        return stmt.order_by(Product.price.desc())
    if sort_by == "rating":
        return stmt.order_by(Product.average_rating.desc(), Product.review_count.desc())
    return stmt


@router.get("/categories", response_model=CategoriesResponse)
async def list_shop_categories(db: AsyncSession = Depends(get_db)):
    """Returns storefront sidebar categories grouped by tagtype with counts."""
    stmt = (
        select(Product.category, func.count(Product.id))
        .where(Product.is_active.is_(True), Product.category.isnot(None))
        .group_by(Product.category)
        .order_by(func.count(Product.id).desc())
    )
    result = await db.execute(stmt)
    categories = [[_tagtype_label(row[0]), row[1]] for row in result.all()]
    return CategoriesResponse(categories=categories)


@router.get("/brands", response_model=BrandsResponse)
async def list_shop_brands(db: AsyncSession = Depends(get_db)):
    """Returns distinct product brands for storefront filters."""
    stmt = (
        select(Product.brand)
        .where(Product.is_active.is_(True))
        .distinct()
        .order_by(Product.brand.asc())
    )
    result = await db.execute(stmt)
    brands = [row[0] for row in result.all()]
    return BrandsResponse(brands=brands)


@router.get("/tagtypes", response_model=TagTypesResponse)
async def list_tagtypes(db: AsyncSession = Depends(get_db)):
    """Returns all distinct tagtype values from active products."""
    stmt = (
        select(Product.tagtype)
        .where(Product.is_active.is_(True), Product.tagtype.isnot(None))
        .distinct()
        .order_by(Product.tagtype.asc())
    )
    result = await db.execute(stmt)
    tagtypes = [row[0] for row in result.all()]
    return TagTypesResponse(tagtypes=tagtypes)


@router.get("/storefront", response_model=StorefrontResponse)
async def get_storefront(
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    sort_by: SortBy = Query("popular"),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    category: list[str] | None = Query(None, description="Repeat for multi-select, e.g. ?category=A&category=B"),
    brand: list[str] | None = Query(None, description="Repeat for multi-select, e.g. ?brand=Generic&brand=Other"),
    tagtype: list[str] | None = Query(None, description="Repeat for multi-select, e.g. ?tagtype=new&tagtype=discount"),
    db: AsyncSession = Depends(get_db),
):
    """Paginated storefront catalog with multi-select filters and sorting."""
    applied = _build_applied_filters(
        categories=category,
        brands=brand,
        tagtypes=tagtype,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
    )

    base = select(Product)
    base = _apply_product_filters(
        base,
        categories=category,
        brands=brand,
        tagtypes=tagtype,
        min_price=min_price,
        max_price=max_price,
    )

    count_stmt = select(func.count(Product.id))
    count_stmt = _apply_product_filters(
        count_stmt,
        categories=category,
        brands=brand,
        tagtypes=tagtype,
        min_price=min_price,
        max_price=max_price,
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = _apply_sort(base, sort_by)
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    products = result.scalars().all()

    total_pages = math.ceil(total / limit) if total else 0
    return StorefrontResponse(
        items=[_product_to_dict(p) for p in products],
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        filters=applied,
    )


@router.get("/products", response_model=list[ProductResponse])
async def list_store_catalog(
    category: list[str] | None = Query(None),
    brand: list[str] | None = Query(None),
    tagtype: list[str] | None = Query(None),
    min_price: float | None = None,
    max_price: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Fetches store products using performance-optimized dynamic filtering queries."""
    stmt = select(Product)
    stmt = _apply_product_filters(
        stmt,
        categories=category,
        brands=brand,
        tagtypes=tagtype,
        min_price=min_price,
        max_price=max_price,
    )

    result = await db.execute(stmt)
    products = result.scalars().all()

    return [_product_to_dict(p) for p in products]


@router.get("/products/{product_id}/reviews", response_model=list[ReviewResponse])
@router.get("/products/{product_id}/review", response_model=list[ReviewResponse])
async def list_product_reviews(
    product_id: str,
    db: AsyncSession = Depends(get_db),
):
    product = await _resolve_product(db, product_id)

    stmt = (
        select(ProductReview)
        .where(ProductReview.product_id == product.id)
        .order_by(ProductReview.created_at.desc())
    )
    reviews = (await db.execute(stmt)).scalars().all()
    return [
        ReviewResponse(
            id=review.id,
            product_id=review.product_id,
            user_id=review.user_id,
            rating=review.rating,
            comment=review.comment,
            created_at=review.created_at.isoformat() if review.created_at else "",
        )
        for review in reviews
    ]


@router.post("/products/{product_id}/review", status_code=status.HTTP_201_CREATED)
async def create_product_review(
    product_id: str,
    data: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Submits a product review and schedules dynamic recalculation of metrics."""
    dup_stmt = select(ProductReview).where(
        ProductReview.user_id == user_id,
        ProductReview.product_id == product_id,
    )
    dup_res = await db.execute(dup_stmt)
    if dup_res.scalars().first():
        raise HTTPException(status_code=400, detail="You have already submitted a review for this product.")

    new_review = ProductReview(
        id=generate_id(16),
        product_id=product_id,
        user_id=user_id,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(new_review)
    await db.flush()

    all_reviews_stmt = select(ProductReview).where(ProductReview.product_id == product_id)
    all_reviews_res = await db.execute(all_reviews_stmt)
    all_reviews = all_reviews_res.scalars().all()

    prod_stmt = select(Product).where(Product.id == product_id)
    prod_res = await db.execute(prod_stmt)
    product = prod_res.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    total_rating = sum(r.rating for r in all_reviews)
    product.review_count = len(all_reviews)
    product.average_rating = round(total_rating / len(all_reviews), 2)

    await db.commit()
    return {"message": "Review added successfully."}


@router.post("/products/{product_id}/like")
async def toggle_product_like(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    stmt = select(ProductLike).where(
        ProductLike.user_id == user_id,
        ProductLike.product_id == product_id,
    )
    result = await db.execute(stmt)
    existing_like = result.scalars().first()

    if existing_like:
        await db.execute(
            delete(ProductLike).where(
                ProductLike.user_id == user_id,
                ProductLike.product_id == product_id,
            )
        )
        await db.commit()
        return {"status": "unliked", "message": "Product removed from likes."}

    db.add(ProductLike(user_id=user_id, product_id=product_id))
    await db.commit()
    return {"status": "liked", "message": "Product marked as useful."}


@router.post("/products/{product_id}/save")
async def toggle_save_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    stmt = select(SavedItem).where(
        SavedItem.user_id == user_id,
        SavedItem.product_id == product_id,
    )
    result = await db.execute(stmt)
    existing_save = result.scalars().first()

    if existing_save:
        await db.execute(
            delete(SavedItem).where(
                SavedItem.user_id == user_id,
                SavedItem.product_id == product_id,
            )
        )
        await db.commit()
        return {"status": "unsaved", "message": "Product removed from saved list."}

    db.add(SavedItem(user_id=user_id, product_id=product_id))
    await db.commit()
    return {"status": "saved", "message": "Product saved for future purchase."}


@router.get("/wishlist", response_model=WishlistResponse)
async def get_wishlist(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    stmt = (
        select(Product, SavedItem)
        .join(SavedItem, SavedItem.product_id == Product.id)
        .where(SavedItem.user_id == user_id, Product.is_active.is_(True))
        .order_by(SavedItem.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    items = [
        WishlistItemResponse(
            product_id=product.id,
            saved=True,
            product=ProductResponse(**_product_to_dict(product)),
        )
        for product, _saved in rows
    ]
    return WishlistResponse(items=items)


# --- Delivery addresses (auth required) ---


async def _clear_default_addresses(db: AsyncSession, user_id: str) -> None:
    stmt = select(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
    for address in (await db.execute(stmt)).scalars().all():
        address.is_default = False


def _address_to_response(address: Address) -> AddressResponse:
    return AddressResponse(
        id=address.id,
        label=address.label,
        full_name=address.full_name,
        phone=address.phone,
        address_line1=address.address_line1,
        address_line2=address.address_line2,
        city=address.city,
        state=address.state,
        pincode=address.pincode,
        is_default=address.is_default,
    )


def _delivery_address_from_order(order: Order) -> DeliveryAddressResponse:
    return DeliveryAddressResponse(
        full_name=order.delivery_full_name,
        phone=order.delivery_phone,
        address_line1=order.delivery_line1,
        address_line2=order.delivery_line2,
        city=order.delivery_city,
        state=order.delivery_state,
        pincode=order.delivery_pincode,
    )


def _order_summary(order: Order) -> OrderSummaryResponse:
    item_count = sum(item.quantity for item in order.items)
    return OrderSummaryResponse(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        status_label=ORDER_STATUS_LABELS.get(order.status, order.status),
        amount=order.amount_paise / 100,
        currency=order.currency,
        item_count=item_count,
        created_at=order.created_at.isoformat() if order.created_at else "",
    )


def _order_detail(order: Order) -> OrderDetailResponse:
    summary = _order_summary(order)
    return OrderDetailResponse(
        **summary.model_dump(),
        razorpay_order_id=order.razorpay_order_id,
        razorpay_payment_id=order.razorpay_payment_id,
        tracking_number=order.tracking_number,
        carrier=order.carrier,
        delivery_address=_delivery_address_from_order(order),
        items=[
            OrderItemResponse(
                product_id=item.product_id,
                title=item.title,
                quantity=item.quantity,
                unit_price=float(item.unit_price),
                line_total=float(item.line_total),
                img_url=item.img,
            )
            for item in order.items
        ],
        timeline=[
            OrderTimelineEventResponse(
                status=event.status,
                status_label=ORDER_STATUS_LABELS.get(event.status, event.status),
                message=event.message,
                created_at=event.created_at.isoformat() if event.created_at else "",
            )
            for event in order.status_events
        ],
    )


@router.get("/addresses", response_model=list[AddressResponse])
async def list_addresses(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    stmt = (
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    addresses = (await db.execute(stmt)).scalars().all()
    return [_address_to_response(a) for a in addresses]


@router.post("/addresses", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    body: AddressCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    existing_count = (
        await db.execute(select(func.count(Address.id)).where(Address.user_id == user_id))
    ).scalar_one()
    is_default = body.is_default or existing_count == 0
    if is_default:
        await _clear_default_addresses(db, user_id)

    address = Address(
        id=generate_id(16),
        user_id=user_id,
        label=body.label,
        full_name=body.full_name,
        phone=body.phone,
        address_line1=body.address_line1,
        address_line2=body.address_line2,
        city=body.city,
        state=body.state,
        pincode=body.pincode,
        is_default=is_default,
    )
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return _address_to_response(address)


@router.put("/addresses/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: str,
    body: AddressUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    address = (
        await db.execute(select(Address).where(Address.id == address_id, Address.user_id == user_id))
    ).scalar_one_or_none()
    if address is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")

    updates = body.model_dump(exclude_unset=True)
    if updates.get("is_default"):
        await _clear_default_addresses(db, user_id)

    for field, value in updates.items():
        setattr(address, field, value)

    await db.commit()
    await db.refresh(address)
    return _address_to_response(address)


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    address = (
        await db.execute(select(Address).where(Address.id == address_id, Address.user_id == user_id))
    ).scalar_one_or_none()
    if address is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")

    was_default = address.is_default
    await db.delete(address)
    await db.flush()

    if was_default:
        next_address = (
            await db.execute(
                select(Address)
                .where(Address.user_id == user_id)
                .order_by(Address.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if next_address is not None:
            next_address.is_default = True

    await db.commit()


# --- Order tracking (auth required) ---


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    status: OrderStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """List the authenticated user's orders (newest first)."""
    orders, total = await list_user_orders(
        db,
        user_id=user_id,
        page=page,
        limit=limit,
        status_filter=status,
    )
    total_pages = math.ceil(total / limit) if total else 0
    return OrderListResponse(
        items=[_order_summary(order) for order in orders],
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
    )


@router.get("/orders/track/{order_number}", response_model=OrderDetailResponse)
async def track_order_by_number(
    order_number: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """Track an order using its human-readable order number (e.g. RI-20260521-ABC)."""
    order = await get_user_order_by_number(db, order_number=order_number, user_id=user_id)
    return _order_detail(order)


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order_detail(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """Full order detail with items, delivery address, and status timeline."""
    order = await get_user_order(db, order_id=order_id, user_id=user_id)
    return _order_detail(order)


# --- Ephemeral cart & Razorpay checkout ---


@router.post("/cart/update")
async def update_cart_item(
    body: CartUpdateRequest,
    db: AsyncSession = Depends(get_db),
    session_id: str = Depends(require_session_id),
    user_id: str | None = Depends(get_current_user_optional),
):
    await upsert_cart_item(
        db,
        session_id=session_id,
        user_id=user_id,
        product_id=body.product_id,
        quantity=body.quantity,
    )
    await db.commit()
    return {"message": "Cart updated.", "session_id": session_id, "user_id": user_id}


@router.get("/cart", response_model=list[CartItemResponse])
async def get_cart(
    db: AsyncSession = Depends(get_db),
    session_id: str = Depends(require_session_id),
    user_id: str | None = Depends(get_current_user_optional),
):
    rows = await fetch_cart_with_products(db, session_id, user_id)
    return [
        CartItemResponse(
            id=item.id,
            product_id=item.product_id,
            quantity=item.quantity,
            title=product.title,
            price=float(product.price),
            img_url=product.img,
            stock_quantity=product.stock_quantity,
            in_stock=product.stock_quantity > 0,
        )
        for item, product in rows
    ]


@router.post("/cart/merge")
async def merge_cart(
    body: CartMergeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    merged = await merge_guest_cart(
        db,
        guest_session_id=body.guest_session_id,
        user_id=user_id,
    )
    await db.commit()
    return {"message": "Guest cart merged.", "merged_items": merged}


@router.post("/checkout/create-order")
async def create_checkout_order(
    body: CheckoutCreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    session_id: str = Depends(require_session_id),
    user_id: str = Depends(get_current_user),
):
    address = await get_user_address(db, address_id=body.address_id, user_id=user_id)
    amount_paise, cart_rows = await calculate_cart_total_paise(db, session_id, user_id)
    client = get_razorpay_client()

    razorpay_order = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "user_id": user_id,
                "address_id": address.id,
                "delivery_city": address.city,
                "delivery_pincode": address.pincode,
            },
        }
    )

    shop_order = await create_pending_order(
        db,
        user_id=user_id,
        address=address,
        amount_paise=amount_paise,
        razorpay_order_id=razorpay_order["id"],
        cart_rows=cart_rows,
    )
    await db.commit()

    return {
        "order_id": razorpay_order["id"],
        "shop_order_id": shop_order.id,
        "order_number": shop_order.order_number,
        "amount": amount_paise,
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID,
        "delivery_address": _address_to_response(address),
    }


@router.post("/checkout/verify")
async def verify_checkout_payment(
    body: CheckoutVerifyRequest,
    db: AsyncSession = Depends(get_db),
    session_id: str = Depends(require_session_id),
    user_id: str = Depends(get_current_user),
):
    client = get_razorpay_client()

    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": body.razorpay_order_id,
                "razorpay_payment_id": body.razorpay_payment_id,
                "razorpay_signature": body.razorpay_signature,
            }
        )
    except razorpay.errors.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment signature verification failed.",
        ) from exc

    order = await confirm_paid_order(
        db,
        user_id=user_id,
        razorpay_order_id=body.razorpay_order_id,
        razorpay_payment_id=body.razorpay_payment_id,
    )
    await clear_cart(db, session_id, user_id)
    await db.commit()

    return {
        "message": "Payment verified successfully. Order completed.",
        "razorpay_order_id": body.razorpay_order_id,
        "razorpay_payment_id": body.razorpay_payment_id,
        "order_id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "status_label": ORDER_STATUS_LABELS.get(order.status, order.status),
    }
