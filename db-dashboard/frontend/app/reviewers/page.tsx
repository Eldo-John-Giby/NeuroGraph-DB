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
      <header className="page-heading">
        <div>
          <p className="eyebrow">Administration / source identities</p>
          <h1>Reviewer catalog</h1>
          <p className="page-subtitle">
            Look up review authors and open their review records.
          </p>
        </div>
        <button className="button-secondary" disabled={loading} onClick={load}>
          Refresh catalog
        </button>
      </header>
      <section className="notice-card">
        <strong>Review authors are different from application users.</strong>
        <p>
          An author ID connects reviews written by the same source account. This
          helps inspect repeated activity. The catalog does not assign an
          account-level fraud score or identify a person as fraudulent.
        </p>
        <p>
          Source + external author key define an identity. The same external key
          in a different source can be a different author. Review records
          enforce their own visibility rules.
        </p>
      </section>
      <section className="panel catalog-lookup">
        <h2>Have an internal reviewer ID?</h2>
        <form action="/reviews" method="get">
          <label htmlFor="reviewer-lookup">Open reviews for reviewer #</label>
          <input
            id="reviewer-lookup"
            name="reviewer_id"
            required
            type="number"
            min="1"
            step="1"
            value={lookup}
            onChange={(e) => setLookup(e.target.value)}
            placeholder="e.g. 12"
          />
          <button className="button-primary">Open review records</button>
        </form>
        <p>
          Use the internal author ID from a saved analysis. Review scores belong
          to a particular model run, not to the author as a whole.
        </p>
      </section>
      <section className="panel registry-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">
              {total.toLocaleString()} source author records
            </p>
            <h2>Browse source identities</h2>
          </div>
        </div>
        <label className="catalog-search">
          Filter this page by source, key or ID
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search the 25 records on this page"
          />
        </label>
        <p className="muted">
          This filter applies to the current page. Use Previous / Next to browse
          the full catalog, or the ID lookup above to open an author directly.
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
                  Source author identities · {matches.length} shown on this page
                </caption>
                <thead>
                  <tr>
                    <th>Internal author ID</th>
                    <th>External author key</th>
                    <th>Source</th>
                    <th>First stored</th>
                    <th>Investigation</th>
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
                      <td>{new Date(item.created_at).toLocaleDateString()}</td>
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
    </AppShell>
  );
}
