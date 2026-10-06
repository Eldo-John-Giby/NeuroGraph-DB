# Benchmark Results Summary

Performance of all models on clean YelpChi (mean +/- std over seeds):

| Model Architecture | ROC-AUC | PR-AUC | F1-Macro |
| :--- | :--- | :--- | :--- |
| `concat` | 0.9783 +/- 0.0042 | 0.9007 +/- 0.0164 | 0.8924 +/- 0.0175 |
| `gnn_only` | 0.7677 +/- 0.0230 | 0.3720 +/- 0.0479 | 0.6480 +/- 0.0204 |
| `neurograph` | 0.9841 +/- 0.0002 | 0.9306 +/- 0.0000 | 0.9089 +/- 0.0019 |
| `text_only` | 0.9784 +/- 0.0092 | 0.9126 +/- 0.0343 | 0.9042 +/- 0.0276 |
