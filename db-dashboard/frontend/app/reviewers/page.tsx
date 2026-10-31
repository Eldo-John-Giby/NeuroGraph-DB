"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../components/AppShell";
import { Pagination } from "../components/ui";
import { useRequireAuth } from "../hooks/useRequireAuth";
import { apiRequest, getErrorMessage } from "../lib/api";

type Reviewer = {
  reviewer_id: number;
  source_system: string;
  external_reviewer_key: string;
  created_at: string;
};
export default function ReviewersPage() {
  const { isLoading, isAuthenticated, isAdmin } = useRequireAuth(true);
  const [items, setItems] = useState<Reviewer[]>([]),
    [total, setTotal] = useState(0),
    [offset, setOffset] = useState(0);
  const [query, setQuery] = useState(""),
    [lookup, setLookup] = useState("");
  const [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const limit = 25;
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<{ items: Reviewer[]; total: number }>(
        `/api/v1/reviewers?limit=${limit}&offset=${offset}`,
      );
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [offset]);
  useEffect(() => {
    if (isAuthenticated && isAdmin) void load();
  }, [isAuthenticated, isAdmin, load]);
  const matches = items.filter((item) =>
    `${item.reviewer_id} ${item.external_reviewer_key} ${item.source_system}`
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );
  if (isLoading || !isAuthenticated || !isAdmin)
    return (
      <div className="session-loading">Checking administrator access…</div>
    );
  return (
    <AppShell>
      <div className="compact-admin">
        <header className="page-heading">
          <div>
            <p className="eyebrow">Administration / source identities</p>
            <h1>Reviewer catalog</h1>
            <p className="page-subtitle">
              Look up review authors and open their review records.
            </p>
          </div>
          <button
            className="button-secondary"
            disabled={loading}
            onClick={load}
          >
            Refresh catalog
          </button>
        </header>
        <section className="panel registry-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">{total.toLocaleString()} source authors</p>
              <h2>Authors</h2>
            </div>
          </div>
          <div className="catalog-tools">
            <form action="/reviews" method="get" className="catalog-lookup">
              <label htmlFor="reviewer-lookup">
                Reviewer ID
                <input
                  id="reviewer-lookup"
                  name="reviewer_id"
                  required
                  type="number"
                  min="1"
                  step="1"
                  value={lookup}
                  onChange={(e) => setLookup(e.target.value)}
                  placeholder="e.g. 129"
                />
              </label>
              <button className="button-secondary">Open reviews →</button>
            </form>
            <label className="catalog-search">
              Filter this page
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Source, author key or ID"
              />
            </label>
          </div>
          <p className="catalog-scope">
            Showing up to 25 authors per page. Use an exact reviewer ID for
            direct lookup.
          </p>
          {loading ? (
            <p role="status">Loading authors…</p>
          ) : error ? (
            <p className="notice-card notice-error" role="alert">
              {error}
            </p>
          ) : (
            <>
              <div className="table-scroll">
                <table className="evidence-table">
                  <caption>
                    Source author identities · {matches.length} shown on this
                    page
                  </caption>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Author key</th>
                      <th>Source</th>
                      <th>First stored</th>
                      <th>Reviews</th>
                    </tr>
                  </thead>
                  <tbody>
                    {matches.map((item) => (
                      <tr key={item.reviewer_id}>
                        <td>#{item.reviewer_id}</td>
                        <td className="registry-key">
                          {item.external_reviewer_key}
                        </td>
                        <td className="registry-key">{item.source_system}</td>
                        <td>
                          {new Date(item.created_at).toLocaleDateString()}
                        </td>
                        <td>
                          <Link
                            className="text-action"
                            href={`/reviews?reviewer_id=${item.reviewer_id}`}
                          >
                            View reviews →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!matches.length && (
                <p>
                  No matching authors on this page. Try a different filter or
                  page.
                </p>
              )}
              <Pagination
                total={total}
                offset={offset}
                limit={limit}
                onPageChange={(next) => {
                  setQuery("");
                  setOffset(next);
                }}
              />
            </>
          )}
        </section>
        <details className="catalog-about">
          <summary>About author identities</summary>
          <p>
            Source + author key identifies a review author, separate from
            website login users. This catalog stores identities; it does not
            assign account-level fraud scores.
          </p>
        </details>
      </div>
    </AppShell>
  );
}
