# Project documentation

Start with the root README for the live application and installation. The maintained technical documents are:

- [Architecture](ARCHITECTURE.md): deployed components and data flow.
- [Model comparison](benchmarks/README.md): four architectures on one fixed real-data test set, recorded runs and reproduction.
- [Model card](MODEL_CARD.md): deployed model, data, decision cutoff and limitations.
- [Data and model provenance](MODEL_AUDIT.md): the boundary between real-data results and obsolete synthetic experiments.
- [API](API_CONTRACT.md): implemented routes and access boundaries.
- [CSV workflow](BATCH_ANALYSIS.md): ingestion, scoring, ownership and saved results.
- [Complete ER diagram](submission/ERD.md), [data dictionary](submission/DATA_DICTIONARY.md) and [normalization](submission/NORMALIZATION.md).
- [Reproduction](REPRODUCIBILITY.md), [deployment](../deploy/aws/README.md) and [release checks](RELEASE_CHECKLIST.md).
- [Course report](submission/REPORT.md), [rubric mapping](submission/RUBRIC.md) and [demonstration](submission/DEMO.md).
- [Final usability review](USABILITY_REVIEW.md): concrete findings, fixes and live workflow checks.
- [CI and release boundaries](CI_AND_RELEASE.md), including the pipeline bonus evidence.
- [Independent review brief](review/INDEPENDENT_REVIEW.md).
- [Plain-English viva guide](defense/BEGINNER_VIVA_GUIDE.md).

The individual records under `runs/` preserve three historical experiments. Their scores are not ranked together because the data representations or evaluation protocols differ. The new matched comparison under `benchmarks/` evaluates four model arms on the same chronological split.
