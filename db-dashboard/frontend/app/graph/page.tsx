'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw,
  Network,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Zap,
  CheckCircle,
  X,
  AlertOctagon,
  Play,
  Search,
  Check,
  Copy,
} from 'lucide-react';
import AppShell from '../components/AppShell';
import {
  PageHeader,
  StatCard,
  LoadingSpinner,
  EmptyState,
  ErrorState,
  StatusBadge,
  InfoBanner,
  WarningBanner,
} from '../components/ui';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { apiRequest, getErrorMessage } from '../lib/api';

// Response types from backend API
interface GraphSyncStatus {
  neo4j: string;
  connection_verified: boolean;
  queue_counts: Record<string, number>;
  message: string;
}

interface GraphSnapshot {
  graph_snapshot_id: number;
  snapshot_key: string;
  dataset_name: string;
  dataset_sha256: string;
  artifact_sha256: string;
  split_protocol_key: string;
  storage_status: string;
  node_count?: number;
}

interface GraphSyncJobResponse {
  graph_sync_job_id: number;
  status: string;
  deduplicated: boolean;
}

type SyncOperation = 'review_upsert' | 'review_delete' | 'snapshot_rebuild';

export default function GraphExplorerPage() {
  const { user, isLoading: authLoading, isAdmin, isAuthenticated } = useRequireAuth(true);

  // --------------------------------------------------------------------------
  // State: Graph Sync & Neo4j Status
  // --------------------------------------------------------------------------
  const [syncStatus, setSyncStatus] = useState<GraphSyncStatus | null>(null);
  const [loadingSyncStatus, setLoadingSyncStatus] = useState<boolean>(true);
  const [syncStatusError, setSyncStatusError] = useState<string | null>(null);

  const fetchSyncStatus = useCallback(async () => {
    setLoadingSyncStatus(true);
    setSyncStatusError(null);
    try {
      const data = await apiRequest<GraphSyncStatus>('/api/v1/graph-sync/status');
      setSyncStatus(data);
    } catch (err) {
      setSyncStatusError(getErrorMessage(err));
    } finally {
      setLoadingSyncStatus(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchSyncStatus();
    }
  }, [isAuthenticated, fetchSyncStatus]);

  // --------------------------------------------------------------------------
  // State: Create Graph Sync Job (Admin Only)
  // --------------------------------------------------------------------------
  const [operation, setOperation] = useState<SyncOperation>('review_upsert');
  const [reviewIdInput, setReviewIdInput] = useState<string>('');
  const [snapshotIdInput, setSnapshotIdInput] = useState<string>('');
  const [idempotencyKey, setIdempotencyKey] = useState<string>('');
  const [jobSubmitting, setJobSubmitting] = useState<boolean>(false);
  const [jobSuccess, setJobSuccess] = useState<GraphSyncJobResponse | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);

  // Initialize and regenerate idempotency key
  const regenerateIdempotencyKey = useCallback(() => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      setIdempotencyKey(crypto.randomUUID());
    } else {
      setIdempotencyKey(`sync-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`);
    }
  }, []);

  useEffect(() => {
    if (isAdmin && !idempotencyKey) {
      regenerateIdempotencyKey();
    }
  }, [isAdmin, idempotencyKey, regenerateIdempotencyKey]);

  const handleCreateJob = async (e: React.FormEvent) => {
    e.preventDefault();
    setJobError(null);
    setJobSuccess(null);

    // Validation
    const isReviewOp = operation === 'review_upsert' || operation === 'review_delete';
    if (isReviewOp) {
      const parsedReviewId = parseInt(reviewIdInput.trim(), 10);
      if (isNaN(parsedReviewId) || parsedReviewId <= 0) {
        setJobError('Please provide a valid positive integer Review ID.');
        return;
      }
    } else {
      const parsedSnapshotId = parseInt(snapshotIdInput.trim(), 10);
      if (isNaN(parsedSnapshotId) || parsedSnapshotId <= 0) {
        setJobError('Please provide a valid positive integer Graph Snapshot ID.');
        return;
      }
    }

    if (!idempotencyKey.trim()) {
      setJobError('Idempotency key is required.');
      return;
    }

    setJobSubmitting(true);
    try {
      const payload: { operation: SyncOperation; review_id?: number; graph_snapshot_id?: number } = {
        operation,
      };

      if (isReviewOp) {
        payload.review_id = parseInt(reviewIdInput.trim(), 10);
      } else {
        payload.graph_snapshot_id = parseInt(snapshotIdInput.trim(), 10);
      }

      const res = await apiRequest<GraphSyncJobResponse>('/api/v1/graph-sync-jobs', {
        method: 'POST',
        headers: {
          'Idempotency-Key': idempotencyKey.trim(),
        },
        body: JSON.stringify(payload),
      });

      setJobSuccess(res);
      // Generate a fresh idempotency key for the next job
      regenerateIdempotencyKey();
      // Automatically refresh sync queue counts
      fetchSyncStatus();
    } catch (err) {
      setJobError(getErrorMessage(err));
    } finally {
      setJobSubmitting(false);
    }
  };

  // --------------------------------------------------------------------------
  // State: Graph Snapshot Inspector
  // --------------------------------------------------------------------------
  const [searchSnapshotId, setSearchSnapshotId] = useState<string>('');
  const [snapshotData, setSnapshotData] = useState<GraphSnapshot | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState<boolean>(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleFetchSnapshot = async (idToFetch?: string) => {
    const rawId = (idToFetch !== undefined ? idToFetch : searchSnapshotId).trim();
    if (!rawId) {
      setSnapshotError('Please enter a Graph Snapshot ID.');
      return;
    }

    const parsedId = parseInt(rawId, 10);
    if (isNaN(parsedId) || parsedId <= 0) {
      setSnapshotError('Snapshot ID must be a positive integer.');
      return;
    }

    setSnapshotLoading(true);
    setSnapshotError(null);
    try {
      const data = await apiRequest<GraphSnapshot>(`/api/v1/graph-snapshots/${parsedId}`);
      setSnapshotData(data);
    } catch (err) {
      setSnapshotData(null);
      setSnapshotError(getErrorMessage(err));
    } finally {
      setSnapshotLoading(false);
    }
  };

  const handleSnapshotFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleFetchSnapshot();
  };

  const copyToClipboard = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    }
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

  // Derive queue counts safely
  const queueCounts = syncStatus?.queue_counts || {};
  const queuedCount = queueCounts['queued'] ?? 0;
  const runningCount = queueCounts['running'] ?? 0;
  const completedCount = queueCounts['completed'] ?? 0;
  const failedCount = queueCounts['failed'] ?? 0;
  const totalJobsCount = Object.values(queueCounts).reduce((acc, val) => acc + val, 0);

  return (
    <AppShell>
      <PageHeader
        title="Graph Explorer"
        subtitle="Neo4j connection health, durable sync queues, and immutable snapshot manifests"
        actions={
          <button
            onClick={fetchSyncStatus}
            disabled={loadingSyncStatus}
            className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/80 px-3.5 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition-colors disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5 text-teal-400" />
            {loadingSyncStatus ? 'Refreshing...' : 'Refresh Status'}
          </button>
        }
      />

      <div className="space-y-8">
        {/* ================================================================== */}
        {/* SECTION 1: Neo4j Connection & Sync Queue Status                    */}
        {/* ================================================================== */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Network className="h-5 w-5 text-teal-400" strokeWidth={1.75} /> Neo4j Connection & Sync Queue
            </h2>
            {syncStatus && (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-400">Connection Verified:</span>
                <StatusBadge
                  status={syncStatus.connection_verified ? 'Verified' : 'Unverified'}
                  variant={syncStatus.connection_verified ? 'success' : 'warning'}
                />
              </div>
            )}
          </div>

          {loadingSyncStatus ? (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-8">
              <LoadingSpinner text="Checking Neo4j status & sync queues..." />
            </div>
          ) : syncStatusError ? (
            <ErrorState
              message={`Failed to fetch graph sync status: ${syncStatusError}`}
              onRetry={fetchSyncStatus}
            />
          ) : syncStatus ? (
            <div className="space-y-4">
              {/* Connection Status Banner */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 shadow-sm">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">
                      {syncStatus.connection_verified ? (
                        <CheckCircle2 className="h-6 w-6 text-emerald-400" strokeWidth={1.75} />
                      ) : (
                        <AlertCircle className="h-6 w-6 text-amber-400" strokeWidth={1.75} />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-white">Neo4j Driver Status:</span>
                        <StatusBadge
                          status={syncStatus.neo4j}
                          variant={
                            syncStatus.neo4j === 'connected'
                              ? 'success'
                              : syncStatus.neo4j === 'configured_unverified'
                              ? 'warning'
                              : 'error'
                          }
                        />
                      </div>
                      <p className="mt-1 text-xs text-slate-400">{syncStatus.message}</p>
                    </div>
                  </div>

                  {!syncStatus.connection_verified && (
                    <div className="shrink-0">
                      <span className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 px-3 py-1.5 text-xs text-amber-300 font-medium">
                        <AlertTriangle className="h-3.5 w-3.5" /> Projection worker inactive
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Sync Queue Counters */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
                <StatCard
                  label="Queued"
                  value={queuedCount}
                  color={queuedCount > 0 ? 'amber' : 'white'}
                  subtext="Awaiting sync worker"
                />
                <StatCard
                  label="Running"
                  value={runningCount}
                  color={runningCount > 0 ? 'sky' : 'white'}
                  subtext="Currently processing"
                />
                <StatCard
                  label="Completed"
                  value={completedCount}
                  color="emerald"
                  subtext="Synced to graph"
                />
                <StatCard
                  label="Failed"
                  value={failedCount}
                  color={failedCount > 0 ? 'rose' : 'white'}
                  subtext="Errors / rejected"
                />
                <StatCard
                  label="Total Sync Jobs"
                  value={totalJobsCount}
                  color="indigo"
                  subtext="All recorded states"
                />
              </div>
            </div>
          ) : null}
        </section>

        {/* ================================================================== */}
        {/* SECTION 2: Create Graph Sync Jobs (Admin Only)                    */}
        {/* ================================================================== */}
        {isAdmin && (
          <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 space-y-5">
            <div className="flex items-start justify-between border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Zap className="h-5 w-5 text-teal-400" strokeWidth={1.75} /> Enqueue Graph Sync Job
                  </h2>
                  <span className="rounded bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-rose-400">
                    Admin Only
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  Submit an idempotent graph projection job to synchronize reviews or rebuild full snapshots.
                </p>
              </div>
            </div>

            {/* Success Banner */}
            {jobSuccess && (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-xs text-emerald-300">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0" />
                    <span>
                      Sync job <strong>#{jobSuccess.graph_sync_job_id}</strong> queued successfully with status{' '}
                      <span className="font-semibold uppercase tracking-wider">{jobSuccess.status}</span>.
                      {jobSuccess.deduplicated && ' (Deduplicated via existing idempotency key)'}
                    </span>
                  </div>
                  <button
                    onClick={() => setJobSuccess(null)}
                    className="text-slate-400 hover:text-white"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Error Banner */}
            {jobError && (
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertOctagon className="h-4 w-4 text-rose-400 shrink-0" />
                    <span>{jobError}</span>
                  </div>
                  <button
                    onClick={() => setJobError(null)}
                    className="text-slate-400 hover:text-white"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}

            <form onSubmit={handleCreateJob} className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* Operation Selection */}
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                    Operation Type
                  </label>
                  <select
                    value={operation}
                    onChange={(e) => {
                      setOperation(e.target.value as SyncOperation);
                      setJobError(null);
                      setJobSuccess(null);
                    }}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="review_upsert">review_upsert (Insert/Update Review)</option>
                    <option value="review_delete">review_delete (Remove/Tombstone Review)</option>
                    <option value="snapshot_rebuild">snapshot_rebuild (Rebuild from Snapshot)</option>
                  </select>
                  <p className="mt-1 text-[11px] text-slate-500">
                    {operation === 'snapshot_rebuild'
                      ? 'Rebuild entire Neo4j graph projection from a verified graph snapshot.'
                      : operation === 'review_upsert'
                      ? 'Upsert review node and relationship edges for a specific review ID.'
                      : 'Remove review node and invalidate dependent projection edges.'}
                  </p>
                </div>

                {/* Dynamic Input: Review ID or Snapshot ID */}
                {operation === 'snapshot_rebuild' ? (
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                      Graph Snapshot ID <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      placeholder="e.g. 1"
                      value={snapshotIdInput}
                      onChange={(e) => setSnapshotIdInput(e.target.value)}
                      required
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                    <p className="mt-1 text-[11px] text-slate-500">
                      Target GraphSnapshot ID to populate the graph from.
                    </p>
                  </div>
                ) : (
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                      Review ID <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      placeholder="e.g. 101"
                      value={reviewIdInput}
                      onChange={(e) => setReviewIdInput(e.target.value)}
                      required
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                    <p className="mt-1 text-[11px] text-slate-500">
                      Specific review ID in PostgreSQL to sync with Neo4j.
                    </p>
                  </div>
                )}
              </div>

              {/* Idempotency Key */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Idempotency-Key Header <span className="text-rose-400">*</span>
                  </label>
                  <button
                    type="button"
                    onClick={regenerateIdempotencyKey}
                    className="text-[11px] text-indigo-400 hover:text-indigo-300 underline font-medium"
                  >
                    Generate New Key
                  </button>
                </div>
                <input
                  type="text"
                  value={idempotencyKey}
                  onChange={(e) => setIdempotencyKey(e.target.value)}
                  placeholder="UUID / unique request identifier"
                  required
                  className="w-full font-mono text-xs rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2 text-slate-300 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
                <p className="mt-1 text-[11px] text-slate-500">
                  Ensures safe retries. Repeated requests with this key will deduplicate instead of duplicating jobs.
                </p>
              </div>

              {/* Form Submission */}
              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={jobSubmitting}
                  className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors disabled:opacity-50"
                >
                  {jobSubmitting ? (
                    <>
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      <span>Enqueuing Job...</span>
                    </>
                  ) : (
                    <>
                      <Play className="h-3.5 w-3.5" />
                      <span>Enqueue Job</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </section>
        )}

        {/* ================================================================== */}
        {/* SECTION 3: Graph Snapshot Details & Provenance Inspector           */}
        {/* ================================================================== */}
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Search className="h-5 w-5 text-teal-400" strokeWidth={1.75} /> Graph Snapshot Inspector
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Query registered graph snapshots to verify cryptographic hashes, split protocols, and storage readiness.
            </p>
          </div>

          {/* Search Bar */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <form onSubmit={handleSnapshotFormSubmit} className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <input
                  type="number"
                  min="1"
                  step="1"
                  placeholder="Enter Graph Snapshot ID (e.g. 1)"
                  value={searchSnapshotId}
                  onChange={(e) => setSearchSnapshotId(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
              <button
                type="submit"
                disabled={snapshotLoading}
                className="flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors disabled:opacity-50 shrink-0"
              >
                {snapshotLoading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    <span>Fetching...</span>
                  </>
                ) : (
                  <>
                    <Search className="h-3.5 w-3.5" />
                    <span>Fetch Snapshot</span>
                  </>
                )}
              </button>
            </form>

            {/* Quick helper buttons */}
            <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
              <span>Quick inspect:</span>
              {[1, 2, 3].map((quickId) => (
                <button
                  key={quickId}
                  type="button"
                  onClick={() => {
                    setSearchSnapshotId(quickId.toString());
                    handleFetchSnapshot(quickId.toString());
                  }}
                  className="rounded border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
                >
                  Snapshot #{quickId}
                </button>
              ))}
            </div>
          </div>

          {/* Snapshot Content / State */}
          {snapshotLoading ? (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12">
              <LoadingSpinner text="Retrieving snapshot manifest from registry..." />
            </div>
          ) : snapshotError ? (
            <ErrorState
              message={snapshotError}
              onRetry={() => handleFetchSnapshot()}
            />
          ) : snapshotData ? (
            <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/80 shadow-sm">
              {/* Card Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 bg-slate-800/40 px-6 py-4 gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-3">
                    <h3 className="text-base font-bold text-white truncate">
                      {snapshotData.snapshot_key}
                    </h3>
                    <StatusBadge status={snapshotData.storage_status} />
                  </div>
                  <p className="mt-0.5 text-xs text-slate-400">
                    Snapshot ID #{snapshotData.graph_snapshot_id} • Dataset: {snapshotData.dataset_name}
                  </p>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  <span className="text-xs text-slate-400">Storage:</span>
                  <StatusBadge
                    status={snapshotData.storage_status}
                    variant={
                      snapshotData.storage_status === 'available'
                        ? 'success'
                        : snapshotData.storage_status === 'archived'
                        ? 'warning'
                        : 'error'
                    }
                  />
                </div>
              </div>

              {/* Metadata Grid */}
              <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    Dataset Name
                  </p>
                  <p className="mt-1 text-sm font-semibold text-white">
                    {snapshotData.dataset_name}
                  </p>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    Split Protocol Key
                  </p>
                  <p className="mt-1 text-sm font-semibold text-indigo-400 font-mono">
                    {snapshotData.split_protocol_key}
                  </p>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    Node Count
                  </p>
                  <p className="mt-1 text-xl font-bold text-emerald-400">
                    {snapshotData.node_count !== undefined && snapshotData.node_count !== null
                      ? snapshotData.node_count.toLocaleString()
                      : 'N/A'}
                  </p>
                </div>

                {/* Hashes */}
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4 md:col-span-2 lg:col-span-3 space-y-4">
                  {/* Dataset SHA256 */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Dataset SHA256 Checksum
                      </span>
                      <button
                        onClick={() => copyToClipboard(snapshotData.dataset_sha256, 'dataset_sha')}
                        className="text-[11px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                      >
                        {copiedKey === 'dataset_sha' ? (
                          <>
                            <Check className="h-3 w-3 text-emerald-400" /> Copied
                          </>
                        ) : (
                          <>
                            <Copy className="h-3 w-3" /> Copy
                          </>
                        )}
                      </button>
                    </div>
                    <div className="rounded border border-slate-800 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-300 break-all select-all">
                      {snapshotData.dataset_sha256}
                    </div>
                  </div>

                  {/* Artifact SHA256 */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Artifact SHA256 Checksum
                      </span>
                      <button
                        onClick={() => copyToClipboard(snapshotData.artifact_sha256, 'artifact_sha')}
                        className="text-[11px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                      >
                        {copiedKey === 'artifact_sha' ? (
                          <>
                            <Check className="h-3 w-3 text-emerald-400" /> Copied
                          </>
                        ) : (
                          <>
                            <Copy className="h-3 w-3" /> Copy
                          </>
                        )}
                      </button>
                    </div>
                    <div className="rounded border border-slate-800 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-300 break-all select-all">
                      {snapshotData.artifact_sha256}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <EmptyState
              icon={<Network className="h-8 w-8 text-slate-500" strokeWidth={1.75} />}
              title="No Snapshot Selected"
              message="Enter a valid Graph Snapshot ID above to inspect immutable provenance, verification status, and cryptographic checksums."
            />
          )}
        </section>
      </div>
    </AppShell>
  );
}
