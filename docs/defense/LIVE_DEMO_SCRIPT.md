# NeuroGraph-DB: current class demonstration

Allow about eight minutes. Use the [beginner viva guide](BEGINNER_VIVA_GUIDE.md) to understand the terms first. This route reflects the final model-first application, not the earlier synthetic-first dashboard.

Live application: https://frontend-three-snowy-10.vercel.app

## 1. Explain the purpose and final result — one minute

Open **Model results** with the researcher account.

> “We help investigate suspicious reviews using their words and connections to earlier reviews. The final model's test ROC-AUC is 0.8105 and macro F1 is 0.6624. These are measured on 9,436 later labelled reviews; they are not an accuracy guarantee for every uploaded CSV.”

Point out the final threshold, approximately 0.7871. A flag is a request for investigation, not proof of fraud.

## 2. Show the actual dataset — one minute

Open `output/viva/OPEN_FIRST.md`, then the 12-row example file and dataset/split proof. The original labelled source has 47,176 real historical Yelp reviews: 28,305 train, 9,435 validation, 9,436 test after chronological ordering. Show `test_exact.csv` and `metrics.json`.

> “Training teaches the model, validation chooses the checkpoint and threshold, and the test measures the locked choice. The downloaded file named testing_data.csv has no labels; it is not the source of these measured test results.”

The small example file deliberately shows both labels from all splits. It is an illustration, not the full test or a newly balanced evaluation.

## 3. Upload and reopen a saved result — two minutes

Open **Upload & analyze**. Download the site's sample CSV and upload it using the compatible, automatically selected historical context. Do not upload the labelled historical evidence files as new reviews.

> “Our model combines frozen RoBERTa text embeddings with three GraphSAGE relationship branches. The connections are same reviewer, same product and rating, and same product within 30 days. Only allowed earlier context is used, with at most 50 recent neighbors per relation.”

Show actual saved scores and relation evidence. Explain that attention is a model weight, not a proof of the real-world reason someone wrote a fake review. An unlabelled sample demonstrates the workflow, not measured accuracy.

Open **Products & history**, select the saved filename, and reopen its calculated result. A repeated identical upload can recover the earlier receipt/run. Show the analysis graph if available.

> “PostgreSQL stores the records and results. PyTorch calculates the scores. Neo4j stores the investigation graph projection.”

Do not promise an autonomous background worker: the current API invokes the processing function while retaining durable job/run state.

## 4. Show the controlled comparison and examples — one minute

Open **Model comparison**. Show the four arms on the same test, then select the three-seed mean. Concatenation has the highest mean; the deployed NeuroGraph seed-42 checkpoint has the highest seed-42 macro F1. Show the historical records below the charts and explain why those older experiments are excluded from the matched ranking.

Open **Example investigation**: point out the synthetic-data banner.

> “The new comparison keeps data and testing conditions fixed while changing architecture. Historical experiments and synthetic restaurant examples have different purposes and are clearly separated.”

Do not claim a controlled improvement over the structured MAT baseline or quote unmeasured SQL-versus-Neo4j response times.

## 5. Demonstrate human feedback and administration — one minute

In **Review feedback**, create a short disposable note about an accessible review, edit it while submitted, and show it in the list. An admin can triage, resolve or reject feedback. Resolved feedback is locked against ordinary author edits.

> “We preserve the original prediction and the human's judgment separately. Feedback does not retrain the model or overwrite its old score.”

Show the admin menus and account-creation function. Describe **Reviewer catalog** as source review authors, not website login users or confirmed fraudsters. Its current API is available to authenticated users even though the sidebar places it under Administration.

## 6. Show database and deployment evidence — one minute

Open the complete ERD and `backend/alembic/versions/0007_database_features.py`. Explain primary/foreign keys, the two aggregate views, feedback moderation procedure and feedback audit trigger. Show the isolated backup/restore evidence if asked.

> “The frontend is on Vercel. The FastAPI backend, PostgreSQL 16 and Neo4j 5 run in Docker on one AWS EC2 server. CloudFormation describes the infrastructure. The AWS Free plan uses finite credits; it is not unlimited free hosting.”

The **Audit operations** screen displays diagnostics, not the full audit table. Its generic readiness status includes a separate legacy model contract; use the active model's status and actual saved inference evidence when discussing that runtime.

Keep credential files off the projector. If a service fails during the demonstration, show saved evidence and state the limitation; do not invent live results.
