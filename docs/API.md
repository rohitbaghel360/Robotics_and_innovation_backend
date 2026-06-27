# R&I Backend API Reference

REST API for the R&I e-commerce platform: authentication, shop catalog, cart, checkout (Razorpay), delivery addresses, and order tracking.

**Base URL (local):** `http://localhost:8000/api/v1`  
**OpenAPI (dev/testing):** `http://localhost:8000/docs`

---

## Table of contents

1. [Quick start](#quick-start)
2. [Authentication](#authentication)
3. [Common headers](#common-headers)
4. [Error responses](#error-responses)
5. [Health](#health)
6. [Auth API](#auth-api)
7. [Shop — Catalog](#shop--catalog)
8. [Shop — Cart](#shop--cart)
9. [Shop — Addresses](#shop--addresses)
10. [Shop — Checkout](#shop--checkout)
11. [Shop — Orders & tracking](#shop--orders--tracking)
12. [Shop — Wishlist & reviews](#shop--wishlist--reviews)
13. [Order status lifecycle](#order-status-lifecycle)
14. [Frontend integration flows](#frontend-integration-flows)
15. [Environment variables](#environment-variables)

---

## Quick start

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"yourpassword"}'

# Use the access_token from the response
export TOKEN="eyJhbGciOiJIUzI1NiIs..."
export SESSION="guest-cart-uuid-here"
```

---

## Authentication

Protected endpoints require a JWT in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Obtain a token via:

- `POST /auth/login` (email + password)
- `POST /auth/register` → `POST /auth/register/verify` (OTP)
- `GET /auth/google/callback` (redirects to frontend with `?token=...`)

Tokens expire after **60 minutes** by default (`ACCESS_TOKEN_EXPIRE_MINUTES`).

---

## Common headers

| Header | Required | Used by |
|--------|----------|---------|
| `Authorization: Bearer <token>` | Yes (protected routes) | Auth, addresses, checkout, orders, wishlist, cart merge |
| `X-Session-ID: <uuid>` | Yes (cart/checkout) | Cart update, get cart, checkout |
| `Content-Type: application/json` | POST/PUT with body | All JSON bodies |

**Guest cart:** Send only `X-Session-ID` (no Bearer).  
**Logged-in checkout:** Send both `Authorization` and `X-Session-ID`.

---

## Error responses

```json
{
  "detail": "Human-readable error message"
}
```

Validation errors (422):

```json
{
  "detail": [
    { "loc": ["body", "email"], "msg": "field required", "type": "missing" }
  ]
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request (empty cart, out of stock, invalid payment) |
| 401 | Missing or invalid token |
| 403 | Forbidden (e.g. email not verified) |
| 404 | Resource not found |
| 409 | Conflict (duplicate email on register) |
| 503 | Service unavailable (e.g. Razorpay not configured) |

---

## Health

### `GET /health`

Liveness probe. Returns app status and database connectivity.

```bash
curl http://localhost:8000/api/v1/health
```

```json
{
  "status": "healthy",
  "environment": "development",
  "database": "connected"
}
```

### `GET /ready`

Readiness probe. Returns `503` if the database is unreachable.

```bash
curl http://localhost:8000/api/v1/ready
```

---

## Auth API

Prefix: `/api/v1/auth`

### Register (step 1 — send OTP)

`POST /register`

```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "password": "securepass1"
}
```

**Response `201`:**

```json
{
  "message": "Verification code sent to your email. It expires in 5 minutes.",
  "email": "user@example.com"
}
```

### Register (step 2 — verify OTP)

`POST /register/verify`

```json
{
  "email": "user@example.com",
  "otp_code": "123456"
}
```

**Response `200`:**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "email": "user@example.com",
  "name": "John Doe"
}
```

### Login

`POST /login`

```json
{
  "email": "user@example.com",
  "password": "securepass1"
}
```

**Response `200`:** Same shape as register verify.

### Current user

`GET /me` — **Auth required**

```json
{
  "id": "0d1d09d197e34375",
  "email": "user@example.com",
  "name": "John Doe",
  "is_verified": true
}
```

### Logout

`POST /logout` — **Auth required**

Stateless JWT logout. Client must discard the token.

```json
{ "message": "Logged out successfully." }
```

### Forgot password

`POST /forgot-password`

```json
{ "email": "user@example.com" }
```

### Reset password

`POST /reset-password-verify`

```json
{
  "email": "user@example.com",
  "otp_code": "123456",
  "new_password": "newsecurepass1"
}
```

### Google OAuth

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/google/login` | Returns `{ "url": "https://accounts.google.com/..." }` |
| `GET` | `/google/callback?code=...` | Server redirect → `{FRONTEND_URL}/login?token=...` |

---

## Shop — Catalog

Prefix: `/api/v1/shop`  
**Auth:** Not required

### Storefront (paginated + filters)

`GET /storefront`

| Query | Type | Description |
|-------|------|-------------|
| `page` | int | Default `1` |
| `limit` | int | Default `12`, max `100` |
| `sort_by` | string | `popular`, `newest`, `price_asc`, `price_desc`, `rating` |
| `category` | string[] | Repeat param: `?category=A&category=B` |
| `brand` | string[] | Multi-select |
| `tagtype` | string[] | Multi-select |
| `min_price` | float | Minimum price |
| `max_price` | float | Maximum price |

```bash
curl "http://localhost:8000/api/v1/shop/storefront?page=1&limit=12&sort_by=popular"
```

**Product fields (excerpt):**

```json
{
  "id": "abc123",
  "title": "Arduino Starter Kit",
  "price": 999.00,
  "stock_quantity": 10,
  "in_stock": true,
  "img_url": "/images/arduino.jpg",
  "average_rating": 4.5,
  "review_count": 12
}
```

### Other catalog endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/products` | Full product list with filters |
| `GET` | `/categories` | Category sidebar data |
| `GET` | `/brands` | Distinct brands |
| `GET` | `/tagtypes` | Distinct tag types |

---

## Shop — Cart

Prefix: `/api/v1/shop`

Guests can add items with `X-Session-ID` only. Login is required at **checkout**, not for cart updates.

### Update cart item

`POST /cart/update`

```json
{
  "product_id": "product_id_here",
  "quantity": 2
}
```

Set `quantity` to `0` to remove the item.

**Headers:** `X-Session-ID` (required), `Authorization` (optional)

### Get cart

`GET /cart`

**Response:**

```json
[
  {
    "id": "cart_item_id",
    "product_id": "product_id",
    "quantity": 2,
    "title": "Arduino Kit",
    "price": 999.00,
    "img_url": "/images/arduino.jpg",
    "stock_quantity": 10,
    "in_stock": true
  }
]
```

### Merge guest cart (after login)

`POST /cart/merge` — **Auth required**

```json
{
  "guest_session_id": "uuid-from-localStorage"
}
```

---

## Shop — Addresses

Prefix: `/api/v1/shop`  
**Auth:** Required for all address endpoints

### List addresses

`GET /addresses`

Returns addresses for the logged-in user (default address first).

### Create address

`POST /addresses`

```json
{
  "label": "Home",
  "full_name": "John Doe",
  "phone": "9876543210",
  "address_line1": "123 Main Street",
  "address_line2": "Apt 4B",
  "city": "Mumbai",
  "state": "Maharashtra",
  "pincode": "400001",
  "is_default": true
}
```

**Response `201`:** Address object with `id`.

### Update address

`PUT /addresses/{address_id}`

Partial update — send only fields to change.

### Delete address

`DELETE /addresses/{address_id}`

**Response:** `204 No Content`

---

## Shop — Checkout

Prefix: `/api/v1/shop`  
**Auth:** Required  
**Headers:** `Authorization` + `X-Session-ID`

### Create payment order

`POST /checkout/create-order`

```json
{
  "address_id": "address_id_here"
}
```

Creates a Razorpay order and a **pending** shop order with line-item snapshots.

**Response:**

```json
{
  "order_id": "order_RazorpayId",
  "shop_order_id": "internal_order_id",
  "order_number": "RI-20260521-A1B2C3D4",
  "amount": 199800,
  "currency": "INR",
  "key_id": "rzp_test_xxx",
  "delivery_address": {
    "id": "...",
    "full_name": "John Doe",
    "phone": "9876543210",
    "address_line1": "123 Main St",
    "city": "Mumbai",
    "state": "Maharashtra",
    "pincode": "400001",
    "is_default": true
  }
}
```

Use `order_id`, `amount`, and `key_id` to open the Razorpay checkout on the frontend.

### Verify payment

`POST /checkout/verify`

Called after Razorpay payment success.

```json
{
  "razorpay_order_id": "order_xxx",
  "razorpay_payment_id": "pay_xxx",
  "razorpay_signature": "signature_from_razorpay"
}
```

**Response:**

```json
{
  "message": "Payment verified successfully. Order completed.",
  "razorpay_order_id": "order_xxx",
  "razorpay_payment_id": "pay_xxx",
  "order_id": "internal_order_id",
  "order_number": "RI-20260521-A1B2C3D4",
  "status": "confirmed",
  "status_label": "Order confirmed"
}
```

On success the cart is cleared and product stock is decremented.

---

## Shop — Orders & tracking

Prefix: `/api/v1/shop`  
**Auth:** Required

### List my orders

`GET /orders`

| Query | Type | Description |
|-------|------|-------------|
| `page` | int | Default `1` |
| `limit` | int | Default `10`, max `50` |
| `status` | string | Filter: `pending_payment`, `confirmed`, `processing`, `shipped`, `delivered`, `cancelled` |

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/shop/orders?page=1&limit=10&status=confirmed"
```

**Response:**

```json
{
  "items": [
    {
      "id": "order_internal_id",
      "order_number": "RI-20260521-A1B2C3D4",
      "status": "confirmed",
      "status_label": "Order confirmed",
      "amount": 1998.00,
      "currency": "INR",
      "item_count": 2,
      "created_at": "2026-05-21T10:30:00"
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1,
  "total_pages": 1
}
```

### Order detail

`GET /orders/{order_id}`

Returns full order with items, delivery address, tracking fields, and status timeline.

```json
{
  "id": "order_internal_id",
  "order_number": "RI-20260521-A1B2C3D4",
  "status": "confirmed",
  "status_label": "Order confirmed",
  "amount": 1998.00,
  "currency": "INR",
  "item_count": 2,
  "created_at": "2026-05-21T10:30:00",
  "razorpay_order_id": "order_xxx",
  "razorpay_payment_id": "pay_xxx",
  "tracking_number": null,
  "carrier": null,
  "delivery_address": {
    "full_name": "John Doe",
    "phone": "9876543210",
    "address_line1": "123 Main St",
    "address_line2": null,
    "city": "Mumbai",
    "state": "Maharashtra",
    "pincode": "400001"
  },
  "items": [
    {
      "product_id": "prod123",
      "title": "Arduino Kit",
      "quantity": 2,
      "unit_price": 999.00,
      "line_total": 1998.00,
      "img_url": "/images/arduino.jpg"
    }
  ],
  "timeline": [
    {
      "status": "pending_payment",
      "status_label": "Awaiting payment",
      "message": "Order created. Complete payment to confirm.",
      "created_at": "2026-05-21T10:30:00"
    },
    {
      "status": "confirmed",
      "status_label": "Order confirmed",
      "message": "Payment received. Your order is confirmed.",
      "created_at": "2026-05-21T10:31:00"
    }
  ]
}
```

### Track by order number

`GET /orders/track/{order_number}`

Example:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/shop/orders/track/RI-20260521-A1B2C3D4"
```

Same response shape as order detail.

---

## Shop — Wishlist & reviews

### Wishlist

`GET /wishlist` — **Auth required**

```json
{
  "items": [
    {
      "product_id": "prod123",
      "saved": true,
      "product": { "...ProductResponse fields..." }
    }
  ]
}
```

### Toggle save (wishlist)

`POST /products/{product_id}/save` — **Auth required**

Returns `{ "status": "saved" }` or `{ "status": "unsaved" }`.

### List reviews

`GET /products/{product_id}/reviews` — No auth  
Also available as `GET /products/{product_id}/review` (alias).

`product_id` may be the product **id** or **slug**.

Returns `200` with an empty array `[]` when there are no reviews yet.  
Returns `404` only when the product does not exist.

```bash
curl "http://localhost:8000/api/v1/shop/products/0254f4923a3c4ae5a7d810795/reviews"
# or by slug:
curl "http://localhost:8000/api/v1/shop/products/sand-paper/reviews"
```

### Submit review

`POST /products/{product_id}/review` — **Auth required**

```json
{
  "rating": 5,
  "comment": "Optional review text"
}
```

### Toggle like

`POST /products/{product_id}/like` — **Auth required**

---

## Order status lifecycle

```
pending_payment → confirmed → processing → shipped → delivered
                      ↓
                  cancelled
```

| Status | Description |
|--------|-------------|
| `pending_payment` | Razorpay order created; awaiting payment |
| `confirmed` | Payment verified; order placed |
| `processing` | Being prepared for dispatch |
| `shipped` | Dispatched (`tracking_number` / `carrier` may be set) |
| `delivered` | Delivered to customer |
| `cancelled` | Order cancelled |

Status timeline events are returned in the `timeline` array on order detail.

---

## Frontend integration flows

### Guest shopping → checkout

```
1. Generate UUID → store as X-Session-ID (localStorage: ri_cart_session)
2. Browse catalog → GET /shop/storefront
3. Add to cart   → POST /shop/cart/update (X-Session-ID only)
4. View cart     → GET /shop/cart
5. Checkout      → redirect to login if no token
6. After login   → POST /shop/cart/merge { guest_session_id }
7. Addresses     → GET/POST /shop/addresses
8. Pay           → POST /shop/checkout/create-order { address_id }
9. Razorpay UI   → on success POST /shop/checkout/verify
10. Success page → use order_number from verify response
11. Track order  → GET /shop/orders/{order_id}
```

### Recommended frontend API modules

| File | Endpoints |
|------|-----------|
| `authApi.js` | `/auth/login`, `/auth/me`, `/auth/logout`, register, reset |
| `shopApi.js` | storefront, wishlist, reviews |
| `cartApi.js` | cart, merge, checkout |
| `addressApi.js` | addresses CRUD |
| `ordersApi.js` | `/shop/orders`, `/shop/orders/{id}`, `/shop/orders/track/{number}` |

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `DB__HOST` | MySQL host (`host.docker.internal` in Docker) |
| `DB__PASSWORD` | MySQL password |
| `JWT_SECRET_KEY` | JWT signing key |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth |
| `FRONTEND_URL` | OAuth redirect target (e.g. `http://localhost:5173`) |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Payment gateway |
| `MAIL_*` | SMTP for OTP emails |

---

## Database migrations

Run SQL scripts when setting up a new environment:

```bash
mysql -u root -p ri_web_auth < scripts/create_cart_items.sql
mysql -u root -p ri_web_auth < scripts/create_addresses.sql
mysql -u root -p ri_web_auth < scripts/create_orders.sql
```

Tables are also created on startup via SQLAlchemy `create_all` when models are registered in `app/db/registry.py`.

---

## cURL cheat sheet

```bash
BASE="http://localhost:8000/api/v1"
TOKEN="your_jwt"
SESSION="your-cart-session-uuid"
ADDRESS_ID="address_id"
ORDER_ID="order_id"
ORDER_NUMBER="RI-20260521-A1B2C3D4"
PRODUCT_ID="product_id"

# Auth
curl -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass"}'
curl "$BASE/auth/me" -H "Authorization: Bearer $TOKEN"
curl -X POST "$BASE/auth/logout" -H "Authorization: Bearer $TOKEN"

# Cart
curl -X POST "$BASE/shop/cart/update" \
  -H "Content-Type: application/json" -H "X-Session-ID: $SESSION" \
  -d "{\"product_id\":\"$PRODUCT_ID\",\"quantity\":1}"
curl "$BASE/shop/cart" -H "X-Session-ID: $SESSION" -H "Authorization: Bearer $TOKEN"
curl -X POST "$BASE/shop/cart/merge" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "{\"guest_session_id\":\"$SESSION\"}"

# Addresses
curl "$BASE/shop/addresses" -H "Authorization: Bearer $TOKEN"
curl -X POST "$BASE/shop/addresses" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"John","phone":"9876543210","address_line1":"123 St","city":"Mumbai","state":"MH","pincode":"400001"}'

# Checkout
curl -X POST "$BASE/shop/checkout/create-order" \
  -H "Authorization: Bearer $TOKEN" -H "X-Session-ID: $SESSION" \
  -H "Content-Type: application/json" -d "{\"address_id\":\"$ADDRESS_ID\"}"
curl -X POST "$BASE/shop/checkout/verify" \
  -H "Authorization: Bearer $TOKEN" -H "X-Session-ID: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"razorpay_order_id":"order_xxx","razorpay_payment_id":"pay_xxx","razorpay_signature":"sig_xxx"}'

# Orders
curl "$BASE/shop/orders" -H "Authorization: Bearer $TOKEN"
curl "$BASE/shop/orders/$ORDER_ID" -H "Authorization: Bearer $TOKEN"
curl "$BASE/shop/orders/track/$ORDER_NUMBER" -H "Authorization: Bearer $TOKEN"

# Wishlist & reviews
curl "$BASE/shop/wishlist" -H "Authorization: Bearer $TOKEN"
curl "$BASE/shop/products/$PRODUCT_ID/reviews"
curl -X POST "$BASE/shop/products/$PRODUCT_ID/save" -H "Authorization: Bearer $TOKEN"
```

---

*Last updated: May 2026 — API version 1.0.0*
