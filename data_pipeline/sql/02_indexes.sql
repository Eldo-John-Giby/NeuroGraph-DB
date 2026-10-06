CREATE INDEX idx_reviews_user_id ON reviews(user_id);
CREATE INDEX idx_reviews_prod_id ON reviews(prod_id);
CREATE INDEX idx_reviews_review_date ON reviews(review_date);
CREATE INDEX idx_reviews_user_prod ON reviews(user_id, prod_id);
CREATE INDEX idx_reviews_label ON reviews(label);
CREATE INDEX idx_reviews_split ON reviews(split);
CREATE INDEX idx_review_variants_variant ON review_variants(variant);
CREATE INDEX idx_fraud_predictions_run_id ON fraud_predictions(run_id);
CREATE INDEX idx_fraud_predictions_score ON fraud_predictions(fraud_score DESC);\n