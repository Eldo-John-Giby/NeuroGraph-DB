#!/usr/bin/env python3
"""Publish recorded benchmark evidence, never handwritten performance numbers."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'artifacts/matched_benchmark/temporal_v1')
    args = parser.parse_args()
    source = args.source
    report = json.loads((source / 'report.json').read_text())
    if fingerprint(source / 'protocol.json') != report['protocol_sha256']:
        raise ValueError('Protocol fingerprint changed')
    if {m['id'] for m in report['models']} != {'text_only', 'graph_only', 'concat', 'neurograph'}:
        raise ValueError('Four complete model arms are required')
    docs = ROOT / 'docs/benchmarks'
    docs.mkdir(parents=True, exist_ok=True)
    for model in report['models']:
        if sorted(r['seed'] for r in model['runs']) != [42, 43, 44]:
            raise ValueError('Three fixed training seeds are required')
        for run in model['runs']:
            name = f"{model['id']}_seed{run['seed']}"
            directory = source / name
            manifest = json.loads((directory / 'manifest.json').read_text())
            if fingerprint(directory / 'manifest.json') != report['artifact_manifests'][name] or manifest['protocol_sha256'] != report['protocol_sha256']:
                raise ValueError('Run manifest changed: ' + name)
            for filename, expected in manifest['files'].items():
                if fingerprint(directory / filename) != expected:
                    raise ValueError('Run artifact changed: ' + name + '/' + filename)
            for filename in ('manifest.json', 'result.json', 'selection.json', 'training_log.json'):
                target = docs / 'runs' / name / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(directory / filename, target)
    records = [
        ('yelpchi_gnn_seed42_20261024T234034Z', 'Structured MAT GNN', '45,954 reviews · 32 supplied numeric features', 'Known-node graph; no raw-text encoder'),
        ('raw_yelpchi_multimodal_seed42_20261025T071547Z', 'Earlier raw multimodal model', '47,176 raw reviews · random stratified split', 'Known-node graph; RoBERTa + GraphSAGE'),
        ('raw_yelpchi_inductive_seed42_20261025T125837Z', 'Deployed NeuroGraph checkpoint', '47,176 raw reviews · chronological split', 'Temporal arrival replay · also the seed-42 arm above'),
    ]
    report['historical'] = []
    for record, name, dataset, protocol in records:
        raw = json.loads((ROOT / 'docs/runs' / (record + '.json')).read_text())
        scores = raw['test_metrics']
        report['historical'].append({'record': record, 'name': name, 'dataset': dataset, 'protocol': protocol,
            'auc': scores['roc_auc'], 'f1': scores['f1_macro'], 'ap': scores['pr_auc'], 'threshold': scores['threshold']})
    report['publication'] = {'training_report_sha256': fingerprint(source / 'report.json'),
        'historical_results_in_matched_ranking': False,
        'live_context_note': 'Temporal replay includes earlier unlabelled arrivals; a live snapshot and uploaded batch may provide different history.'}
    published = docs / 'comparison.json'
    published.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    shutil.copyfile(source / 'protocol.json', docs / 'protocol.json')
    website = ROOT / 'db-dashboard/frontend/public/benchmarks'
    website.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(published, website / 'comparison.json')
    with (docs / 'results.csv').open('w', newline='') as handle:
        fields = ['model', 'seed', 'roc_auc', 'pr_auc', 'f1_macro', 'precision', 'recall', 'threshold', 'best_epoch', 'reused_deployed_checkpoint']
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for model in report['models']:
            for run in model['runs']:
                writer.writerow({'model': model['id'], 'seed': run['seed'], 'best_epoch': run['best_epoch'],
                    'reused_deployed_checkpoint': run['reused_deployed_checkpoint'], **{key: run['test'][key] for key in fields[2:8]}})
    print(json.dumps({'published': str(published), 'website': str(website / 'comparison.json'), 'sha256': fingerprint(published)}, indent=2))


if __name__ == '__main__':
    main()
