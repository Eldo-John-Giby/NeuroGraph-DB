'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw,
  Activity,
  Database,
  Cpu,
  Share2,
  GitMerge,
  ShieldCheck,
} from 'lucide-react';
import AppShell from '../../components/AppShell';
import {
  PageHeader,
  StatCard,
  LoadingSpinner,
  InfoBanner,
  StatusBadge,
  ErrorState,
} from '../../components/ui';
import { useRequireAuth } from '../../hooks/useRequireAuth';
import { apiRequest, getErrorMessage } from '../../lib/api';

interface SystemHealthResponse {
  status: 'ready' | 'not_ready' | string;
  checks: {
    postgresql: string;
    verified_model: string;
    neo4j: string;
    [key: string]: string;
  };
}

interface GraphSyncStatusResponse {
  neo4j: string;
  connection_verified: boolean;
  queue_counts: Record<string, number>;
  message?: string;
}

interface ModelStatusResponse {
  status: string;
  inference_available: boolean;
  reason: string;
  supported_modes: string[];
  details?: string;
}

export default function AdminAuditPage() {
  const { isLoading: authLoading, isAdmin, isAuthenticated } = useRequireAuth(true);

  // Section 1: System Health State
  const [healthData, setHealthData] = useState<SystemHealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthTimestamp, setHealthTimestamp] = useState<string | null>(null);

  // Section 2: Graph Sync State
  const [syncData, setSyncData] = useState<GraphSyncStatusResponse | null>(null);
  const [syncLoading, setSyncLoading] = useState<boolean>(true);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncTimestamp, setSyncTimestamp] = useState<string | null>(null);

  // Section 3: Model Status State
  const [modelData, setModelData] = useState<ModelStatusResponse | null>(null);
  const [modelLoading, setModelLoading] = useState<boolean>(true);
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelTimestamp, setModelTimestamp] = useState<string | null>(null);

  // Fetch System Health (/health/ready)
  // Backend returns 200 or 503 with JSON: { status: "ready" | "not_ready", checks: { postgresql, verified_model, neo4j } }
  const fetchHealth = useCallback(async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const response = await fetch('/health/ready');
      const data = await response.json().catch(() => null);

      if (data && typeof data === 'object' && data.checks) {
        setHealthData(data as SystemHealthResponse);
      } else {
        throw new Error(response.statusText || 'Health check responded with invalid format');
      }
      setHealthTimestamp(new Date().toLocaleTimeString());
    } catch (err: unknown) {
      setHealthError(getErrorMessage(err));
    } finally {
      setHealthLoading(false);
    }
  }, []);

  // Fetch Graph Sync (/api/v1/graph-sync/status)
  const fetchGraphSync = useCallback(async () => {
    setSyncLoading(true);
    setSyncError(null);
    try {
      const data = await apiRequest<GraphSyncStatusResponse>('/api/v1/graph-sync/status');
      setSyncData(data);
      setSyncTimestamp(new Date().toLocaleTimeString());
    } catch (err: unknown) {
      setSyncError(getErrorMessage(err));
    } finally {
      setSyncLoading(false);
    }
  }, []);

  // Fetch Model Status (/api/v1/models/status)
  const fetchModelStatus = useCallback(async () => {
    setModelLoading(true);
    setModelError(null);
    try {
      const data = await apiRequest<ModelStatusResponse>('/api/v1/models/status');
      setModelData(data);
      setModelTimestamp(new Date().toLocaleTimeString());
    } catch (err: unknown) {
      setModelError(getErrorMessage(err));
    } finally {
      setModelLoading(false);
    }
  }, []);

  // Refresh all sections independently
  const handleRefreshAll = () => {
    fetchHealth();
    fetchGraphSync();
    fetchModelStatus();
  };

  useEffect(() => {
    if (isAuthenticated && isAdmin) {
      fetchHealth();
      fetchGraphSync();
      fetchModelStatus();
    }
  }, [isAuthenticated, isAdmin, fetchHealth, fetchGraphSync, fetchModelStatus]);

  if (authLoading || !isAuthenticated || !isAdmin) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <LoadingSpinner text="Verifying administrative access..." />
      </div>
    );
  }

  return (
    <AppShell>
      <PageHeader
        title="Audit & Database Operations"
        subtitle="Infrastructure health diagnostics, graph sync pipeline queues, and ML inference runtime status"
        actions={
          <button
            onClick={handleRefreshAll}
            className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5 text-teal-400" />
            Refresh All Diagnostics
          </button>
        }
      />

      <div className="space-y-6">
        {/* Info Banner specified in requirements */}
        <InfoBanner
          title="Audit Log Service Notice"
          message="Audit log viewing endpoints will be available in a future release. Mutation records and security access events are actively recorded in the PostgreSQL audit_logs table via database triggers."
        />

        {/* SECTION 1: System Health */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-bold text-sm">
                <Activity className="h-4 w-4 text-emerald-400" />
              </span>
              <div>
                <h3 className="text-base font-bold text-white">Section 1: System Readiness & Component Health</h3>
                <p className="text-xs text-slate-400">
                  Target probe: <code className="text-emerald-400 font-mono text-xs">GET /health/ready</code>
                  {healthTimestamp && <span className="ml-2 text-slate-500">Last checked at {healthTimestamp}</span>}
                </p>
              </div>
            </div>
            <button
              onClick={fetchHealth}
              disabled={healthLoading}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors disabled:opacity-50"
            >
              {healthLoading ? 'Probing...' : 'Re-check'}
            </button>
          </div>

          {healthLoading ? (
            <div className="py-8">
              <LoadingSpinner text="Executing readiness health checks..." />
            </div>
          ) : healthError ? (
            <ErrorState message={healthError} onRetry={fetchHealth} />
          ) : healthData ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-lg bg-slate-950/60 p-4 border border-slate-800">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Overall Readiness State
                  </span>
                  <StatusBadge
                    status={healthData.status === 'ready' ? 'Ready' : 'Not Ready'}
                    variant={healthData.status === 'ready' ? 'success' : 'warning'}
                  />
                </div>
                <span className="text-xs font-mono text-slate-500">
                  HTTP {healthData.status === 'ready' ? '200 OK' : '503 Service Unavailable'}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* PostgreSQL */}
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <Database className="h-3.5 w-3.5 text-slate-300" /> PostgreSQL RDBMS
                    </span>
                    <StatusBadge
                      status={healthData.checks.postgresql}
                      variant={healthData.checks.postgresql === 'available' ? 'success' : 'error'}
                    />
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Primary 3NF transactional datastore for reviews, users, and audit logs.
                  </p>
                </div>

                {/* Verified Model */}
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <Cpu className="h-3.5 w-3.5 text-slate-300" /> Verified ML Model
                    </span>
                    <StatusBadge
                      status={healthData.checks.verified_model}
                      variant={healthData.checks.verified_model === 'available' ? 'success' : 'warning'}
                    />
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Model checkpoint state-dict and verified preprocessing pipeline bundle.
                  </p>
                </div>

                {/* Neo4j */}
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <Share2 className="h-3.5 w-3.5 text-slate-300" /> Neo4j Graph DB
                    </span>
                    <StatusBadge
                      status={healthData.checks.neo4j}
                      variant={
                        healthData.checks.neo4j === 'available'
                          ? 'success'
                          : healthData.checks.neo4j === 'configured_unverified'
                          ? 'warning'
                          : 'neutral'
                      }
                    />
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Graph database instance for topological projection and subgraphs.
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* SECTION 2: Graph Sync Status */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 font-bold text-sm">
                <GitMerge className="h-4 w-4 text-indigo-400" />
              </span>
              <div>
                <h3 className="text-base font-bold text-white">Section 2: Graph Synchronization Pipeline Status</h3>
                <p className="text-xs text-slate-400">
                  Target probe: <code className="text-indigo-400 font-mono text-xs">GET /api/v1/graph-sync/status</code>
                  {syncTimestamp && <span className="ml-2 text-slate-500">Last checked at {syncTimestamp}</span>}
                </p>
              </div>
            </div>
            <button
              onClick={fetchGraphSync}
              disabled={syncLoading}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors disabled:opacity-50"
            >
              {syncLoading ? 'Syncing...' : 'Re-check'}
            </button>
          </div>

          {syncLoading ? (
            <div className="py-8">
              <LoadingSpinner text="Querying graph sync queue and Neo4j status..." />
            </div>
          ) : syncError ? (
            <ErrorState message={syncError} onRetry={fetchGraphSync} />
          ) : syncData ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Neo4j Configuration
                      </p>
                      <p className="text-sm font-bold text-white mt-1 capitalize font-mono">
                        {syncData.neo4j}
                      </p>
                    </div>
                    <StatusBadge
                      status={syncData.neo4j}
                      variant={syncData.neo4j === 'configured_unverified' ? 'warning' : 'neutral'}
                    />
                  </div>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Connection Verification
                      </p>
                      <p className="text-sm font-bold text-white mt-1">
                        {syncData.connection_verified ? 'Verified Active' : 'Unverified / Disconnected'}
                      </p>
                    </div>
                    <StatusBadge
                      status={syncData.connection_verified ? 'Verified' : 'Unverified'}
                      variant={syncData.connection_verified ? 'success' : 'warning'}
                    />
                  </div>
                </div>
              </div>

              {/* Queue Counts */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                  Sync Worker Job Queues (<code className="text-slate-300 font-mono">graph_sync_jobs</code>)
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <StatCard
                    label="Queued Jobs"
                    value={syncData.queue_counts?.queued || 0}
                    color="amber"
                  />
                  <StatCard
                    label="Running Jobs"
                    value={syncData.queue_counts?.running || 0}
                    color="sky"
                  />
                  <StatCard
                    label="Completed Jobs"
                    value={syncData.queue_counts?.completed || 0}
                    color="emerald"
                  />
                  <StatCard
                    label="Failed / Retried"
                    value={syncData.queue_counts?.failed || 0}
                    color="rose"
                  />
                </div>
              </div>

              {syncData.message && (
                <div className="rounded-lg border border-slate-800/80 bg-slate-950/60 p-3 text-xs text-slate-400 font-mono">
                  <span className="text-slate-500">Worker Status:</span> {syncData.message}
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* SECTION 3: Model Status */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500/20 text-sky-400 border border-sky-500/30 font-bold text-sm">
                <Cpu className="h-4 w-4 text-sky-400" />
              </span>
              <div>
                <h3 className="text-base font-bold text-white">Section 3: ML Model & Inference Availability</h3>
                <p className="text-xs text-slate-400">
                  Target probe: <code className="text-sky-400 font-mono text-xs">GET /api/v1/models/status</code>
                  {modelTimestamp && <span className="ml-2 text-slate-500">Last checked at {modelTimestamp}</span>}
                </p>
              </div>
            </div>
            <button
              onClick={fetchModelStatus}
              disabled={modelLoading}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors disabled:opacity-50"
            >
              {modelLoading ? 'Inspecting...' : 'Re-check'}
            </button>
          </div>

          {modelLoading ? (
            <div className="py-8">
              <LoadingSpinner text="Evaluating ML model checkpoint & inference runtime..." />
            </div>
          ) : modelError ? (
            <ErrorState message={modelError} onRetry={fetchModelStatus} />
          ) : modelData ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Inference State
                      </p>
                      <p className="text-sm font-bold text-white mt-1 capitalize">
                        {modelData.status}
                      </p>
                    </div>
                    <StatusBadge
                      status={modelData.status}
                      variant={modelData.status === 'available' ? 'success' : 'error'}
                    />
                  </div>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Inference Pipeline
                      </p>
                      <p className="text-sm font-bold text-white mt-1">
                        {modelData.inference_available ? 'Ready for Execution' : 'Disabled / Offline'}
                      </p>
                    </div>
                    <StatusBadge
                      status={modelData.inference_available ? 'Available' : 'Unavailable'}
                      variant={modelData.inference_available ? 'success' : 'error'}
                    />
                  </div>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Diagnostics Code
                      </p>
                      <p className="text-xs font-mono font-bold text-amber-400 mt-1">
                        {modelData.reason}
                      </p>
                    </div>
                    <StatusBadge status={modelData.reason} variant="warning" />
                  </div>
                </div>
              </div>

              {/* Supported Modes */}
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  Supported Inference Modes
                </p>
                {modelData.supported_modes && modelData.supported_modes.length > 0 ? (
                  <div className="flex gap-2">
                    {modelData.supported_modes.map((mode, idx) => (
                      <span
                        key={idx}
                        className="rounded bg-indigo-500/15 border border-indigo-500/30 px-2.5 py-1 text-xs font-mono text-indigo-300"
                      >
                        {mode}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic">
                    No active inference modes currently registered in runtime registry.
                  </p>
                )}
              </div>

              {/* Details Explanation */}
              {modelData.details && (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-xs text-slate-300 leading-relaxed">
                  <span className="font-semibold text-amber-300">Bundle Verification Details: </span>
                  {modelData.details}
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* SECTION 4: Database Triggers & Audit Log Compliance Specification */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
          <div className="flex items-center gap-3 mb-4">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30 font-bold text-sm">
              <ShieldCheck className="h-4 w-4 text-rose-400" />
            </span>
            <div>
              <h3 className="text-base font-bold text-white">Automated Trigger Audit Architecture</h3>
              <p className="text-xs text-slate-400">
                PostgreSQL <code className="text-rose-400 font-mono">audit_logs</code> schema and event coverage
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-xs font-mono">
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
              <span className="text-slate-500 block text-[10px] uppercase font-sans">Auth Events</span>
              <span className="text-slate-300">auth.login</span>
              <span className="text-slate-500 block text-[10px]">auth.logout, auth.refresh</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
              <span className="text-slate-500 block text-[10px] uppercase font-sans">User Events</span>
              <span className="text-slate-300">user.create</span>
              <span className="text-slate-500 block text-[10px]">user.role_change</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
              <span className="text-slate-500 block text-[10px] uppercase font-sans">Review Events</span>
              <span className="text-slate-300">review.create</span>
              <span className="text-slate-500 block text-[10px]">review.variant_upsert</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
              <span className="text-slate-500 block text-[10px] uppercase font-sans">Sync Events</span>
              <span className="text-slate-300">graph_sync.enqueue</span>
              <span className="text-slate-500 block text-[10px]">sync.batch_commit</span>
            </div>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            Every administrative mutation, token revocation, review submission, and sync job dispatch automatically writes an immutable row with actor user ID, UTC timestamp, entity type, and entity key. A full interactive audit trail table viewer with filterable actor search will be unlocked in the next minor version deployment.
          </p>
        </div>
      </div>
    </AppShell>
  );
}
