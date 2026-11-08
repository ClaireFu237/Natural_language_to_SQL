SELECT COUNT(*) AS completed_order_count
FROM starbucks_mock.orders
WHERE order_status = 'completed';
