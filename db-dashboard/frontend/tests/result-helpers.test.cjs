const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");
const exportsForTest = {};
vm.runInNewContext(
  ts.transpileModule(readFileSync("app/lib/result-helpers.ts", "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2021,
    },
  }).outputText,
  { exports: exportsForTest },
);
const { resultSummary, selectResultRows, resultsCsv } = exportsForTest;
function row(n, score, decision = "cleared", text = "A review") {
  return {
    row_number: n,
    row_state: "accepted",
    uploaded_review_key: `source-${n}`,
    validation_errors: [],
    review: {
      review_id: n,
      reviewer_id: 12,
      product_id: 23,
      review_text: text,
      rating: 4,
      reviewed_at: null,
    },
    prediction: score == null ? null : { risk_score: score, decision },
  };
}
test("summary respects saved decisions even when a displayed rounded cutoff could disagree", () => {
  const rows = [
    row(1, 0.78705),
    row(2, 0.78708, "flagged"),
    row(3, null),
    { ...row(4, null), row_state: "rejected" },
  ];
  assert.deepEqual(JSON.parse(JSON.stringify(resultSummary(rows))), {
    scored: 2,
    flagged: 1,
    notFlagged: 1,
    rejected: 1,
    unscored: 1,
  });
});
test("missing predictions are not counted as safe and empty results have no invented metrics", () => {
  assert.equal(resultSummary([row(1, null)]).notFlagged, 0);
  assert.equal(resultSummary([]).scored, 0);
});
test("filter finds full text and internal author IDs; score ordering preserves source rows", () => {
  const rows = [
    row(2, 0.2, "cleared", "A long review with NEEDLE at its end"),
    row(3, 0.9, "flagged"),
    row(1, 0.9, "flagged"),
  ];
  assert.equal(
    selectResultRows(rows, "needle", "all", "score")[0].row_number,
    2,
  );
  assert.equal(selectResultRows(rows, "12", "all", "score").length, 3);
  assert.equal(
    selectResultRows(rows, "", "flagged", "score")
      .map((r) => r.row_number)
      .join(","),
    "1,3",
  );
  assert.equal(rows.map((r) => r.row_number).join(","), "2,3,1");
});
test("CSV preserves all import outcomes, exact scores and run cutoff without inventing accuracy", () => {
  const rows = [
    row(1, 0.7870707071, "flagged", 'Text, "quoted"\nnext line'),
    {
      ...row(2, null),
      row_state: "rejected",
      validation_errors: [{ message: "Bad date" }],
    },
  ];
  const csv = resultsCsv(rows, 19, 0.7870707);
  assert.ok(csv.includes('"0.7870707071"'));
  assert.ok(csv.includes('"0.7870707"'));
  assert.ok(csv.includes('Text, ""quoted""\nnext line'));
  assert.ok(csv.includes("Bad date"));
  assert.ok(!csv.includes("accuracy"));
});
test("CSV neutralizes spreadsheet formulas including leading whitespace and controls", () => {
  for (const value of [
    '=HYPERLINK("bad")',
    " +1",
    "\t@SUM(1)",
    "-1+2",
    "\n=1",
  ]) {
    const csv = resultsCsv([row(1, 0.1, "cleared", value)], 19, null);
    assert.ok(csv.includes("\"'" + value.replaceAll('"', '""') + '"'));
  }
});
