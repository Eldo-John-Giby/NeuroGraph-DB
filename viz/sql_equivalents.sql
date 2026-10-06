-- 1. Fraud Rings: Users sharing at least 3 flagged products
SELECT r1.user_id AS u1_id, r2.user_id AS u2_id, COUNT(DISTINCT r1.prod_id) AS shared_flagged_products
FROM reviews r1
JOIN reviews r2 ON r1.prod_id = r2.prod_id AND r1.user_id != r2.user_id
WHERE r1.label = 1 AND r2.label = 1
GROUP BY r1.user_id, r2.user_id
HAVING COUNT(DISTINCT r1.prod_id) >= 3
ORDER BY shared_flagged_products DESC;

-- 2. Camouflage Users: High-score reviews mixed with many low-score reviews
SELECT user_id,
       SUM(CASE WHEN fraud_score > 0.8 THEN 1 ELSE 0 END) AS high_score_count,
       SUM(CASE WHEN fraud_score < 0.3 THEN 1 ELSE 0 END) AS low_score_count,
       COUNT(*) AS total_reviews
FROM reviews
GROUP BY user_id
HAVING SUM(CASE WHEN fraud_score > 0.8 THEN 1 ELSE 0 END) > 0
   AND SUM(CASE WHEN fraud_score < 0.3 THEN 1 ELSE 0 END) > 5
   AND COUNT(*) > 10
ORDER BY high_score_count DESC;

-- 3. Products with bursts of flagged reviews
SELECT prod_id, COUNT(*) AS flagged_count
FROM reviews
WHERE label = 1
GROUP BY prod_id
HAVING COUNT(*) > 10
ORDER BY flagged_count DESC;

-- 4. 2-hop neighborhood of one flagged review
-- (Requires recursive CTEs or specific joins in SQL, simplified here to show co-reviews)
SELECT r1.review_id, r1.user_id, r1.prod_id, r2.review_id AS co_review_id, r2.user_id AS co_user_id
FROM reviews r1
JOIN reviews r2 ON (r1.prod_id = r2.prod_id OR r1.user_id = r2.user_id) AND r1.review_id != r2.review_id
WHERE r1.label = 1
LIMIT 50;

-- 5. Top suspicious users
SELECT user_id, AVG(fraud_score) AS avg_fraud_score, COUNT(*) AS review_count
FROM reviews
GROUP BY user_id
HAVING COUNT(*) >= 3
ORDER BY avg_fraud_score DESC
LIMIT 10;
