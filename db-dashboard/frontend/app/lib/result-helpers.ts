/** Presentation helpers use saved decisions; they never rescore a review. */
export type ResultRow = {
  row_number: number;
  row_state: string;
  uploaded_review_key: string | null;
  validation_errors: Array<{ message?: string; code?: string }>;
  review: {
    review_id: number;
    reviewer_id: number | null;
    product_id: number | null;
    review_text: string | null;
    rating: number | null;
    reviewed_at: string | null;
  } | null;
  prediction: { risk_score: number; decision: "flagged" | "cleared" } | null;
};

/** Relation weights describe a three-way model gate, not individual neighbors. */
export function relationGateLabel(weight: number | undefined, count: number | undefined): string {
  if (count == null) return "Context count unavailable";
  if (count <= 0) return "No eligible neighbors";
  if (weight == null || !Number.isFinite(weight)) return "Weight unavailable";
  return `${(weight * 100).toFixed(1)}%`;
}

export function resultSummary(rows: ResultRow[]) {
  const scored = rows.filter((row) => row.prediction !== null);
  const flagged = scored.filter(
    (row) => row.prediction?.decision === "flagged",
  ).length;
  return {
    scored: scored.length,
    flagged,
    notFlagged: scored.length - flagged,
    rejected: rows.filter((row) => row.row_state === "rejected").length,
    unscored: rows.filter(
      (row) => row.row_state !== "rejected" && row.prediction === null,
    ).length,
  };
}

export function selectResultRows<T extends ResultRow>(
  rows: T[],
  query: string,
  decision: string,
  order: string,
): T[] {
  const needle = query.trim().toLowerCase();
  const selected = rows.filter((row) => {
    const state =
      row.prediction?.decision ??
      (row.row_state === "rejected" ? "rejected" : "unscored");
    return (
      (decision === "all" || state === decision) &&
      `${row.uploaded_review_key ?? ""} ${row.review?.review_id ?? ""} ${row.review?.reviewer_id ?? ""} ${row.review?.product_id ?? ""} ${row.review?.review_text ?? ""}`
        .toLowerCase()
        .includes(needle)
    );
  });
  return selected.sort((a, b) =>
    order === "row"
      ? a.row_number - b.row_number
      : (b.prediction?.risk_score ?? -1) - (a.prediction?.risk_score ?? -1) ||
        a.row_number - b.row_number,
  );
}

function csvCell(value: unknown): string {
  let text = value == null ? "" : String(value);
  // Spreadsheet programs can execute formulas even inside CSV quotes.
  if (/^[\s\uFEFF]*[=+\-@]/.test(text) || /^[\t\r\n]/.test(text))
    text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}
export function resultsCsv(
  rows: ResultRow[],
  batchId: number,
  threshold: number | null,
): string {
  const cells: unknown[][] = [
    [
      "batch_id",
      "csv_row",
      "source_review_id",
      "internal_review_id",
      "internal_reviewer_id",
      "internal_product_id",
      "rating",
      "review_date",
      "review_text",
      "import_state",
      "model_risk_score",
      "saved_decision",
      "run_threshold",
      "import_errors",
    ],
  ];
  for (const row of rows)
    cells.push([
      batchId,
      row.row_number,
      row.uploaded_review_key,
      row.review?.review_id,
      row.review?.reviewer_id,
      row.review?.product_id,
      row.review?.rating,
      row.review?.reviewed_at,
      row.review?.review_text,
      row.row_state,
      row.prediction?.risk_score,
      row.prediction
        ? row.prediction.decision === "flagged"
          ? "Flagged for review"
          : "Not flagged"
        : "",
      threshold,
      row.validation_errors.map((e) => e.message || e.code).join("; "),
    ]);
  return "\uFEFF" + cells.map((row) => row.map(csvCell).join(",")).join("\r\n");
}
