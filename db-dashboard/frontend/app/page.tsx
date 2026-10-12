'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from './context/AuthContext';
import { apiRequest } from './lib/api';

interface ExperimentRun {
  id: number;
  seed: number;
  timeSec: number;
  f1Macro: number;
  precision: number;
  recall: number;
  auc: number;
  graphVariant: { id: number; name: string };
  mlModel: { id: number; name: string };
}

interface SQLSummary {
  model_name: string;
  variant_name: string;
  total_runs: string | number;
  avg_f1_macro: number;
  avg_auc: number;
  avg_time_sec: number;
  peak_auc: number;
  peak_f1: number;
}

interface AuditLogItem {
  id: number;
  action: string;
  method: string;
  endpoint: string;
  details: string;
  timestamp: string;
  user?: { username: string; role: string };
}

export default function DashboardPage() {
  const router = useRouter();
  const { user, token, logout, isLoading: authLoading } = useAuth();

  // Tab navigation
  const [activeTab, setActiveTab] = useState<'runs' | 'view' | 'procedure' | 'audit'>('runs');

  // Runs Data state
  const [runs, setRuns] = useState<ExperimentRun[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalRecords, setTotalRecords] = useState(0);

  // Search & Filtering
  const [search, setSearch] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedVariant, setSelectedVariant] = useState('');
  const [minAuc, setMinAuc] = useState('');

  // Dropdown options
  const [models, setModels] = useState<{ id: number; name: string }[]>([]);
  const [variants, setVariants] = useState<{ id: number; name: string }[]>([]);

  // Modal / CRUD Form State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRunId, setEditingRunId] = useState<number | null>(null);
  const [formModelId, setFormModelId] = useState<number>(1);
  const [formVariantId, setFormVariantId] = useState<number>(1);
  const [formSeed, setFormSeed] = useState<number>(42);
  const [formTime, setFormTime] = useState<number>(12.5);
  const [formF1, setFormF1] = useState<number>(0.85);
  const [formPrecision, setFormPrecision] = useState<number>(0.84);
  const [formRecall, setFormRecall] = useState<number>(0.86);
  const [formAuc, setFormAuc] = useState<number>(0.92);

  // Advanced SQL View State
  const [sqlSummaries, setSqlSummaries] = useState<SQLSummary[]>([]);
  const [loadingSql, setLoadingSql] = useState(false);

  // Stored Procedure Form State
  const [procModel, setProcModel] = useState('NeuroGraph-DB (Ours)');
  const [procVariant, setProcVariant] = useState('camo_topo_p30');
  const [procSeed, setProcSeed] = useState(999);
  const [procAuc, setProcAuc] = useState(0.945);
  const [procF1, setProcF1] = useState(0.912);
  const [procMsg, setProcMsg] = useState<string | null>(null);

  // Audit Logs State (Bonus)
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Protect route
  useEffect(() => {
    if (!authLoading && !token) {
      router.push('/login');
    }
  }, [authLoading, token, router]);

  // Load models & variants lookup
  useEffect(() => {
    if (token) {
      apiRequest('/api/models').then(setModels).catch(console.error);
      apiRequest('/api/variants').then(setVariants).catch(console.error);
    }
  }, [token]);

  // Fetch Experiment Runs
  const fetchRuns = async () => {
    if (!token) return;
    setLoadingRuns(true);
    try {
      const queryParams = new URLSearchParams({
        page: page.toString(),
        limit: '10',
      });
      if (search) queryParams.append('search', search);
      if (selectedModel) queryParams.append('modelId', selectedModel);
      if (selectedVariant) queryParams.append('variantId', selectedVariant);
      if (minAuc) queryParams.append('minAuc', minAuc);

      const res = await apiRequest(`/api/runs?${queryParams.toString()}`);
      setRuns(res.data);
      setTotalPages(res.pagination.totalPages);
      setTotalRecords(res.pagination.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingRuns(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchRuns();
    }
  }, [token, page, selectedModel, selectedVariant, minAuc]);

  // Search debounce / trigger
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchRuns();
  };

  // Fetch SQL View
  const fetchSqlView = async () => {
    setLoadingSql(true);
    try {
      const res = await apiRequest('/api/advanced/view');
      setSqlSummaries(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingSql(false);
    }
  };

  // Fetch Audit Logs
  const fetchAuditLogs = async () => {
    setLoadingAudit(true);
    try {
      const res = await apiRequest('/api/audit-logs');
      setAuditLogs(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAudit(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'view') fetchSqlView();
    if (activeTab === 'audit' && user?.role === 'ADMIN') fetchAuditLogs();
  }, [activeTab]);

  // Delete Run (Admin Only)
  const handleDeleteRun = async (id: number) => {
    if (!confirm(`Are you sure you want to delete Experiment Run #${id}?`)) return;
    try {
      await apiRequest(`/api/runs/${id}`, { method: 'DELETE' });
      fetchRuns();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  // Save / Edit Run
  const handleSaveRun = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingRunId) {
        await apiRequest(`/api/runs/${editingRunId}`, {
          method: 'PUT',
          body: JSON.stringify({
            timeSec: formTime,
            f1Macro: formF1,
            precision: formPrecision,
            recall: formRecall,
            auc: formAuc,
          }),
        });
      } else {
        await apiRequest('/api/runs', {
          method: 'POST',
          body: JSON.stringify({
            graphVariantId: formVariantId,
            mlModelId: formModelId,
            seed: formSeed,
            timeSec: formTime,
            f1Macro: formF1,
            precision: formPrecision,
            recall: formRecall,
            auc: formAuc,
          }),
        });
      }
      setIsModalOpen(false);
      setEditingRunId(null);
      fetchRuns();
    } catch (err: any) {
      alert(`Operation failed: ${err.message}`);
    }
  };

  const openEditModal = (run: ExperimentRun) => {
    setEditingRunId(run.id);
    setFormModelId(run.mlModel.id);
    setFormVariantId(run.graphVariant.id);
    setFormSeed(run.seed);
    setFormTime(run.timeSec);
    setFormF1(run.f1Macro);
    setFormPrecision(run.precision);
    setFormRecall(run.recall);
    setFormAuc(run.auc);
    setIsModalOpen(true);
  };

  const openCreateModal = () => {
    setEditingRunId(null);
    if (models.length > 0) setFormModelId(models[0].id);
    if (variants.length > 0) setFormVariantId(variants[0].id);
    setFormSeed(42);
    setFormTime(10.5);
    setFormF1(0.85);
    setFormPrecision(0.84);
    setFormRecall(0.86);
    setFormAuc(0.91);
    setIsModalOpen(true);
  };

  // Execute Stored Procedure
  const handleExecuteProcedure = async (e: React.FormEvent) => {
    e.preventDefault();
    setProcMsg(null);
    try {
      const res = await apiRequest('/api/advanced/procedure', {
        method: 'POST',
        body: JSON.stringify({
          modelName: procModel,
          variantName: procVariant,
          seed: Number(procSeed),
          timeSec: 15.0,
          f1Macro: Number(procF1),
          precision: 0.90,
          recall: 0.92,
          auc: Number(procAuc),
        }),
      });
      setProcMsg(`✓ Success: ${res.message}`);
      fetchRuns();
    } catch (err: any) {
      setProcMsg(`✘ Failed: ${err.message}`);
    }
  };

  if (authLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
        Authenticating session...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-16">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600/30 text-indigo-400 font-bold border border-indigo-500/40">
              ⬡
            </span>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white">
                NeuroGraph-DB
              </h1>
              <p className="text-xs text-slate-400">
                VIT BCSE302P Database Dashboard & ML Hub
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <span className="block text-sm font-semibold text-white">
                {user.username}
              </span>
              <span className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                user.role === 'ADMIN'
                  ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                  : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
              }`}>
                {user.role}
              </span>
            </div>
            <button
              onClick={logout}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="mx-auto max-w-7xl px-6 pt-8">
        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 mb-6 gap-2">
          <button
            onClick={() => setActiveTab('runs')}
            className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors ${
              activeTab === 'runs'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            📊 Experiment Runs & CRUD
          </button>
          <button
            onClick={() => setActiveTab('view')}
            className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors ${
              activeTab === 'view'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            ⚡ Raw SQL View (v_model_performance)
          </button>
          <button
            onClick={() => setActiveTab('procedure')}
            className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors ${
              activeTab === 'procedure'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            ⚙️ Stored Procedure (sp_record_run)
          </button>
          {user.role === 'ADMIN' && (
            <button
              onClick={() => setActiveTab('audit')}
              className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors ${
                activeTab === 'audit'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              🛡️ Audit Logs (+1 Bonus)
            </button>
          )}
        </div>

        {/* TAB 1: EXPERIMENT RUNS & CRUD */}
        {activeTab === 'runs' && (
          <div className="space-y-6">
            {/* Filter Bar */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 md:grid-cols-5 gap-3">
                <div className="md:col-span-2">
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search model or variant name..."
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <select
                    value={selectedModel}
                    onChange={(e) => { setSelectedModel(e.target.value); setPage(1); }}
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="">All ML Models</option>
                    {models.map(m => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <select
                    value={selectedVariant}
                    onChange={(e) => { setSelectedVariant(e.target.value); setPage(1); }}
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="">All Graph Variants</option>
                    {variants.map(v => (
                      <option key={v.id} value={v.id}>{v.name}</option>
                    ))}
                  </select>
                </div>
                <div className="flex gap-2">
                  <button
                    type="submit"
                    className="flex-1 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
                  >
                    Filter
                  </button>
                  <button
                    type="button"
                    onClick={openCreateModal}
                    className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-500 whitespace-nowrap"
                  >
                    + New Run
                  </button>
                </div>
              </form>
            </div>

            {/* Table */}
            <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="bg-slate-800/80 text-xs font-semibold uppercase tracking-wider text-slate-400">
                    <tr>
                      <th className="px-4 py-3">ID</th>
                      <th className="px-4 py-3">ML Model</th>
                      <th className="px-4 py-3">Graph Variant</th>
                      <th className="px-4 py-3">Seed</th>
                      <th className="px-4 py-3">AUC</th>
                      <th className="px-4 py-3">F1-Macro</th>
                      <th className="px-4 py-3">Precision</th>
                      <th className="px-4 py-3">Recall</th>
                      <th className="px-4 py-3">Time (s)</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                    {loadingRuns ? (
                      <tr>
                        <td colSpan={10} className="px-4 py-8 text-center text-slate-500 font-sans">
                          Loading experiment runs...
                        </td>
                      </tr>
                    ) : runs.length === 0 ? (
                      <tr>
                        <td colSpan={10} className="px-4 py-8 text-center text-slate-500 font-sans">
                          No experiment runs found matching criteria.
                        </td>
                      </tr>
                    ) : (
                      runs.map((r) => (
                        <tr key={r.id} className="hover:bg-slate-800/40 transition-colors">
                          <td className="px-4 py-3 text-slate-400">#{r.id}</td>
                          <td className="px-4 py-3 font-semibold text-white font-sans">
                            {r.mlModel.name}
                          </td>
                          <td className="px-4 py-3 font-sans text-indigo-400">
                            {r.graphVariant.name}
                          </td>
                          <td className="px-4 py-3 text-slate-400">{r.seed}</td>
                          <td className="px-4 py-3 font-bold text-emerald-400">
                            {r.auc.toFixed(4)}
                          </td>
                          <td className="px-4 py-3 text-sky-400">
                            {r.f1Macro.toFixed(4)}
                          </td>
                          <td className="px-4 py-3 text-slate-300">{r.precision.toFixed(4)}</td>
                          <td className="px-4 py-3 text-slate-300">{r.recall.toFixed(4)}</td>
                          <td className="px-4 py-3 text-slate-400">{r.timeSec.toFixed(2)}s</td>
                          <td className="px-4 py-3 text-right space-x-2 font-sans">
                            <button
                              onClick={() => openEditModal(r)}
                              className="rounded bg-indigo-600/20 px-2 py-1 text-xs font-semibold text-indigo-400 hover:bg-indigo-600/30"
                            >
                              Edit
                            </button>
                            {user.role === 'ADMIN' && (
                              <button
                                onClick={() => handleDeleteRun(r.id)}
                                className="rounded bg-rose-600/20 px-2 py-1 text-xs font-semibold text-rose-400 hover:bg-rose-600/30"
                              >
                                Delete
                              </button>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination Bar */}
              <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900/80 px-4 py-3 text-xs text-slate-400">
                <div>
                  Showing {runs.length} of {totalRecords} runs (Page {page} of {totalPages || 1})
                </div>
                <div className="flex gap-2">
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    className="rounded border border-slate-700 bg-slate-800 px-3 py-1 font-semibold text-slate-300 disabled:opacity-40 hover:bg-slate-700"
                  >
                    Previous
                  </button>
                  <button
                    disabled={page >= totalPages}
                    onClick={() => setPage(p => p + 1)}
                    className="rounded border border-slate-700 bg-slate-800 px-3 py-1 font-semibold text-slate-300 disabled:opacity-40 hover:bg-slate-700"
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: RAW SQL VIEW */}
        {activeTab === 'view' && (
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <h2 className="text-base font-bold text-white mb-1">
                Raw PostgreSQL View: <code className="text-indigo-400 font-mono">v_model_performance_summary</code>
              </h2>
              <p className="text-xs text-slate-400">
                Executes directly against the database view calculating aggregated model averages and peak metrics across graph variants.
              </p>
            </div>

            <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 shadow-xl">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Model</th>
                    <th className="px-4 py-3">Variant</th>
                    <th className="px-4 py-3">Runs</th>
                    <th className="px-4 py-3">Avg AUC</th>
                    <th className="px-4 py-3">Avg F1</th>
                    <th className="px-4 py-3">Peak AUC</th>
                    <th className="px-4 py-3">Peak F1</th>
                    <th className="px-4 py-3">Avg Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                  {loadingSql ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-slate-500 font-sans">
                        Querying SQL view...
                      </td>
                    </tr>
                  ) : sqlSummaries.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-slate-500 font-sans">
                        No view records returned. (Ensure advanced_sql.sql has been executed).
                      </td>
                    </tr>
                  ) : (
                    sqlSummaries.map((s, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/40">
                        <td className="px-4 py-3 font-semibold text-white font-sans">{s.model_name}</td>
                        <td className="px-4 py-3 font-sans text-indigo-400">{s.variant_name}</td>
                        <td className="px-4 py-3 text-slate-400">{s.total_runs}</td>
                        <td className="px-4 py-3 font-bold text-emerald-400">{Number(s.avg_auc).toFixed(4)}</td>
                        <td className="px-4 py-3 text-sky-400">{Number(s.avg_f1_macro).toFixed(4)}</td>
                        <td className="px-4 py-3 text-emerald-300">{Number(s.peak_auc).toFixed(4)}</td>
                        <td className="px-4 py-3 text-sky-300">{Number(s.peak_f1).toFixed(4)}</td>
                        <td className="px-4 py-3 text-slate-400">{Number(s.avg_time_sec).toFixed(2)}s</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: STORED PROCEDURE */}
        {activeTab === 'procedure' && (
          <div className="max-w-2xl rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
            <h2 className="text-lg font-bold text-white mb-2">
              Execute Stored Procedure: <code className="text-indigo-400 font-mono">sp_record_experiment_run</code>
            </h2>
            <p className="text-xs text-slate-400 mb-6">
              Invokes a PL/pgSQL stored procedure that transactionally inserts or updates an experiment run, resolving foreign keys on the fly. Requires <strong className="text-rose-400">ADMIN</strong> role.
            </p>

            {procMsg && (
              <div className="mb-4 rounded-lg border border-slate-700 bg-slate-800/90 p-3 text-sm font-mono">
                {procMsg}
              </div>
            )}

            {user.role !== 'ADMIN' ? (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-400">
                Access Restricted: Only Admin users can invoke raw database Stored Procedures. Current role: {user.role}.
              </div>
            ) : (
              <form onSubmit={handleExecuteProcedure} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Model Name</label>
                    <input
                      type="text"
                      value={procModel}
                      onChange={(e) => setProcModel(e.target.value)}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Graph Variant</label>
                    <input
                      type="text"
                      value={procVariant}
                      onChange={(e) => setProcVariant(e.target.value)}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Seed</label>
                    <input
                      type="number"
                      value={procSeed}
                      onChange={(e) => setProcSeed(parseInt(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">AUC</label>
                    <input
                      type="number"
                      step="0.001"
                      value={procAuc}
                      onChange={(e) => setProcAuc(parseFloat(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">F1-Macro</label>
                    <input
                      type="number"
                      step="0.001"
                      value={procF1}
                      onChange={(e) => setProcF1(parseFloat(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow hover:bg-indigo-500"
                >
                  CALL sp_record_experiment_run(...)
                </button>
              </form>
            )}
          </div>
        )}

        {/* TAB 4: AUDIT LOGS (BONUS) */}
        {activeTab === 'audit' && user.role === 'ADMIN' && (
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <h2 className="text-base font-bold text-white mb-1">
                🛡️ Audit Logging Engine (Industry Best Practice Bonus)
              </h2>
              <p className="text-xs text-slate-400">
                Tracks every state-changing mutation (POST/PUT/DELETE) alongside database triggers, recording timestamps, user identity, action, and JSON payloads.
              </p>
            </div>

            <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 shadow-xl">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">User</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Method</th>
                    <th className="px-4 py-3">Endpoint</th>
                    <th className="px-4 py-3">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                  {loadingAudit ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-slate-500 font-sans">
                        Fetching audit records...
                      </td>
                    </tr>
                  ) : auditLogs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-slate-500 font-sans">
                        No audit logs recorded yet.
                      </td>
                    </tr>
                  ) : (
                    auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-800/40">
                        <td className="px-4 py-3 text-slate-400">#{log.id}</td>
                        <td className="px-4 py-3 text-slate-400 font-sans">
                          {new Date(log.timestamp).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 font-semibold text-indigo-400 font-sans">
                          {log.user ? log.user.username : 'System/Trigger'}
                        </td>
                        <td className="px-4 py-3 text-emerald-400 font-bold">{log.action}</td>
                        <td className="px-4 py-3 text-amber-300">{log.method}</td>
                        <td className="px-4 py-3 text-slate-300">{log.endpoint}</td>
                        <td className="px-4 py-3 text-slate-400 max-w-xs truncate" title={log.details}>
                          {log.details || '-'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* CRUD MODAL FOR CREATE / EDIT RUN */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-4">
              {editingRunId ? `Edit Experiment Run #${editingRunId}` : 'Create New Experiment Run'}
            </h3>
            <form onSubmit={handleSaveRun} className="space-y-4">
              {!editingRunId && (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">ML Model</label>
                    <select
                      value={formModelId}
                      onChange={(e) => setFormModelId(parseInt(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                    >
                      {models.map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Graph Variant</label>
                    <select
                      value={formVariantId}
                      onChange={(e) => setFormVariantId(parseInt(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                    >
                      {variants.map(v => (
                        <option key={v.id} value={v.id}>{v.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Seed</label>
                    <input
                      type="number"
                      required
                      value={formSeed}
                      onChange={(e) => setFormSeed(parseInt(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                    />
                  </div>
                </>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">AUC</label>
                  <input
                    type="number"
                    step="0.001"
                    required
                    value={formAuc}
                    onChange={(e) => setFormAuc(parseFloat(e.target.value))}
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">F1-Macro</label>
                  <input
                    type="number"
                    step="0.001"
                    required
                    value={formF1}
                    onChange={(e) => setFormF1(parseFloat(e.target.value))}
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Precision</label>
                  <input
                    type="number"
                    step="0.001"
                    required
                    value={formPrecision}
                    onChange={(e) => setFormPrecision(parseFloat(e.target.value))}
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Recall</label>
                  <input
                    type="number"
                    step="0.001"
                    required
                    value={formRecall}
                    onChange={(e) => setFormRecall(parseFloat(e.target.value))}
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Time (s)</label>
                  <input
                    type="number"
                    step="0.1"
                    required
                    value={formTime}
                    onChange={(e) => setFormTime(parseFloat(e.target.value))}
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                  />
                </div>
              </div>

              <div className="mt-6 flex justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
                >
                  {editingRunId ? 'Update Run' : 'Create Run'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
