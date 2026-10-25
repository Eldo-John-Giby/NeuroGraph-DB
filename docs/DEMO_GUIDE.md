# NeuroGraph-DB Live Defense Demonstration Guide

This guide details the step-by-step procedures, environment prerequisites, and a seven-minute demonstration route for the NeuroGraph-DB academic defense.

---

## 1. Prerequisites & Startup Sequence

Ensure Docker Desktop is active before initiating system components.

### Port Requirements
- **PostgreSQL 15:** `localhost:5432`
- **Neo4j 5 (APOC):** `localhost:7474` (HTTP Browser), `localhost:7687` (Bolt)
- **FastAPI Backend:** `localhost:8000`
- **Next.js Frontend:** `localhost:3000`

### Step-by-Step Startup

```bash
# Terminal 1: Launch Storage Services
docker compose -f data_pipeline/docker-compose.postgres.yml up -d
docker compose -f viz/docker-compose.neo4j.yml up -d

# Terminal 2: Initialize Relational Database & Start FastAPI
cd backend
alembic upgrade head
python scripts/seed_roles.py
python scripts/seed_users.py
python scripts/register_verified_multimodal.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3: Launch Next.js Dashboard
cd db-dashboard/frontend
npm run dev
```

### Readiness Verification
Execute:
```bash
curl -s http://localhost:8000/health/ready | jq .
```
Expected response:
```json
{
  "status": "ready",
  "checks": {
    "postgresql": "ready",
    "verified_model": "ready",
    "neo4j": "ready"
  }
}
```

---

## 2. Sample Demo CSV Preparation

To demonstrate Lane 3 (Inductive Restaurant CSV Assessment), prepare a clean CSV file named `sample_restaurant_batch.csv` with the required six columns and **zero** ground-truth labels:

```csv
review_id,reviewer_id,product_id,rating,review_date,review_text
demo-rev-001,user-hist-1,prod-hist-1,5,2011-04-10,"Outstanding seasonal menu and attentive waitstaff. Will definitely return!"
demo-rev-002,user-bomb-99,prod-hist-1,1,2011-04-12,"Horrible experience. Rude staff, cold food, and completely overpriced. Avoid at all costs!"
demo-rev-003,user-bomb-99,prod-hist-2,1,2011-04-12,"Disgusting hygiene and terrible management. Zero stars if possible."
demo-rev-004,user-new-42,prod-hist-1,4,2011-04-15,"Pleasant ambiance and great dessert selection, though parking was difficult."
```

Save this file locally to your desktop or working directory for the intake demonstration.

---

## 3. Seven-Minute Demo Route

| Phase | Duration | Screen / Route | Core Message & Action |
|---|---|---|---|
| **1. Authentication** | 0:30 | `/login` | Log in as `admin@neurograph.local` using the one-click demo button. Emphasize Argon2id password hashing, database-backed session revocation, and RBAC enforcement. |
| **2. Risk Overview & 3 Lanes** | 1:00 | `/` | Present the three distinct visual lanes. Explain that Lane 1 is scenario evidence only, Lane 2 is a frozen transductive benchmark, and Lane 3 is live inductive scoring. |
| **3. Synthetic Neo4j Campaign** | 0:45 | `/campaigns/harbor-table-review-bombing-seed-42` | Inspect the Harbor Table review-bombing attack (100 synthetic reviews). Show PostgreSQL summary statistics and Neo4j Cypher multi-hop fraud ring detection. Reiterate: **no fake ML scores are shown here**. |
| **4. Verified Transductive Benchmark** | 0:45 | `/` (Lane 2) | Highlight the 47,176-review raw text YelpChi benchmark (ROC-AUC `0.8439`, F1 `0.6860`, threshold `0.6732`). Explain the frozen RoBERTa + PyG multi-relational architecture and transductive known-node boundary. |
| **5. Model Registry & Reproduction** | 0:45 | `/models` | Show the model registry. Highlight bundle manifest SHA-256 (`653729f3...`), pinned tokenizer revision (`e2da8e2f...`), and demonstrate that the serving layer reproduces fixed review `--AweNX8vPGD` within $1\times 10^{-6}$. |
| **6. Inductive CSV Intake** | 0:45 | `/reviews/submit` | Select the permitted historical graph context snapshot (`inductive-rur-rsr-rtr-v1`). Upload `sample_restaurant_batch.csv`. Point out immediate transactional schema validation and row-level acceptance. |
| **7. Queued / Completed Worker State** | 0:45 | `/reviews/submit` | Show the batch in `queued` status. Explain the durable leased worker queue (`inductive_inference_jobs`). Click **"Process now"** to execute temporal graph stitching and RoBERTa inference. |
| **8. Flagged Evidence & Relation Attention** | 1:15 | `/reviews/submit` (Lane 3) | Inspect scored results. Examine the risk distribution, actual fraud scores, and decision badges. Expand the **Relation Attention** bar (`RUR`, `RSR`, `RTR` %). Open the **Graph Evidence Modal** to reveal the 64-char stitched graph and embedding hashes. |
| **9. Audit Trail & Provenance** | 0:30 | `/admin/audit` | Conclude on the audit log. Show immutable records of session logins, snapshot permissions, and batch executions. Emphasize fail-closed safety and anti-leakage invariants. |

---

## 4. Disaster Recovery & Fallback Procedures

In the event of network disruption or local machine instability during the presentation, follow these pre-rehearsed recovery steps:

### Scenario A: Neo4j Service Unreachable
- **Symptoms:** Neo4j container stopped or connection refused on `7687`.
- **System Behavior:** FastAPI automatically isolates Neo4j; `/health/ready` reports `neo4j: unconfigured` or `degraded`. Relational and ML scoring operations remain fully functional.
- **Presenter Pivot:** State cleanly: *"Neo4j is decoupled from primary ingestion. PostgreSQL continues to serve as the ACID system of record, and model inference proceeds uninterrupted."*

### Scenario B: PyTorch / CUDA Kernel Initialization Delay
- **Symptoms:** First-time model execution takes several seconds to load RoBERTa weights into memory.
- **Action:** Pre-warm the model before the defense by executing `ml/reproduce_yelpchi_inductive_bundle.py` once.

### Scenario C: Unrecoverable Local Machine Crash
- **Mandatory Policy:** Pre-recorded backup footage of the complete 7-minute demonstration route must be available on a USB drive or secondary display.
- **Labeling Requirement:** If backup video footage is displayed, the presenter **must** verbally state:
  > *"Due to a hardware disruption, we are displaying pre-recorded footage of the live system execution recorded on this exact build with identical manifest checksums."*
  Never present pre-recorded footage as live interactive execution.
