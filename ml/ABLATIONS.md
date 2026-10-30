# Controlled model ablations

The [matched benchmark](../docs/benchmarks/README.md) varies architecture while holding the real review identities, chronological split, validation-selection objective, text encoder and eligible graph construction fixed.

The four arms are text-only, graph-only, simple concatenation and NeuroGraph attention/gated fusion. Input modalities and parameter counts intentionally differ; these are architecture ablations, not equal-parameter replicas. The website provides exact seed results and three-seed mean/sample SD.

Earlier synthetic ablation scores are superseded. They cannot establish performance on real review text or an independent held-out dataset.
