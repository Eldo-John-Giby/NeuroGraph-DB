"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { InductiveBatchSection } from "../../components/InductiveBatchSection";
import { SavedAnalysis, analysisName } from "../../components/AnalysisCard";
import { useRequireAuth } from "../../hooks/useRequireAuth";
import { apiRequest, getErrorMessage } from "../../lib/api";

export default function SavedAnalysisPage() {
  const params = useParams<{ batchId: string }>();
  const id = Number(params.batchId);
  const { isLoading, isAuthenticated } = useRequireAuth();
  const [batch, setBatch] = useState<SavedAnalysis | null>(null),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!isAuthenticated) return;
    if (!Number.isSafeInteger(id) || id < 1) {
      setError("This analysis link is invalid.");
      return;
    }
    setError("");
    apiRequest<SavedAnalysis>(`/api/v1/batch-analyses/${id}`)
      .then(setBatch)
      .catch((e) => setError(getErrorMessage(e)));
  }, [isAuthenticated, id, revision]);
  if (isLoading || !isAuthenticated)
    return <div className="session-loading">Loading saved analysis…</div>;
  return (
    <AppShell>
      <Link href="/products" className="back-link">
        ← Your analysis library
      </Link>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Saved analysis / Batch #{id}</p>
          <h1 className="filename-heading">
            {batch ? analysisName(batch) : "Saved results"}
          </h1>
          <p className="page-subtitle">
            {batch
              ? `Uploaded ${new Date(batch.created_at).toLocaleString()} · ${batch.row_count} rows · ${batch.status.replaceAll("_", " ")}`
              : "Retrieving your saved analysis."}
          </p>
        </div>
        <button
          className="button-secondary"
          onClick={() => setRevision((r) => r + 1)}
        >
          Refresh results
        </button>
      </header>
      {error ? (
        <div className="notice-card notice-error" role="alert">
          {error}
        </div>
      ) : batch ? (
        <>
          <InductiveBatchSection
            key={id}
            initialBatchId={id}
            showHeading={false}
            refreshKey={String(revision)}
          />
        </>
      ) : (
        <p className="notice-card">Loading the saved result…</p>
      )}
    </AppShell>
  );
}
