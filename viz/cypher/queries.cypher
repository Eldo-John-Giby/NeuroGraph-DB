// 1. Fraud Rings: Users sharing at least 3 flagged products
MATCH (u1:User)-[:WROTE]->(r1:Review)-[:ABOUT]->(p:Product)<-[:ABOUT]-(r2:Review)<-[:WROTE]-(u2:User)
WHERE u1 <> u2 AND r1.label = 1 AND r2.label = 1
WITH u1, u2, COUNT(DISTINCT p) AS shared_flagged_products
WHERE shared_flagged_products >= 3
RETURN u1.user_id, u2.user_id, shared_flagged_products
ORDER BY shared_flagged_products DESC;

// 2. Camouflage Users: High-score reviews mixed with many low-score reviews
MATCH (u:User)-[:WROTE]->(r:Review)
WITH u, 
     SUM(CASE WHEN r.fraud_score > 0.8 THEN 1 ELSE 0 END) AS high_score_count,
     SUM(CASE WHEN r.fraud_score < 0.3 THEN 1 ELSE 0 END) AS low_score_count,
     COUNT(r) AS total_reviews
WHERE high_score_count > 0 AND low_score_count > 5 AND total_reviews > 10
RETURN u.user_id, high_score_count, low_score_count, total_reviews
ORDER BY high_score_count DESC;

// 3. Products with bursts of flagged reviews (Simplified: count of flagged reviews)
MATCH (p:Product)<-[:ABOUT]-(r:Review)
WHERE r.label = 1
WITH p, COUNT(r) AS flagged_count
WHERE flagged_count > 10
RETURN p.prod_id, flagged_count
ORDER BY flagged_count DESC;

// 4. 2-hop neighborhood of one flagged review
MATCH path = (r1:Review {label: 1})-[:ABOUT|WROTE*1..2]-(n)
RETURN path
LIMIT 50;

// 5. Top suspicious users
MATCH (u:User)-[:WROTE]->(r:Review)
WITH u, AVG(r.fraud_score) AS avg_fraud_score, COUNT(r) AS review_count
WHERE review_count >= 3
RETURN u.user_id, avg_fraud_score, review_count
ORDER BY avg_fraud_score DESC
LIMIT 10;
