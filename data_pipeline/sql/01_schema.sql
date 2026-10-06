CREATE TABLE users (
    user_id TEXT PRIMARY KEY
);

CREATE TABLE products (
    prod_id TEXT PRIMARY KEY
);

CREATE TABLE reviews (
    review_id TEXT PRIMARY KEY,
    node_idx INT UNIQUE NOT NULL,
    user_id TEXT REFERENCES users(user_id),
    prod_id TEXT REFERENCES products(prod_id),
    rating SMALLINT CHECK (rating >= 1 AND rating <= 5),
    review_date DATE,
    review_text TEXT,
    label SMALLINT,
    split TEXT
);

CREATE TABLE review_variants (
    review_id TEXT REFERENCES reviews(review_id),
    variant TEXT,
    review_text TEXT,
    PRIMARY KEY(review_id, variant)
);

CREATE TABLE fraud_predictions (
    review_id TEXT REFERENCES reviews(review_id),
    run_id TEXT,
    model_name TEXT,
    variant TEXT NOT NULL DEFAULT 'clean',
    fraud_score REAL,
    predicted_label SMALLINT,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY(review_id, run_id)
);\n