"""Scientific contracts for selection, graph representation and published scores."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import importlib

import numpy as np
import torch
from sklearn.metrics import f1_score

from ml.benchmark_matched import select_threshold, sparse_edges, metrics
from ml.models.matched_baselines import build_matched_model

ROOT = Path(__file__).resolve().parents[2]


class MatchedEvaluationTests(unittest.TestCase):
    def test_encoder_failure_cannot_create_random_features(self):
        import pandas as pd
        module = importlib.import_module('data_pipeline.scripts.04_embed_text')
        frame = pd.DataFrame({'node_idx': [0], 'review_text': ['A genuine source review.']})
        with patch.object(module.os.path, 'exists', return_value=True), patch.object(module.pd, 'read_parquet', return_value=frame), patch('transformers.AutoTokenizer.from_pretrained', side_effect=RuntimeError('offline')), patch.object(module.torch, 'save') as writer:
            with self.assertRaisesRegex(RuntimeError, 'no embeddings were generated'):
                module.embed_reviews(use_gpu=False)
            writer.assert_not_called()

    def test_validation_threshold_matches_exhaustive_reference(self):
        rng = np.random.default_rng(941)
        for n in (40, 301, 1500):
            labels = (rng.random(n) < 0.15).astype(int)
            scores = np.round(rng.random(n), 2)
            candidates = np.linspace(0.01, 0.99, 199)
            f1 = [f1_score(labels, scores >= t, average='macro', zero_division=0) for t in candidates]
            expected = int(np.argmax(f1))
            threshold, actual = select_threshold(labels, scores)
            self.assertEqual(threshold, candidates[expected])
            self.assertAlmostEqual(actual, f1[expected], places=12)

    def test_sparse_graph_preserves_forward_results_and_gradients(self):
        torch.manual_seed(17)
        graph = {'review_ids': list('abcdef')}
        for relation in ('rur', 'rsr', 'rtr'):
            graph['edge_index_' + relation] = torch.tensor([[0, 0, 1, 2, 3], [1, 3, 3, 4, 5]])
        sparse = sparse_edges(graph)
        coo = {r: graph['edge_index_' + r] for r in ('rur', 'rsr', 'rtr')}
        for variant in ('text_only', 'graph_only', 'concat', 'neurograph'):
            model = build_matched_model(variant, text_dim=8, meta_dim=4, hidden_dim=12, dropout=0)
            text, meta = torch.randn(6, 8), torch.randn(6, 4)
            expected = model(text, meta, coo)
            expected.sum().backward()
            gradients = {n: p.grad.clone() for n, p in model.named_parameters() if p.grad is not None}
            model.zero_grad(set_to_none=True)
            actual = model(text, meta, sparse)
            actual.sum().backward()
            torch.testing.assert_close(actual, expected, atol=1e-6, rtol=1e-5)
            for name, p in model.named_parameters():
                if name in gradients:
                    torch.testing.assert_close(p.grad, gradients[name], atol=1e-5, rtol=1e-4)

    def test_stress_removal_has_no_label_dependency(self):
        graph = {'review_ids': list(range(100))}
        for r in ('rur', 'rsr', 'rtr'):
            graph['edge_index_' + r] = torch.stack((torch.arange(99), torch.arange(1, 100)))
        a, b = sparse_edges(graph, keep=0.7), sparse_edges(graph, keep=0.7)
        for r in a:
            torch.testing.assert_close(a[r].to_dense(), b[r].to_dense())
            self.assertLess(a[r]._nnz(), 99)

    def test_published_results_match_private_predictions_when_installed(self):
        directory = ROOT / 'artifacts/matched_benchmark/temporal_v1'
        if not (directory / 'report.json').is_file():
            self.skipTest('Private trained comparison artifacts are not installed')
        report = json.loads((directory / 'report.json').read_text())
        reference_indices = None
        reference_labels = None
        for model in report['models']:
            for run in model['runs']:
                with np.load(directory / f"{model['id']}_seed{run['seed']}" / 'predictions.npz') as p:
                    if reference_indices is None:
                        reference_indices = p['indices'].copy()
                        reference_labels = p['labels'].copy()
                    np.testing.assert_array_equal(p['indices'], reference_indices)
                    np.testing.assert_array_equal(p['labels'], reference_labels)
                    self.assertEqual(len(p['labels']), 9436)
                    calculated = metrics(p['labels'], p['scores'], run['test']['threshold'])
                    self.assertEqual(calculated, run['test'])
        self.assertEqual({m['id'] for m in report['models']}, {'text_only', 'graph_only', 'concat', 'neurograph'})

    def test_website_and_documentation_use_the_same_record(self):
        document = ROOT / 'docs/benchmarks/comparison.json'
        website = ROOT / 'db-dashboard/frontend/public/benchmarks/comparison.json'
        self.assertEqual(document.read_bytes(), website.read_bytes())
        report = json.loads(document.read_text())
        self.assertEqual(report['protocol']['split_counts'], {'train': 28305, 'validation': 9435, 'test': 9436})
        for model in report['models']:
            self.assertEqual([r['seed'] for r in model['runs']], [42, 43, 44])
            for metric in ('roc_auc', 'pr_auc', 'f1_macro'):
                values = [r['test'][metric] for r in model['runs']]
                self.assertAlmostEqual(model['aggregate'][metric]['mean'], np.mean(values), places=12)
                self.assertAlmostEqual(model['aggregate'][metric]['std'], np.std(values, ddof=1), places=12)
        for old in report['historical']:
            raw = json.loads((ROOT / 'docs/runs' / (old['record'] + '.json')).read_text())['test_metrics']
            self.assertEqual(old['auc'], raw['roc_auc'])
            self.assertEqual(old['f1'], raw['f1_macro'])
            self.assertEqual(old['ap'], raw['pr_auc'])


if __name__ == '__main__':
    unittest.main()
