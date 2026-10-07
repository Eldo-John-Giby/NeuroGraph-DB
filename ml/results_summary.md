# Benchmark Results Summary

Performance of all models on clean YelpChi (mean +/- std over seeds):

| Model Architecture | ROC-AUC | PR-AUC | F1-Macro |
| :--- | :--- | :--- | :--- |
| `concat` | 0.9728 +/- 0.0031 | 0.9191 +/- 0.0080 | 0.9156 +/- 0.0062 |
| `gnn_only` | 0.9256 +/- 0.0023 | 0.7084 +/- 0.0130 | 0.7830 +/- 0.0056 |
| `neurograph` | 0.9943 +/- 0.0014 | 0.9754 +/- 0.0111 | 0.9366 +/- 0.0436 |
| `text_only` | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.9993 +/- 0.0012 |
