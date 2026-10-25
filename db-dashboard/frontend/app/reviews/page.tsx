'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { Star, Plus, Filter, ClipboardList, X, Zap } from 'lucide-react';
import AppShell from '../components/AppShell';
import {
  PageHeader,
  StatCard,
  TableSkeleton,
  EmptyState,
  ErrorState,
  StatusBadge,
  Pagination,
  LoadingSpinner,
} from '../components/ui';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { apiRequest, getErrorMessage } from '../lib/api';

interface ReviewItem {
  review_id: number;
  source_system: string | null;
  source_review_key: string | null;
  reviewer_id: number | null;
  product_id: number | null;
  rating: number | null;
  review_text: string | null;
  reviewed_at: string | null;
  has_ground_truth: boolean;
}

interface ReviewListResponse {
  items: ReviewItem[];
  total: number;
  limit: number;
  offset: number;
}

interface PredictionItem {
  prediction_id: number;
  fraud_score: number;
  predicted_label: number;
  inference_run_id: number;
  threshold_used: number;
  created_at?: string;
}

export default function ReviewHistoryPage() {
  const { user, isLoading: authLoading, isAuthenticated } = useRequireAuth();

  // Review List State
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [limit] = useState(15);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter Form Inputs
  const [sourceSystemInput, setSourceSystemInput] = useState('');
  const [reviewerIdInput, setReviewerIdInput] = useState('');
  const [productIdInput, setProductIdInput] = useState('');
  const [groundTruthInput, setGroundTruthInput] = useState<'all' | 'true' | 'false'>('all');

  // Applied Filter State
  const [appliedFilters, setAppliedFilters] = useState<{
    source_system: string;
    reviewer_id: string;
    product_id: string;
    ground_truth_available: 'all' | 'true' | 'false';
  }>({
    source_system: '',
    reviewer_id: '',
    product_id: '',
    ground_truth_available: 'all',
  });

  // Selected Review for Detail Modal / Slide-over
  const [selectedReview, setSelectedReview] = useState<ReviewItem | null>(null);
  const [reviewPredictions, setReviewPredictions] = useState<PredictionItem[]>([]);
  const [loadingPredictions, setLoadingPredictions] = useState(false);
  const [predictionsError, setPredictionsError] = useState<string | null>(null);

  // Fetch Reviews Callback
  const fetchReviews = useCallback(async () => {
    if (!isAuthenticated) return;

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set('limit', String(limit));
      params.set('offset', String(offset));

      if (appliedFilters.source_system.trim()) {
        params.set('source_system', appliedFilters.source_system.trim());
      }
      if (appliedFilters.reviewer_id.trim()) {
        params.set('reviewer_id', appliedFilters.reviewer_id.trim());
      }
      if (appliedFilters.product_id.trim()) {
        params.set('product_id', appliedFilters.product_id.trim());
      }
      if (appliedFilters.ground_truth_available === 'true') {
        params.set('ground_truth_available', 'true');
      } else if (appliedFilters.ground_truth_available === 'false') {
        params.set('ground_truth_available', 'false');
      }

      const res = await apiRequest<ReviewListResponse>(`/api/v1/reviews?${params.toString()}`);
      setReviews(res.items || []);
      setTotal(res.total || 0);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, limit, offset, appliedFilters]);

  // Load reviews on filter or offset change
  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  // Fetch predictions for selected review
  useEffect(() => {
    if (!selectedReview) {
      setReviewPredictions([]);
      setPredictionsError(null);
      return;
    }

    let isMounted = true;
    async function fetchPredictions() {
      if (!selectedReview) return;
      setLoadingPredictions(true);
      setPredictionsError(null);

      try {
        const res = await apiRequest<{ items: PredictionItem[] }>(
          `/api/v1/reviews/${selectedReview.review_id}/predictions?limit=10&offset=0`
        );
        if (isMounted) {
          setReviewPredictions(res.items || []);
        }
      } catch (err: unknown) {
        if (isMounted) {
          // If 404 or other, set message
          setPredictionsError(getErrorMessage(err));
        }
      } finally {
        if (isMounted) setLoadingPredictions(false);
      }
    }

    fetchPredictions();

    return () => {
      isMounted = false;
    };
  }, [selectedReview]);

  // Handle Filter Form Submit
  const handleApplyFilters = (e: React.FormEvent) => {
    e.preventDefault();
    setOffset(0); // Reset to page 1
    setAppliedFilters({
      source_system: sourceSystemInput,
      reviewer_id: reviewerIdInput,
      product_id: productIdInput,
      ground_truth_available: groundTruthInput,
    });
  };

  // Reset Filters
  const handleResetFilters = () => {
    setSourceSystemInput('');
    setReviewerIdInput('');
    setProductIdInput('');
    setGroundTruthInput('all');
    setOffset(0);
    setAppliedFilters({
      source_system: '',
      reviewer_id: '',
      product_id: '',
      ground_truth_available: 'all',
    });
  };

  const hasActiveFilters =
    Boolean(appliedFilters.source_system) ||
    Boolean(appliedFilters.reviewer_id) ||
    Boolean(appliedFilters.product_id) ||
    appliedFilters.ground_truth_available !== 'all';

  // Render Stars Helper
  const renderRating = (rating: number | null) => {
    if (rating === null || rating === undefined) {
      return <span className="text-slate-500">—</span>;
    }
    return (
      <div className="flex items-center gap-1.5" title={`Rating: ${rating} / 5`}>
        <div className="flex items-center gap-0.5 text-xs">
          {Array.from({ length: 5 }).map((_, i) => (
            <Star
              key={i}
              className={`h-3 w-3 ${i < rating ? 'fill-amber-400 text-amber-400' : 'text-slate-700'}`}
            />
          ))}
        </div>
        <span className="text-xs font-semibold text-slate-300 font-mono">({rating})</span>
      </div>
    );
  };

  // Format Date Helper
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return <span className="text-slate-500">—</span>;
    try {
      const d = new Date(dateStr);
      return (
        <span className="text-xs text-slate-300 whitespace-nowrap" title={d.toISOString()}>
          {d.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          })}{' '}
          <span className="text-slate-500 text-[11px]">
            {d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </span>
      );
    } catch {
      return <span className="text-slate-400">{dateStr}</span>;
    }
  };

  if (authLoading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <LoadingSpinner text="Checking authentication..." />
      </div>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page Header */}
        <PageHeader
          title="Review History"
          subtitle="Explore ingested review records, graph connections, and ground-truth risk labels."
          actions={
            <Link
              href="/reviews/submit"
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-indigo-500 transition-colors"
            >
              <Plus className="h-4 w-4" /> Submit Review
            </Link>
          }
        />

        {/* Stat Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard
            label="Total Reviews"
            value={total.toLocaleString()}
            color="white"
            subtext="In database catalog"
          />
          <StatCard
            label="Active Filter"
            value={hasActiveFilters ? 'Applied' : 'None'}
            color={hasActiveFilters ? 'sky' : 'indigo'}
            subtext={hasActiveFilters ? 'Showing filtered results' : 'Viewing all records'}
          />
          <StatCard
            label="Page Size"
            value={limit}
            color="indigo"
            subtext={`Offset: ${offset}`}
          />
          <StatCard
            label="Loaded In View"
            value={reviews.length}
            color="emerald"
            subtext={`Out of ${total} total`}
          />
        </div>

        {/* Filter Bar */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
          <form onSubmit={handleApplyFilters} className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Filter className="h-3.5 w-3.5 text-slate-400" /> Filter Reviews
              </span>
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={handleResetFilters}
                  className="text-xs text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
                >
                  Clear all filters
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              {/* Source System */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                  Source System
                </label>
                <input
                  type="text"
                  placeholder="e.g. amazon, yelp"
                  value={sourceSystemInput}
                  onChange={(e) => setSourceSystemInput(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Reviewer ID */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                  Reviewer ID
                </label>
                <input
                  type="number"
                  min="1"
                  placeholder="e.g. 1042"
                  value={reviewerIdInput}
                  onChange={(e) => setReviewerIdInput(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Product ID */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                  Product ID
                </label>
                <input
                  type="number"
                  min="1"
                  placeholder="e.g. 805"
                  value={productIdInput}
                  onChange={(e) => setProductIdInput(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Ground Truth Available */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                  Ground Truth Status
                </label>
                <select
                  value={groundTruthInput}
                  onChange={(e) => setGroundTruthInput(e.target.value as 'all' | 'true' | 'false')}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="all">All Reviews</option>
                  <option value="true">Has Ground Truth</option>
                  <option value="false">No Ground Truth</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={handleResetFilters}
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700 transition-colors"
              >
                Reset
              </button>
              <button
                type="submit"
                className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors flex items-center gap-1.5 shadow"
              >
                <span>Filter</span>
              </button>
            </div>
          </form>
        </div>

        {/* Content Area */}
        {loading ? (
          <TableSkeleton rows={7} cols={7} />
        ) : error ? (
          <ErrorState message={error} onRetry={fetchReviews} />
        ) : reviews.length === 0 ? (
          <EmptyState
            icon={<ClipboardList className="h-8 w-8 text-slate-500" />}
            title="No reviews found"
            message={
              hasActiveFilters
                ? 'No review records match the active filter criteria. Try adjusting or clearing your filters.'
                : 'No reviews have been ingested into the system yet. Submit your first review to get started.'
            }
            action={
              hasActiveFilters ? (
                <button
                  onClick={handleResetFilters}
                  className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 transition-colors"
                >
                  Clear Filters
                </button>
              ) : (
                <Link
                  href="/reviews/submit"
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
                >
                  Submit a Review
                </Link>
              )
            }
          />
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 shadow-lg">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-800/60 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    <th scope="col" className="px-4 py-3">
                      Review ID
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Source
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Reviewer ID
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Product ID
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Rating
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Reviewed At
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Has Ground Truth
                    </th>
                    <th scope="col" className="px-4 py-3 text-right">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {reviews.map((r) => {
                    const isSelected = selectedReview?.review_id === r.review_id;
                    return (
                      <tr
                        key={r.review_id}
                        onClick={() => setSelectedReview(r)}
                        className={`cursor-pointer transition-colors hover:bg-slate-800/40 ${
                          isSelected ? 'bg-indigo-950/30 border-l-2 border-indigo-500' : ''
                        }`}
                      >
                        {/* Review ID */}
                        <td className="px-4 py-3.5 whitespace-nowrap font-mono text-xs font-bold text-white">
                          #{r.review_id}
                        </td>

                        {/* Source */}
                        <td className="px-4 py-3.5 whitespace-nowrap">
                          {r.source_system ? (
                            <div className="flex flex-col">
                              <span className="font-semibold text-xs text-slate-200">
                                {r.source_system}
                              </span>
                              {r.source_review_key && (
                                <span className="text-[10px] text-slate-500 font-mono">
                                  {r.source_review_key}
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-500 text-xs">—</span>
                          )}
                        </td>

                        {/* Reviewer ID */}
                        <td className="px-4 py-3.5 whitespace-nowrap text-xs text-slate-300 font-mono">
                          {r.reviewer_id !== null ? `#${r.reviewer_id}` : <span className="text-slate-500">—</span>}
                        </td>

                        {/* Product ID */}
                        <td className="px-4 py-3.5 whitespace-nowrap text-xs text-slate-300 font-mono">
                          {r.product_id !== null ? `#${r.product_id}` : <span className="text-slate-500">—</span>}
                        </td>

                        {/* Rating */}
                        <td className="px-4 py-3.5 whitespace-nowrap">
                          {renderRating(r.rating)}
                        </td>

                        {/* Reviewed At */}
                        <td className="px-4 py-3.5 whitespace-nowrap">
                          {formatDate(r.reviewed_at)}
                        </td>

                        {/* Has Ground Truth */}
                        <td className="px-4 py-3.5 whitespace-nowrap">
                          {r.has_ground_truth ? (
                            <StatusBadge status="Available" variant="success" />
                          ) : (
                            <StatusBadge status="Unlabeled" variant="neutral" />
                          )}
                        </td>

                        {/* Action */}
                        <td className="px-4 py-3.5 whitespace-nowrap text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedReview(r);
                            }}
                            className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
                          >
                            Details →
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Component */}
            <Pagination
              offset={offset}
              limit={limit}
              total={total}
              onPageChange={(newOffset) => setOffset(newOffset)}
            />
          </div>
        )}

        {/* Selected Review Detail Slide-Over / Modal */}
        {selectedReview && (
          <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/60 backdrop-blur-xs">
            <div className="h-full w-full max-w-xl bg-slate-900 border-l border-slate-800 p-6 overflow-y-auto flex flex-col justify-between shadow-2xl">
              <div className="space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400">
                      Review Record Detail
                    </span>
                    <h3 className="text-xl font-bold text-white">
                      Review #{selectedReview.review_id}
                    </h3>
                  </div>
                  <button
                    onClick={() => setSelectedReview(null)}
                    className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                {/* Metadata Grid */}
                <div className="grid grid-cols-2 gap-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-xs">
                  <div>
                    <p className="text-slate-500 font-semibold uppercase text-[10px]">Source System</p>
                    <p className="text-slate-200 mt-0.5 font-medium">
                      {selectedReview.source_system || '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500 font-semibold uppercase text-[10px]">Source Key</p>
                    <p className="text-slate-200 mt-0.5 font-mono">
                      {selectedReview.source_review_key || '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500 font-semibold uppercase text-[10px]">Reviewer ID</p>
                    <p className="text-slate-200 mt-0.5 font-mono">
                      {selectedReview.reviewer_id ? `#${selectedReview.reviewer_id}` : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500 font-semibold uppercase text-[10px]">Product ID</p>
                    <p className="text-slate-200 mt-0.5 font-mono">
                      {selectedReview.product_id ? `#${selectedReview.product_id}` : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500 font-semibold uppercase text-[10px]">Rating</p>
                    <div className="mt-0.5">{renderRating(selectedReview.rating)}</div>
                  </div>
                  <div>
                    <p className="text-slate-500 font-semibold uppercase text-[10px]">Reviewed At</p>
                    <p className="text-slate-200 mt-0.5">{formatDate(selectedReview.reviewed_at)}</p>
                  </div>
                  <div className="col-span-2 border-t border-slate-800/80 pt-2 flex items-center justify-between">
                    <span className="text-slate-500 uppercase text-[10px] font-semibold">
                      Ground Truth Status
                    </span>
                    {selectedReview.has_ground_truth ? (
                      <StatusBadge status="Verified Labeled" variant="success" />
                    ) : (
                      <StatusBadge status="Unlabeled" variant="neutral" />
                    )}
                  </div>
                </div>

                {/* Review Text */}
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                    Review Text Content
                  </h4>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4 text-xs font-mono text-slate-200 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                    {selectedReview.review_text || (
                      <span className="text-slate-500 italic">No text content provided.</span>
                    )}
                  </div>
                </div>

                {/* Prior Inference Predictions */}
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center justify-between">
                    <span>ML Risk Predictions</span>
                    <span className="text-[10px] font-normal text-slate-500">
                      {reviewPredictions.length} recorded
                    </span>
                  </h4>
                  {loadingPredictions ? (
                    <LoadingSpinner text="Loading predictions..." />
                  ) : predictionsError ? (
                    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-xs text-slate-400">
                      No prediction records available.
                    </div>
                  ) : reviewPredictions.length === 0 ? (
                    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4 text-center text-xs text-slate-500">
                      No ML predictions generated for this review yet.
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {reviewPredictions.map((pred) => (
                        <div
                          key={pred.prediction_id}
                          className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/80 p-3 text-xs"
                        >
                          <div>
                            <span className="font-semibold text-white">
                              Run #{pred.inference_run_id}
                            </span>
                            <span className="text-slate-500 text-[10px] ml-2">
                              Threshold: {pred.threshold_used}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-slate-300">
                              Score: {(pred.fraud_score * 100).toFixed(1)}%
                            </span>
                            <StatusBadge
                              status={pred.predicted_label === 1 ? 'High Risk' : 'Normal'}
                              variant={pred.predicted_label === 1 ? 'error' : 'success'}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Actions Footer */}
              <div className="border-t border-slate-800 pt-4 flex items-center justify-between mt-6">
                <button
                  onClick={() => setSelectedReview(null)}
                  className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 transition-colors"
                >
                  Close
                </button>
                <Link
                  href={`/reviews/submit`}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
                >
                  <Zap className="h-3.5 w-3.5" /> Run Inference on Review #{selectedReview.review_id}
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
