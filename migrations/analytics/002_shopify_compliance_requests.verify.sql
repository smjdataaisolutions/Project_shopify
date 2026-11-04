SELECT status, count(*) AS request_count
FROM shopify_compliance_requests
GROUP BY status
ORDER BY status;

SELECT count(*) AS invalid_tenant_references
FROM shopify_compliance_requests request
LEFT JOIN shops shop ON shop.id = request.shop_id
WHERE shop.id IS NULL;

SELECT count(*) AS invalid_order_id_documents
FROM shopify_compliance_requests
WHERE jsonb_typeof(order_ids) <> 'array';
