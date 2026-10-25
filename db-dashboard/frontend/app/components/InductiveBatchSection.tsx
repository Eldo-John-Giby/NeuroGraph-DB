'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  FileSpreadsheet,
  Layers,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  Check,
  RefreshCw,
  Play,
  Info,
  XCircle,
  Hash,
} from 'lucide-react';
import { apiRequest, getErrorMessage } from '../lib/api';

export interface BatchAnalysisSummary {
  batch_analysis_id: number;
  batch_key: string;
  status: string;
  row_count: number;
  accepted_count: number;
  rejected_count: number;
  inference_run_id: number | null;
  historic_graph_snapshot_id: number | null;
  upload_sha256: string;
  blocking_reasons: string[];
  created_at: string;
  scoring_available?: boolean;
  inference_run?: {
    inference_run_id: number;
    run_key: string;
    status: string;
    threshold: number;
    requested_count: number;
    completed_count: number;
    created_at: string;
    completed_at: string | null;
  } | null;
  job?: {
    job_id: number;
    status: string;
    attempt_count: number;
    max_attempts: number;
    worker_id: string | null;
    last_error_code: string | null;
    last_error: string | null;
  } | null;
}

export interface PredictionEvidence {
  graph_snapshot_id: number;
  relation_schema_version: string;
  context_cutoff_at: string | null;
  neighbor_counts: {
    rur?: number;
    rsr?: number;
    rtr?: number;
  };
  historic_review_ids: number[];
  stitched_graph_sha256: string;
  input_feature_sha256: string;
  embedding_sha256: string;
  bundle_manifest_sha256: string;
}

export interface BatchRowResult {
  row_number: number;
  row_state: string;
  uploaded_review_key: string | null;
  validation_errors: Array<{ field?: string; code?: string; message?: string }>;
  review: {
    review_id: number;
    reviewer_id: number | null;
    product_id: number | null;
    rating: number | null;
    reviewed_at: string | null;
    review_text: string | null;
  } | null;
  prediction: {
    fraud_prediction_id: number;
    risk_score: number;
    predicted_label: number;
    decision: 'flagged' | 'cleared';
    attention_weights: {
      rur?: number;
      rsr?: number;
      rtr?: number;
    };
    graph_status: string;
    evidence: PredictionEvidence | null;
  } | null;
}

function truncateHash(hash: string, lead = 8, trail = 8): string {
  if (!hash) return '—';
  if (hash.length <= lead + trail) return hash;
  return `${hash.slice(0, lead)}...${hash.slice(-trail)}`;
}

export function InductiveBatchSection({
  initialBatchId,
  showHeading = true,
}: {
  initialBatchId?: number;
  showHeading?: boolean;
}) {
  const [batches, setBatches] = useState<BatchAnalysisSummary[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(initialBatchId ?? null);
  const [currentBatch, setCurrentBatch] = useState<BatchAnalysisSummary | null>(null);
  const [results, setResults] = useState<BatchRowResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [scoring, setScoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<{
    reviewKey: string;
    evidence: PredictionEvidence;
    score: number;
    decision: string;
  } | null>(null);

  const copyToClipboard = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    }
  };

  const fetchBatches = useCallback(async () => {
    try {
      const data = await apiRequest<{ items: BatchAnalysisSummary[] }>('/api/v1/batch-analyses?limit=20');
      const list = data.items || [];
      setBatches(list);
      if (list.length > 0 && selectedBatchId === null) {
        setSelectedBatchId(list[0].batch_analysis_id);
      }
    } catch (err) {
      // If no batches exist yet, that is normal
      setBatches([]);
    }
  }, [selectedBatchId]);

  const fetchBatchDetails = useCallback(async (batchId: number) => {
    setLoading(true);
    setError(null);
    try {
      const [batchData, resultsData] = await Promise.all([
        apiRequest<BatchAnalysisSummary>(`/api/v1/batch-analyses/${batchId}`),
        apiRequest<{ items: BatchRowResult[] }>(`/api/v1/batch-analyses/${batchId}/results?limit=50`),
      ]);
      setCurrentBatch(batchData);
      setResults(resultsData.items || []);
    } catch (err) {
      setError(getErrorMessage(err));
      setCurrentBatch(null);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchBatches();
  }, [fetchBatches]);

  useEffect(() => {
    if (initialBatchId) {
      setSelectedBatchId(initialBatchId);
    }
  }, [initialBatchId]);

  useEffect(() => {
    if (selectedBatchId !== null) {
      void fetchBatchDetails(selectedBatchId);
    } else {
      setLoading(false);
    }
  }, [selectedBatchId, fetchBatchDetails]);

  const handleScoreBatch = async () => {
    if (!selectedBatchId) return;
    setScoring(true);
    setError(null);
    try {
      await apiRequest<BatchAnalysisSummary>(`/api/v1/batch-analyses/${selectedBatchId}/score`, {
        method: 'POST',
      });
      await fetchBatchDetails(selectedBatchId);
      await fetchBatches();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setScoring(false);
    }
  };

  // Distribution calculations
  const stats = useMemo(() => {
    const scored = results.filter((r) => r.prediction !== null);
    if (!scored.length) return null;

    let low = 0;
    let moderate = 0;
    let elevated = 0;
    let high = 0;
    let flagged = 0;

    for (const item of scored) {
      const s = item.prediction!.risk_score;
      if (item.prediction!.decision === 'flagged') flagged++;
      if (s < 0.25) low++;
      else if (s < 0.5) moderate++;
      else if (s < 0.787) elevated++;
      else high++;
    }

    return {
      totalScored: scored.length,
      flaggedCount: flagged,
      clearedCount: scored.length - flagged,
      flagRate: (flagged / scored.length) * 100,
      distribution: [
        { label: 'Low (<0.25)', count: low, pct: (low / scored.length) * 100, color: 'bg-emerald-500' },
        { label: 'Moderate (0.25-0.50)', count: moderate, pct: (moderate / scored.length) * 100, color: 'bg-teal-500' },
        { label: 'Elevated (0.50-0.787)', count: elevated, pct: (elevated / scored.length) * 100, color: 'bg-amber-500' },
        { label: 'High (≥0.787)', count: high, pct: (high / scored.length) * 100, color: 'bg-rose-500' },
      ],
    };
  }, [results]);

  return (
    <div className="space-y-4 pt-6 border-t border-[#e2e5df]">
      {showHeading && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#6366f1]">
              Lane 3: Inductive Restaurant CSV Assessment
            </span>
          </div>
          <div className="flex items-center gap-2">
            {batches.length > 0 && (
              <select
                className="text-xs bg-[#fffefa] border border-[#d2d9d4] rounded px-2.5 py-1 text-[#22302a] focus:outline-none focus:ring-1 focus:ring-[#6366f1]"
                value={selectedBatchId ?? ''}
                onChange={(e) => setSelectedBatchId(Number(e.target.value))}
              >
                {batches.map((b) => (
                  <option key={b.batch_analysis_id} value={b.batch_analysis_id}>
                    Batch #{b.batch_analysis_id} ({b.status} · {b.accepted_count} rows)
                  </option>
                ))}
              </select>
            )}
            <button
              onClick={() => {
                if (selectedBatchId !== null) void fetchBatchDetails(selectedBatchId);
                void fetchBatches();
              }}
              className="button-secondary text-xs py-1 px-2.5 inline-flex items-center gap-1.5"
              disabled={loading || scoring}
            >
              <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      )}

      {/* Provenance Banner */}
      <div className="bg-[#f5f3ff] border border-[#ddd6fe] rounded-md px-3.5 py-2 flex items-center justify-between text-xs text-[#5b21b6]">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="h-4 w-4 text-[#7c3aed]" />
          <span>
            <strong>INDUCTIVE RESTAURANT BATCH SCORING</strong> — Real-time temporal graph inference on uploaded CSVs
          </span>
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[#6d28d9] bg-[#ede9fe] px-2 py-0.5 rounded">
          inductive-rur-rsr-rtr-v1
        </span>
      </div>

      {loading && (
        <div className="notice-card text-xs text-[#74817b] animate-pulse">
          Loading inductive batch data…
        </div>
      )}

      {!loading && error && (
        <div className="notice-card notice-error text-xs">
          <strong>Batch assessment unavailable</strong>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && !currentBatch && (
        <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] p-8 text-center text-xs text-[#74817b]">
          <FileSpreadsheet className="h-8 w-8 text-[#9ba6a0] mx-auto mb-2" />
          <p className="font-semibold text-[#22302a] text-sm mb-1">No Inductive Batch Uploads Found</p>
          <p className="max-w-md mx-auto mb-4 text-[#74817b]">
            Upload a restaurant review CSV in the intake workspace with a permitted snapshot to trigger real-time inductive GNN scoring.
          </p>
        </div>
      )}

      {!loading && currentBatch && (
        <>
          {/* Status Alert for Incomplete Batches */}
          {currentBatch.status === 'queued' && (
            <div className="rounded-lg border border-[#fed7aa] bg-[#fff7ed] p-4 text-xs text-[#9a3412] flex items-start justify-between gap-3">
              <div className="flex items-start gap-2.5">
                <Clock className="h-4 w-4 text-[#ea580c] mt-0.5 shrink-0" />
                <div>
                  <strong className="block text-sm text-[#7c2d12]">Batch #{currentBatch.batch_analysis_id} is Queued</strong>
                  <p className="mt-0.5 text-[#9a3412]">
                    Review records are persisted. Inference is queued in the durable worker queue. No placeholder scores or synthetic predictions are displayed.
                  </p>
                </div>
              </div>
              <button
                onClick={handleScoreBatch}
                disabled={scoring}
                className="button-primary bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs px-3 py-1.5 shrink-0 inline-flex items-center gap-1.5"
              >
                <Play className="h-3 w-3" />
                {scoring ? 'Scoring…' : 'Process now'}
              </button>
            </div>
          )}

          {currentBatch.status === 'failed' && (
            <div className="rounded-lg border border-[#fecdd3] bg-[#fff1f2] p-4 text-xs text-[#9f1239] flex items-start gap-2.5">
              <XCircle className="h-4 w-4 text-[#e11d48] mt-0.5 shrink-0" />
              <div>
                <strong className="block text-sm text-[#881337]">Batch #{currentBatch.batch_analysis_id} Failed</strong>
                <p className="mt-0.5 text-[#9f1239]">
                  Inference failed: {currentBatch.job?.last_error || currentBatch.blocking_reasons.join(', ') || 'Worker execution error'}. No fabricated predictions were written.
                </p>
              </div>
            </div>
          )}

          {currentBatch.status === 'blocked' && (
            <div className="rounded-lg border border-[#e2e5df] bg-[#f9faf7] p-4 text-xs text-[#74817b] flex items-start gap-2.5">
              <AlertTriangle className="h-4 w-4 text-[#f59e0b] mt-0.5 shrink-0" />
              <div>
                <strong className="block text-sm text-[#22302a]">Scoring Blocked</strong>
                <p className="mt-0.5 text-[#74817b]">
                  Requirements not satisfied: {currentBatch.blocking_reasons.join(', ')}.
                </p>
              </div>
            </div>
          )}

          {/* Metric Overview Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <article className="metric-card">
              <p>Model version</p>
              <div className="text-sm font-semibold truncate text-[#22302a]">
                raw-yelpchi-inductive-roberta-gnn-v1
              </div>
              <small className="flex items-center gap-1 font-mono text-[10px] text-[#74817b]">
                Manifest: {truncateHash(results[0]?.prediction?.evidence?.bundle_manifest_sha256 || '9d4f10a81937987ae7588d86e29191d355af296c6efc29ec3e5b331282d23edd', 6, 6)}
                <button
                  onClick={() =>
                    copyToClipboard(
                      results[0]?.prediction?.evidence?.bundle_manifest_sha256 ||
                        '9d4f10a81937987ae7588d86e29191d355af296c6efc29ec3e5b331282d23edd',
                      'manifest'
                    )
                  }
                  className="hover:text-[#22302a]"
                >
                  {copiedKey === 'manifest' ? <Check className="h-2.5 w-2.5 text-emerald-600" /> : <Copy className="h-2.5 w-2.5" />}
                </button>
              </small>
            </article>

            <article className="metric-card">
              <p>Graph context scope</p>
              <div className="text-sm font-semibold text-[#22302a]">
                Snapshot #{currentBatch.historic_graph_snapshot_id ?? '1'}
              </div>
              <small className="text-[10px] text-[#74817b]">
                Scope: inductive-rur-rsr-rtr-v1 (47,176 nodes)
              </small>
            </article>

            <article className="metric-card">
              <p>Decision threshold</p>
              <div className="text-sm font-semibold text-[#22302a]">
                0.787071
              </div>
              <small className="text-[10px] text-[#74817b]">
                Derived from validation set; test labels untouched
              </small>
            </article>

            <article className="metric-card">
              <p>Intake breakdown</p>
              <div className="text-sm font-semibold text-[#22302a]">
                {currentBatch.accepted_count} <span className="text-xs font-normal text-emerald-600">accepted</span>
                {currentBatch.rejected_count > 0 && (
                  <span className="text-xs font-normal text-rose-500 ml-1.5">/ {currentBatch.rejected_count} rejected</span>
                )}
              </div>
              <small className="text-[10px] text-[#74817b]">
                Total rows submitted: {currentBatch.row_count}
              </small>
            </article>
          </div>

          {/* Risk Assessment Summary Banner */}
          {stats && currentBatch.status === 'completed' && (
            <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] p-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-3 pb-3 border-b border-[#edf0eb]">
                <div>
                  <h3 className="text-sm font-bold text-[#22302a] flex items-center gap-1.5">
                    <ShieldCheck className="h-4 w-4 text-[#6366f1]" />
                    Risk Assessment Overview
                  </h3>
                  <p className="text-xs text-[#74817b] mt-0.5">
                    Temporal graph risk scoring with text-conditioned relation attention.
                  </p>
                </div>
                <div className="flex items-center gap-4 text-xs">
                  <div>
                    <span className="text-[#74817b]">Flagged: </span>
                    <strong className="text-rose-600 font-bold">{stats.flaggedCount}</strong>
                    <span className="text-[#9ba6a0] ml-1">({stats.flagRate.toFixed(1)}%)</span>
                  </div>
                  <div>
                    <span className="text-[#74817b]">Cleared: </span>
                    <strong className="text-emerald-600 font-bold">{stats.clearedCount}</strong>
                  </div>
                </div>
              </div>

              {/* Score Distribution Bar */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-[11px] text-[#74817b]">
                  <span>Score distribution</span>
                  <span>Threshold: 0.7871</span>
                </div>
                <div className="h-3 w-full bg-[#f4f6f3] rounded-full overflow-hidden flex">
                  {stats.distribution.map((d, i) =>
                    d.pct > 0 ? (
                      <div
                        key={i}
                        className={`${d.color} transition-all`}
                        style={{ width: `${d.pct}%` }}
                        title={`${d.label}: ${d.count} reviews (${d.pct.toFixed(1)}%)`}
                      />
                    ) : null
                  )}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[10px] text-[#74817b]">
                  {stats.distribution.map((d, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <span className={`w-2 h-2 rounded-full ${d.color}`} />
                      <span>{d.label}: <strong>{d.count}</strong></span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Scored Reviews Table */}
          {results.length > 0 && (
            <div className="panel p-0 overflow-hidden">
              <div className="px-4 py-3 border-b border-[#e2e5df] flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-[#22302a]">Scored Reviews & Graph Evidence</h3>
                  <p className="text-xs text-[#74817b]">
                    Review risk assessments, actual fraud scores, dynamic relation attention, and neighborhood counts.
                  </p>
                </div>
                <span className="text-xs text-[#74817b]">
                  {results.length} rows
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="evidence-table w-full text-xs">
                  <thead>
                    <tr className="bg-[#f9faf7] text-[#74817b] border-b border-[#e2e5df]">
                      <th className="py-2 px-3 text-left">Review ID</th>
                      <th className="py-2 px-3 text-left">Rating & Date</th>
                      <th className="py-2 px-3 text-left">Review Excerpt</th>
                      <th className="py-2 px-3 text-right">Actual Fraud Score</th>
                      <th className="py-2 px-3 text-center">Decision</th>
                      <th className="py-2 px-3 text-left">Relation Attention</th>
                      <th className="py-2 px-3 text-center">Neighbors (RUR / RSR / RTR)</th>
                      <th className="py-2 px-center text-right">Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((row) => {
                      const pred = row.prediction;
                      const isFlagged = pred?.decision === 'flagged';
                      const att = pred?.attention_weights;
                      const ev = pred?.evidence;

                      return (
                        <tr key={row.row_number} className="border-b border-[#edf0eb] hover:bg-[#fbfcf9]">
                          <td className="py-2.5 px-3 font-mono text-[11px] text-[#22302a]">
                            {row.uploaded_review_key || `Row #${row.row_number}`}
                          </td>
                          <td className="py-2.5 px-3 whitespace-nowrap text-[#74817b]">
                            {row.review?.rating ? `${row.review.rating} ★` : '—'} ·{' '}
                            {row.review?.reviewed_at
                              ? new Date(row.review.reviewed_at).toLocaleDateString()
                              : '—'}
                          </td>
                          <td className="py-2.5 px-3 max-w-xs truncate text-[#22302a]" title={row.review?.review_text || ''}>
                            {row.review?.review_text || '—'}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono font-semibold">
                            {pred ? (
                              <span className={isFlagged ? 'text-rose-600' : 'text-emerald-700'}>
                                {pred.risk_score.toFixed(4)}
                              </span>
                            ) : (
                              <span className="text-[#9ba6a0] font-normal">Pending</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            {pred ? (
                              <span
                                className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                                  isFlagged
                                    ? 'bg-rose-100 text-rose-700 border border-rose-200'
                                    : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                                }`}
                              >
                                {isFlagged ? 'Flagged' : 'Cleared'}
                              </span>
                            ) : (
                              <span className="subtle-tag">{row.row_state}</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3">
                            {att ? (
                              <div className="space-y-1 w-28">
                                <div className="h-1.5 w-full bg-[#f0f2ee] rounded-full overflow-hidden flex">
                                  <div
                                    className="bg-indigo-500"
                                    style={{ width: `${((att.rur || 0) * 100).toFixed(0)}%` }}
                                    title={`RUR: ${((att.rur || 0) * 100).toFixed(1)}%`}
                                  />
                                  <div
                                    className="bg-emerald-500"
                                    style={{ width: `${((att.rsr || 0) * 100).toFixed(0)}%` }}
                                    title={`RSR: ${((att.rsr || 0) * 100).toFixed(1)}%`}
                                  />
                                  <div
                                    className="bg-amber-500"
                                    style={{ width: `${((att.rtr || 0) * 100).toFixed(0)}%` }}
                                    title={`RTR: ${((att.rtr || 0) * 100).toFixed(1)}%`}
                                  />
                                </div>
                                <div className="flex justify-between text-[9px] text-[#74817b] font-mono">
                                  <span title="Reviewer relation attention">U:{((att.rur || 0) * 100).toFixed(0)}%</span>
                                  <span title="Product-Rating relation attention">S:{((att.rsr || 0) * 100).toFixed(0)}%</span>
                                  <span title="Temporal relation attention">T:{((att.rtr || 0) * 100).toFixed(0)}%</span>
                                </div>
                              </div>
                            ) : (
                              <span className="text-[#9ba6a0] text-[10px]">—</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-center text-[11px] font-mono text-[#74817b]">
                            {ev ? (
                              <span>
                                {ev.neighbor_counts.rur ?? 0} / {ev.neighbor_counts.rsr ?? 0} / {ev.neighbor_counts.rtr ?? 0}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            {ev ? (
                              <button
                                onClick={() =>
                                  setSelectedEvidence({
                                    reviewKey: row.uploaded_review_key || `Row #${row.row_number}`,
                                    evidence: ev,
                                    score: pred!.risk_score,
                                    decision: pred!.decision,
                                  })
                                }
                                className="text-action text-[11px] inline-flex items-center gap-1 font-medium hover:underline"
                              >
                                View evidence
                              </button>
                            ) : (
                              <span className="text-[#9ba6a0] text-[10px]">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Evidence Modal / Drawer */}
          {selectedEvidence && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
              <div className="bg-[#fffefa] border border-[#e2e5df] rounded-xl shadow-xl max-w-lg w-full p-5 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#edf0eb]">
                  <div>
                    <h4 className="text-sm font-bold text-[#22302a]">
                      Graph Evidence · {selectedEvidence.reviewKey}
                    </h4>
                    <p className="text-xs text-[#74817b]">
                      Risk assessment: <strong>{selectedEvidence.score.toFixed(4)}</strong> ({selectedEvidence.decision})
                    </p>
                  </div>
                  <button
                    onClick={() => setSelectedEvidence(null)}
                    className="text-[#9ba6a0] hover:text-[#22302a] text-lg font-bold"
                  >
                    ×
                  </button>
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-[#74817b] block text-[10px] uppercase font-semibold">Context Cutoff</span>
                    <span className="font-mono text-[#22302a]">
                      {selectedEvidence.evidence.context_cutoff_at
                        ? new Date(selectedEvidence.evidence.context_cutoff_at).toISOString()
                        : '—'}
                    </span>
                  </div>

                  <div>
                    <span className="text-[#74817b] block text-[10px] uppercase font-semibold">
                      Connected Historic Neighbors ({selectedEvidence.evidence.historic_review_ids.length})
                    </span>
                    <div className="bg-[#f9faf7] rounded p-2 font-mono text-[11px] max-h-20 overflow-y-auto">
                      {selectedEvidence.evidence.historic_review_ids.length > 0
                        ? selectedEvidence.evidence.historic_review_ids.join(', ')
                        : 'No direct historic connections found within cutoff'}
                    </div>
                  </div>

                  <div className="space-y-1.5 pt-2 border-t border-[#edf0eb]">
                    <span className="text-[#74817b] block text-[10px] uppercase font-semibold">
                      Deterministic Integrity Hashes
                    </span>
                    <div className="space-y-1 font-mono text-[10px]">
                      <div className="flex justify-between items-center bg-[#f4f6f3] px-2 py-1 rounded">
                        <span className="text-[#74817b]">Stitched Graph:</span>
                        <span className="text-[#22302a]">
                          {truncateHash(selectedEvidence.evidence.stitched_graph_sha256, 12, 12)}
                        </span>
                      </div>
                      <div className="flex justify-between items-center bg-[#f4f6f3] px-2 py-1 rounded">
                        <span className="text-[#74817b]">Input Features:</span>
                        <span className="text-[#22302a]">
                          {truncateHash(selectedEvidence.evidence.input_feature_sha256, 12, 12)}
                        </span>
                      </div>
                      <div className="flex justify-between items-center bg-[#f4f6f3] px-2 py-1 rounded">
                        <span className="text-[#74817b]">Embedding SHA:</span>
                        <span className="text-[#22302a]">
                          {truncateHash(selectedEvidence.evidence.embedding_sha256, 12, 12)}
                        </span>
                      </div>
                      <div className="flex justify-between items-center bg-[#f4f6f3] px-2 py-1 rounded">
                        <span className="text-[#74817b]">Bundle Manifest:</span>
                        <span className="text-[#22302a]">
                          {truncateHash(selectedEvidence.evidence.bundle_manifest_sha256, 12, 12)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    onClick={() => setSelectedEvidence(null)}
                    className="button-secondary text-xs px-3 py-1.5"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
