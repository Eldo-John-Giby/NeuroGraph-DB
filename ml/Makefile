.PHONY: all mock train-all ablate robustness attention export test clean

PYTHON ?= python

all: mock train-all robustness ablate attention

mock:
	$(PYTHON) mock_data.py

train-all:
	$(PYTHON) train.py --model text_only --epochs 60
	$(PYTHON) train.py --model gnn_only --epochs 60
	$(PYTHON) train.py --model concat --epochs 60
	$(PYTHON) train.py --model neurograph --epochs 60

ablate:
	$(PYTHON) ablations.py --epochs 50

robustness:
	$(PYTHON) robustness.py --epochs 50

attention:
	$(PYTHON) attention_analysis.py --epochs 50

export:
	$(PYTHON) export_predictions.py --run-id $$(ls -t ../artifacts/predictions/*.parquet 2>/dev/null | head -n 1 | sed 's/.*predictions\///' | sed 's/\.parquet//')

test:
	$(PYTHON) -m pytest tests/
