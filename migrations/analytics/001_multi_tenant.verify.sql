SELECT shop_domain, status, sync_status, last_synced_at
FROM shops
ORDER BY shop_domain;

SELECT 'products' AS table_name, shop_id, count(*) FROM products GROUP BY shop_id
UNION ALL
SELECT 'product_variants', shop_id, count(*) FROM product_variants GROUP BY shop_id
UNION ALL
SELECT 'locations', shop_id, count(*) FROM locations GROUP BY shop_id
UNION ALL
SELECT 'inventory', shop_id, count(*) FROM inventory GROUP BY shop_id
UNION ALL
SELECT 'orders', shop_id, count(*) FROM orders GROUP BY shop_id
UNION ALL
SELECT 'order_line_items', shop_id, count(*) FROM order_line_items GROUP BY shop_id
UNION ALL
SELECT 'shopify_sync_state', shop_id, count(*) FROM shopify_sync_state GROUP BY shop_id
ORDER BY table_name, shop_id;

SELECT 'variant_without_product' AS check_name, count(*) AS failures
FROM product_variants v
LEFT JOIN products p ON p.shop_id = v.shop_id AND p.id = v.product_id
WHERE v.product_id IS NOT NULL AND p.id IS NULL
UNION ALL
SELECT 'line_without_order', count(*)
FROM order_line_items li
LEFT JOIN orders o ON o.shop_id = li.shop_id AND o.id = li.order_id
WHERE li.order_id IS NOT NULL AND o.id IS NULL
UNION ALL
SELECT 'cross_tenant_variant_product', count(*)
FROM product_variants v
JOIN products p ON p.id = v.product_id AND p.shop_id <> v.shop_id
UNION ALL
SELECT 'cross_tenant_line_order', count(*)
FROM order_line_items li
JOIN orders o ON o.id = li.order_id AND o.shop_id <> li.shop_id;
