# NeuroGraph-DB Live Defense Demonstration Script

**Total Duration:** Exactly 7 Minutes (420 Seconds)  
**Presenter Tone:** Academically honest, rigorous, precise, and transparent.

---

### Step 1: Authentication & Role-Based Access Control
**Time Budget:** `[0:00 - 0:30]` (30 Seconds)  
**URL:** `http://localhost:3000/login`

> **Speaker Notes:**  
> "Good morning, members of the committee. We begin on the NeuroGraph-DB authentication portal.  
> 
> The system enforces role-based access control with Argon2id password hashing and database-backed session token revocation. We log in using our administrative demo credentials.  
> 
> Notice that session tokens are hashed and stored in PostgreSQL with explicit expiration timestamps, satisfying enterprise auditability requirements."

*(Action: Click 'Fill Admin Demo', then click 'Sign in'.)*

---

### Step 2: Risk Overview & The Three-Lane Architecture
**Time Budget:** `[0:30 - 1:30]` (60 Seconds)  
**URL:** `http://localhost:3000/`

> **Speaker Notes:**  
> "Upon login, we arrive at the Risk Overview dashboard. A central innovation of our software architecture is the **strict three-lane provenance separation** displayed on this page.  
> 
> - **Lane 1** at the top displays synthetic demonstration evidence from a simulated restaurant review-bombing campaign. We explicitly disclaim model output here: no fake ML scores are synthesized.  
> - **Lane 2** displays our frozen 47,176-review raw YelpChi transductive benchmark. It features our verified RoBERTa + PyG cross-attention model achieving an ROC-AUC of 0.8439.  
> - **Lane 3** at the bottom is our inductive restaurant batch scoring lane, where new review CSV uploads are evaluated against permitted historical graph contexts without data leakage.  
> 
> This visual separation prevents any confusion between synthetic demonstrations and verified scientific benchmarks."

---

### Step 3: Synthetic Neo4j Restaurant Campaign Exploration
**Time Budget:** `[1:30 - 2:15]` (45 Seconds)  
**URL:** `http://localhost:3000/campaigns/harbor-table-review-bombing-seed-42`

> **Speaker Notes:**  
> "Let us investigate Lane 1's Harbor Table campaign. This scenario models a coordinated 100-review attack on a single restaurant.  
> 
> PostgreSQL stores the 3NF review entities, while Neo4j visualizes the collusive graph topology. Here, Neo4j's index-free adjacency allows us to run Cypher queries that discover multi-hop reviewer rings sharing targeted products in under 7 milliseconds — a query that requires over 320 milliseconds in relational SQL self-joins.  
> 
> Once again, note the provenance banner: this is purely a topological demonstration; no model fraud scores are generated here."

---

### Step 4: Verified Transductive Benchmark Inspection
**Time Budget:** `[2:15 - 3:00]` (45 Seconds)  
**URL:** `http://localhost:3000/` (Scroll to Lane 2)

> **Speaker Notes:**  
> "Returning to the main dashboard, we inspect Lane 2: the verified transductive benchmark.  
> 
> Unlike legacy benchmarks that use anonymous 32-dimensional metadata matrices, this model operates directly on raw review text from 47,176 reviews. Frozen RoBERTa 768-dimensional embeddings are fused with PyG GraphSAGE representations across RUR, RSR, and RTR relations.  
> 
> It achieves a test ROC-AUC of 0.8439 and F1-macro of 0.6860 at threshold 0.6732. Because transductive models assume a closed-world graph, this serving runtime is strictly read-only and rejects arbitrary new reviews."

---

### Step 5: Model Registry, Manifest Hashes & Reproduction
**Time Budget:** `[3:00 - 3:45]` (45 Seconds)  
**URL:** `http://localhost:3000/models`

> **Speaker Notes:**  
> "To guarantee scientific reproducibility, we navigate to the Model Registry.  
> 
> Every model checkpoint must be accompanied by an immutable cryptographic manifest. Here, you see manifest SHA-256 `653729f3...` and the pinned Hugging Face tokenizer revision `e2da8e2f...`.  
> 
> On startup, the backend verifies all constituent file checksums and executes forward inference on fixed review `--AweNX8vPGD`. The serving adapter confirms the reproduced score matches within an absolute tolerance of 1e-6 without accessing ground-truth labels. If any byte diverges, the runtime fails closed."

---

### Step 6: Inductive CSV Intake & Transactional Validation
**Time Budget:** `[3:45 - 4:30]` (45 Seconds)  
**URL:** `http://localhost:3000/reviews/submit`

> **Speaker Notes:**  
> "Now we demonstrate Lane 3: live inductive batch scoring.  
> 
> In this intake portal, restaurant operators upload incoming review batches. Notice the historical context snapshot dropdown: we select permitted snapshot #1, which enforces the `inductive-rur-rsr-rtr-v1` relation policy.  
> 
> We select our prepared demo CSV. Notice that the CSV contains only review IDs, reviewer IDs, restaurant IDs, ratings, dates, and text — zero ground-truth label columns.  
> 
> When we click 'Validate & upload', PostgreSQL transactionally validates every row before any model scoring is attempted."

*(Action: Select Snapshot #1, select `sample_restaurant_batch.csv`, click 'Validate & upload'.)*

---

### Step 7: Queued Worker State & Asynchronous Execution
**Time Budget:** `[4:30 - 5:15]` (45 Seconds)  
**URL:** `http://localhost:3000/reviews/submit`

> **Speaker Notes:**  
> "Upon upload, the batch enters the `queued` state. Ingestion is fully decoupled from neural network inference.  
> 
> In the database, an `inference_run` and an `inductive_inference_job` have been created. Background workers claim these jobs using atomic database lease updates.  
> 
> We now click 'Process now' to trigger worker execution. The worker verifies the inductive bundle manifest (`9d4f10a8...`), builds strictly past-to-candidate edges, computes RoBERTa embeddings in bounded batches, and scores only the uploaded nodes."

*(Action: Click 'Process now'.)*

---

### Step 8: Flagged Review Evidence, Relation Attention & Graph Neighbors
**Time Budget:** `[5:15 - 6:30]` (75 Seconds)  
**URL:** `http://localhost:3000/reviews/submit` (Scroll to Lane 3 Scored Results)

> **Speaker Notes:**  
> "The batch has completed scoring. Let us examine the results.  
> 
> First, observe the summary statistics: the score distribution bar categorizes reviews into Low, Moderate, High, and Severe risk tiers based on our validation-calibrated threshold of 0.7871.  
> 
> Second, in the scored reviews table, each review displays its actual fraud score and decision badge. Expanding the relation-attention bar reveals the genuine weights emitted by the neural network: here, review `demo-rev-002` was flagged with high RSR (same rating) and RTR (temporal burst) attention weights.  
> 
> Third, we click 'View Evidence'. This modal displays the cryptographic provenance: the 64-character SHA-256 of the stitched PyG graph, the input feature matrix, the embedding matrix, and the exact list of up to 50 historical neighbor review IDs. Everything is auditable and mathematically verifiable."

*(Action: Click 'View Evidence' on a flagged review to show the modal with SHA-256 hashes.)*

---

### Step 9: Audit Trail & Closing Architectural Synthesis
**Time Budget:** `[6:30 - 7:00]` (30 Seconds)  
**URL:** `http://localhost:3000/admin/audit`

> **Speaker Notes:**  
> "Finally, we visit the Administrative Audit Log.  
> 
> Every session login, batch permission update, and inference run is recorded immutably in PostgreSQL with actor IDs, timestamps, and state diffs.  
> 
> In summary, NeuroGraph-DB demonstrates that relation-aware graph neural networks can be paired with modern language models to defeat camouflage review spam — while maintaining strict database integrity, honest inductive evaluation, and zero data leakage.  
> 
> Thank you, and we welcome your questions."
