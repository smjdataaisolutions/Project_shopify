CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  title TEXT,
  handle TEXT,
  status TEXT,
  vendor TEXT,
  product_type TEXT,
  tags JSONB,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS product_variants (
  id TEXT PRIMARY KEY,
  product_id TEXT,
  title TEXT,
  sku TEXT,
  barcode TEXT,
  price NUMERIC,
  inventory_policy TEXT,
  inventory_quantity INTEGER,
  inventory_item_id TEXT,
  inventory_tracked BOOLEAN
);

CREATE TABLE IF NOT EXISTS locations (
  id TEXT PRIMARY KEY,
  name TEXT,
  is_active BOOLEAN,
  fulfills_online_orders BOOLEAN,
  has_active_inventory BOOLEAN,
  address JSONB
);

CREATE TABLE IF NOT EXISTS inventory (
  inventory_item_id TEXT NOT NULL,
  location_id TEXT NOT NULL,
  location_name TEXT,
  sku TEXT,
  tracked BOOLEAN,
  requires_shipping BOOLEAN,
  quantities JSONB,
  updated_at TIMESTAMPTZ,
  PRIMARY KEY (inventory_item_id, location_id)
);

CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY,
  display_name TEXT,
  first_name TEXT,
  last_name TEXT,
  email TEXT,
  phone TEXT,
  default_address JSONB,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  name TEXT,
  customer_id TEXT,
  created_at TIMESTAMPTZ,
  processed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  refunded_at TIMESTAMPTZ,
  currency_code TEXT,
  financial_status TEXT,
  fulfillment_status TEXT,
  sales_channel TEXT,
  subtotal_price NUMERIC,
  total_discount NUMERIC,
  total_shipping NUMERIC,
  total_tax NUMERIC,
  total_price NUMERIC,
  total_refunded NUMERIC,
  refund_reason TEXT
);

ALTER TABLE orders ADD COLUMN IF NOT EXISTS subtotal_price NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_discount NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_shipping NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_tax NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_price NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refunded_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_refunded NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_reason TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS sales_channel TEXT;

CREATE TABLE IF NOT EXISTS order_line_items (
  id TEXT PRIMARY KEY,
  order_id TEXT,
  product_id TEXT,
  variant_id TEXT,
  title TEXT,
  sku TEXT,
  quantity INTEGER,
  current_quantity INTEGER,
  fulfillable_quantity INTEGER,
  unit_price NUMERIC,
  currency_code TEXT
);
