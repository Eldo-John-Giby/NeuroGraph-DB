"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../components/AppShell";
import { useRequireAuth } from "../hooks/useRequireAuth";
import { apiRequest, getErrorMessage } from "../lib/api";
import { Pagination } from "../components/ui";

type Model = {
  model_version_id: number;
  version_key: string;
  architecture_version: string;
  lifecycle_status: string;
  supported_inference_mode: string;
  checkpoint_sha256: string | null;
  preprocessing_version_id: number;
  recommended_threshold: number | null;
  provenance: string;
};
type Preprocessor = {
  preprocessing_version_id: number;
  version_key: string;
  preprocessing_sha256: string;
  lifecycle_status: string;
};
type Runtime = {
  available: boolean;
  reproduction_verified?: boolean;
  details?: string;
  run_id?: string;
  manifest_sha256?: string;
  threshold?: number;
};
type Run = {
  inference_run_id: number;
  run_key: string;
  status: string;
  requested_count: number;
  completed_count: number;
  threshold: number;
  created_at: string;
  model: { version_key: string };
  graph_snapshot: { snapshot_key: string };
};

export default function ModelRegistryPage() {
  const { isLoading, isAuthenticated, isAdmin } = useRequireAuth(true);
  const [models, setModels] = useState<Model[]>([]);
  const [preprocessors, setPreprocessors] = useState<Preprocessor[]>([]);
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [offset, setOffset] = useState(0),
    [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [m, p, r, execution] = await Promise.all([
        apiRequest<{ items: Model[] }>("/api/v1/model-versions"),
        apiRequest<{ items: Preprocessor[] }>("/api/v1/preprocessing-versions"),
        apiRequest<Runtime>("/api/v1/verified-inductive/status"),
        apiRequest<{ items: Run[]; total: number }>(
          `/api/v1/inference-runs?limit=10&offset=${offset}`,
        ),
      ]);
      setModels(m.items);
      setPreprocessors(p.items);
      setRuntime(r);
      setRuns(execution.items);
      setTotal(execution.total);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [offset]);
  useEffect(() => {
    if (isAuthenticated && isAdmin) void load();
  }, [isAuthenticated, isAdmin, load]);
  if (isLoading || !isAuthenticated || !isAdmin)
    return (
      <div className="session-loading">Checking administrator access…</div>
    );
  return (
    <AppShell>
      <div className="compact-admin">
        <header className="page-heading">
          <div>
            <p className="eyebrow">Administration / model provenance</p>
            <h1>Model registry</h1>
            <p className="page-subtitle">
              Registered models and scoring history.
            </p>
          </div>
          <button
            className="button-secondary"
            disabled={loading}
            onClick={load}
          >
            Refresh registry
          </button>
        </header>
        <div className="registry-page-actions">
          <span className="subtle-tag">Read-only registry</span>
          <Link className="text-action" href="/benchmarks">
            Compare model performance →
          </Link>
        </div>
        {loading && (
          <p className="notice-card" role="status">
            Checking the current upload runtime and registry…
          </p>
        )}
        {error && (
          <p className="notice-card notice-error" role="alert">
            {error}
          </p>
        )}
        {!loading && !error && (
          <>
            <section className="panel registry-runtime">
              <div className="runtime-overview">
                <div>
                  <p className="eyebrow">CSV scoring model</p>
                  <h2>NeuroGraph</h2>
                  <p>RoBERTa + relational GNN</p>
                </div>
                <div className="runtime-facts">
                  <span
                    className={
                      runtime?.available ? "decision-clear" : "decision-error"
                    }
                  >
                    {runtime?.available ? "Available" : "Unavailable"}
                  </span>
                  <span>
                    <small>Decision cutoff</small>
                    <strong>
                      {runtime?.threshold == null
                        ? "—"
                        : runtime.threshold.toFixed(4)}
                    </strong>
                  </span>
                  <span>
                    <small>Artifact check</small>
                    <strong>
                      {runtime?.reproduction_verified
                        ? "Verified"
                        : "Unverified"}
                    </strong>
                  </span>
                </div>
              </div>
              {!runtime?.available && (
                <p role="status">
                  {runtime?.details || "Runtime unavailable."}
                </p>
              )}
              <details>
                <summary>Runtime identity</summary>
                <dl className="identity-list">
                  <dt>Training run</dt>
                  <dd>{runtime?.run_id || "Unavailable"}</dd>
                  <dt>Manifest SHA-256</dt>
                  <dd>{runtime?.manifest_sha256 || "Unavailable"}</dd>
                </dl>
              </details>
            </section>
            <section className="registry-section">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Registered checkpoints</p>
                  <h2>Registered models</h2>
                </div>
                <span>{models.length} records</span>
              </div>
              <div className="registry-grid">
                {models.map((model) => (
                  <article className="panel" key={model.model_version_id}>
                    <p className="eyebrow">
                      Model #{model.model_version_id} ·{" "}
                      {model.provenance === "synthetic_demo"
                        ? "Synthetic fixture"
                        : model.provenance}
                    </p>
                    <h3>
                      {model.supported_inference_mode === "inductive_batch_v1"
                        ? "NeuroGraph · CSV analysis"
                        : "Multimodal · historical benchmark"}
                    </h3>
                    <p>
                      {model.supported_inference_mode === "inductive_batch_v1"
                        ? "New review uploads"
                        : "Prepared graph nodes only"}
                    </p>
                    <dl className="identity-list">
                      <dt>Status</dt>
                      <dd>
                        <span
                          className={
                            model.lifecycle_status === "verified"
                              ? "decision-clear"
                              : "decision-pending"
                          }
                        >
                          {model.lifecycle_status}
                        </span>
                      </dd>
                      <dt>Cutoff</dt>
                      <dd>
                        {model.recommended_threshold == null
                          ? "Not recorded"
                          : model.recommended_threshold.toFixed(7)}
                      </dd>
                      <dt>Preprocessor</dt>
                      <dd>#{model.preprocessing_version_id}</dd>
                    </dl>
                    <details>
                      <summary>Version details</summary>
                      <dl className="identity-list">
                        <dt>Version key</dt>
                        <dd>{model.version_key}</dd>
                        <dt>Architecture</dt>
                        <dd>{model.architecture_version}</dd>
                        <dt>Checkpoint SHA-256</dt>
                        <dd>{model.checkpoint_sha256 || "Not recorded"}</dd>
                      </dl>
                    </details>
                  </article>
                ))}
              </div>
              {!models.length && (
                <p className="notice-card">No models registered.</p>
              )}
            </section>
            <section className="panel registry-section">
              <h2>Scoring history</h2>
              <p className="registry-section-note">
                Saved scoring jobs ·{" "}
                <Link href="/products" className="text-action">
                  Open analysis library →
                </Link>
              </p>
              <div className="table-scroll">
                <table className="evidence-table">
                  <caption>Recorded inference jobs across the registry</caption>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Model</th>
                      <th>State</th>
                      <th>Completed / requested</th>
                      <th>Cutoff used</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.inference_run_id}>
                        <td>
                          <details>
                            <summary>#{run.inference_run_id}</summary>
                            <p className="registry-key">{run.run_key}</p>
                            <p className="registry-key">
                              Context: {run.graph_snapshot.snapshot_key}
                            </p>
                          </details>
                        </td>
                        <td className="registry-key">
                          {run.model.version_key}
                        </td>
                        <td>{run.status}</td>
                        <td>
                          {run.completed_count} / {run.requested_count}
                        </td>
                        <td>{run.threshold.toFixed(7)}</td>
                        <td>{new Date(run.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!runs.length && <p>No scoring jobs recorded.</p>}
              <Pagination
                total={total}
                offset={offset}
                limit={10}
                onPageChange={setOffset}
              />
            </section>
            <details className="panel registry-section">
              <summary>Preprocessing versions</summary>
              <p>Preparation rules linked to each registered model.</p>
              {preprocessors.map((prep) => (
                <article key={prep.preprocessing_version_id}>
                  <h3 className="registry-key">
                    #{prep.preprocessing_version_id} · {prep.version_key}
                  </h3>
                  <p>{prep.lifecycle_status}</p>
                  <p className="registry-key">
                    SHA-256: {prep.preprocessing_sha256}
                  </p>
                </article>
              ))}
            </details>
          </>
        )}
      </div>
    </AppShell>
  );
}
