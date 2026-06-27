-- Migrate product IDs from BINARY(16) to VARCHAR(25) (tables must be empty or backup first)
USE ri_web_auth;

SET FOREIGN_KEY_CHECKS = 0;

ALTER TABLE product_reviews DROP FOREIGN KEY product_reviews_ibfk_1;
ALTER TABLE product_reviews DROP FOREIGN KEY product_reviews_ibfk_2;
ALTER TABLE product_likes DROP FOREIGN KEY product_likes_ibfk_1;
ALTER TABLE product_likes DROP FOREIGN KEY product_likes_ibfk_2;
ALTER TABLE saved_items DROP FOREIGN KEY saved_items_ibfk_1;
ALTER TABLE saved_items DROP FOREIGN KEY saved_items_ibfk_2;

ALTER TABLE products MODIFY id VARCHAR(25) NOT NULL;
ALTER TABLE product_reviews MODIFY id VARCHAR(25) NOT NULL;
ALTER TABLE product_reviews MODIFY product_id VARCHAR(25) NOT NULL;
ALTER TABLE product_reviews MODIFY user_id VARCHAR(25) NOT NULL;
ALTER TABLE product_likes MODIFY product_id VARCHAR(25) NOT NULL;
ALTER TABLE product_likes MODIFY user_id VARCHAR(25) NOT NULL;
ALTER TABLE saved_items MODIFY product_id VARCHAR(25) NOT NULL;
ALTER TABLE saved_items MODIFY user_id VARCHAR(25) NOT NULL;

ALTER TABLE product_reviews
  ADD CONSTRAINT product_reviews_ibfk_1 FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
  ADD CONSTRAINT product_reviews_ibfk_2 FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE product_likes
  ADD CONSTRAINT product_likes_ibfk_1 FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  ADD CONSTRAINT product_likes_ibfk_2 FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE;

ALTER TABLE saved_items
  ADD CONSTRAINT saved_items_ibfk_1 FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  ADD CONSTRAINT saved_items_ibfk_2 FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE;

SET FOREIGN_KEY_CHECKS = 1;
