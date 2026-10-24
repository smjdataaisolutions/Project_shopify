-- Guarded rollback for pre-onboarding recovery only.
DO $$
BEGIN
  IF (SELECT count(*) FROM shops) <> 1
     OR NOT EXISTS (
       SELECT 1 FROM shops
       WHERE shop_domain = 'test-store-martina.myshopify.com'
     ) THEN
    RAISE EXCEPTION 'Rollback refused: more than the development tenant exists';
  END IF;
END $$;

ALTER TABLE inventory DROP CONSTRAINT IF EXISTS fk_inventory_shop_location;
ALTER TABLE order_line_items DROP CONSTRAINT IF EXISTS fk_order_line_items_shop_order;
ALTER TABLE product_variants DROP CONSTRAINT IF EXISTS fk_product_variants_shop_product;

ALTER TABLE products DROP CONSTRAINT products_pkey;
ALTER TABLE product_variants DROP CONSTRAINT product_variants_pkey;
ALTER TABLE locations DROP CONSTRAINT locations_pkey;
ALTER TABLE inventory DROP CONSTRAINT inventory_pkey;
ALTER TABLE orders DROP CONSTRAINT orders_pkey;
ALTER TABLE order_line_items DROP CONSTRAINT order_line_items_pkey;
ALTER TABLE shopify_sync_state DROP CONSTRAINT shopify_sync_state_pkey;

ALTER TABLE products ADD CONSTRAINT products_pkey PRIMARY KEY (id);
ALTER TABLE product_variants ADD CONSTRAINT product_variants_pkey PRIMARY KEY (id);
ALTER TABLE locations ADD CONSTRAINT locations_pkey PRIMARY KEY (id);
ALTER TABLE inventory ADD CONSTRAINT inventory_pkey
  PRIMARY KEY (inventory_item_id, location_id);
ALTER TABLE orders ADD CONSTRAINT orders_pkey PRIMARY KEY (id);
ALTER TABLE order_line_items ADD CONSTRAINT order_line_items_pkey PRIMARY KEY (id);
ALTER TABLE shopify_sync_state ADD CONSTRAINT shopify_sync_state_pkey PRIMARY KEY (source);

ALTER TABLE products DROP COLUMN shop_id;
ALTER TABLE product_variants DROP COLUMN shop_id;
ALTER TABLE locations DROP COLUMN shop_id;
ALTER TABLE inventory DROP COLUMN shop_id;
ALTER TABLE orders DROP COLUMN shop_id;
ALTER TABLE order_line_items DROP COLUMN shop_id;
ALTER TABLE shopify_sync_state DROP COLUMN shop_id;

DROP TABLE shops;
