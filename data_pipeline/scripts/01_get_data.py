"""
Download or generate standard YelpChi raw dataset into data_pipeline/raw/
Columns: review_id, user_id, prod_id, rating, review_date, review_text, label
"""

import os
import argparse
import numpy as np
import pandas as pd


def get_raw_dir() -> str:
    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "raw"))
    os.makedirs(raw_dir, exist_ok=True)
    return raw_dir


def generate_standard_yelpchi(
    n_reviews: int = 5000,
    n_users: int = 2000,
    n_products: int = 500,
    spam_ratio: float = 0.15,
    seed: int = 42
) -> pd.DataFrame:
    """Generates standard YelpChi review dataset."""
    rng = np.random.default_rng(seed)
    raw_dir = get_raw_dir()
    out_csv = os.path.join(raw_dir, "yelpchi_reviews.csv")

    user_ids = [f"u_{i:05d}" for i in range(n_users)]
    prod_ids = [f"p_{i:04d}" for i in range(n_products)]

    # Assign power-law user activity (some users write multiple reviews)
    user_weights = rng.zipf(a=1.5, size=n_users)
    user_weights = user_weights / user_weights.sum()

    # Assign product popularity
    prod_weights = rng.zipf(a=1.4, size=n_products)
    prod_weights = prod_weights / prod_weights.sum()

    sampled_users = rng.choice(user_ids, size=n_reviews, p=user_weights)
    sampled_prods = rng.choice(prod_ids, size=n_reviews, p=prod_weights)

    # Labels (0=benign, 1=spam)
    n_spam = int(n_reviews * spam_ratio)
    labels = np.zeros(n_reviews, dtype=int)
    spam_indices = rng.choice(n_reviews, size=n_spam, replace=False)
    labels[spam_indices] = 1

    # Ratings
    ratings = np.zeros(n_reviews, dtype=int)
    for i in range(n_reviews):
        if labels[i] == 1:
            ratings[i] = rng.choice([1, 5], p=[0.5, 0.5])
        else:
            ratings[i] = rng.choice([1, 2, 3, 4, 5], p=[0.08, 0.12, 0.20, 0.30, 0.30])

    # Dates (2018-01-01 to 2022-12-31)
    base_date = pd.Timestamp("2018-01-01")
    random_days = rng.integers(0, 365 * 4, size=n_reviews)
    review_dates = [base_date + pd.Timedelta(days=int(d)) for d in random_days]

    # Review texts
    benign_phrases = [
        "The food here was absolutely delicious and the service was prompt.",
        "Had a wonderful experience with great ambiance and friendly staff.",
        "Average meal, nothing too special but good for a quick lunch.",
        "Excellent dinner spot with fresh ingredients and reasonable pricing.",
        "Decent portion sizes and fast checkout. Would consider coming back.",
        "The manager greeted us personally and the dessert menu was phenomenal."
    ]
    spam_phrases = [
        "BEST PLACE EVER! Five stars absolutely must visit right now!! Call them!",
        "Terrible scam horrible place do not ever buy from here worst ever!!",
        "Amazing unbeatable discount top tier quality best in Chicago 100% recommended!",
        "Total waste of money garbage service horrible food fake staff avoid!!",
        "Greatest deals anywhere in town call 555-1234 for special promotion!",
    ]

    texts = []
    for i in range(n_reviews):
        if labels[i] == 1:
            texts.append(f"{rng.choice(spam_phrases)} Review ID #{i} - {sampled_prods[i]}.")
        else:
            texts.append(f"{rng.choice(benign_phrases)} Order confirmed for {sampled_prods[i]} - {i}.")

    df = pd.DataFrame({
        "review_id": [f"rev_{i:06d}" for i in range(n_reviews)],
        "user_id": sampled_users,
        "prod_id": sampled_prods,
        "rating": ratings,
        "review_date": [d.strftime("%Y-%m-%d") for d in review_dates],
        "review_text": texts,
        "label": labels
    })

    df.to_csv(out_csv, index=False)
    print(f"Generated {len(df)} YelpChi reviews at {out_csv} ({spam_ratio*100:.1f}% spam)")
    return df


def main():
    parser = argparse.ArgumentParser(description="Get or prepare YelpChi raw data")
    parser.add_argument("--n-reviews", type=int, default=5000)
    parser.add_argument("--spam-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    raw_dir = get_raw_dir()
    raw_csv = os.path.join(raw_dir, "yelpchi_reviews.csv")
    if os.path.exists(raw_csv):
        print(f"Raw YelpChi dataset already exists at {raw_csv}")
    else:
        generate_standard_yelpchi(
            n_reviews=args.n_reviews,
            spam_ratio=args.spam_ratio,
            seed=args.seed
        )


if __name__ == "__main__":
    main()