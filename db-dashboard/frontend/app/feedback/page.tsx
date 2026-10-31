'use client';

import { FormEvent, useCallback, useEffect, useState, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import AppShell from '../components/AppShell';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useAuth } from '../context/AuthContext';
import { apiRequest, getErrorMessage } from '../lib/api';

type Feedback = { feedback_id: number; review_id: number; submitted_by_user_id: number; feedback_type: string; ground_truth_label: number | null; comment: string; status: string; created_at: string };
type Review = { review_id: number; review_text?: string; rating?: number };
const blank = { review_id: '', feedback_type: 'review_quality', ground_truth_label: '', comment: '' };

function FeedbackContent() {
  const searchParams = useSearchParams();
  const batchParam = searchParams.get('batch_id') || '';
  const backToBatch = /^[1-9]\d*$/.test(batchParam) ? batchParam : null;
  const { isLoading, isAuthenticated, isAdmin } = useRequireAuth();
  const { user } = useAuth();
  const [items, setItems] = useState<Feedback[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [form, setForm] = useState(blank);
  const [editing, setEditing] = useState<number | null>(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [summary, setSummary] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    const reviewId = searchParams.get('review_id') || '';
    if (/^[1-9]\d*$/.test(reviewId)) setForm(current => ({...current, review_id: reviewId}));
  }, [searchParams]);

  const load = useCallback(async () => {
    try {
      const data = await apiRequest<{items: Feedback[]; total: number}>(`/api/v1/feedback?limit=10&offset=${offset}&q=${encodeURIComponent(query)}${status ? `&status=${status}` : ''}`);
      setItems(data.items); setTotal(data.total);
    } catch (e) { setError(getErrorMessage(e)); }
  }, [offset, query, status]);
  useEffect(() => { if (isAuthenticated && !isLoading) void load(); }, [isAuthenticated, isLoading, load]);
  useEffect(() => {
    if (!isAuthenticated || isLoading) return;
    void apiRequest<{items: Review[]}>('/api/v1/reviews?limit=100').then(d => setReviews(d.items)).catch(e => setError(getErrorMessage(e)));
    if (isAdmin) void apiRequest<Record<string, number>>('/api/v1/database/summary').then(setSummary).catch(e => setError(getErrorMessage(e)));
  }, [isAuthenticated, isLoading, isAdmin]);

  async function mutate(operation: () => Promise<unknown>, message: string) {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); setNotice(message); await load(); return true; }
    catch (e) { setError(getErrorMessage(e)); return false; }
    finally { setBusy(false); }
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    const body = { ...form, review_id: Number(form.review_id), ground_truth_label: form.ground_truth_label === '' ? null : Number(form.ground_truth_label) };
    if (await mutate(() => apiRequest(`/api/v1/feedback${editing ? `/${editing}` : ''}`, { method: editing ? 'PATCH' : 'POST', body: JSON.stringify(body) }), 'Feedback saved. Model predictions remain unchanged.')) { setForm(blank); setEditing(null); }
  }
  if (isLoading || !isAuthenticated) return <div className="loading-workspace">Loading workspace...</div>;
  return <AppShell>
    {backToBatch && <Link className="back-link" href={`/products/${backToBatch}`}>← Back to saved analysis #{backToBatch}</Link>}
    <header className="page-header"><div><p className="eyebrow">HUMAN REVIEW</p><h1>Review feedback</h1><p>Record an investigation note or a proposed label correction. Feedback does not change saved model scores or retrain the model.</p></div></header>
    {error && <p role="alert" className="feedback-error">{error}</p>}
    {notice && <p role="status" className="feedback-notice">{notice}</p>}
    {summary && <p className="feedback-notice">Database views: {summary.batches} uploads, {summary.scored} saved predictions, {summary.products} products and {summary.reviews} reviews. These totals include all users and reference data.</p>}
    <section className="feedback-panel"><h2>{editing ? 'Edit submitted feedback' : 'Add feedback'}</h2>
      <form onSubmit={save} className="feedback-form">
        <label>Review ID <input required type="number" min="1" list="review-ids" disabled={editing !== null} value={form.review_id} onChange={e => setForm({...form, review_id: e.target.value})}/><datalist id="review-ids">{reviews.map(r => <option key={r.review_id} value={r.review_id}>Rating {r.rating ?? '-'} · {r.review_text?.slice(0, 80)}</option>)}</datalist><small>Use an ID from Review records or a saved analysis. Suggestions show up to 100 visible reviews.</small></label>
        <label>Feedback type<select value={form.feedback_type} onChange={e => setForm({...form, feedback_type: e.target.value})}><option value="review_quality">Review quality</option><option value="label_correction">Proposed label correction</option><option value="other">Other investigation note</option></select></label>
        <label>Proposed label<select value={form.ground_truth_label} onChange={e => setForm({...form, ground_truth_label: e.target.value})}><option value="">No label proposed</option><option value="0">0 · Genuine review</option><option value="1">1 · Suspected spam</option></select></label>
        <label className="feedback-wide">Investigation note<textarea required minLength={3} maxLength={2000} rows={3} value={form.comment} onChange={e => setForm({...form, comment: e.target.value})}/></label>
        <div className="feedback-wide"><button className="button-primary" disabled={busy}>{busy ? 'Saving...' : editing ? 'Save changes' : 'Submit feedback'}</button>{editing && <button type="button" className="button-secondary" onClick={() => {setEditing(null); setForm(blank);}}>Cancel edit</button>}</div>
      </form>
    </section>
    <section className="feedback-panel"><h2>{isAdmin ? 'Feedback moderation' : 'Your feedback history'}</h2>
      <div className="feedback-filters"><label>Search notes<input type="search" value={query} onChange={e => {setQuery(e.target.value); setOffset(0);}}/></label><label>Status<select value={status} onChange={e => {setStatus(e.target.value); setOffset(0);}}><option value="">All statuses</option>{['submitted','triaged','resolved','rejected'].map(s => <option key={s}>{s}</option>)}</select></label><button className="button-secondary" onClick={load}>Refresh</button></div>
      {!items.length && <p>No matching feedback yet.</p>}
      {items.map(item => <article className="feedback-item" key={item.feedback_id}><div><strong>Review #{item.review_id} · {item.feedback_type.replaceAll('_',' ')}</strong><span className="feedback-status">{item.status}</span></div><p>{item.comment}</p><small>{new Date(item.created_at).toLocaleString()} · Proposed label: {item.ground_truth_label ?? 'none'}</small><div className="feedback-actions">
        {item.status === 'submitted' && item.submitted_by_user_id === user?.user_id && <><button className="button-secondary" disabled={busy} onClick={() => {setEditing(item.feedback_id); setForm({review_id: String(item.review_id), feedback_type: item.feedback_type, ground_truth_label: item.ground_truth_label === null ? '' : String(item.ground_truth_label), comment: item.comment}); window.scrollTo({top:0, behavior:'smooth'});}}>Edit</button><button className="button-secondary" disabled={busy} onClick={() => mutate(() => apiRequest(`/api/v1/feedback/${item.feedback_id}`, {method:'DELETE'}), 'Feedback removed; its database audit record is retained.')}>Remove</button></>}
        {isAdmin && ['triaged','resolved','rejected'].filter(s => s !== item.status).map(s => <button className="button-secondary" disabled={busy} key={s} onClick={() => mutate(() => apiRequest(`/api/v1/feedback/${item.feedback_id}/resolve`, {method:'POST', body:JSON.stringify({status:s})}), `Feedback marked ${s}.`)}>Mark {s}</button>)}
      </div></article>)}
      <div className="feedback-actions"><button disabled={!offset} className="button-secondary" onClick={() => setOffset(Math.max(0,offset-10))}>Previous</button><span>{total ? `${offset+1}-${Math.min(offset+10,total)} of ${total}` : '0 results'}</span><button disabled={offset+10 >= total} className="button-secondary" onClick={() => setOffset(offset+10)}>Next</button></div>
    </section>
  </AppShell>;
}

export default function FeedbackPage() {
  return <Suspense fallback={<div className="session-loading">Loading feedback…</div>}><FeedbackContent/></Suspense>;
}
