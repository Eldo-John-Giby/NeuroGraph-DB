# Graph context sensitivity

The current [matched benchmark](../docs/benchmarks/README.md) includes a fixed, label-blind missing-context test. After clean training and validation selection, remove 10%, 30% or 50% of graph links with a fixed random seed. Retain model weights and each run's validation cutoff. Record the same test-set metrics.

The website plots ROC-AUC against the fraction of removed links. A text-only model is unchanged because it does not consume graph links. Edge removal is a sensitivity check, not evidence of resistance to actual coordinated attacks, topology camouflage or LLM-generated rewrites.

The older near-perfect Protocol A/B tables were produced on synthetic label-conditioned fixtures and are not real-data robustness evidence. They have been replaced by this explicitly scoped measured test.
