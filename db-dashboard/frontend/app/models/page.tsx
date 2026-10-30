'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw,
  Cpu,
  Lock,
  Layers,
  Sliders,
  History,
  Check,
  Copy,
} from 'lucide-react';
import AppShell from '../components/AppShell';
import {
  PageHeader,
  LoadingSpinner,
  TableSkeleton,
  EmptyState,
  ErrorState,
  StatusBadge,
  Pagination,
} from '../components/ui';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { apiRequest, getErrorMessage } from '../lib/api';
import { VerifiedBenchmarkSection } from '../components/VerifiedBenchmarkSection';

// ============================================================================
// Type Definitions
// ============================================================================

interface ModelInferenceStatus {
  status: string;
  inference_available: boolean;
  reason: string;
  supported_modes: string[];
  details: string;
}

interface ModelVersionItem {
  model_version_id: number;
  version_key: string;
  model_name: string;
  architecture_version: string;
  lifecycle_status: string;
  supported_inference_mode: string;
  checkpoint_sha256: string;
  preprocessing_version_id: number;
  recommended_threshold: number | null;
}

interface ModelVersionsResponse {
  items: ModelVersionItem[];
}

interface PreprocessingVersionItem {
  preprocessing_version_id: number;
  version_key: string;
  preprocessing_sha256: string;
  lifecycle_status: string;
}

interface PreprocessingVersionsResponse {
  items: PreprocessingVersionItem[];
}

interface InferenceRunItem {
  inference_run_id: number;
  run_key: string;
  status: string;
  requested_count: number;
  completed_count: number;
  threshold: number;
  created_at: string;
  completed_at: string | null;
  model: {
    model_version_id: number;
    version_key: string;
    model_name: string;
    checkpoint_sha256: string;
    preprocessing_version_id: number;
  };
  graph_snapshot: {
    graph_snapshot_id: number;
    snapshot_key: string;
    artifact_sha256: string;
  };
}

interface InferenceRunsResponse {
  items: InferenceRunItem[];
  total: number;
  limit: number;
  offset: number;
}

// ============================================================================
// Helper Utilities
// ============================================================================

function truncateHash(hash: string, lead = 8, trail = 8): string {
  if (!hash) return '—';
  if (hash.length <= lead + trail) return hash;
  return `${hash.slice(0, lead)}...${hash.slice(-trail)}`;
}

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

export default function ModelEvaluationPage() {
  const { user, isLoading: authLoading, isAuthenticated } = useRequireAuth(true);

  // Clipboard copy state
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copyToClipboard = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    }
  };

  // --------------------------------------------------------------------------
  // SECTION 1: Model Inference Status
  // --------------------------------------------------------------------------
  const [inferenceStatus, setInferenceStatus] = useState<ModelInferenceStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState<boolean>(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoadingStatus(true);
    setStatusError(null);
    try {
      const data = await apiRequest<ModelInferenceStatus>('/api/v1/models/status');
      setInferenceStatus(data);
    } catch (err) {
      setStatusError(getErrorMessage(err));
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  // --------------------------------------------------------------------------
  // SECTION 2: Model Versions
  // --------------------------------------------------------------------------
  const [modelVersions, setModelVersions] = useState<ModelVersionItem[]>([]);
  const [loadingModels, setLoadingModels] = useState<boolean>(true);
  const [modelsError, setModelsError] = useState<string | null>(null);

  const fetchModelVersions = useCallback(async () => {
    setLoadingModels(true);
    setModelsError(null);
    try {
      const data = await apiRequest<ModelVersionsResponse>('/api/v1/model-versions');
      setModelVersions(data.items || []);
    } catch (err) {
      setModelsError(getErrorMessage(err));
    } finally {
      setLoadingModels(false);
    }
  }, []);

  // --------------------------------------------------------------------------
  // SECTION 3: Preprocessing Versions
  // --------------------------------------------------------------------------
  const [prepVersions, setPrepVersions] = useState<PreprocessingVersionItem[]>([]);
  const [loadingPrep, setLoadingPrep] = useState<boolean>(true);
  const [prepError, setPrepError] = useState<string | null>(null);

  const fetchPrepVersions = useCallback(async () => {
    setLoadingPrep(true);
    setPrepError(null);
    try {
      const data = await apiRequest<PreprocessingVersionsResponse>('/api/v1/preprocessing-versions');
      setPrepVersions(data.items || []);
    } catch (err) {
      setPrepError(getErrorMessage(err));
    } finally {
      setLoadingPrep(false);
    }
  }, []);

  // --------------------------------------------------------------------------
  // SECTION 4: Recent Inference Runs
  // --------------------------------------------------------------------------
  const [inferenceRuns, setInferenceRuns] = useState<InferenceRunItem[]>([]);
  const [runsTotal, setRunsTotal] = useState<number>(0);
  const [runsOffset, setRunsOffset] = useState<number>(0);
  const runsLimit = 10;
  const [loadingRuns, setLoadingRuns] = useState<boolean>(true);
  const [runsError, setRunsError] = useState<string | null>(null);

  const fetchInferenceRuns = useCallback(async (offset: number) => {
    setLoadingRuns(true);
    setRunsError(null);
    try {
      const data = await apiRequest<InferenceRunsResponse>(
        `/api/v1/inference-runs?limit=${runsLimit}&offset=${offset}`
      );
      setInferenceRuns(data.items || []);
      setRunsTotal(data.total || 0);
      setRunsOffset(data.offset || 0);
    } catch (err) {
      setRunsError(getErrorMessage(err));
    } finally {
      setLoadingRuns(false);
    }
  }, [runsLimit]);

  // Initial fetch for all sections independently
  useEffect(() => {
    if (isAuthenticated) {
      fetchStatus();
      fetchModelVersions();
      fetchPrepVersions();
      fetchInferenceRuns(0);
    }
  }, [isAuthenticated, fetchStatus, fetchModelVersions, fetchPrepVersions, fetchInferenceRuns]);

  const handleRefreshAll = () => {
    fetchStatus();
    fetchModelVersions();
    fetchPrepVersions();
    fetchInferenceRuns(runsOffset);
  };

  // --------------------------------------------------------------------------
  // Auth Loading Guard
  // --------------------------------------------------------------------------
  if (authLoading || !user) {
    return (
      <AppShell>
        <LoadingSpinner text="Authenticating user session..." />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        title="Model Registry & Evaluation"
        subtitle="Manage validated model checkpoints, preprocessors, and inference execution runs"
        actions={
          <button
            onClick={handleRefreshAll}
            className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/80 px-3.5 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5 text-teal-400" />
            Refresh All
          </button>
        }
      />

      <div className="space-y-8">
        {/* ================================================================== */}
        {/* SECTION 1: Model Inference Availability Status                     */}
        {/* ================================================================== */}
        <section>
          {loadingStatus ? (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <LoadingSpinner text="Checking model runtime availability..." />
            </div>
          ) : statusError ? (
            <ErrorState
              message={`Failed to check inference runtime availability: ${statusError}`}
              onRetry={fetchStatus}
            />
          ) : inferenceStatus ? (
            <div
              className={`rounded-xl border p-5 transition-colors ${
                inferenceStatus.inference_available
                  ? 'border-emerald-500/30 bg-emerald-500/10'
                  : 'border-amber-500/30 bg-amber-500/5'
              }`}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div className="mt-1">
                    {inferenceStatus.inference_available ? (
                      <Cpu className="h-7 w-7 text-emerald-400" strokeWidth={1.75} />
                    ) : (
                      <Lock className="h-7 w-7 text-amber-400" strokeWidth={1.75} />
                    )}
                  </div>
                  <div>
                    <div className="flex flex-wrap items-center gap-2.5">
                      <h3 className="text-base font-bold text-white">
                        Historical known-node runtime
                      </h3>
                      <StatusBadge
                        status={inferenceStatus.status}
                        variant={inferenceStatus.inference_available ? 'success' : 'error'}
                      />
                      <span className="rounded bg-slate-800 border border-slate-700 px-2 py-0.5 text-[10px] font-mono text-slate-300">
                        Reason: {inferenceStatus.reason}
                      </span>
                    </div>

                    <p className="mt-1.5 text-xs text-slate-300 max-w-3xl leading-relaxed">
                      {inferenceStatus.details}
                    </p>

                    {/* Supported Modes */}
                    <div className="mt-3 flex items-center gap-2">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                        Supported Modes:
                      </span>
                      {inferenceStatus.supported_modes && inferenceStatus.supported_modes.length > 0 ? (
                        inferenceStatus.supported_modes.map((mode) => (
                          <span
                            key={mode}
                            className="rounded bg-indigo-500/15 border border-indigo-500/30 px-2 py-0.5 text-[10px] font-medium text-indigo-300 uppercase tracking-wider"
                          >
                            {mode}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs italic text-slate-500">None registered</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="shrink-0 flex items-center">
                  <div className="rounded-lg border border-slate-700/60 bg-slate-900/80 px-4 py-2.5 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Live Inference
                    </p>
                    <p
                      className={`mt-0.5 text-sm font-bold uppercase ${
                        inferenceStatus.inference_available ? 'text-emerald-400' : 'text-amber-400'
                      }`}
                    >
                      {inferenceStatus.inference_available ? 'Active' : 'Locked'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </section>

        {/* ================================================================== */}
        {/* VERIFIED BENCHMARK SECTION: Labelled Raw YelpChi Multimodal GNN   */}
        {/* ================================================================== */}
        <p className="notice-card">This status describes the earlier known-node runtimes. The deployed new-review model is shown on Model results. Open <a className="text-action" href="/benchmarks">Model comparison</a> for all four models evaluated on the same chronological test set.</p>
        <VerifiedBenchmarkSection />

        {/* ================================================================== */}
        {/* SECTION 2: Model Versions Table                                   */}
        {/* ================================================================== */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Layers className="h-5 w-5 text-teal-400" strokeWidth={1.75} /> Model Versions
              </h2>
              <p className="mt-0.5 text-xs text-slate-400">
                Registered neural architectures, checkpoint hashes, and recommended classification thresholds
              </p>
            </div>
            {modelVersions.length > 0 && (
              <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-300 border border-slate-700">
                {modelVersions.length} {modelVersions.length === 1 ? 'version' : 'versions'}
              </span>
            )}
          </div>

          {loadingModels ? (
            <TableSkeleton rows={4} cols={8} />
          ) : modelsError ? (
            <ErrorState
              message={`Failed to load model versions: ${modelsError}`}
              onRetry={fetchModelVersions}
            />
          ) : modelVersions.length === 0 ? (
            <EmptyState
              icon={<Cpu className="h-8 w-8 text-slate-500" strokeWidth={1.75} />}
              title="No Model Versions Found"
              message="No neural network model versions have been registered in the database catalog yet."
            />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60 shadow-sm">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-800/80 uppercase tracking-wider text-[10px] font-semibold text-slate-400 border-b border-slate-800">
                  <tr>
                    <th scope="col" className="px-4 py-3.5">ID</th>
                    <th scope="col" className="px-4 py-3.5">Version Key</th>
                    <th scope="col" className="px-4 py-3.5">Model Name</th>
                    <th scope="col" className="px-4 py-3.5">Architecture</th>
                    <th scope="col" className="px-4 py-3.5">Lifecycle Status</th>
                    <th scope="col" className="px-4 py-3.5">Inference Mode</th>
                    <th scope="col" className="px-4 py-3.5">Threshold</th>
                    <th scope="col" className="px-4 py-3.5">Checkpoint SHA256</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {modelVersions.map((m) => (
                    <tr key={m.model_version_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 font-mono font-medium text-slate-400">
                        #{m.model_version_id}
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold text-white">
                        {m.version_key}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-200">
                        {m.model_name}
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {m.architecture_version}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={m.lifecycle_status} />
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-300 border border-slate-700/60">
                          {m.supported_inference_mode}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-indigo-400 font-semibold">
                        {m.recommended_threshold !== null && m.recommended_threshold !== undefined
                          ? m.recommended_threshold.toFixed(4)
                          : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400">
                          <span title={m.checkpoint_sha256}>
                            {truncateHash(m.checkpoint_sha256, 6, 6)}
                          </span>
                          <button
                            type="button"
                            onClick={() => copyToClipboard(m.checkpoint_sha256, `model_ckpt_${m.model_version_id}`)}
                            title="Copy full SHA256"
                            className="rounded p-1 text-slate-500 hover:text-indigo-400 transition-colors"
                          >
                            {copiedKey === `model_ckpt_${m.model_version_id}` ? (
                              <Check className="h-3 w-3 text-emerald-400" />
                            ) : (
                              <Copy className="h-3 w-3" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* ================================================================== */}
        {/* SECTION 3: Preprocessing Versions Table                           */}
        {/* ================================================================== */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Sliders className="h-5 w-5 text-teal-400" strokeWidth={1.75} /> Preprocessing Versions
              </h2>
              <p className="mt-0.5 text-xs text-slate-400">
                Text tokenization, vocabulary manifests, and feature normalization pipelines
              </p>
            </div>
            {prepVersions.length > 0 && (
              <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-300 border border-slate-700">
                {prepVersions.length} {prepVersions.length === 1 ? 'version' : 'versions'}
              </span>
            )}
          </div>

          {loadingPrep ? (
            <TableSkeleton rows={3} cols={4} />
          ) : prepError ? (
            <ErrorState
              message={`Failed to load preprocessing versions: ${prepError}`}
              onRetry={fetchPrepVersions}
            />
          ) : prepVersions.length === 0 ? (
            <EmptyState
              icon={<Sliders className="h-8 w-8 text-slate-500" strokeWidth={1.75} />}
              title="No Preprocessing Versions Found"
              message="No preprocessing pipelines or tokenization manifests have been registered yet."
            />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60 shadow-sm">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-800/80 uppercase tracking-wider text-[10px] font-semibold text-slate-400 border-b border-slate-800">
                  <tr>
                    <th scope="col" className="px-4 py-3.5">ID</th>
                    <th scope="col" className="px-4 py-3.5">Version Key</th>
                    <th scope="col" className="px-4 py-3.5">Preprocessing SHA256</th>
                    <th scope="col" className="px-4 py-3.5">Lifecycle Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {prepVersions.map((p) => (
                    <tr key={p.preprocessing_version_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 font-mono font-medium text-slate-400">
                        #{p.preprocessing_version_id}
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold text-white">
                        {p.version_key}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400">
                          <span title={p.preprocessing_sha256}>
                            {truncateHash(p.preprocessing_sha256, 8, 8)}
                          </span>
                          <button
                            type="button"
                            onClick={() => copyToClipboard(p.preprocessing_sha256, `prep_sha_${p.preprocessing_version_id}`)}
                            title="Copy full SHA256"
                            className="rounded p-1 text-slate-500 hover:text-indigo-400 transition-colors"
                          >
                            {copiedKey === `prep_sha_${p.preprocessing_version_id}` ? (
                              <Check className="h-3 w-3 text-emerald-400" />
                            ) : (
                              <Copy className="h-3 w-3" />
                            )}
                          </button>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={p.lifecycle_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* ================================================================== */}
        {/* SECTION 4: Recent Inference Runs Table & Pagination               */}
        {/* ================================================================== */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <History className="h-5 w-5 text-teal-400" strokeWidth={1.75} /> Recent Inference Runs
              </h2>
              <p className="mt-0.5 text-xs text-slate-400">
                Audit trail of historical model predictions, batch execution states, and score thresholds
              </p>
            </div>
            {runsTotal > 0 && (
              <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-300 border border-slate-700">
                {runsTotal} {runsTotal === 1 ? 'total run' : 'total runs'}
              </span>
            )}
          </div>

          {loadingRuns ? (
            <TableSkeleton rows={5} cols={6} />
          ) : runsError ? (
            <ErrorState
              message={`Failed to load inference runs: ${runsError}`}
              onRetry={() => fetchInferenceRuns(runsOffset)}
            />
          ) : inferenceRuns.length === 0 ? (
            <EmptyState
              icon={<History className="h-8 w-8 text-slate-500" strokeWidth={1.75} />}
              title="No Inference Runs Recorded"
              message="No inference runs have been executed yet against registered model versions and graph snapshots."
            />
          ) : (
            <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-800/80 uppercase tracking-wider text-[10px] font-semibold text-slate-400 border-b border-slate-800">
                    <tr>
                      <th scope="col" className="px-4 py-3.5">Run Key</th>
                      <th scope="col" className="px-4 py-3.5">Status</th>
                      <th scope="col" className="px-4 py-3.5">Model Name</th>
                      <th scope="col" className="px-4 py-3.5">Requested / Completed</th>
                      <th scope="col" className="px-4 py-3.5">Threshold</th>
                      <th scope="col" className="px-4 py-3.5">Created At</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {inferenceRuns.map((r) => {
                      const modelName =
                        r.model?.model_name || r.model?.version_key || `Model #${r.model?.model_version_id || '—'}`;
                      return (
                        <tr key={r.inference_run_id} className="hover:bg-slate-800/40 transition-colors">
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-1.5 font-mono text-white font-medium">
                              <span title={r.run_key}>{truncateHash(r.run_key, 6, 6)}</span>
                              <button
                                type="button"
                                onClick={() => copyToClipboard(r.run_key, `run_key_${r.inference_run_id}`)}
                                title="Copy full run key"
                                className="rounded p-1 text-slate-500 hover:text-indigo-400 transition-colors"
                              >
                                {copiedKey === `run_key_${r.inference_run_id}` ? (
                                  <Check className="h-3 w-3 text-emerald-400" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </button>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge status={r.status} />
                          </td>
                          <td className="px-4 py-3 font-medium text-slate-200">
                            {modelName}
                          </td>
                          <td className="px-4 py-3 font-mono">
                            <span className="text-emerald-400 font-semibold">{r.completed_count}</span>
                            <span className="text-slate-500"> / </span>
                            <span className="text-slate-300">{r.requested_count}</span>
                          </td>
                          <td className="px-4 py-3 font-mono text-indigo-400 font-semibold">
                            {r.threshold !== undefined && r.threshold !== null
                              ? r.threshold.toFixed(4)
                              : '—'}
                          </td>
                          <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                            {formatDate(r.created_at)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <Pagination
                offset={runsOffset}
                limit={runsLimit}
                total={runsTotal}
                onPageChange={(newOffset) => fetchInferenceRuns(newOffset)}
              />
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
