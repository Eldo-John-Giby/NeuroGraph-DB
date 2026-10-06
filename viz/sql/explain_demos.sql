-- 1. Reviews per user
-- Before index: Sequential Scan ~XX ms
-- After index: Index Scan ~XX ms
EXPLAIN ANALYZE 
SELECT user_id, COUNT(*) FROM reviews GROUP BY user_id;

-- 2. Avg rating per product
-- Before index: Sequential Scan ~XX ms
-- After index: Index Scan ~XX ms
EXPLAIN ANALYZE 
SELECT prod_id, AVG(rating) FROM reviews GROUP BY prod_id;

-- 3. Spam rate per month (using string manipulation for simplicity)
-- Before index: Sequential Scan ~XX ms
-- After index: Index Scan ~XX ms
EXPLAIN ANALYZE 
SELECT SUBSTRING(date FROM 1 FOR 7) AS month, AVG(label) FROM reviews GROUP BY month;

-- 4. Top users by spam count
-- Before index: Sequential Scan ~XX ms
-- After index: Index Scan ~XX ms
EXPLAIN ANALYZE 
SELECT user_id, SUM(label) AS spam_count FROM reviews GROUP BY user_id ORDER BY spam_count DESC LIMIT 10;

-- 5. Users-reviews-products join
-- Before index: Hash Join ~XX ms
-- After index: Nested Loop with Index Scan ~XX ms
EXPLAIN ANALYZE 
SELECT u.name, p.name, r.rating 
FROM reviews r
JOIN users u ON r.user_id = u.user_id
JOIN products p ON r.prod_id = p.prod_id
LIMIT 100;
