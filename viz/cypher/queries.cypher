// 1. Fraud Rings: Users sharing at least 3 flagged products
MATCH (u1:User)-[:WROTE]->(r1:Review)-[:ABOUT]->(p:Product)<-[:ABOUT]-(r2:Review)<-[:WROTE]-(u2:User)
WHERE u1 <> u2 AND r1.label = 1 AND r2.label = 1
WITH u1, u2, COUNT(DISTINCT p) AS shared_flagged_products
WHERE shared_flagged_products >= 3
RETURN u1.user_id, u2.user_id, shared_flagged_products
ORDER BY shared_flagged_products DESC;

// 2. Identify Camouflage Users via Bimodal Score Variance
// Statistical Justification (YelpChi Empirical Distributions):
// - $high_th (default 0.80): Operating threshold corresponding to >90% precision on 15% minority spam class.
// - $low_th  (default 0.30): 25th percentile (Q1) of predicted fraud scores for confirmed benign reviews.
// - $min_reviews (default 5): Minimum activity threshold to establish statistical significance.
// - Condition: Detects high variance / bimodal behavior where spammers seed benign reviews to disguise attacks.
MATCH (u:User)-[:WROTE]->(r:Review)
WITH u,
     count(r) AS total_reviews,
     sum(CASE WHEN r.fraud_score >= $high_th THEN 1 ELSE 0 END) AS high_score_count,
     sum(CASE WHEN r.fraud_score <= $low_th THEN 1 ELSE 0 END) AS low_score_count,
     stDev(r.fraud_score) AS score_variance
WHERE total_reviews >= $min_reviews
  AND high_score_count >= 1
  AND low_score_count >= 2
  AND (toFloat(low_score_count) / total_reviews) >= 0.40
RETURN u.user_id, total_reviews, high_score_count, low_score_count, 
       round(score_variance, 3) AS score_std_dev,
       round(toFloat(low_score_count) / total_reviews, 2) AS camo_ratio
ORDER BY camo_ratio DESC, score_std_dev DESC;

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
