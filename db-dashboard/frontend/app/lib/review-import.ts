import Papa from "papaparse";

export const IMPORT_FIELDS = [
  "review_id",
  "reviewer_id",
  "product_id",
  "rating",
  "review_date",
  "review_text",
] as const;
export type ImportField = (typeof IMPORT_FIELDS)[number];
export type ColumnMap = Record<ImportField, string>;
export type ReviewExport = {
  headers: string[];
  rows: string[][];
  mapping: ColumnMap;
  canonical: boolean;
  original: string;
};
export type ImportOptions = {
  businessId: string;
  separateAuthors: boolean;
  dateOrder: "iso" | "dmy" | "mdy";
};
const aliases: Record<ImportField, string[]> = {
  review_id: ["reviewid", "id", "reviewurl"],
  reviewer_id: [
    "reviewerid",
    "authorid",
    "userid",
    "contributorid",
    "reviewerprofileurl",
    "authorprofileurl",
    "profileurl",
    "reviewerurl",
  ],
  product_id: [
    "productid",
    "placeid",
    "locationid",
    "businessid",
    "restaurantid",
    "hotelid",
    "asin",
  ],
  rating: ["rating", "starrating", "stars", "reviewrating", "reviewstars"],
  review_date: [
    "reviewdate",
    "createtime",
    "createdat",
    "publishedat",
    "publishedtime",
    "publisheddate",
    "date",
    "timestamp",
  ],
  review_text: [
    "reviewtext",
    "comment",
    "text",
    "content",
    "reviewbody",
    "reviewcontent",
    "review",
  ],
};
const normalized = (value: string) =>
  value
    .replace(/^\uFEFF/, "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");

export function readReviewExport(text: string): ReviewExport {
  if (new TextEncoder().encode(text).length > 8 * 1024 * 1024)
    throw new Error("Choose a CSV no larger than 8 MiB.");
  const parsed = Papa.parse<string[]>(text, {
    header: false,
    skipEmptyLines: "greedy",
    delimitersToGuess: [",", ";", "\t"],
  });
  const error = parsed.errors.find(
    (error) => error.code !== "UndetectableDelimiter",
  );
  if (error) throw new Error(`CSV could not be read: ${error.message}`);
  if (parsed.data.length < 2)
    throw new Error("The CSV needs a header and at least one review.");
  const headers = parsed.data[0].map((value) =>
    value.replace(/^\uFEFF/, "").trim(),
  );
  if (
    headers.some((header) => !header) ||
    new Set(headers.map(normalized)).size !== headers.length
  )
    throw new Error("Use unique, nonempty column names.");
  const rows = parsed.data.slice(1);
  if (rows.length > 5000)
    throw new Error("Upload at most 5,000 reviews at a time.");
  if (rows.some((row) => row.length !== headers.length))
    throw new Error(
      "A CSV row has a different number of fields from the header. Check its commas and quotes.",
    );
  const mapping = Object.fromEntries(
    IMPORT_FIELDS.map((field) => {
      const candidates = headers.filter((header) =>
        aliases[field].includes(normalized(header)),
      );
      return [
        field,
        headers.includes(field)
          ? field
          : candidates.length === 1
            ? candidates[0]
            : "",
      ];
    }),
  ) as ColumnMap;
  // Preserve native-file bytes/identities and let the existing backend validate rows.
  const canonical =
    parsed.meta.delimiter === "," &&
    IMPORT_FIELDS.every((field) => headers.includes(field));
  return { headers, rows, mapping, canonical, original: text };
}

export function importCell(
  data: ReviewExport,
  row: string[],
  field: ImportField,
  map: ColumnMap,
): string {
  const index = data.headers.indexOf(map[field]);
  return index < 0 ? "" : (row[index] || "").trim();
}

export function missingAuthorCount(data: ReviewExport, map: ColumnMap): number {
  return data.rows.filter((row) => !importCell(data, row, "reviewer_id", map))
    .length;
}

export function requiresValueConversion(
  data: ReviewExport,
  map: ColumnMap,
): boolean {
  return data.rows.some(
    (row) =>
      /^(?:ONE|TWO|THREE|FOUR|FIVE|[1-5]\.0+|[1-5]\s*(?:STARS?|\/\s*5))$/i.test(
        importCell(data, row, "rating", map),
      ) ||
      /^(?:\d{4}\/\d{1,2}\/\d{1,2}|\d{1,2}[\/-]\d{1,2}[\/-]\d{4})$/.test(
        importCell(data, row, "review_date", map),
      ),
  );
}

const untouchedNative = (
  data: ReviewExport,
  map: ColumnMap,
  options: ImportOptions,
) =>
  data.canonical &&
  !requiresValueConversion(data, map) &&
  IMPORT_FIELDS.every((field) => map[field] === field) &&
  !options.businessId &&
  !options.separateAuthors &&
  options.dateOrder === "iso";

export function importIssues(
  data: ReviewExport,
  map: ColumnMap,
  options: ImportOptions,
): string[] {
  if (untouchedNative(data, map, options)) return [];
  const problems: string[] = [];
  for (const field of ["rating", "review_date", "review_text"] as const)
    if (!map[field])
      problems.push(`Choose the ${field.replaceAll("_", " ")} column.`);
  const selected = Object.values(map).filter(Boolean);
  if (new Set(selected).size !== selected.length)
    problems.push("Use a different column for each field.");
  if (selected.some((header) => !data.headers.includes(header)))
    problems.push("A selected column is not in this file.");
  if (!map.product_id && !options.businessId.trim())
    problems.push("Enter the business or product ID for this file.");
  if (options.businessId.trim().length > 255)
    problems.push("Business or product ID must be at most 255 characters.");
  if (missingAuthorCount(data, map) && !options.separateAuthors)
    problems.push(
      "Confirm import without author connections, or choose an author ID column.",
    );
  if (
    map.reviewer_id &&
    /(?:name|display)/i.test(map.reviewer_id) &&
    !options.separateAuthors
  )
    problems.push(
      "Names are not unique author IDs. Choose a profile URL/ID, or import without author connections.",
    );
  if (
    options.dateOrder === "iso" &&
    data.rows.some((row) =>
      /^\d{1,2}[\/-]\d{1,2}[\/-]\d{4}$/.test(
        importCell(data, row, "review_date", map),
      ),
    )
  )
    problems.push("Choose the day/month order for this file.");
  return problems;
}

function ratingValue(value: string): string {
  const words: Record<string, string> = {
    ONE: "1",
    TWO: "2",
    THREE: "3",
    FOUR: "4",
    FIVE: "5",
  };
  const clean = value.trim().toUpperCase();
  if (words[clean]) return words[clean];
  const match = clean.match(/^([1-5])(?:\.0+)?(?:\s*(?:STARS?|\/\s*5))?$/);
  return match ? match[1] : value; // Invalid values remain invalid for backend row validation.
}

function dateValue(value: string, order: ImportOptions["dateOrder"]): string {
  if (/^\d{4}-\d{2}-\d{2}(?:$|T| )/.test(value)) return value;
  const yearFirst = value.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
  if (yearFirst)
    return `${yearFirst[1]}-${yearFirst[2].padStart(2, "0")}-${yearFirst[3].padStart(2, "0")}`;
  const local = value.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})$/);
  if (local && order !== "iso") {
    const day = order === "dmy" ? local[1] : local[2];
    const month = order === "dmy" ? local[2] : local[1];
    return `${local[3]}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  }
  return value; // Never invent an absolute date for “2 days ago” or guess DD/MM vs MM/DD.
}

async function fingerprint(parts: string[]): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(parts));
  return Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    (b) => b.toString(16).padStart(2, "0"),
  ).join("");
}

export async function normalizeReviewExport(
  data: ReviewExport,
  map: ColumnMap,
  options: ImportOptions,
): Promise<string> {
  const issues = importIssues(data, map, options);
  if (issues.length) throw new Error(issues[0]);
  if (untouchedNative(data, map, options)) return data.original;
  const unsafeAuthorName = /(?:name|display)/i.test(map.reviewer_id);
  const rows: string[][] = [];
  for (const row of data.rows) {
    const product =
      importCell(data, row, "product_id", map) || options.businessId.trim();
    const rating = ratingValue(importCell(data, row, "rating", map));
    const date = dateValue(
      importCell(data, row, "review_date", map),
      options.dateOrder,
    );
    const text = importCell(data, row, "review_text", map);
    const author = unsafeAuthorName
      ? ""
      : importCell(data, row, "reviewer_id", map);
    const review =
      importCell(data, row, "review_id", map) ||
      `local-${await fingerprint([product, author, rating, date, text])}`;
    // One local identity per unidentified review prevents fabricated same-author edges.
    const authorKey =
      author || `unknown-${await fingerprint([product, review])}`;
    rows.push([review, authorKey, product, rating, date, text]);
  }
  const csv = Papa.unparse(
    { fields: [...IMPORT_FIELDS], data: rows },
    { newline: "\r\n" },
  );
  if (new TextEncoder().encode(csv).length > 8 * 1024 * 1024)
    throw new Error(
      "The converted CSV exceeds 8 MiB. Split it into smaller files.",
    );
  return csv;
}
