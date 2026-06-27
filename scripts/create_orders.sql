USE ri_web_auth;

CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(25) NOT NULL PRIMARY KEY,
    user_id VARCHAR(25) NOT NULL,
    address_id VARCHAR(25) NULL,
    order_number VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending_payment',
    amount_paise INT NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    razorpay_order_id VARCHAR(64) NULL,
    razorpay_payment_id VARCHAR(64) NULL,
    delivery_full_name VARCHAR(255) NOT NULL,
    delivery_phone VARCHAR(20) NOT NULL,
    delivery_line1 VARCHAR(255) NOT NULL,
    delivery_line2 VARCHAR(255) NULL,
    delivery_city VARCHAR(100) NOT NULL,
    delivery_state VARCHAR(100) NOT NULL,
    delivery_pincode VARCHAR(10) NOT NULL,
    tracking_number VARCHAR(64) NULL,
    carrier VARCHAR(64) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT orders_user_fk FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT orders_address_fk FOREIGN KEY (address_id) REFERENCES addresses (id) ON DELETE SET NULL,
    UNIQUE KEY uq_orders_order_number (order_number),
    UNIQUE KEY uq_orders_razorpay_order_id (razorpay_order_id),
    INDEX idx_orders_user (user_id),
    INDEX idx_orders_status (status)
);

CREATE TABLE IF NOT EXISTS order_items (
    id VARCHAR(25) NOT NULL PRIMARY KEY,
    order_id VARCHAR(25) NOT NULL,
    product_id VARCHAR(25) NOT NULL,
    title VARCHAR(255) NOT NULL,
    img VARCHAR(512) NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    quantity INT NOT NULL,
    line_total DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT order_items_order_fk FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
    CONSTRAINT order_items_product_fk FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT,
    INDEX idx_order_items_order (order_id)
);

CREATE TABLE IF NOT EXISTS order_status_events (
    id VARCHAR(25) NOT NULL PRIMARY KEY,
    order_id VARCHAR(25) NOT NULL,
    status VARCHAR(32) NOT NULL,
    message VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT order_status_events_order_fk FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
    INDEX idx_order_status_events_order (order_id)
);
