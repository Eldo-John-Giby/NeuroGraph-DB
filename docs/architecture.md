# NeuroGraph-DB Architecture

## System Architecture

```mermaid
graph TD
    A[Raw YelpChi] -->|ETL Pipeline| B[(PostgreSQL)]
    B -->|neo4j_sync.py| C[(Neo4j)]
    B -->|PyTorch Pipeline| D[Fraud Predictions]
    D -->|neo4j_sync.py| C
    C -->|Query| E[Streamlit App]
```

## Entity-Relationship Diagram (Postgres)

```mermaid
erDiagram
    USER ||--o{ REVIEW : writes
    PRODUCT ||--o{ REVIEW : has
    USER {
        int user_id PK
        string name
    }
    PRODUCT {
        int prod_id PK
        string name
    }
    REVIEW {
        int review_id PK
        int user_id FK
        int prod_id FK
        float rating
        date date
        int label
        string text
    }
```

## Dual-Branch Cross-Attention Model

```mermaid
graph LR
    A[Text] -->|RoBERTa| B[Semantic Features]
    C[Relations] -->|GNN| D[Topology Features]
    B --> E((Multi-Head Cross-Attention))
    D --> E
    E --> F[Fraud Score]
```

## Camouflage Attack Pipeline

```mermaid
graph TD
    A[Spam Reviews] -->|LLM Rewrite| B[Semantic Camouflage]
    C[Spam Users] -->|Add Benign Reviews| D[Topology Camouflage]
    B --> E[Attacked Data]
    D --> E
```

## Threat Model and Evaluation Protocol

**Attacker Capability:** The attacker can rewrite their own spam text using an LLM (Semantic Camouflage) and can add benign-looking activity or reviews to regular products (Topology Camouflage) to evade detection.
**Out of Scope (NOT modeled):** Creating completely new accounts/nodes on the fly, label flipping, and white-box gradient attacks.

**Evaluation Protocols:**
- **Protocol A (Standard Evaluation):** Train on clean data, test on attacked data.
- **Protocol B (Adversarial Training):** Train on a mix of clean and attacked data, test on attacked data to measure robustness improvements.
