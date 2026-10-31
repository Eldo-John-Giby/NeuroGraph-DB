const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");
const Papa = require("papaparse");
const api = {};
vm.runInNewContext(
  ts.transpileModule(readFileSync("app/lib/review-import.ts", "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2021,
      esModuleInterop: true,
    },
  }).outputText,
  {
    exports: api,
    require,
    TextEncoder,
    crypto: require("node:crypto").webcrypto,
  },
);
const {
  readReviewExport: read,
  importIssues: issues,
  normalizeReviewExport: normalize,
} = api;
const options = { businessId: "", separateAuthors: false, dateOrder: "iso" };
const native =
  "review_id,reviewer_id,product_id,rating,review_date,review_text\r\nr1,u1,p1,5,2026-10-20,Good food\r\n";
const exported =
  'reviewId,authorId,placeId,starRating,createTime,comment\na1,u1,p1,FIVE,2026-10-20T12:00:00Z,"Good, fresh food"\na2,u2,p1,2.0,2026-10-21,"Slow service\nbut good food"';
const parsedRows = (csv) => Papa.parse(csv, { header: true }).data;
test("native CSV bytes and identities are preserved, including extra unused ID columns", async () => {
  const data = read(native);
  assert.equal(data.canonical, true);
  assert.equal(await normalize(data, data.mapping, options), native);
  const extra = read(
    native
      .replace("review_text\r\n", "review_text,id\r\n")
      .replace("Good food\r\n", "Good food,extra\r\n"),
  );
  assert.equal(extra.mapping.review_id, "review_id");
  assert.equal(await normalize(extra, extra.mapping, options), extra.original);
});
test("native invalid rows still reach authoritative backend validation without invented IDs", async () => {
  const data = read(native.replace("r1,u1,p1", "r1,,p1"));
  assert.equal(issues(data, data.mapping, options).length, 0);
  assert.equal(await normalize(data, data.mapping, options), data.original);
});
test("common Google-style headers, word ratings, decimals and quoted multiline text normalize", async () => {
  const data = read(exported);
  assert.equal(issues(data, data.mapping, options).length, 0);
  const rows = parsedRows(await normalize(data, data.mapping, options));
  assert.equal(rows.length, 2);
  assert.equal(rows[0].rating, "5");
  assert.equal(rows[1].rating, "2");
  assert.equal(rows[1].review_text, "Slow service\nbut good food");
  assert.equal(rows[0].review_id, "a1");
  assert.equal(rows[0].reviewer_id, "u1");
});
test("semicolon and tab files are detected without corrupting quoted delimiters", async () => {
  for (const delimiter of [";", "\t"]) {
    const source = Papa.unparse(
      [
        ["reviewId", "authorId", "placeId", "stars", "date", "text"],
        ["1", "u", "p", "4/5", "2026/10/20", "Food, service; fine"],
      ],
      { delimiter },
    );
    const data = read(source);
    const row = parsedRows(await normalize(data, data.mapping, options))[0];
    assert.equal(row.rating, "4");
    assert.equal(row.review_date, "2026-10-20");
    assert.equal(row.review_text, "Food, service; fine");
  }
});
test("missing business and author identifiers require explicit setup", async () => {
  const data = read("stars,date,comment\n5,2026-10-20,Good food");
  assert.ok(
    issues(data, data.mapping, options).some((x) => x.includes("business")),
  );
  assert.ok(
    issues(data, data.mapping, options).some((x) => x.includes("author")),
  );
  const rows = parsedRows(
    await normalize(data, data.mapping, {
      ...options,
      businessId: "hotel-1",
      separateAuthors: true,
    }),
  );
  assert.equal(rows[0].product_id, "hotel-1");
  assert.match(rows[0].review_id, /^local-[a-f0-9]{64}$/);
  assert.match(rows[0].reviewer_id, /^unknown-[a-f0-9]{64}$/);
});
test("unidentified authors stay separate while real author IDs are retained", async () => {
  const data = read(
    "reviewId,authorId,placeId,stars,date,comment\na1,,p,5,2026-10-20,Same text\na2,,p,5,2026-10-20,Same text\na3,real-user,p,5,2026-10-20,Same text",
  );
  const rows = parsedRows(
    await normalize(data, data.mapping, { ...options, separateAuthors: true }),
  );
  assert.notEqual(rows[0].reviewer_id, rows[1].reviewer_id);
  assert.equal(rows[2].reviewer_id, "real-user");
});
test("generated review IDs are stable across row ordering and exact duplicates remain detectable", async () => {
  const header = "placeId,stars,date,comment\n";
  const first = read(header + "p,5,2026-10-20,A\np,4,2026-10-21,B");
  const second = read(header + "p,4,2026-10-21,B\np,5,2026-10-20,A");
  const opts = { ...options, separateAuthors: true };
  const a = parsedRows(await normalize(first, first.mapping, opts)),
    b = parsedRows(await normalize(second, second.mapping, opts));
  assert.equal(a[0].review_id, b[1].review_id);
  assert.equal(a[0].reviewer_id, b[1].reviewer_id);
  const duplicate = read(header + "p,5,2026-10-20,A\np,5,2026-10-20,A");
  const d = parsedRows(await normalize(duplicate, duplicate.mapping, opts));
  assert.equal(d[0].review_id, d[1].review_id);
});
test("display names are never automatically treated as stable account identifiers", async () => {
  const data = read(
    "reviewId,displayName,placeId,stars,date,comment\na,Alice,p,5,2026-10-20,A",
  );
  assert.equal(data.mapping.reviewer_id, "");
  const map = { ...data.mapping, reviewer_id: "displayName" };
  assert.ok(issues(data, map, options).some((x) => x.includes("Names")));
  const row = parsedRows(
    await normalize(data, map, { ...options, separateAuthors: true }),
  )[0];
  assert.match(row.reviewer_id, /^unknown-/);
});
test("ambiguous dates require an explicit order; relative dates and 10-point ratings are not guessed", async () => {
  const data = read(
    "reviewId,authorId,placeId,stars,date,comment\na,u,p,8/10,03/04/2026,A",
  );
  assert.ok(
    issues(data, data.mapping, options).some((x) => x.includes("day/month")),
  );
  const dmy = parsedRows(
    await normalize(data, data.mapping, { ...options, dateOrder: "dmy" }),
  )[0];
  const mdy = parsedRows(
    await normalize(data, data.mapping, { ...options, dateOrder: "mdy" }),
  )[0];
  assert.equal(dmy.review_date, "2026-04-03");
  assert.equal(mdy.review_date, "2026-03-04");
  assert.equal(dmy.rating, "8/10");
  const relative = read(data.original.replace("03/04/2026", "2 days ago"));
  assert.equal(
    parsedRows(await normalize(relative, relative.mapping, options))[0]
      .review_date,
    "2 days ago",
  );
});
test("duplicate/ambiguous columns and malformed files fail instead of shifting review text", () => {
  for (const input of [
    "stars,stars,date\n1,2,2026-10-20",
    "stars,date,comment\n5,2026-10-20,food,extra",
    'stars,date,comment\n5,2026-10-20,"unclosed',
    "stars,date,\n5,2026-10-20,food",
  ])
    assert.throws(() => read(input));
  assert.throws(() => read("stars,date,comment"));
  const ambiguous = read(
    "reviewId,authorId,placeId,stars,rating,date,text\na,u,p,5,4,2026-10-20,A",
  );
  assert.equal(ambiguous.mapping.rating, "rating");
});
test("manual mapping cannot reuse a column for multiple required fields", () => {
  const data = read(exported);
  const map = { ...data.mapping, review_text: data.mapping.rating };
  assert.ok(
    issues(data, map, options).some((x) => x.includes("different column")),
  );
});
test("upload row and byte limits remain enforced before transformation", () => {
  assert.throws(
    () => read("stars,date,comment\n" + "5,2026-10-20,A\n".repeat(5001)),
    /5,000/,
  );
  assert.throws(
    () =>
      read("stars,date,comment\n5,2026-10-20," + "x".repeat(8 * 1024 * 1024)),
    /8 MiB/,
  );
});

test("native column names also adapt export-style ratings and explicit date orders", async () => {
  const data = read(native.replace(",5,2026-10-20,", ",FIVE,03/04/2026,"));
  assert.ok(
    issues(data, data.mapping, options).some((x) => x.includes("day/month")),
  );
  const row = parsedRows(
    await normalize(data, data.mapping, { ...options, dateOrder: "dmy" }),
  )[0];
  assert.equal(row.rating, "5");
  assert.equal(row.review_date, "2026-04-03");
  assert.equal(row.review_id, "r1");
  assert.equal(row.reviewer_id, "u1");
});
