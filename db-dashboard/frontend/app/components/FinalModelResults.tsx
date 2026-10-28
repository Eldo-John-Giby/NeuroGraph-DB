'use client';
import { useCallback, useEffect, useState } from 'react';
import { apiRequest, getErrorMessage } from '../lib/api';

type ModelStatus = { available: boolean; details?: string; run_id: string; manifest_sha256: string; threshold: number; reproduction_verified: boolean; metrics: { roc_auc: number; f1_macro: number; pr_auc: number }; split: { train_nodes: number; validation_nodes: number; test_nodes: number } };

export default function FinalModelResults() {
  const [status,setStatus] = useState<ModelStatus|null>(null);
  const [error,setError] = useState('');
  const [loading,setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { const result = await apiRequest<ModelStatus>('/api/v1/verified-inductive/status'); if (!result.available) throw new Error(result.details || 'Model unavailable'); setStatus(result); }
    catch (e) { setError(getErrorMessage(e)); } finally { setLoading(false); }
  },[]);
  useEffect(()=>{ void load(); },[load]);
  return <section className="model-results-section" aria-label="Final model test results">
    <div className="section-heading"><div><p className="eyebrow">Final model · RoBERTa + relational GNN</p><h2>Tested on reviews it had never seen.</h2></div><span className="verified-chip">Inductive temporal replay</span></div>
    <p className="muted">The final model combines review text, reviewer connections, product ratings, and timing. These are held-out test results from the verified training bundle.</p>
    {loading && <div className="notice-card" role="status">Verifying model results…</div>}
    {error && <div className="notice-card notice-error" role="alert"><p>{error}</p><button className="text-action" onClick={load}>Retry model check</button></div>}
    {!loading && !error && status && <>
      <div className="model-metrics">
        <article><span>Test ROC-AUC</span><strong>{status.metrics.roc_auc.toFixed(4)}</strong><small>Ranking suspicious reviews</small></article>
        <article><span>Test F1-macro</span><strong>{status.metrics.f1_macro.toFixed(4)}</strong><small>Balanced across both classes</small></article>
        <article><span>Test PR-AUC</span><strong>{status.metrics.pr_auc.toFixed(4)}</strong><small>Precision–recall under imbalance</small></article>
        <article><span>Unseen test reviews</span><strong>{status.split.test_nodes.toLocaleString()}</strong><small>Chronologically held out</small></article>
      </div>
      <div className="result-proof"><span className="verified-dot"/>Checksum and fixed-review reproduction verified<span>Decision threshold: <strong>{status.threshold.toFixed(4)}</strong> · selected on validation data</span></div>
      <details className="proof-details"><summary>Inspect the evaluation and model identity</summary><p>Training: {status.split.train_nodes.toLocaleString()} reviews · Validation: {status.split.validation_nodes.toLocaleString()} · Test: {status.split.test_nodes.toLocaleString()}. Past-to-new-review edges preserve the temporal boundary. Performance on your own unlabelled CSV cannot be measured without ground-truth labels.</p><dl><dt>Run</dt><dd>{status.run_id}</dd><dt>SHA-256 manifest</dt><dd>{status.manifest_sha256}</dd></dl></details>
    </>}
  </section>;
}
