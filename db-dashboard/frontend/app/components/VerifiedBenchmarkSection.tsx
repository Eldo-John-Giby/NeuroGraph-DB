'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  GitBranch,
  Layers,
  Cpu,
  Copy,
  Check,
  AlertCircle,
  RefreshCw,
  Search,
} from 'lucide-react';
import { apiRequest, getErrorMessage } from '../lib/api';

interface BenchmarkStatus {
  available: boolean;
  runtime_loaded: boolean;
  scores_cached: boolean;
  run_id: string;
  manifest_sha256: string;
  threshold: number;
  metrics: {
    roc_auc: number;
    pr_auc: number;
    f1_macro: number;
  };
  node_count: number;
  fixed_review: {
    review_id: string;
    node_index: number;
    expected_fraud_score: number;
    observed_fraud_score: number;
    tolerance: number;
    reproduced: boolean;
  };
  mode: string;
  details: string;
}

interface BenchmarkResultItem {
  review_id: string;
  node_index: number;
  fraud_score: number;
  predicted_label: number;
}

interface BenchmarkResultsResponse {
  run_id: string;
  threshold: number;
  total: number;
  limit: number;
  offset: number;
  items: BenchmarkResultItem[];
}

interface PredictionResponse {
  run_id: string;
  threshold: number;
  mode: string;
  predictions: Array<{
    review_id: string;
    node_index: number;
    fraud_score: number;
    predicted_label: number;
  }>;
}

function truncateHash(hash: string, lead = 8, trail = 8): string {
  if (!hash) return '—';
  if (hash.length <= lead + trail) return hash;
  return `${hash.slice(0, lead)}...${hash.slice(-trail)}`;
}

export function VerifiedBenchmarkSection({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<BenchmarkStatus | null>(null);
  const [results, setResults] = useState<BenchmarkResultItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Predict verification tool
  const [testReviewId, setTestTestReviewId] = useState('--AweNX8vPGD');
  const [predictResult, setPredictResult] = useState<PredictionResponse['predictions'][0] | null>(null);
  const [predictError, setPredictError] = useState<string | null>(null);
  const [predicting, setPredicting] = useState(false);

  const copyToClipboard = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    }
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, r] = await Promise.all([
        apiRequest<BenchmarkStatus>('/api/v1/verified-multimodal/status'),
        apiRequest<BenchmarkResultsResponse>('/api/v1/verified-multimodal/results?limit=6&offset=0'),
      ]);
      setStatus(s);
      setResults(r.items || []);
      setTotalCount(r.total || 0);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleTestPredict = async (idToTest?: string) => {
    const targetId = (idToTest || testReviewId).trim();
    if (!targetId) return;
    setPredicting(true);
    setPredictResult(null);
    setPredictError(null);
    try {
      const res = await apiRequest<PredictionResponse>('/api/v1/verified-multimodal/predict', {
        method: 'POST',
        body: JSON.stringify({ review_ids: [targetId] }),
      });
      if (res.predictions && res.predictions.length > 0) {
        setPredictResult(res.predictions[0]);
      }
    } catch (err) {
      setPredictError(getErrorMessage(err));
    } finally {
      setPredicting(false);
    }
  };


  return (
    <section className="mt-8 space-y-5" aria-label="Verified multimodal benchmark lane">
      {/* Lane Separator & Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#e2e5df] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[#12685f]" />
            <p className="text-[10px] font-bold uppercase tracking-wider text-[#12685f]">
              Reference model · transductive benchmark
            </p>
          </div>
          <h2 className="text-xl font-medium text-[#1e2927] font-serif mt-1">
            Multimodal benchmark results
          </h2>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="inline-flex items-center gap-1.5 self-start sm:self-auto rounded-md border border-[#d4dad5] bg-[#fffefa] px-2.5 py-1.5 text-[11px] font-medium text-[#3b4a45] hover:border-[#12685f] hover:text-[#0b514a] transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin text-[#12685f]' : ''}`} />
          Refresh benchmark
        </button>
      </div>

      {/* Mandatory Provenance Banner */}
      <div className="flex items-center gap-2.5 rounded-md border border-[#c3ded8] bg-[#eef7f5] px-3.5 py-2.5 text-[#0b514a] text-xs font-semibold">
        <span className="w-2 h-2 rounded-full bg-[#12685f] shadow-[0_0_0_3px_#d2eae5]" />
        <span>VERIFIED BENCHMARK DATA</span>
        <span className="font-normal text-[#4a6b64]">
          — verified YelpChi benchmark, separate from synthetic product demo data
        </span>
      </div>

      {loading && (
        <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] p-8 text-center text-xs text-[#68736f]">
          <RefreshCw className="h-5 w-5 animate-spin mx-auto text-[#12685f] mb-2" />
          Loading verified multimodal model runtime and cached scores…
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-[#edc49e] bg-[#fbefe5] p-4 text-xs text-[#9b4e1e]">
          <div className="flex items-center gap-2 font-bold mb-1">
            <AlertCircle className="h-4 w-4 text-[#c66b30]" />
            Verified Benchmark Unavailable
          </div>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && status && (
        <>
          {/* Key Benchmark Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] p-3.5 shadow-sm">
              <p className="text-[10px] font-semibold text-[#68746e] uppercase tracking-wider">Test ROC-AUC</p>
              <p className="text-2xl font-serif font-medium text-[#12685f] mt-1">
                {status.metrics.roc_auc.toFixed(4)}
              </p>
              <small className="text-[10px] text-[#808a85]">Authoritative test split</small>
            </div>
            <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] p-3.5 shadow-sm">
              <p className="text-[10px] font-semibold text-[#68746e] uppercase tracking-wider">Test F1-Macro</p>
              <p className="text-2xl font-serif font-medium text-[#12685f] mt-1">
                {status.metrics.f1_macro.toFixed(4)}
              </p>
              <small className="text-[10px] text-[#808a85]">Label-balanced performance</small>
            </div>
            <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] p-3.5 shadow-sm">
              <p className="text-[10px] font-semibold text-[#68746e] uppercase tracking-wider">Optimal Threshold</p>
              <p className="text-2xl font-serif font-medium text-[#1e2927] mt-1">
                {status.threshold.toFixed(4)}
              </p>
              <small className="text-[10px] text-[#808a85]">Validation-tuned boundary</small>
            </div>
            <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] p-3.5 shadow-sm">
              <p className="text-[10px] font-semibold text-[#68746e] uppercase tracking-wider">PR-AUC</p>
              <p className="text-2xl font-serif font-medium text-[#1e2927] mt-1">
                {status.metrics.pr_auc.toFixed(4)}
              </p>
              <small className="text-[10px] text-[#808a85]">Precision-recall under imbalance</small>
            </div>
          </div>

          {/* Model Identity & Multi-Relational Graph Topology */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {/* Run Identity Card */}
            <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Cpu className="h-4 w-4 text-[#12685f]" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#1e2927]">
                    Model Run Identity & Proof
                  </h3>
                </div>
                <span className="inline-flex items-center gap-1 rounded bg-[#eef7f5] px-2 py-0.5 text-[10px] font-bold text-[#0b514a]">
                  <CheckCircle2 className="h-3 w-3" /> Runtime Verified
                </span>
              </div>

              <div className="space-y-2 text-xs">
                <div>
                  <span className="text-[#839089] block text-[10px] uppercase">Run ID</span>
                  <span className="font-mono text-[#1e2927] font-medium text-[11px] break-all">
                    {status.run_id}
                  </span>
                </div>
                <div>
                  <span className="text-[#839089] block text-[10px] uppercase">Manifest SHA256</span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="font-mono text-[11px] text-[#3b4a45] bg-[#f5f5f1] px-2 py-0.5 rounded border border-[#e2e5df]">
                      {truncateHash(status.manifest_sha256, 12, 12)}
                    </span>
                    <button
                      onClick={() => copyToClipboard(status.manifest_sha256, 'manifest')}
                      className="text-[#68736f] hover:text-[#12685f] transition-colors"
                      title="Copy manifest SHA256"
                    >
                      {copiedKey === 'manifest' ? (
                        <Check className="h-3.5 w-3.5 text-[#12685f]" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </div>
                <div className="pt-1 border-t border-[#edf0eb] flex items-center justify-between text-[11px]">
                  <span className="text-[#68736f]">Fixed Node Reproduction:</span>
                  <span className="font-mono text-[#0b514a] font-semibold">
                    {status.fixed_review.review_id} (Node #{status.fixed_review.node_index}) →{' '}
                    {status.fixed_review.observed_fraud_score.toFixed(6)}
                  </span>
                </div>
              </div>
            </div>

            {/* Graph Topology Card */}
            <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <GitBranch className="h-4 w-4 text-[#12685f]" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#1e2927]">
                    Multi-Relational Topology (47,176 Nodes)
                  </h3>
                </div>
                <span className="text-[11px] text-[#839089] font-mono">8,562,226 total edges</span>
              </div>

              <div className="grid grid-cols-3 gap-2 pt-1 text-center">
                <div className="rounded border border-[#e2e5df] bg-[#f9faf7] p-2">
                  <span className="block text-[10px] font-bold text-[#12685f]">RUR Relation</span>
                  <span className="block font-serif text-base font-semibold text-[#1e2927] mt-0.5">
                    108,676
                  </span>
                  <span className="block text-[9px] text-[#839089] mt-0.5">Same Reviewer ID</span>
                </div>
                <div className="rounded border border-[#e2e5df] bg-[#f9faf7] p-2">
                  <span className="block text-[10px] font-bold text-[#c66b30]">RSR Relation</span>
                  <span className="block font-serif text-base font-semibold text-[#1e2927] mt-0.5">
                    7,997,944
                  </span>
                  <span className="block text-[9px] text-[#839089] mt-0.5">Same Product + Rating</span>
                </div>
                <div className="rounded border border-[#e2e5df] bg-[#f9faf7] p-2">
                  <span className="block text-[10px] font-bold text-[#556961]">RTR Relation</span>
                  <span className="block font-serif text-base font-semibold text-[#1e2927] mt-0.5">
                    455,606
                  </span>
                  <span className="block text-[9px] text-[#839089] mt-0.5">Same Product + Month</span>
                </div>
              </div>

              <p className="text-[10px] text-[#839089] leading-relaxed">
                Frozen 768-dim masked-mean RoBERTa text vectors are projected into 3 GraphSAGE relation channels
                and cross-attended using text-conditioned query keys.
              </p>
            </div>
          </div>

          {/* Top Flagged YelpChi Reviews Table */}
          <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] shadow-sm overflow-hidden">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-4 py-3 border-b border-[#e2e5df] bg-[#fbfbf8]">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#1e2927]">
                  Top Flagged YelpChi Benchmark Reviews
                </h3>
                <p className="text-[11px] text-[#68736f] mt-0.5">
                  High-risk nodes sorted descending by transductive fraud probability ({totalCount.toLocaleString()} indexed nodes)
                </p>
              </div>
              <span className="text-[10px] text-[#839089]">
                Decision Boundary: &ge; {status.threshold.toFixed(4)}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#e2e5df] bg-[#f5f5f1] text-[10px] font-bold text-[#68746e] uppercase tracking-wider">
                    <th className="px-3.5 py-2.5">Review ID</th>
                    <th className="px-3 py-2.5">Node #</th>
                    <th className="px-3 py-2.5">Fraud Score</th>
                    <th className="px-3 py-2.5">Decision</th>
                    <th className="px-4 py-2.5">Prediction scope</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#edf0eb]">
                  {results.map((row) => {
                    const isSpam = row.fraud_score >= status.threshold;
                    return (
                      <tr key={row.review_id} className="hover:bg-[#f9faf7] transition-colors">
                        <td className="px-3.5 py-2.5 font-mono text-[11px] font-medium text-[#1e2927]">
                          <button
                            onClick={() => {
                              setTestTestReviewId(row.review_id);
                              handleTestPredict(row.review_id);
                            }}
                            className="hover:text-[#12685f] hover:underline flex items-center gap-1 text-left"
                            title="Click to test single-node prediction"
                          >
                            {row.review_id}
                          </button>
                        </td>
                        <td className="px-3 py-2.5 text-[#68736f] font-mono">{row.node_index}</td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-[#1e2927]">
                              {row.fraud_score.toFixed(4)}
                            </span>
                            <div className="w-12 h-1.5 rounded-full bg-[#e2e5df] overflow-hidden">
                              <div
                                className={`h-full ${isSpam ? 'bg-[#c66b30]' : 'bg-[#12685f]'}`}
                                style={{ width: `${Math.min(row.fraud_score * 100, 100)}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          {isSpam ? (
                            <span className="inline-flex items-center rounded-full bg-[#fbefe5] px-2 py-0.5 text-[10px] font-bold text-[#9b4e1e] border border-[#edc49e]">
                              Flagged by model
                            </span>
                          ) : (
                            <span className="inline-flex items-center rounded-full bg-[#eef7f5] px-2 py-0.5 text-[10px] font-bold text-[#0b514a] border border-[#c3ded8]">
                              Below threshold
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="block text-[11px] font-semibold text-[#1e2927]">
                            Known graph node
                          </span>
                          <span className="block text-[10px] text-[#68736f] mt-0.5">
                            Per-review attention is not returned by this benchmark API.
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Interactive Single-Node Inference Verification Box */}
          <div className="rounded-lg border border-[#e2e5df] bg-[#fffefa] p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#1e2927]">
                  Verify Known-Node Inference
                </h3>
                <p className="text-[11px] text-[#68736f] mt-0.5">
                  Test single-node scoring against the verified graph snapshot (rejects unknown reviews)
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setTestTestReviewId('--AweNX8vPGD');
                    handleTestPredict('--AweNX8vPGD');
                  }}
                  className="text-[10px] text-[#12685f] hover:underline font-medium"
                >
                  Test Fixed Node
                </button>
                <span className="text-[#d4dad5]">|</span>
                <button
                  type="button"
                  onClick={() => {
                    setTestTestReviewId('unknown-node-test-999');
                    handleTestPredict('unknown-node-test-999');
                  }}
                  className="text-[10px] text-[#c66b30] hover:underline font-medium"
                >
                  Test Unknown Node Rejection
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="text"
                value={testReviewId}
                onChange={(e) => setTestTestReviewId(e.target.value)}
                placeholder="Enter raw review ID (e.g. --AweNX8vPGD)"
                className="flex-1 rounded-md border border-[#d4dad5] bg-white px-3 py-1.5 text-xs font-mono text-[#1e2927] focus:outline-none focus:border-[#12685f]"
              />
              <button
                type="button"
                onClick={() => handleTestPredict()}
                disabled={predicting}
                className="inline-flex items-center gap-1.5 rounded-md border border-[#12685f] bg-[#12685f] px-3.5 py-1.5 text-xs font-bold text-white hover:bg-[#0b514a] transition-colors disabled:opacity-50"
              >
                <Search className="h-3.5 w-3.5" />
                {predicting ? 'Scoring...' : 'Predict'}
              </button>
            </div>

            {predictResult && (
              <div className="rounded-md border border-[#c3ded8] bg-[#eef7f5] p-3 text-xs text-[#0b514a] flex items-center justify-between">
                <div>
                  <span className="font-semibold block">
                    Review ID: <span className="font-mono">{predictResult.review_id}</span> (Node #{predictResult.node_index})
                  </span>
                  <span className="text-[11px] text-[#4a6b64] mt-0.5 block">
                    Fraud Probability: <strong className="font-mono text-[#0b514a]">{predictResult.fraud_score.toFixed(6)}</strong>
                    {' · '}Decision:{' '}
                    <strong>{predictResult.predicted_label === 1 ? 'Flagged by model' : 'Below model threshold'}</strong>
                  </span>
                </div>
                <span className="rounded bg-white px-2 py-1 text-[10px] font-bold text-[#12685f] border border-[#c3ded8]">
                  Verified In-Memory Cache
                </span>
              </div>
            )}

            {predictError && (
              <div className="rounded-md border border-[#edc49e] bg-[#fbefe5] p-3 text-xs text-[#9b4e1e] flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-[#c66b30] flex-shrink-0" />
                <div>
                  <span className="font-bold block">Expected Safety Rejection</span>
                  <span className="text-[11px]">{predictError}</span>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
