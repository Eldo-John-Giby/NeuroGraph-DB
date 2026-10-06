import time

def mock_explain():
    print("Running EXPLAIN ANALYZE demos (Mock Mode)")
    queries = [
        "Reviews per user",
        "Avg rating per product",
        "Spam rate per month",
        "Top users by spam count",
        "Users-reviews-products join"
    ]
    for i, q in enumerate(queries):
        print(f"\nQuery {i+1}: {q}")
        print("  Without Index: 45ms (Sequential Scan)")
        print("  With Index: 5ms (Index Scan)")
        time.sleep(0.5)

if __name__ == '__main__':
    # In real usage, this would connect to postgres and run data_pipeline/sql/02_indexes.sql inside a transaction
    mock_explain()
