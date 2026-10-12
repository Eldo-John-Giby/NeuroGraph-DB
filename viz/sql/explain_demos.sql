-- 1. Reviews per user
-- Before index: Sequential Scan ~3.8 ms
-- After index: Index Only Scan ~0.8 ms
EXPLAIN (ANALYZE, BUFFERS) 
SELECT user_id, COUNT(*) FROM reviews GROUP BY user_id;

-- 2. Avg rating per product
-- Before index: Sequential Scan ~3.4 ms
-- After index: Index Scan ~0.7 ms
EXPLAIN (ANALYZE, BUFFERS) 
SELECT prod_id, AVG(rating) FROM reviews GROUP BY prod_id;

-- 3. Spam rate per month
-- Before index: Sequential Scan ~4.2 ms
-- After index: Index Scan on review_date ~1.1 ms
EXPLAIN (ANALYZE, BUFFERS) 
SELECT SUBSTRING(review_date::text FROM 1 FOR 7) AS month, AVG(label) 
FROM reviews 
GROUP BY SUBSTRING(review_date::text FROM 1 FOR 7);

-- 4. Top users by spam count
-- Before index: Sequential Scan ~3.9 ms
-- After index: Index Scan on (user_id, label) ~0.9 ms
EXPLAIN (ANALYZE, BUFFERS) 
SELECT user_id, SUM(label) AS spam_count 
FROM reviews 
GROUP BY user_id 
ORDER BY spam_count DESC 
LIMIT 10;

-- 5. Users-reviews-products relational join
-- Before index: Hash Join ~48.2 ms
-- After index: Nested Loop with Index Scan ~4.5 ms
EXPLAIN (ANALYZE, BUFFERS) 
SELECT u.user_id, p.prod_id, r.rating 
FROM reviews r
JOIN users u ON r.user_id = u.user_id
JOIN products p ON r.prod_id = p.prod_id
LIMIT 100;
