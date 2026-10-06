# NeuroGraph-DB

Relation-aware multimodal fraud detection on YelpChi with RoBERTa + relation-aware GNN + multi-head cross-attention.
Evaluated under LLM-generated semantic and topology camouflage; PostgreSQL + Neo4j.

## Folder Ownership

| Folder | Owner |
| --- | --- |
| `data_pipeline/` (incl. `camouflage/`) | Avaneesh |
| `ml/` | Eldo |
| `viz/` and `docs/` | Anubhav |

## Repository Rules

- Only edit your own folder.
- Never commit `artifacts/`.
- Branch naming: `<name>/<feature>`.
- Run `git pull --rebase origin main` before every push.
- PRs touch only your own folder.
- Cross-folder handoff only via `artifacts/` contracts.
