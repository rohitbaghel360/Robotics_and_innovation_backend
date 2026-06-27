USE ri_web_auth;

CREATE TABLE IF NOT EXISTS cart_items (
    id VARCHAR(25) NOT NULL,
    session_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(25) NULL,
    product_id VARCHAR(25) NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    CONSTRAINT unique_session_product UNIQUE (session_id, product_id),
    CONSTRAINT cart_items_product_fk FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
    CONSTRAINT cart_items_user_fk FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    INDEX idx_cart_session (session_id),
    INDEX idx_cart_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
