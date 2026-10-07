import argparse
import pandas as pd
import os
from neo4j import GraphDatabase

def run_query(tx, query, parameters=None):
    return tx.run(query, parameters)

def sync_to_neo4j(uri, user, password, source, subgraph, variant):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    if source == 'mock':
        users = pd.read_csv('mock_data/users.csv')
        products = pd.read_csv('mock_data/products.csv')
        reviews = pd.read_csv('mock_data/reviews.csv')
    else:
        # Connect to Postgres and fetch data (mocked here for brevity if no PG)
        print("Postgres connection not implemented in mock mode. Use --source mock")
        return

    if variant and os.path.exists(f'review_variants/{variant}.csv'):
        reviews = pd.read_csv(f'review_variants/{variant}.csv')

    if subgraph:
        reviews = reviews.nlargest(3000, 'fraud_score')
        valid_users = reviews['user_id'].unique()
        valid_products = reviews['prod_id'].unique()
        users = users[users['user_id'].isin(valid_users)]
        products = products[products['prod_id'].isin(valid_products)]

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
                SET r.node_idx = row.node_idx, r.rating = row.rating, r.date = row.date, 
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
    
    driver.close()
    print("Sync complete.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='mock', choices=['mock', 'postgres'])
    parser.add_argument('--subgraph', action='store_true')
    parser.add_argument('--variant', type=str, default=None)
    args = parser.parse_args()
    
    sync_to_neo4j("neo4j://localhost:7687", "neo4j", "neurograph123", args.source, args.subgraph, args.variant)
