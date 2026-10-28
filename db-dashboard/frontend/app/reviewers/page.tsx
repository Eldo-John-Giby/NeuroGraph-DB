'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { RefreshCw, User, Share2, Users, Zap } from 'lucide-react';
import AppShell from '../components/AppShell';
import { PageHeader, StatCard, LoadingSpinner, TableSkeleton, EmptyState, InfoBanner, StatusBadge } from '../components/ui';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { apiRequest, isApiError } from '../lib/api';

interface Reviewer {
  reviewer_id: number;
  source_system: string;
  external_reviewer_key: string;
  created_at: string;
  total_reviews?: number;
  average_rating?: number;
  risk_score?: number;
}

interface ReviewersResponse {
  items?: Reviewer[];
  total?: number;
  limit?: number;
  offset?: number;
}

export default function ReviewersPage() {
  const { isLoading: authLoading, isAuthenticated } = useRequireAuth();
  const [loading, setLoading] = useState<boolean>(true);
  const [reviewers, setReviewers] = useState<Reviewer[] | null>(null);
  const [isNotImplemented, setIsNotImplemented] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchReviewers = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    setIsNotImplemented(false);

    try {
      const data = await apiRequest<ReviewersResponse | Reviewer[]>('/api/v1/reviewers');
      if (Array.isArray(data)) {
        setReviewers(data);
      } else if (data && Array.isArray(data.items)) {
        setReviewers(data.items);
      } else {
        setReviewers([]);
      }
    } catch (err: unknown) {
      // 404 or missing route indicates the endpoint is not yet implemented
      if (isApiError(err) && (err.status === 404 || err.code === 'not_found' || err.status === 405)) {
        setIsNotImplemented(true);
      } else {
        // Any other error also marks as not yet implemented per specification with details
        setIsNotImplemented(true);
        if (err instanceof Error) {
          setFetchError(err.message);
        }
      }
      setReviewers(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchReviewers();
    }
  }, [isAuthenticated, fetchReviewers]);

  if (authLoading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <LoadingSpinner text="Authenticating session..." />
      </div>
    );
  }

  return (
    <AppShell>
      <PageHeader
        title="Reviewer Management"
        subtitle="Inspect reviewer metadata, fraud score distributions, and camouflage account clustering"
        actions={
          <button
            onClick={fetchReviewers}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5 text-teal-400" />
            {loading ? 'Checking...' : 'Refresh Endpoint'}
          </button>
        }
      />

      {loading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-24 rounded-xl border border-slate-800 bg-slate-900/60 animate-pulse" />
            ))}
          </div>
          <TableSkeleton rows={6} cols={5} />
        </div>
      ) : isNotImplemented ? (
        <div className="space-y-6">
          {/* Info Banner specified in requirements */}
          <InfoBanner
            title="Reviewer Management Endpoint Status"
            message="Reviewer management endpoints are not yet implemented on the backend. This page will be functional once the /api/v1/reviewers routes are deployed."
          />

          {fetchError && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs font-mono text-slate-400">
              <span className="text-slate-500">API Response Detail:</span> {fetchError}
            </div>
          )}

          {/* Conceptual Description & Architecture */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 text-lg">
                <User className="h-5 w-5 text-indigo-400" />
              </div>
              <div className="space-y-2">
                <h3 className="text-base font-bold text-white">
                  Conceptual Architecture: Reviewer Entities & Bipartite Graph Modeling
                </h3>
                <p className="text-sm leading-relaxed text-slate-300">
                  In the NeuroGraph-DB framework, reviewers represent the source node partition in the heterogeneous bipartite graph{' '}
                  <code className="text-indigo-400 font-mono text-xs">(:Reviewer)-[:REVIEWED]→(:Product)</code>. Rather than evaluating textual reviews in isolation, the database correlates individual reviewer behavioral patterns with graph topology.
                </p>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                <div className="flex items-center gap-2 text-indigo-400 mb-2 font-semibold text-sm">
                  <Share2 className="h-4 w-4 text-indigo-400" /> Topological Camouflage Detection
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Fraudulent accounts frequently intersperse benign reviews to disguise coordinated review attacks. Graph Neural Networks compute local neighborhood entropy to identify synthetic credibility farming.
                </p>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                <div className="flex items-center gap-2 text-emerald-400 mb-2 font-semibold text-sm">
                  <Users className="h-4 w-4 text-emerald-400" /> Sybil & Cluster Infiltration
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Graph projection identifies dense reviewer-reviewer co-review cliques targeting shared products within narrow temporal windows, revealing organized review-broker operations.
                </p>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                <div className="flex items-center gap-2 text-amber-400 mb-2 font-semibold text-sm">
                  <Zap className="h-4 w-4 text-amber-400" /> Multi-Modal Fusion Alignment
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Cross-attention mechanisms join reviewer textual embeddings with GNN node embeddings, ensuring that sudden semantic drift aligns with structural fraud scores.
                </p>
              </div>
            </div>

            {/* Planned Schema Preview */}
            <div className="mt-6 border-t border-slate-800/80 pt-5">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                Target Schema Specification (<code className="text-slate-300 font-mono">reviewers</code> table)
              </h4>
              <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/80">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-800 bg-slate-900/80 text-slate-400">
                    <tr>
                      <th className="px-4 py-2.5 font-semibold">Column</th>
                      <th className="px-4 py-2.5 font-semibold">SQL Type</th>
                      <th className="px-4 py-2.5 font-semibold">Constraint</th>
                      <th className="px-4 py-2.5 font-semibold">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                    <tr>
                      <td className="px-4 py-2 text-indigo-400">reviewer_id</td>
                      <td className="px-4 py-2 text-slate-400">BigInteger</td>
                      <td className="px-4 py-2 text-emerald-400">PRIMARY KEY</td>
                      <td className="px-4 py-2 font-sans text-slate-400">Synthetic surrogate sequence ID</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 text-indigo-400">source_system</td>
                      <td className="px-4 py-2 text-slate-400">VARCHAR(100)</td>
                      <td className="px-4 py-2 text-amber-400">NOT NULL, UQ(source, key)</td>
                      <td className="px-4 py-2 font-sans text-slate-400">Origin platform identifier (e.g. amazon, yelp)</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 text-indigo-400">external_reviewer_key</td>
                      <td className="px-4 py-2 text-slate-400">VARCHAR(255)</td>
                      <td className="px-4 py-2 text-amber-400">NOT NULL, UQ(source, key)</td>
                      <td className="px-4 py-2 font-sans text-slate-400">Native platform user account ID / hash</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 text-indigo-400">created_at</td>
                      <td className="px-4 py-2 text-slate-400">TIMESTAMPTZ</td>
                      <td className="px-4 py-2 text-slate-500">DEFAULT NOW()</td>
                      <td className="px-4 py-2 font-sans text-slate-400">Timestamp of initial record ingestion</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-slate-800/80 pt-5">
              <p className="text-xs text-slate-400">
                You can currently filter and inspect individual reviews submitted by reviewer ID in the review history stream.
              </p>
              <Link
                href="/reviews"
                className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                Explore Review History →
              </Link>
            </div>
          </div>
        </div>
      ) : reviewers && reviewers.length > 0 ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard label="Reviewers on this page" value={reviewers.length} color="indigo" />
            <StatCard
              label="Linked review totals"
              value="Not provided"
              color="emerald"
            />
            <StatCard
              label="Model risk"
              value="Open an analysis"
              color="rose"
            />
            <StatCard
              label="Sources on this page"
              value={Array.from(new Set(reviewers.map((r) => r.source_system))).length}
              color="sky"
            />
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Reviewer ID</th>
                    <th className="px-4 py-3">External Key</th>
                    <th className="px-4 py-3">Source System</th>
                    <th className="px-4 py-3">Created At</th>
                    <th className="px-4 py-3">Risk Assessment</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                  {reviewers.map((reviewer) => (
                    <tr key={reviewer.reviewer_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 font-semibold text-indigo-400">#{reviewer.reviewer_id}</td>
                      <td className="px-4 py-3 text-white font-mono">{reviewer.external_reviewer_key}</td>
                      <td className="px-4 py-3">
                        <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300 border border-slate-700">
                          {reviewer.source_system}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-400 font-sans">
                        {reviewer.created_at ? new Date(reviewer.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {reviewer.risk_score !== undefined ? (
                          <StatusBadge
                            status={reviewer.risk_score > 0.7 ? 'High Risk' : reviewer.risk_score > 0.4 ? 'Moderate' : 'Verified'}
                            variant={reviewer.risk_score > 0.7 ? 'error' : reviewer.risk_score > 0.4 ? 'warning' : 'success'}
                          />
                        ) : (
                          <StatusBadge status="Pending Eval" variant="neutral" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-sans">
                        <Link
                          href={`/reviews?reviewer_id=${reviewer.reviewer_id}`}
                          className="rounded bg-indigo-600/20 px-2.5 py-1 text-xs font-semibold text-indigo-400 hover:bg-indigo-600/30 transition-colors"
                        >
                          View Reviews
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <EmptyState
          icon={<Users className="h-8 w-8 text-slate-500" />}
          title="No Reviewers Found"
          message="No reviewer entities have been recorded in the database yet."
          action={
            <button
              onClick={fetchReviewers}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
            >
              Reload
            </button>
          }
        />
      )}
    </AppShell>
  );
}
