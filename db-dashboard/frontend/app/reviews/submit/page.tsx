"use client";
import {
  ChangeEvent,
  DragEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  CheckCircle2,
  FileSpreadsheet,
  UploadCloud,
  ChevronRight,
} from "lucide-react";
import AppShell from "../../components/AppShell";
import { useRequireAuth } from "../../hooks/useRequireAuth";
import { apiRequest, getErrorMessage } from "../../lib/api";
import {
  readReviewExport,
  normalizeReviewExport,
  importIssues,
  missingAuthorCount,
  importCell,
  IMPORT_FIELDS,
  type ReviewExport,
  type ColumnMap,
  type ImportOptions,
} from "../../lib/review-import";

type Snapshot = {
  graph_snapshot_id: number;
  snapshot_key: string;
  batch_context_permitted: boolean;
  context_scope_key: string | null;
  relation_schema_version: string;
  storage_status: string;
  provenance: string;
};
type Receipt = {
  batch_analysis_id: number;
  status: string;
  row_count: number;
  accepted_count: number;
  rejected_count: number;
};
type ImportRow = {
  row_number: number;
  validation_errors: { message?: string; code?: string }[];
};
const fieldLabels = {
  review_id: "Review ID",
  reviewer_id: "Author ID / profile URL",
  product_id: "Business / product ID",
  rating: "Rating",
  review_date: "Review date",
  review_text: "Review text",
};
const initialOptions: ImportOptions = {
  businessId: "",
  separateAuthors: false,
  dateOrder: "iso",
};
function compatible(snapshot: Snapshot) {
  return (
    snapshot.batch_context_permitted &&
    snapshot.storage_status === "available" &&
    snapshot.provenance === "real" &&
    (snapshot.context_scope_key === "inductive-rur-rsr-rtr-v1" ||
      snapshot.relation_schema_version === "inductive-rur-rsr-rtr-v1")
  );
}

export default function BatchAnalysisPage() {
  const { isLoading, isAuthenticated } = useRequireAuth();
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const fileGeneration = useRef(0);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]),
    [snapshotId, setSnapshotId] = useState<number | null>(null),
    [contextLoading, setContextLoading] = useState(true),
    [contextError, setContextError] = useState("");
  const [file, setFile] = useState<File | null>(null),
    [parsed, setParsed] = useState<ReviewExport | null>(null),
    [mapping, setMapping] = useState<ColumnMap | null>(null),
    [options, setOptions] = useState<ImportOptions>(initialOptions),
    [parsing, setParsing] = useState(false);
  const [dragging, setDragging] = useState(false),
    [phase, setPhase] = useState<"idle" | "preparing" | "saving" | "scoring">(
      "idle",
    ),
    [error, setError] = useState(""),
    [receipt, setReceipt] = useState<Receipt | null>(null),
    [rejected, setRejected] = useState<ImportRow[]>([]);
  const loadContext = useCallback(async () => {
    setContextLoading(true);
    setContextError("");
    try {
      const data = await apiRequest<{ items: Snapshot[] }>(
        "/api/v1/graph-snapshots",
      );
      const choices = data.items.filter(compatible);
      setSnapshots(choices);
      setSnapshotId(choices[0]?.graph_snapshot_id ?? null);
      if (!choices.length)
        setContextError(
          "No compatible history is available. Contact an administrator.",
        );
    } catch (e) {
      setContextError(getErrorMessage(e));
    } finally {
      setContextLoading(false);
    }
  }, []);
  useEffect(() => {
    if (isAuthenticated) void loadContext();
  }, [isAuthenticated, loadContext]);
  const selectFile = async (candidate?: File) => {
    if (!candidate || phase !== "idle") return;
    const generation = ++fileGeneration.current;
    setError("");
    setReceipt(null);
    setRejected([]);
    setFile(null);
    setParsed(null);
    setMapping(null);
    setOptions(initialOptions);
    setParsing(false);
    if (!candidate.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a CSV file.");
      return;
    }
    if (candidate.size > 8 * 1024 * 1024) {
      setError("The CSV must be no larger than 8 MiB.");
      return;
    }
    setParsing(true);
    try {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(
        await candidate.arrayBuffer(),
      );
      const data = readReviewExport(text);
      if (generation !== fileGeneration.current) return;
      setFile(candidate);
      setParsed(data);
      setMapping(data.mapping);
    } catch (e) {
      if (generation === fileGeneration.current)
        setError(
          e instanceof TypeError
            ? "Use a UTF-8 encoded CSV."
            : getErrorMessage(e),
        );
    } finally {
      if (generation === fileGeneration.current) setParsing(false);
    }
  };
  const issues = useMemo(
    () => (parsed && mapping ? importIssues(parsed, mapping, options) : []),
    [parsed, mapping, options],
  );
  const needsSetup = Boolean(parsed && !parsed.canonical);
  const unknownAuthors =
    parsed && mapping ? missingAuthorCount(parsed, mapping) : 0;
  const drop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    void selectFile(event.dataTransfer.files[0]);
  };
  const upload = async () => {
    if (
      !file ||
      !parsed ||
      !mapping ||
      issues.length ||
      !snapshotId ||
      phase !== "idle"
    )
      return;
    setPhase("preparing");
    setError("");
    setReceipt(null);
    setRejected([]);
    try {
      const csv = await normalizeReviewExport(parsed, mapping, options);
      const prepared =
        csv === parsed.original
          ? file
          : new File([csv], file.name, { type: "text/csv" });
      const limitedAuthors =
        !parsed.canonical &&
        (unknownAuthors > 0 || /(?:name|display)/i.test(mapping.reviewer_id));
      const source = `csv-${file.name.replace(/[^a-zA-Z0-9_-]/g, "-").slice(0, limitedAuthors ? 60 : 80)}${limitedAuthors ? "-limited-authors" : ""}`;
      const form = new FormData();
      form.append("file", prepared);
      form.append("source_system", source);
      form.append("historic_graph_snapshot_id", String(snapshotId));
      setPhase("saving");
      const saved = await apiRequest<Receipt>("/api/v1/batch-analyses", {
        method: "POST",
        body: form,
      });
      setReceipt(saved);
      if (!saved.accepted_count) {
        const rows = await apiRequest<{ items: ImportRow[] }>(
          `/api/v1/batch-analyses/${saved.batch_analysis_id}/results?limit=100`,
        );
        setRejected(rows.items);
        return;
      }
      if (saved.status !== "completed") {
        setPhase("scoring");
        const data = new FormData();
        data.append("historic_graph_snapshot_id", String(snapshotId));
        await apiRequest(
          `/api/v1/batch-analyses/${saved.batch_analysis_id}/score`,
          { method: "POST", body: data },
        );
      }
      router.push(`/products/${saved.batch_analysis_id}`);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setPhase("idle");
    }
  };
  if (isLoading || !isAuthenticated)
    return <div className="session-loading">Loading your workspace…</div>;
  return (
    <AppShell>
      <header className="page-heading">
        <div>
          <p className="eyebrow">New analysis</p>
          <h1>Upload reviews</h1>
          <p className="page-subtitle">
            Choose a CSV. We’ll match its columns before analysis.
          </p>
        </div>
        <Link className="button-secondary" href="/products">
          Analysis history →
        </Link>
      </header>
      <div className="upload-workflow">
        <section className="panel upload-panel">
          <div className="section-heading">
            <h2>Review file</h2>
            <FileSpreadsheet size={24} aria-hidden="true" />
          </div>
          <input
            ref={input}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            disabled={phase !== "idle"}
            onChange={(event: ChangeEvent<HTMLInputElement>) => {
              void selectFile(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <div
            role="button"
            tabIndex={0}
            aria-label="Choose review CSV"
            aria-disabled={phase !== "idle"}
            className={`dropzone ${dragging ? "dropzone-active" : ""}`}
            onClick={() => phase === "idle" && input.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                if (phase === "idle") input.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={drop}
          >
            <UploadCloud size={31} />
            <strong>
              {parsing
                ? "Reading file…"
                : file
                  ? file.name
                  : "Drop a CSV or browse files"}
            </strong>
            <small>
              {file && parsed
                ? `${parsed.rows.length.toLocaleString()} reviews · ${(file.size / 1024).toFixed(1)} KB`
                : "Up to 5,000 reviews · 8 MiB · UTF-8"}
            </small>
          </div>
          {parsed && mapping && (
            <section className="import-preview" aria-label="Import preview">
              <div className="import-preview-heading">
                <strong>{parsed.rows.length} rows detected</strong>
                <span
                  className={
                    issues.length ? "decision-pending" : "decision-clear"
                  }
                >
                  {issues.length ? "Check columns" : "Ready to import"}
                </span>
              </div>
              {needsSetup && (
                <>
                  <details open={issues.length > 0} className="import-mapping">
                    <summary>Column mapping</summary>
                    <div className="import-mapping-grid">
                      {IMPORT_FIELDS.map((field) => (
                        <label key={field}>
                          {fieldLabels[field]}
                          <select
                            value={mapping[field]}
                            disabled={phase !== "idle"}
                            onChange={(e) =>
                              setMapping({
                                ...mapping,
                                [field]: e.target.value,
                              })
                            }
                          >
                            <option value="">
                              {field === "review_id"
                                ? "Generate local IDs"
                                : field === "reviewer_id"
                                  ? "Not available"
                                  : field === "product_id"
                                    ? "Set one business below"
                                    : "Choose column"}
                            </option>
                            {parsed.headers.map((header) => (
                              <option key={header} value={header}>
                                {header}
                              </option>
                            ))}
                          </select>
                        </label>
                      ))}
                    </div>
                    <p className="import-hint">
                      Use stable author IDs or profile URLs, not names.
                    </p>
                  </details>
                  {!mapping.product_id && (
                    <label className="import-business">
                      Business / product ID
                      <input
                        maxLength={255}
                        placeholder="e.g. your Google place ID or restaurant key"
                        value={options.businessId}
                        disabled={phase !== "idle"}
                        onChange={(e) =>
                          setOptions({ ...options, businessId: e.target.value })
                        }
                      />
                      <small>
                        Applies to every review in this file. Multi-business
                        files need a business ID column.
                      </small>
                    </label>
                  )}
                  {(unknownAuthors > 0 ||
                    /(?:name|display)/i.test(mapping.reviewer_id)) && (
                    <label className="import-author-choice">
                      <input
                        type="checkbox"
                        checked={options.separateAuthors}
                        disabled={phase !== "idle"}
                        onChange={(e) =>
                          setOptions({
                            ...options,
                            separateAuthors: e.target.checked,
                          })
                        }
                      />
                      <span>
                        Import unidentified authors separately
                        <small>
                          Unidentified reviews get separate local identities;
                          same-author links won’t be inferred for them.
                        </small>
                      </span>
                    </label>
                  )}
                  <label className="import-date-order">
                    Date format
                    <select
                      value={options.dateOrder}
                      disabled={phase !== "idle"}
                      onChange={(e) =>
                        setOptions({
                          ...options,
                          dateOrder: e.target
                            .value as ImportOptions["dateOrder"],
                        })
                      }
                    >
                      <option value="iso">ISO / year first</option>
                      <option value="dmy">DD/MM/YYYY</option>
                      <option value="mdy">MM/DD/YYYY</option>
                    </select>
                  </label>
                  {!mapping.review_id && (
                    <p className="import-hint">
                      Stable local review IDs will be generated from the
                      imported content.
                    </p>
                  )}
                </>
              )}
              {issues.length > 0 && (
                <p className="import-action-needed" role="status">
                  {issues[0]}
                </p>
              )}
              <details className="import-sample">
                <summary>Preview rows</summary>
                <div className="table-scroll">
                  <table className="evidence-table">
                    <thead>
                      <tr>
                        <th>Rating</th>
                        <th>Date</th>
                        <th>Review text</th>
                      </tr>
                    </thead>
                    <tbody>
                      {parsed.rows.slice(0, 3).map((row, index) => (
                        <tr key={index}>
                          <td>
                            {importCell(parsed, row, "rating", mapping) || "—"}
                          </td>
                          <td>
                            {importCell(parsed, row, "review_date", mapping) ||
                              "—"}
                          </td>
                          <td>
                            {importCell(parsed, row, "review_text", mapping) ||
                              "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </section>
          )}
          <div className="upload-context compact-upload-context">
            <CheckCircle2 size={17} />
            <div>
              <strong>
                {contextLoading
                  ? "Checking model context…"
                  : contextError
                    ? "Context unavailable"
                    : "Model context ready"}
              </strong>
              {contextError && (
                <>
                  <p>{contextError}</p>
                  <button className="text-action" onClick={loadContext}>
                    Retry
                  </button>
                </>
              )}
            </div>
          </div>
          {snapshots.length > 1 && (
            <label className="context-selector">
              Historical context
              <select
                value={snapshotId ?? ""}
                onChange={(e) => setSnapshotId(Number(e.target.value))}
              >
                {snapshots.map((s) => (
                  <option key={s.graph_snapshot_id} value={s.graph_snapshot_id}>
                    {s.snapshot_key}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="upload-footer">
            <span>Results are saved to your account.</span>
            <button
              className="button-primary"
              disabled={
                !file ||
                !parsed ||
                issues.length > 0 ||
                !snapshotId ||
                contextLoading ||
                parsing ||
                phase !== "idle"
              }
              onClick={upload}
            >
              {phase === "preparing"
                ? "Preparing…"
                : phase === "saving"
                  ? "Saving…"
                  : phase === "scoring"
                    ? "Analyzing…"
                    : "Upload & analyze"}
              <ChevronRight size={14} />
            </button>
          </div>
          {error && (
            <div className="notice-card notice-error" role="alert">
              <strong>Check your file</strong>
              <p>{error}</p>
              {receipt && (
                <Link
                  href={`/products/${receipt.batch_analysis_id}`}
                  className="text-action"
                >
                  Open saved batch →
                </Link>
              )}
            </div>
          )}
          {receipt && receipt.accepted_count === 0 && (
            <div className="notice-card notice-error">
              <strong>No rows imported</strong>
              <p>
                {receipt.row_count} submitted · {receipt.rejected_count} import
                errors.
              </p>
              <ul>
                {rejected.map((row) => (
                  <li key={row.row_number}>
                    Row {row.row_number}:{" "}
                    {row.validation_errors
                      .map((e) => e.message || e.code)
                      .join("; ")}
                  </li>
                ))}
              </ul>
              <Link
                href={`/products/${receipt.batch_analysis_id}`}
                className="text-action"
              >
                View import errors →
              </Link>
            </div>
          )}
        </section>
        <aside className="upload-guide panel compact-upload-guide">
          <h2>File requirements</h2>
          <p>
            Rating, review text and an actual review date are required. Common
            export column names are detected automatically.
          </p>
          <ul>
            <li>Native NeuroGraph CSV</li>
            <li>Review exports with mappable columns</li>
            <li>Comma, semicolon or tab-separated CSV</li>
          </ul>
          <a className="button-secondary" href="/sample-reviews.csv" download>
            Download sample CSV
          </a>
          <details>
            <summary>Google exports & missing fields</summary>
            <p>
              CSV export tools use different columns. Names such as starRating,
              comment and createTime are recognized. JSON, Excel files and live
              Google account sync are not supported here.
            </p>
            <p>
              If author IDs are missing, you can import those reviews
              separately. Choose a business ID once for a single-business file.
              Missing ratings, text or real dates cannot be inferred; relative
              dates such as “2 days ago” need an absolute-date export.
            </p>
          </details>
          <p className="prediction-caveat">
            Flags are investigation signals, not proof of fraud.
          </p>
        </aside>
      </div>
    </AppShell>
  );
}
