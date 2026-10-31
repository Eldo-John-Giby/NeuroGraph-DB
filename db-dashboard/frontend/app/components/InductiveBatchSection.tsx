"use client";

import React, {
  useEffect,
  useState,
  useCallback,
  useMemo,
  useRef,
} from "react";
import Link from "next/link";
import {
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileWarning,
} from "lucide-react";
import { apiRequest, getErrorMessage } from "../lib/api";
import {
  resultSummary,
  selectResultRows,
  resultsCsv,
  relationGateLabel,
} from "../lib/result-helpers";
import { BatchRelationshipGraph } from "./BatchRelationshipGraph";

export interface BatchAnalysisSummary {
  batch_analysis_id: number;
  batch_key: string;
  source_system?: string;
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
    decision: "flagged" | "cleared";
    attention_weights: {
      rur?: number;
      rsr?: number;
      rtr?: number;
    };
    graph_status: string;
    evidence: PredictionEvidence | null;
  } | null;
}

export function InductiveBatchSection({
  initialBatchId,
  showHeading = true,
  refreshKey,
}: {
  initialBatchId?: number;
  showHeading?: boolean;
  refreshKey?: string;
}) {
  const [batches, setBatches] = useState<BatchAnalysisSummary[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(
    initialBatchId ?? null,
  );
  const [currentBatch, setCurrentBatch] = useState<BatchAnalysisSummary | null>(
    null,
  );
  const [results, setResults] = useState<BatchRowResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [scoring, setScoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRow, setSelectedRow] = useState<BatchRowResult | null>(null);
  const [query, setQuery] = useState(""),
    [decision, setDecision] = useState("all");
  const [order, setOrder] = useState("score"),
    [page, setPage] = useState(0);
  const [modelVersions, setModelVersions] = useState<
    Array<{ version_key: string; supported_inference_mode: string }>
  >([]);
  const [snapshot, setSnapshot] = useState<{
    graph_snapshot_id: number;
    snapshot_key: string;
    node_count: number;
  } | null>(null);
  const requestGeneration = useRef(0);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (selectedRow && dialog.current) dialog.current.showModal();
  }, [selectedRow]);
  useEffect(() => {
    setPage(0);
  }, [query, decision, order, selectedBatchId]);
  useEffect(() => {
    void apiRequest<{
      items: Array<{ version_key: string; supported_inference_mode: string }>;
    }>("/api/v1/model-versions")
      .then((d) => setModelVersions(d.items))
      .catch(() => setModelVersions([]));
  }, []);
  useEffect(() => {
    setSnapshot(null);
    const id = currentBatch?.historic_graph_snapshot_id;
    if (!id) return;
    let active = true;
    void apiRequest<{
      graph_snapshot_id: number;
      snapshot_key: string;
      node_count: number;
    }>(`/api/v1/graph-snapshots/${id}`)
      .then((d) => {
        if (active) setSnapshot(d);
      })
      .catch(() => {
        if (active) setSnapshot(null);
      });
    return () => {
      active = false;
    };
  }, [currentBatch?.historic_graph_snapshot_id]);

  const fetchBatches = useCallback(async () => {
    if (initialBatchId) return;
    try {
      const data = await apiRequest<{ items: BatchAnalysisSummary[] }>(
        "/api/v1/batch-analyses?limit=20",
      );
      const list = data.items || [];
      setBatches(list);
      if (list.length > 0 && selectedBatchId === null) {
        const saved = list.find((batch) => batch.accepted_count > 0);
        setSelectedBatchId((saved || list[0]).batch_analysis_id);
      }
    } catch (err) {
      setError(getErrorMessage(err));
      setLoading(false);
    }
  }, [selectedBatchId, initialBatchId]);

  const fetchBatchDetails = useCallback(async (batchId: number) => {
    const generation = ++requestGeneration.current;
    setLoading(true);
    setError(null);
    try {
      const [batchData, resultsData] = await Promise.all([
        apiRequest<BatchAnalysisSummary>(`/api/v1/batch-analyses/${batchId}`),
        apiRequest<{ items: BatchRowResult[]; total: number }>(
          `/api/v1/batch-analyses/${batchId}/results?limit=100`,
        ),
      ]);
      const allRows = [...(resultsData.items || [])];
      for (let offset = 100; offset < resultsData.total; offset += 100) {
        const page = await apiRequest<{ items: BatchRowResult[] }>(
          `/api/v1/batch-analyses/${batchId}/results?limit=100&offset=${offset}`,
        );
        allRows.push(...page.items);
      }
      if (generation !== requestGeneration.current) return;
      setCurrentBatch(batchData);
      setResults(allRows);
    } catch (err) {
      if (generation !== requestGeneration.current) return;
      setError(getErrorMessage(err));
      setCurrentBatch(null);
      setResults([]);
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
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
  }, [selectedBatchId, fetchBatchDetails, refreshKey]);

  useEffect(() => {
    if (
      !["queued", "running"].includes(currentBatch?.status || "") ||
      selectedBatchId === null
    )
      return;
    const timer = setInterval(() => {
      void fetchBatchDetails(selectedBatchId);
    }, 5000);
    return () => clearInterval(timer);
  }, [currentBatch?.status, selectedBatchId, fetchBatchDetails]);

  const handleScoreBatch = async () => {
    if (!selectedBatchId) return;
    setScoring(true);
    setError(null);
    try {
      await apiRequest<BatchAnalysisSummary>(
        `/api/v1/batch-analyses/${selectedBatchId}/score`,
        {
          method: "POST",
        },
      );
      await fetchBatchDetails(selectedBatchId);
      await fetchBatches();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setScoring(false);
    }
  };

  const stats = useMemo(() => resultSummary(results), [results]);
  const filteredRows = useMemo(
    () => selectResultRows(results, query, decision, order),
    [results, query, decision, order],
  );
  const visibleRows = filteredRows.slice(page * 25, (page + 1) * 25);
  const threshold = currentBatch?.inference_run?.threshold ?? null;
  const evidence = results.find((row) => row.prediction?.evidence)?.prediction
    ?.evidence;
  const modelName = modelVersions.find(
    (model) => model.supported_inference_mode === "inductive_batch_v1",
  )?.version_key;
  const exportResults = () => {
    if (!currentBatch) return;
    const url = URL.createObjectURL(
      new Blob(
        [resultsCsv(results, currentBatch.batch_analysis_id, threshold)],
        { type: "text/csv;charset=utf-8" },
      ),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `neurograph-batch-${currentBatch.batch_analysis_id}-results.csv`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <div className="analysis-results">
      {showHeading && (
        <div className="analysis-toolbar">
          <label>
            Saved CSV analysis
            <select
              value={selectedBatchId ?? ""}
              onChange={(e) => setSelectedBatchId(Number(e.target.value))}
            >
              <option value="" disabled>
                Select an upload
              </option>
              {batches.map((batch) => (
                <option
                  key={batch.batch_analysis_id}
                  value={batch.batch_analysis_id}
                >
                  Batch #{batch.batch_analysis_id} · {batch.row_count} rows ·{" "}
                  {batch.status}
                </option>
              ))}
            </select>
          </label>
          <button
            className="button-secondary"
            disabled={loading || scoring}
            onClick={() => {
              if (selectedBatchId) void fetchBatchDetails(selectedBatchId);
              void fetchBatches();
            }}
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      )}
      {loading && (
        <p className="notice-card" role="status">
          Loading saved results…
        </p>
      )}
      {!loading && error && (
        <p className="notice-card notice-error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && !currentBatch && (
        <p className="notice-card">
          No saved analysis yet.{" "}
          <Link href="/reviews/submit" className="text-action">
            Upload a CSV →
          </Link>
        </p>
      )}
      {!loading && !error && currentBatch && (
        <>
          <section
            className="panel result-takeaway"
            aria-label="Analysis summary"
          >
            <div className="result-summary-heading">
              <div>
                <p className="eyebrow">Saved results</p>
                <h2>Analysis summary</h2>
              </div>
              <span className="result-sample-count">
                {stats.scored} / {currentBatch.row_count} scored
              </span>
            </div>
            <div className="result-kpi-grid">
              {[
                {
                  label: "Flagged",
                  count: stats.flagged,
                  tone: "flagged",
                  filter: "flagged",
                  Icon: AlertTriangle,
                },
                {
                  label: "Not flagged",
                  count: stats.notFlagged,
                  tone: "clear",
                  filter: "cleared",
                  Icon: CheckCircle2,
                },
                {
                  label: "Unscored",
                  count: stats.unscored,
                  tone: "pending",
                  filter: "unscored",
                  Icon: Clock3,
                },
                {
                  label: "Import errors",
                  count: stats.rejected,
                  tone: "error",
                  filter: "rejected",
                  Icon: FileWarning,
                },
              ].map(({ label, count, tone, filter, Icon }) => (
                <button
                  type="button"
                  className={`result-kpi result-kpi-${tone}`}
                  key={filter}
                  onClick={() => {
                    setDecision(filter);
                    document
                      .getElementById("saved-review-list")
                      ?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }}
                  aria-label={`Show ${count} ${label.toLowerCase()} reviews`}
                >
                  <span>
                    <Icon size={17} aria-hidden="true" />
                    {label}
                  </span>
                  <strong>{count}</strong>
                </button>
              ))}
            </div>
            {stats.scored > 0 && (
              <div
                className="result-split-bar"
                role="img"
                aria-label={`${stats.flagged} flagged and ${stats.notFlagged} not flagged out of ${stats.scored} scored`}
              >
                <span
                  className="split-flagged"
                  style={{ width: `${(stats.flagged / stats.scored) * 100}%` }}
                />
                <span
                  className="split-clear"
                  style={{
                    width: `${(stats.notFlagged / stats.scored) * 100}%`,
                  }}
                />
              </div>
            )}
            <div className="result-summary-footer">
              <p>
                Flags need human review. Scores are model signals, not proof of
                fraud. If fake reviews are rare in your file, a larger share of
                flags may be false positives. Accuracy on your file is unknown
                without independent labels.
              </p>
              <span>
                Cutoff{" "}
                <strong>
                  {threshold == null ? "Not assigned" : threshold.toFixed(4)}
                </strong>
              </span>
            </div>
          </section>
          {["running", "queued"].includes(currentBatch.status) && (
            <div className="notice-card" role="status">
              <strong>Analysis {currentBatch.status}</strong>
              <p>
                This page checks for saved results automatically. You can reopen
                it from Products &amp; history.
              </p>
              {currentBatch.status === "queued" && (
                <button
                  className="button-secondary"
                  disabled={scoring}
                  onClick={handleScoreBatch}
                >
                  {scoring ? "Processing…" : "Process now"}
                </button>
              )}
            </div>
          )}
          {["failed", "blocked"].includes(currentBatch.status) && (
            <div className="notice-card notice-error" role="alert">
              <strong>Analysis {currentBatch.status}</strong>
              <p>
                {currentBatch.job?.last_error ||
                  currentBatch.blocking_reasons.join(", ") ||
                  "Scoring could not finish."}
              </p>
              {currentBatch.status === "failed" &&
                currentBatch.accepted_count > 0 && (
                  <button
                    className="button-secondary"
                    disabled={scoring}
                    onClick={handleScoreBatch}
                  >
                    {scoring ? "Retrying…" : "Retry analysis"}
                  </button>
                )}
            </div>
          )}
          {stats.rejected > 0 && (
            <div className="notice-card notice-error">
              <strong>{stats.rejected} rows were rejected during import</strong>
              <p>
                Rejected rows have no prediction. Filter the list to “Import
                errors” to see what needs correcting.
              </p>
              <button
                className="text-action"
                onClick={() => setDecision("rejected")}
              >
                Show import errors →
              </button>
            </div>
          )}
          <details className="panel result-method">
            <summary>Method & run details</summary>
            <div className="result-method-grid">
              {currentBatch.source_system?.endsWith("-limited-authors") && (
                <article>
                  <h3>Limited author IDs</h3>
                  <p>
                    Unidentified authors were imported with separate local
                    identities. Same-author connections cannot be inferred for
                    those reviews.
                  </p>
                </article>
              )}
              <article>
                <h3>Decision cutoff</h3>
                <p>
                  {threshold == null
                    ? "No run cutoff recorded yet."
                    : `The saved cutoff is ${threshold.toFixed(7)}. A score at or above it is flagged for human review; a lower score is not flagged.`}{" "}
                  The model’s recommended cutoff was selected on validation
                  data, not adjusted to make your file look better.
                </p>
              </article>
              <article>
                <h3>Historical context</h3>
                <p>
                  {currentBatch.historic_graph_snapshot_id
                    ? `Snapshot #${currentBatch.historic_graph_snapshot_id}`
                    : "No snapshot selected"}
                  {snapshot
                    ? ` · ${snapshot.node_count.toLocaleString()} stored review nodes`
                    : ""}
                  . This is the available reference graph, not the number of
                  neighbors used for every row. Uploaded author and product
                  identities are separate from the Yelp reference data, so
                  ordinary uploads use connections and prior counts within that
                  file, not Yelp author or product history. The snapshot checks
                  model compatibility; its stored node count does not imply
                  historical neighbors were used.
                </p>
              </article>
              <article>
                <h3>Relationship types</h3>
                <p>
                  Same author (RUR); same product and star rating (RSR); same
                  product within 30 days (RTR). These links can also occur
                  naturally. Counts and attention weights do not prove
                  manipulation.
                </p>
              </article>
            </div>
            <details>
              <summary>Recorded model and file fingerprints</summary>
              <dl className="identity-list">
                <dt>Model family</dt>
                <dd>{modelName || "Not available from registry"}</dd>
                <dt>Scoring run</dt>
                <dd>{currentBatch.inference_run?.run_key || "Not assigned"}</dd>
                <dt>Snapshot key</dt>
                <dd>{snapshot?.snapshot_key || "Not available"}</dd>
                <dt>Relation policy</dt>
                <dd>
                  {evidence?.relation_schema_version || "No saved evidence yet"}
                </dd>
                <dt>Scored bundle manifest</dt>
                <dd>
                  {evidence?.bundle_manifest_sha256 || "No saved evidence yet"}
                </dd>
                <dt>Uploaded file SHA-256</dt>
                <dd>{currentBatch.upload_sha256}</dd>
              </dl>
              <p>
                Fingerprints identify the saved inputs and model files. They do
                not establish prediction correctness. The model family above is
                the registry’s inductive entry; the saved bundle fingerprint is
                the identity recorded for this analysis.
              </p>
            </details>
          </details>
          <section className="panel" id="saved-review-list">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Saved row-level decisions</p>
                <h2>Reviews</h2>
              </div>
              <button
                className="button-secondary"
                disabled={!results.length}
                onClick={exportResults}
              >
                Export results
              </button>
            </div>
            <div className="analysis-toolbar">
              <label>
                Search reviews
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Review, author or product ID"
                />
              </label>
              <label>
                Show
                <select
                  value={decision}
                  onChange={(e) => setDecision(e.target.value)}
                >
                  <option value="all">All rows</option>
                  <option value="flagged">Flagged</option>
                  <option value="cleared">Not flagged</option>
                  <option value="rejected">Import errors</option>
                  <option value="unscored">Accepted, unscored</option>
                </select>
              </label>
              <label>
                Order
                <select
                  value={order}
                  onChange={(e) => setOrder(e.target.value)}
                >
                  <option value="score">Highest score first</option>
                  <option value="row">Original CSV row</option>
                </select>
              </label>
            </div>
            <div className="table-scroll">
              <table className="evidence-table result-table">
                <caption>
                  {filteredRows.length} matching rows · {results.length} total
                  saved row outcomes
                </caption>
                <thead>
                  <tr>
                    <th>Review / CSV row</th>
                    <th>Review text</th>
                    <th>Risk score</th>
                    <th>Decision</th>
                    <th>Inspect</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row) => (
                    <tr
                      key={row.row_number}
                      className={
                        row.prediction?.decision === "flagged"
                          ? "result-row-flagged"
                          : ""
                      }
                    >
                      <td>
                        <strong className="registry-key">
                          {row.uploaded_review_key || "No source ID"}
                        </strong>
                        <small>
                          CSV row {row.row_number}
                          {row.review
                            ? ` · internal review #${row.review.review_id}`
                            : ""}
                        </small>
                        <small>
                          {row.review?.rating == null
                            ? ""
                            : `${row.review.rating}/5 stars`}
                          {row.review?.reviewed_at
                            ? ` · ${new Date(row.review.reviewed_at).toLocaleDateString()}`
                            : ""}
                        </small>
                      </td>
                      <td>
                        <p className="review-excerpt">
                          {row.review?.review_text ||
                            row.validation_errors
                              .map((e) => e.message || e.code)
                              .join("; ") ||
                            "No review text stored"}
                        </p>
                      </td>
                      <td>
                        <div
                          className={`result-score ${row.prediction?.decision === "flagged" ? "score-flagged" : row.prediction ? "score-clear" : ""}`}
                        >
                          <strong>
                            {row.prediction
                              ? row.prediction.risk_score.toFixed(4)
                              : "—"}
                          </strong>
                          {row.prediction && (
                            <span className="score-track" aria-hidden="true">
                              <span
                                style={{
                                  width: `${Math.min(1, Math.max(0, row.prediction.risk_score)) * 100}%`,
                                }}
                              />
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <span
                          className={
                            row.prediction?.decision === "flagged"
                              ? "decision-flagged"
                              : row.prediction
                                ? "decision-clear"
                                : row.row_state === "rejected"
                                  ? "decision-error"
                                  : "decision-pending"
                          }
                        >
                          {row.prediction
                            ? row.prediction.decision === "flagged"
                              ? "Flagged"
                              : "Not flagged"
                            : row.row_state === "rejected"
                              ? "Import error"
                              : "Not scored"}
                        </span>
                      </td>
                      <td>
                        <button
                          className="text-action"
                          onClick={() => setSelectedRow(row)}
                          aria-label={`Open review ${row.uploaded_review_key || `CSV row ${row.row_number}`}`}
                        >
                          Open review →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!filteredRows.length && (
              <p>
                No rows match these filters.{" "}
                <button
                  className="text-action"
                  onClick={() => {
                    setQuery("");
                    setDecision("all");
                  }}
                >
                  Show all rows
                </button>
              </p>
            )}
            <div className="analysis-pagination">
              <button
                className="button-secondary"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous reviews
              </button>
              <span>
                {filteredRows.length ? page * 25 + 1 : 0}–
                {Math.min((page + 1) * 25, filteredRows.length)} of{" "}
                {filteredRows.length}
              </span>
              <button
                className="button-secondary"
                disabled={(page + 1) * 25 >= filteredRows.length}
                onClick={() => setPage((p) => p + 1)}
              >
                Next reviews
              </button>
            </div>
          </section>
          {currentBatch.status === "completed" && (
            <BatchRelationshipGraph
              key={currentBatch.batch_analysis_id}
              batchId={currentBatch.batch_analysis_id}
            />
          )}
          {selectedRow && (
            <dialog
              ref={dialog}
              className="review-dialog"
              aria-labelledby="review-detail-title"
              onCancel={() => setSelectedRow(null)}
              onClose={() => setSelectedRow(null)}
            >
              <header>
                <div>
                  <p className="eyebrow">CSV row {selectedRow.row_number}</p>
                  <h2 id="review-detail-title">
                    {selectedRow.uploaded_review_key || "Review details"}
                  </h2>
                </div>
                <button
                  autoFocus
                  className="button-secondary"
                  onClick={() => {
                    dialog.current?.close();
                    setSelectedRow(null);
                  }}
                >
                  Close review
                </button>
              </header>
              <div className="review-dialog-body">
                <p>
                  <strong>
                    {selectedRow.prediction
                      ? selectedRow.prediction.decision === "flagged"
                        ? "Flagged for human review"
                        : "Not flagged by this model run"
                      : "No model prediction"}
                  </strong>
                  {selectedRow.prediction
                    ? ` · score ${selectedRow.prediction.risk_score.toFixed(4)}`
                    : ""}
                  {threshold != null
                    ? ` · run cutoff ${threshold.toFixed(7)}`
                    : ""}
                </p>
                <p className="review-detail-note">
                  Model decision · verify against the review and its context.
                </p>
                <h3>Full review text</h3>
                <p className="full-review-text">
                  {selectedRow.review?.review_text ||
                    "No accepted text stored for this row."}
                </p>
                {selectedRow.validation_errors.length > 0 && (
                  <p className="notice-error">
                    {selectedRow.validation_errors
                      .map((e) => e.message || e.code)
                      .join("; ")}
                  </p>
                )}
                {selectedRow.review && (
                  <>
                    <p>
                      Internal review #{selectedRow.review.review_id} · author #
                      {selectedRow.review.reviewer_id ?? "unrecorded"} · product
                      #{selectedRow.review.product_id ?? "unrecorded"}
                    </p>
                    <div className="review-actions">
                      <Link
                        className="button-primary"
                        href={`/feedback?review_id=${selectedRow.review.review_id}&batch_id=${currentBatch.batch_analysis_id}`}
                      >
                        Add feedback
                      </Link>
                      {selectedRow.review.reviewer_id && (
                        <Link
                          className="button-secondary"
                          href={`/reviews?reviewer_id=${selectedRow.review.reviewer_id}`}
                        >
                          Author’s reviews
                        </Link>
                      )}
                    </div>
                  </>
                )}
                {selectedRow.prediction?.evidence ? (
                  <>
                    <h3>Saved relationship context</h3>
                    <p>
                      Same author:{" "}
                      {selectedRow.prediction.evidence.neighbor_counts.rur ?? 0}{" "}
                      · Same product/rating:{" "}
                      {selectedRow.prediction.evidence.neighbor_counts.rsr ?? 0}{" "}
                      · Same product within 30 days:{" "}
                      {selectedRow.prediction.evidence.neighbor_counts.rtr ?? 0}
                      . A zero means no eligible direct connections of that type
                      were saved; the model still uses text and numeric
                      features.
                    </p>
                    <p>
                      Context cutoff:{" "}
                      {selectedRow.prediction.evidence.context_cutoff_at
                        ? new Date(
                            selectedRow.prediction.evidence.context_cutoff_at,
                          ).toLocaleString()
                        : "Not recorded"}
                    </p>
                    {selectedRow.prediction.attention_weights && (
                      <p>
                        Model relation gate: same author —{" "}
                        {relationGateLabel(selectedRow.prediction.attention_weights.rur, selectedRow.prediction.evidence.neighbor_counts.rur)}
                        ; same product/rating —{" "}
                        {relationGateLabel(selectedRow.prediction.attention_weights.rsr, selectedRow.prediction.evidence.neighbor_counts.rsr)}
                        ; timing —{" "}
                        {relationGateLabel(selectedRow.prediction.attention_weights.rtr, selectedRow.prediction.evidence.neighbor_counts.rtr)}
                        . Percentages describe the model’s three-way relation
                        gate, not individual neighbors. Empty relations are
                        hidden without renormalizing the remaining weights.
                        These are not fraud probabilities or causal explanations.
                      </p>
                    )}
                    <details>
                      <summary>
                        Connected review IDs and integrity fingerprints
                      </summary>
                      <p className="registry-key">
                        Connected historical IDs:{" "}
                        {selectedRow.prediction.evidence.historic_review_ids.join(
                          ", ",
                        ) || "None recorded"}
                      </p>
                      <dl className="identity-list">
                        {Object.entries(selectedRow.prediction.evidence)
                          .filter(([key]) => key.endsWith("sha256"))
                          .map(([key, value]) => (
                            <React.Fragment key={key}>
                              <dt>{key.replaceAll("_", " ")}</dt>
                              <dd>{String(value)}</dd>
                            </React.Fragment>
                          ))}
                      </dl>
                    </details>
                  </>
                ) : (
                  <p>No graph evidence is saved for this row.</p>
                )}
              </div>
            </dialog>
          )}
        </>
      )}
    </div>
  );
}
