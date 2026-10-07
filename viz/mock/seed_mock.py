import os
import random
import pandas as pd
import numpy as np
import json

os.makedirs('mock_data', exist_ok=True)
os.makedirs('artifacts/results/model_1', exist_ok=True)
os.makedirs('artifacts/camouflage', exist_ok=True)
os.makedirs('review_variants', exist_ok=True)

NUM_USERS = 300
NUM_PRODUCTS = 100
NUM_REVIEWS = 2000
NUM_RINGS = 3

users = pd.DataFrame({'user_id': range(1, NUM_USERS + 1), 'name': [f'User_{i}' for i in range(1, NUM_USERS + 1)]})
products = pd.DataFrame({'prod_id': range(1, NUM_PRODUCTS + 1), 'name': [f'Product_{i}' for i in range(1, NUM_PRODUCTS + 1)]})

reviews_data = []
for i in range(1, NUM_REVIEWS + 1 - NUM_RINGS * 10):
    reviews_data.append({
        'review_id': i,
        'user_id': random.randint(1, NUM_USERS),
        'prod_id': random.randint(1, NUM_PRODUCTS),
        'rating': random.choice([1.0, 2.0, 3.0, 4.0, 5.0]),
        'date': f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        'label': 0,
        'fraud_score': random.uniform(0.0, 0.4),
        'text_snippet': f'This is a normal review {i}',
        'node_idx': i
    })

# Plant fraud rings with camouflage reviews
start_idx = len(reviews_data) + 1
camo_edges = []
for ring in range(NUM_RINGS):
    ring_users = random.sample(range(1, NUM_USERS + 1), 5)
    ring_products = random.sample(range(1, NUM_PRODUCTS + 1), 3)
    
    # Fraudulent behavior
    for _ in range(10):
        u = random.choice(ring_users)
        p = random.choice(ring_products)
        rid = start_idx
        reviews_data.append({
            'review_id': rid,
            'user_id': u,
            'prod_id': p,
            'rating': 5.0,
            'date': "2023-10-01",
            'label': 1,
            'fraud_score': random.uniform(0.8, 1.0),
            'text_snippet': f'SPAM REVIEW {rid} - buy this now!',
            'node_idx': rid
        })
        start_idx += 1
        
        # Camouflage links (added later for variants)
        for _ in range(2):
            camo_edges.append({'src': rid, 'dst': random.randint(1, NUM_REVIEWS - 50), 'relation': 'CAMO_LINK', 'variant': 'topo_1'})

reviews = pd.DataFrame(reviews_data)

users.to_csv('mock_data/users.csv', index=False)
products.to_csv('mock_data/products.csv', index=False)
reviews.to_csv('mock_data/reviews.csv', index=False)

camo_df = pd.DataFrame(camo_edges)
camo_df.to_csv('artifacts/camouflage/edges_added_topo_1.csv', index=False)

# Semantic variants (rewritten texts)
semantic_variants = reviews.copy()
semantic_variants['text_snippet'] = semantic_variants['text_snippet'].apply(lambda x: x + " (LLM Rewritten)" if 'SPAM' in x else x)
semantic_variants.to_csv('review_variants/semantic_1.csv', index=False)

# Mock Metrics
metrics = {
    "AUC": 0.92,
    "F1-Macro": 0.88,
    "PR-AUC": 0.90
}
with open('artifacts/results/model_1/metrics.json', 'w') as f:
    json.dump(metrics, f)

# Fake robustness summary
robustness = pd.DataFrame({
    'model': ['NeuroGraph', 'NeuroGraph', 'Baseline', 'Baseline'],
    'variant': ['clean', 'topo_1', 'clean', 'topo_1'],
    'AUC': [0.95, 0.85, 0.80, 0.60],
    'F1-Macro': [0.92, 0.81, 0.75, 0.55],
    'PR-AUC': [0.94, 0.82, 0.77, 0.58],
    'attack_strength': [0, 1, 0, 1],
    'family': ['clean', 'topology', 'clean', 'topology']
})
robustness.to_csv('mock_data/robustness_summary.csv', index=False)

print("Mock data seeded.")
