'use client';

import React, { ChangeEvent, DragEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import AppShell from '../../components/AppShell';
import { InductiveBatchSection } from '../../components/InductiveBatchSection';
import { useRequireAuth } from '../../hooks/useRequireAuth';
import { apiRequest, getErrorMessage } from '../../lib/api';

const PAGE_SIZE = 25;
const DEMO_SOURCE = 'synthetic_demo';
const CAMPAIGN_KEY = 'harbor-table-review-bombing-seed-42';
type Review = { review_id: number; source_system: string | null; source_review_key: string | null; reviewer_id: number | null; product_id: number | null; rating: number | null; review_text: string | null; reviewed_at: string | null };
type ReviewRow = { review: Review; reviewer: string; product: string };
type Page<T> = { items: T[]; total: number; limit: number; offset: number };
type BatchStatus = { batch_analysis_id: number; status: string; row_count: number; accepted_count: number; rejected_count: number; blocking_reasons: string[]; scoring_available?: boolean };
type BatchResult = { row_number: number; row_state: string; uploaded_review_key: string | null; validation_errors: Array<{ field?: string; code?: string; message?: string }>; review: Review | null; prediction: any };
type CampaignSummary = { campaign_key: string; campaign_name: string; provenance: string; product: { product_id: number; name: string | null }; attack_window: { start: string; end: string }; attack_review_count: number; distinct_attack_reviewers: number; one_star_review_count: number; attack_mean_rating: number | null; attack_reviews_per_day: number | null; reviewers_overlapping_prior_campaign: number; interpretation: string };

function friendlyError(error: unknown) { return getErrorMessage(error); }

export default function BatchAnalysisPage() {
  const { isLoading: authLoading, isAuthenticated } = useRequireAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [reviewTotal, setReviewTotal] = useState(0);
  const [summary, setSummary] = useState<CampaignSummary | null>(null);
  const [campaignError, setCampaignError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [batch, setBatch] = useState<BatchStatus | null>(null);
  const [batchRows, setBatchRows] = useState<BatchResult[]>([]);
  const [batchTotal, setBatchTotal] = useState(0);
  const [batchOffset, setBatchOffset] = useState(0);
  const [batchLoading, setBatchLoading] = useState(false);
  const [scoringBatch, setScoringBatch] = useState(false);
  const [showUploaded, setShowUploaded] = useState(false);
  const [snapshots, setSnapshots] = useState<Array<{ graph_snapshot_id: number; snapshot_key: string; batch_context_permitted: boolean; context_scope_key: string | null }>>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(null);

  const loadScenario = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true); setLoadError(null); setCampaignError(null);
    let activeCampaign: CampaignSummary;
    try {
      activeCampaign = await apiRequest<CampaignSummary>(`/api/v1/synthetic-campaigns/${CAMPAIGN_KEY}/summary`);
      setSummary(activeCampaign);
    } catch (error) {
      setSummary(null); setCampaignError(friendlyError(error)); setLoadError('Campaign details are needed to scope these reviews to the selected product.');
      setRows([]); setReviewTotal(0); setLoading(false); return;
    }
    try {
      const [reviewResult, reviewerResult, productResult] = await Promise.allSettled([
        apiRequest<Page<Review>>(`/api/v1/reviews?source_system=${DEMO_SOURCE}&product_id=${activeCampaign.product.product_id}&limit=100&offset=0`),
        apiRequest<Page<{ reviewer_id: number; external_reviewer_key: string | null }>>('/api/v1/reviewers?limit=100&offset=0'),
        apiRequest<Page<{ product_id: number; external_product_key: string | null; display_name: string | null }>>('/api/v1/products?limit=100&offset=0'),
      ]);
      if (reviewResult.status === 'rejected') throw reviewResult.reason;
      const firstPage = reviewResult.value;
      const reviewers = reviewerResult.status === 'fulfilled' ? reviewerResult.value : { items: [], total: 0, limit: 100, offset: 0 };
      const products = productResult.status === 'fulfilled' ? productResult.value : { items: [], total: 0, limit: 100, offset: 0 };
      const reviewPages = [firstPage.items || []];
      for (let offset = 100; offset < firstPage.total; offset += 100) {
        const next = await apiRequest<Page<Review>>(`/api/v1/reviews?source_system=${DEMO_SOURCE}&product_id=${activeCampaign.product.product_id}&limit=100&offset=${offset}`);
        reviewPages.push(next.items || []);
      }
      const reviewerNames = new Map(reviewers.items.map(x => [x.reviewer_id, x.external_reviewer_key || `Reviewer ${x.reviewer_id}`]));
      const productNames = new Map(products.items.map(x => [x.product_id, x.display_name || x.external_product_key || `Product ${x.product_id}`]));
      const reviewRows = reviewPages.flat().map(review => ({
        review,
        reviewer: review.reviewer_id == null ? 'Unknown reviewer' : reviewerNames.get(review.reviewer_id) || `Reviewer ${review.reviewer_id}`,
        product: review.product_id === activeCampaign.product.product_id ? activeCampaign.product.name || 'Product name not supplied' : review.product_id == null ? 'Unknown product' : productNames.get(review.product_id) || `Product ${review.product_id}`,
      }));
      setRows(reviewRows); setReviewTotal(firstPage.total);
    } catch (error) {
      setLoadError(friendlyError(error)); setRows([]); setReviewTotal(0);
    } finally { setLoading(false); }
  }, [isAuthenticated]);
  useEffect(() => { void loadScenario(); }, [loadScenario]);

  useEffect(() => {
    if (!isAuthenticated) return;
    apiRequest<{ items: Array<{ graph_snapshot_id: number; snapshot_key: string; batch_context_permitted: boolean; context_scope_key: string | null }> }>('/api/v1/graph-snapshots')
      .then(res => {
        const items = res.items || [];
        setSnapshots(items);
        const permitted = items.find(s => s.batch_context_permitted);
        if (permitted) {
          setSelectedSnapshotId(permitted.graph_snapshot_id);
        }
      })
      .catch(err => {
        console.error('Failed to load snapshots:', err);
      });
  }, [isAuthenticated]);

  const loadBatchPage = useCallback(async (batchId: number, offset: number) => {
    setBatchLoading(true); setUploadError(null);
    try {
      const [status, results] = await Promise.all([
        apiRequest<BatchStatus>(`/api/v1/batch-analyses/${batchId}`),
        apiRequest<Page<BatchResult>>(`/api/v1/batch-analyses/${batchId}/results?limit=${PAGE_SIZE}&offset=${offset}`),
      ]);
      setBatch(status); setBatchRows(results.items || []); setBatchTotal(results.total); setBatchOffset(offset);
    } catch (error) { setUploadError(friendlyError(error)); }
    finally { setBatchLoading(false); }
  }, []);

  const selectFile = (candidate?: File) => {
    if (!candidate) return;
    setUploadError(null); setBatch(null); setBatchRows([]); setBatchTotal(0);
    if (!candidate.name.toLowerCase().endsWith('.csv')) { setFile(null); setUploadError('Choose a .csv file to continue.'); return; }
    setFile(candidate);
  };
  const onFileInput = (event: ChangeEvent<HTMLInputElement>) => selectFile(event.target.files?.[0]);
  const onDrop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); setDragging(false); selectFile(event.dataTransfer.files?.[0]); };

  const uploadCsv = async () => {
    if (!file) return;
    setUploading(true); setUploadError(null); setBatch(null); setBatchRows([]); setShowUploaded(true);
    try {
      const form = new FormData(); form.append('file', file);
      form.append('source_system', `csv-${file.name.replace(/[^a-zA-Z0-9_-]/g, '-').slice(0, 80)}`);
      if (selectedSnapshotId) {
        form.append('historic_graph_snapshot_id', String(selectedSnapshotId));
      }
      const created = await apiRequest<BatchStatus>('/api/v1/batch-analyses', { method: 'POST', body: form });
      setBatch(created); await loadBatchPage(created.batch_analysis_id, 0);
    } catch (error) { setUploadError(friendlyError(error)); }
    finally { setUploading(false); }
  };

  const scoreBatch = async (batchId: number) => {
    setScoringBatch(true); setUploadError(null);
    try {
      await apiRequest(`/api/v1/batch-analyses/${batchId}/score`, { method: 'POST' });
      await loadBatchPage(batchId, 0);
    } catch (err) {
      setUploadError(friendlyError(err));
    } finally {
      setScoringBatch(false);
    }
  };

  const lowRatedCount = useMemo(() => rows.filter(x => x.review.rating === 1).length, [rows]);
  const meanRating = useMemo(() => {
    const rated = rows.filter(x => typeof x.review.rating === 'number');
    return rated.length ? rated.reduce((sum, x) => sum + (x.review.rating || 0), 0) / rated.length : null;
  }, [rows]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return rows.filter(({ review, reviewer, product }) => !needle || [review.source_review_key, review.review_text, String(review.review_id), reviewer, product].some(v => (v || '').toLowerCase().includes(needle)));
  }, [rows, query]);
  const pageRows = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  if (authLoading) return <AppShell><div className="workspace-notice">Checking session…</div></AppShell>;
  if (!isAuthenticated) return null;
  return <AppShell>
    <header className="page-heading"><div><p className="eyebrow">Workspace / Intake</p><h1>Batch analysis</h1><p className="page-subtitle">Upload review records, inspect validation, and browse persisted synthetic product scenario evidence.</p></div><button className="button-secondary" onClick={() => void loadScenario()} disabled={loading}>Refresh data</button></header>
    <div className="provenance-banner"><span className="provenance-mark" aria-hidden="true"/>SYNTHETIC DEMO DATA <span>— scenario reviews and evidence; no model scores</span></div>
    <div className="batch-layout">
      <section className="panel upload-panel"><div className="panel-title"><div><p className="eyebrow">CSV intake</p><h2>Upload a review batch</h2></div><p>Required columns: review_id, reviewer_id, product_id, rating, review_date, review_text</p></div>
        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="snapshot-select" style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted, #4b5563)', marginBottom: '0.25rem' }}>
            Historical Graph Context Snapshot (Optional for Inductive Scoring)
          </label>
          <select
            id="snapshot-select"
            value={selectedSnapshotId ?? ''}
            onChange={e => setSelectedSnapshotId(e.target.value ? Number(e.target.value) : null)}
            style={{
              width: '100%',
              padding: '0.45rem 0.6rem',
              borderRadius: '0.375rem',
              border: '1px solid var(--border-color, #e5e7eb)',
              backgroundColor: 'var(--bg-input, #fff)',
              fontSize: '0.8125rem',
              color: 'var(--text-color, #111827)',
            }}
          >
            <option value="">None (Intake validation only · scoring ineligible)</option>
            {snapshots.map(s => (
              <option key={s.graph_snapshot_id} value={s.graph_snapshot_id}>
                Snapshot #{s.graph_snapshot_id} ({s.snapshot_key}) {s.batch_context_permitted ? `[Context Permitted: ${s.context_scope_key || 'yes'}]` : '[Ineligible]'}
              </option>
            ))}
          </select>
        </div>
        <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={onFileInput}/>
        <div role="button" tabIndex={0} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }} onClick={() => inputRef.current?.click()} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop} className={`dropzone ${dragging ? 'dropzone-active' : ''}`}>
          <span className="upload-glyph" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 16V4m0 0L7 9m5-5 5 5M5 15v5h14v-5"/></svg></span><strong>Drop a CSV here or <span>browse files</span></strong><small>Each row is validated and stored before scoring is considered.</small>
          {file && <em>{file.name} · {(file.size / 1024).toFixed(1)} KB</em>}
        </div>
        <div className="upload-footer"><p>{selectedSnapshotId ? 'Selected snapshot enables inductive temporal graph scoring upon successful intake.' : 'Scoring remains unavailable until a compatible verified model runtime and snapshot are selected.'}</p><button className="button-primary" onClick={() => void uploadCsv()} disabled={!file || uploading}>{uploading ? 'Validating…' : 'Validate & upload'}</button></div>
        {uploadError && <div className="inline-error" role="alert"><strong>Batch request failed</strong><p>{uploadError}</p></div>}
        {batch && <div className="validation-preview"><div className="preview-heading"><h3>Validation preview · Batch #{batch.batch_analysis_id}</h3><span className="subtle-tag">{batch.status}</span></div>
          <div className="validation-counts"><ValidationCount label="Rows" value={batch.row_count}/><ValidationCount label="Accepted" value={batch.accepted_count}/><ValidationCount label="Rejected" value={batch.rejected_count}/></div>
          <div className="progress-timeline"><TimelineStep label="Uploaded" active/><i/><TimelineStep label="Validated" active={batch.status === 'blocked' || batch.status === 'validation_failed' || batch.status === 'queued' || batch.status === 'completed'}/><i/><TimelineStep label={batch.status === 'queued' ? 'Queued for scoring' : batch.status === 'completed' ? 'Scored' : 'Scoring unavailable'} active={batch.status === 'queued' || batch.status === 'completed'}/></div>
          {batch.status === 'queued' && (
            <div style={{ marginTop: '0.875rem', padding: '0.75rem', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '0.375rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
              <div>
                <strong style={{ fontSize: '0.8125rem', color: '#166534', display: 'block' }}>Inductive Scoring Queued</strong>
                <span style={{ fontSize: '0.75rem', color: '#15803d' }}>Ready for temporal relation graph stitching and RoBERTa-GNN evaluation.</span>
              </div>
              <button
                className="button-primary"
                onClick={() => void scoreBatch(batch.batch_analysis_id)}
                disabled={scoringBatch}
                style={{ whiteSpace: 'nowrap', fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
              >
                {scoringBatch ? 'Processing…' : 'Process now'}
              </button>
            </div>
          )}
          {batch.blocking_reasons?.length > 0 && <p className="blocking-note">Scoring blocked: {batch.blocking_reasons.join(', ')}</p>}
          <div className="validation-list">{batchLoading ? <p>Loading row results…</p> : batchRows.map(row => <div className="validation-row" key={row.row_number}><strong>Row {row.row_number}</strong><span className={row.row_state === 'accepted' ? 'accepted-state' : 'rejected-state'}>{row.row_state}</span><p>{row.validation_errors.length ? row.validation_errors.map(x => x.message || x.field || x.code).join(' · ') : row.uploaded_review_key || 'Accepted without validation errors'}</p></div>)}</div>
        </div>}
      </section>
      <section className="panel scenario-panel"><div className="panel-title"><div><p className="eyebrow">Persisted scenario</p><h2>{summary?.campaign_name || 'Product review evidence'}</h2></div><Link className="text-action" href={`/campaigns/${CAMPAIGN_KEY}`}>Investigate <span aria-hidden="true">→</span></Link></div>
        <div className="scenario-metrics"><ScenarioMetric label="Synthetic reviews" value={loading ? '…' : reviewTotal.toLocaleString()} note="Rows returned by review API"/><ScenarioMetric label="One-star ratings" value={loading ? '…' : (summary?.one_star_review_count ?? lowRatedCount).toLocaleString()} note="Review rating; not a fraud decision"/><ScenarioMetric label="Mean rating" value={loading ? '…' : (summary?.attack_mean_rating ?? meanRating)?.toFixed(2) ?? '—'} note={summary ? 'Campaign attack window · out of 5' : 'Available from loaded review rows · out of 5'}/></div>
        {summary ? <div className="scenario-facts"><div><span>Product</span><strong>{summary.product.name || 'Name not supplied'}</strong></div><div><span>Attack window</span><strong>{dateRange(summary.attack_window.start, summary.attack_window.end)}</strong></div><div><span>Reviewers</span><strong>{summary.distinct_attack_reviewers}</strong></div><div><span>Prior campaign overlap</span><strong>{summary.reviewers_overlapping_prior_campaign}</strong></div></div> : campaignError && <div className="inline-error migration-hint"><strong>Campaign analytics did not load</strong><p>{campaignError}</p><small>If migrations were recently added, from <code>backend/</code> run <code>alembic upgrade head</code>, then restart the API. The review list can still load independently.</small></div>}
        {loadError && <div className="inline-error" role="alert"><strong>Review records did not load</strong><p>{loadError}</p></div>}
        {loading && <div className="loading-line">Loading synthetic review records…</div>}
        <p className="scenario-caveat">Review counts and ratings come from PostgreSQL-backed API records. No risk score or attention value is generated here.</p>
      </section>
    </div>
    <div style={{ marginTop: '1.5rem', marginBottom: '1.5rem' }}>
      <InductiveBatchSection initialBatchId={batch?.batch_analysis_id} showHeading={false} />
    </div>

    <section className="panel results-panel"><div className="results-heading"><div><p className="eyebrow">Source records</p><h2>{showUploaded ? 'Uploaded batch results' : 'Product review history'}</h2><p>{showUploaded ? 'Accepted and rejected rows from the batch API.' : 'Persisted synthetic_demo reviews. Decisions and model scores are not available for this scenario.'}</p></div><div className="results-controls"><div className="segmented-control"><button className={!showUploaded ? 'selected' : ''} onClick={() => setShowUploaded(false)}>Scenario reviews</button><button className={showUploaded ? 'selected' : ''} onClick={() => setShowUploaded(true)} disabled={!batch}>Uploaded batch</button></div>{!showUploaded && <input className="search-input" value={query} onChange={e => { setQuery(e.target.value); setPage(0); }} placeholder="Search reviews…" aria-label="Search reviews"/>}</div></div>
      {showUploaded ? batch ? batchLoading ? <div className="empty-records">Loading uploaded rows…</div> : <ReviewTable rows={batchRows.map(result => ({ review: result.review, rowState: result.row_state, key: result.uploaded_review_key, errors: result.validation_errors }))}/>:<div className="empty-records">Upload a CSV to inspect its accepted and rejected rows.</div> : loading ? <div className="empty-records">Loading reviews…</div> : loadError ? <div className="empty-records">The review endpoint returned an error. Refresh after the backend issue is resolved.</div> : pageRows.length ? <ReviewTable rows={pageRows.map(({ review }) => ({ review, rowState: 'persisted', key: review.source_review_key, errors: [] }))}/> : <div className="empty-records">No matching synthetic review records were returned by the API.</div>}
      {!showUploaded && !loading && !loadError && <div className="table-pagination"><span>{filtered.length.toLocaleString()} of {reviewTotal.toLocaleString()} reviews</span><div><button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}>Previous</button><button onClick={() => setPage(page + 1)} disabled={(page + 1) * PAGE_SIZE >= filtered.length}>Next</button></div></div>}
      {showUploaded && batch && <div className="table-pagination"><span>{batchTotal.toLocaleString()} submitted rows · stored batch #{batch.batch_analysis_id}</span><div><button onClick={() => void loadBatchPage(batch.batch_analysis_id, Math.max(0, batchOffset - PAGE_SIZE))} disabled={batchOffset === 0}>Previous</button><button onClick={() => void loadBatchPage(batch.batch_analysis_id, batchOffset + PAGE_SIZE)} disabled={batchOffset + PAGE_SIZE >= batchTotal}>Next</button></div></div>}
    </section>
  </AppShell>;
}

function dateRange(a: string, b: string) { return `${new Date(a).toLocaleDateString()} – ${new Date(b).toLocaleDateString()}`; }
function ScenarioMetric({ label, value, note }: { label: string; value: string; note: string }) { return <article className="scenario-metric"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>; }
function ValidationCount({ label, value }: { label: string; value: number }) { return <div><strong>{value.toLocaleString()}</strong><span>{label}</span></div>; }
function TimelineStep({ label, active }: { label: string; active: boolean }) { return <span className={active ? 'timeline-active' : ''}><i/>{label}</span>; }
function ReviewTable({ rows }: { rows: Array<{ review: Review | null; rowState: string; key: string | null; errors: Array<{ message?: string; field?: string; code?: string }> }> }) {
  return <div className="table-scroll"><table className="evidence-table"><thead><tr><th>Review</th><th>Reviewer ID</th><th>Product ID</th><th>Date</th><th>Rating</th><th>Record status</th></tr></thead><tbody>{rows.map((row, i) => <tr key={`${row.key || row.review?.review_id || 'row'}-${i}`}><td className="review-text-cell"><strong>{row.key || (row.review ? `Review #${row.review.review_id}` : 'Review key not supplied')}</strong><p>{row.review?.review_text || row.errors.map(x => x.message || x.field || x.code).join(' · ') || 'Review text not supplied'}</p></td><td>{row.review?.reviewer_id ?? '—'}</td><td>{row.review?.product_id ?? '—'}</td><td>{row.review?.reviewed_at ? new Date(row.review.reviewed_at).toLocaleDateString() : '—'}</td><td>{row.review?.rating == null ? '—' : `${row.review.rating} / 5`}</td><td><span className={row.rowState === 'rejected' ? 'rejected-pill' : row.review ? 'stored-pill' : 'rejected-pill'}>{row.rowState}</span></td></tr>)}</tbody></table></div>;
}
