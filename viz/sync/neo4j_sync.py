import argparse
import pandas as pd
import os
from neo4j import GraphDatabase

def run_query(tx, query, parameters=None):
    return tx.run(query, parameters)

def sync_to_neo4j(uri, user, password, source, subgraph, variant, db_url=None):
    if db_url is None:
        db_url = os.environ.get("DATABASE_URL", "postgresql://neuro:neuro@localhost:5432/neurograph")

    if source == 'mock':
        users = pd.read_csv('mock_data/users.csv')
        products = pd.read_csv('mock_data/products.csv')
        reviews = pd.read_csv('mock_data/reviews.csv')
    else:
        # Connect to Postgres and fetch real data
        try:
            import psycopg2
            print(f"Connecting to PostgreSQL at {db_url}...")
            conn = psycopg2.connect(db_url)
            users_query = "SELECT user_id, user_id AS name FROM users;"
            products_query = "SELECT prod_id, prod_id AS name FROM products;"
            reviews_query = """
                SELECT 
                    r.review_id,
                    r.node_idx,
                    r.user_id,
                    r.prod_id,
                    r.rating,
                    r.review_date::text AS date,
                    r.label,
                    SUBSTRING(r.review_text FROM 1 FOR 120) AS text_snippet,
                    COALESCE(fp.fraud_score, 0.0) AS fraud_score
                FROM reviews r
                LEFT JOIN (
                    SELECT DISTINCT ON (review_id) review_id, fraud_score
                    FROM fraud_predictions
                    ORDER BY review_id, created_at DESC
                ) fp ON r.review_id = fp.review_id;
            """
            users = pd.read_sql(users_query, conn)
            products = pd.read_sql(products_query, conn)
            reviews = pd.read_sql(reviews_query, conn)
            conn.close()
            print(f"Fetched {len(users)} users, {len(products)} products, and {len(reviews)} reviews from PostgreSQL.")
        except Exception as e:
            print(f"PostgreSQL connection unavailable ({e}). Falling back to local processed YelpChi dataset...")
            parquet_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data_pipeline', 'raw', 'processed_reviews.parquet')
            if os.path.exists(parquet_path):
                raw_df = pd.read_parquet(parquet_path)
                users = pd.DataFrame({'user_id': raw_df['user_id'].unique(), 'name': raw_df['user_id'].unique()})
                products = pd.DataFrame({'prod_id': raw_df['prod_id'].unique(), 'name': raw_df['prod_id'].unique()})
                reviews = raw_df[['review_id', 'node_idx', 'user_id', 'prod_id', 'rating', 'label']].copy()
                reviews['date'] = raw_df['review_date'].astype(str)
                reviews['text_snippet'] = raw_df['review_text'].astype(str).str.slice(0, 120)
                reviews['fraud_score'] = 0.0
                print(f"Loaded {len(users)} users, {len(products)} products, {len(reviews)} reviews from YelpChi parquet.")
            else:
                users = pd.read_csv('mock_data/users.csv')
                products = pd.read_csv('mock_data/products.csv')
                reviews = pd.read_csv('mock_data/reviews.csv')

    if 'name' not in users.columns:
        users['name'] = users['user_id']
    if 'name' not in products.columns:
        products['name'] = products['prod_id']

    if variant and os.path.exists(f'review_variants/{variant}.csv'):
        reviews = pd.read_csv(f'review_variants/{variant}.csv')

    reviews['fraud_score'] = pd.to_numeric(reviews['fraud_score'], errors='coerce').fillna(0.0)

    if subgraph:
        n_samples = min(3000, len(reviews))
        reviews = reviews.nlargest(n_samples, 'fraud_score')
        valid_users = reviews['user_id'].unique()
        valid_products = reviews['prod_id'].unique()
        users = users[users['user_id'].isin(valid_users)]
        products = products[products['prod_id'].isin(valid_products)]

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
    except Exception as e:
        print(f"Unable to create Neo4j driver ({e}).")
        return

    try:
        with driver.session() as session:
            # Constraints
            session.execute_write(run_query, "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE")
            session.execute_write(run_query, "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.prod_id IS UNIQUE")
            session.execute_write(run_query, "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Review) REQUIRE r.review_id IS UNIQUE")

            # Sync Users (Batched)
            users_batch = users.to_dict('records')
            for i in range(0, len(users_batch), 5000):
                session.execute_write(run_query, """
                    UNWIND $batch AS row
                    MERGE (u:User {user_id: row.user_id})
                    SET u.name = row.name
                """, {"batch": users_batch[i:i+5000]})

            # Sync Products
            products_batch = products.to_dict('records')
            for i in range(0, len(products_batch), 5000):
                session.execute_write(run_query, """
                    UNWIND $batch AS row
                    MERGE (p:Product {prod_id: row.prod_id})
                    SET p.name = row.name
                """, {"batch": products_batch[i:i+5000]})

            # Sync Reviews and Edges
            reviews_batch = reviews.to_dict('records')
            for i in range(0, len(reviews_batch), 5000):
                session.execute_write(run_query, """
                    UNWIND $batch AS row
                    MERGE (r:Review {review_id: row.review_id})
                    SET r.node_idx = row.node_idx, r.rating = row.rating, r.date = toString(row.date), 
                        r.label = row.label, r.fraud_score = row.fraud_score, r.text_snippet = row.text_snippet
                    WITH row, r
                    MATCH (u:User {user_id: row.user_id})
                    MATCH (p:Product {prod_id: row.prod_id})
                    MERGE (u)-[:WROTE]->(r)
                    MERGE (r)-[:ABOUT]->(p)
                """, {"batch": reviews_batch[i:i+5000]})

            # Topology Variant
            if variant and subgraph:
                camo_file = f'artifacts/camouflage/edges_added_{variant}.csv'
                if os.path.exists(camo_file):
                    camo = pd.read_csv(camo_file)
                    camo_batch = camo.to_dict('records')
                    for i in range(0, len(camo_batch), 5000):
                        session.execute_write(run_query, """
                            UNWIND $batch AS row
                            MATCH (r1:Review {review_id: row.src})
                            MATCH (r2:Review {review_id: row.dst})
                            MERGE (r1)-[rel:CAMO_LINK]->(r2)
                            SET rel.variant = row.variant
                        """, {"batch": camo_batch[i:i+5000]})
        print("Neo4j sync complete.")
    except Exception as e:
        print(f"Neo4j sync failed ({e}). Check if Neo4j is running.")
    finally:
        driver.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='postgres', choices=['mock', 'postgres'])
    parser.add_argument('--subgraph', action='store_true')
    parser.add_argument('--variant', type=str, default=None)
    parser.add_argument('--db-url', type=str, default=None)
    parser.add_argument('--neo4j-uri', type=str, default=os.environ.get("NEO4J_URI", "neo4j://localhost:7687"))
    parser.add_argument('--neo4j-user', type=str, default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument('--neo4j-password', type=str, default=os.environ.get("NEO4J_PASSWORD", "neurograph123"))
    args = parser.parse_args()
    
    sync_to_neo4j(args.neo4j_uri, args.neo4j_user, args.neo4j_password, args.source, args.subgraph, args.variant, db_url=args.db_url)
