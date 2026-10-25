'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import AppShell from '../../components/AppShell';
import { useRequireAuth } from '../../hooks/useRequireAuth';
import { apiRequest, getErrorMessage } from '../../lib/api';

type Summary = { campaign_key: string; campaign_name: string; provenance: string; product: { name: string | null }; attack_window: { start: string; end: string }; comparison_window: { start: string; end: string }; attack_review_count: number; distinct_attack_reviewers: number; one_star_review_count: number; attack_mean_rating: number | null; attack_reviews_per_day: number | null; comparison_review_count: number; campaign_member_count: number; reviewers_overlapping_prior_campaign: number; linked_prior_campaign_key: string | null; description: string; interpretation: string };
type Member = { reviewer_id: number; external_reviewer_key: string; membership_type: string; provenance: string; evidence: { attack_review_count: number; attack_one_star_count: number; attack_review_keys: Array<string | null>; attack_review_times: Array<string | null>; attack_review_ratings: Array<number | null>; attack_review_texts: Array<string | null>; overlapped_prior_campaign: boolean; prior_review_count: number; prior_review_keys: Array<string | null>; prior_review_times: Array<string | null>; prior_review_ratings: Array<number | null>; evidence_notes: string[]; source: string } };
type Members = { provenance: string; items: Member[]; total: number };
type GraphNode = { labels: string[]; key: string; provenance: string; name?: string; campaign_name?: string; campaign_key?: string; external_reviewer_key?: string; source_review_key?: string; rating?: number; reviewed_at?: string; review_text?: string };
type GraphRel = { type: string; source_key: string; target_key: string; provenance: string };
type Graph = { provenance: string; source: string; model_inference_used: boolean; nodes: GraphNode[]; relationships: GraphRel[] };

const lane = (n: GraphNode) => {
  const matched = n.labels.find(x => ['Campaign', 'Reviewer', 'Review', 'Restaurant', 'Product'].includes(x));
  if (matched === 'Restaurant') return 'Product';
  return matched || 'Other';
};
const displayNode = (n: GraphNode) => n.name || n.campaign_name || n.external_reviewer_key || n.source_review_key || n.labels[0] || 'Node';

function CampaignGraph({ graph }: { graph: Graph }) {
  const lanes = ['Campaign', 'Reviewer', 'Review', 'Product'];
  const grouped = lanes.map(name => graph.nodes.filter(n => lane(n) === name));
  const rowGap = 50, height = Math.max(450, ...grouped.map(x => x.length * rowGap + 100));
  const xs = [110, 350, 600, 850];
  const positions = new Map<string, { x: number; y: number }>();
  grouped.forEach((nodes, i) => nodes.forEach((node, j) => positions.set(node.key, { x: xs[i], y: 58 + j * rowGap })));
  const kind = new Map(graph.nodes.map(n => [n.key, lane(n)]));
  const colors: Record<string, string> = { Campaign: '#d97706', Reviewer: '#0f766e', Review: '#64748b', Product: '#164e63', Restaurant: '#164e63' };
  return <div className="graph-scroll"><svg viewBox={`0 0 960 ${height}`} className="campaign-graph" role="img" aria-label="Synthetic campaign relationship graph">
    {graph.relationships.map((r, i) => { const a = positions.get(r.source_key), b = positions.get(r.target_key); if (!a || !b) return null; return <line key={`${r.type}-${i}`} x1={a.x + 45} y1={a.y} x2={b.x - 45} y2={b.y} className="graph-edge"><title>{r.type}</title></line>; })}
    {lanes.map((name, i) => <text key={name} x={xs[i]} y="24" textAnchor="middle" className="graph-lane">{name}</text>)}
    {graph.nodes.map(n => { const p = positions.get(n.key); if (!p) return null; const k = kind.get(n.key) || 'Other'; return <g key={n.key} transform={`translate(${p.x},${p.y})`}><circle r="11" fill={colors[k] || '#64748b'} stroke="#fff" strokeWidth="3"/><text x="17" y="4" className="graph-node-label">{displayNode(n).slice(0, 32)}</text><title>{`${k}: ${displayNode(n)}${n.rating != null ? ` · ${n.rating} stars` : ''}`}</title></g>; })}
  </svg></div>;
}

export default function CampaignInvestigationPage() {
  const params = useParams<{ campaignKey: string }>();
  const campaignKey = decodeURIComponent(params.campaignKey);
  const { user, isLoading: authLoading, isAuthenticated } = useRequireAuth();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [members, setMembers] = useState<Members | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    setLoading(true); setError(null); setGraphError(null);
    const base = `/api/v1/synthetic-campaigns/${encodeURIComponent(campaignKey)}`;
    try {
      const [s, m] = await Promise.all([apiRequest<Summary>(`${base}/summary`), apiRequest<Members>(`${base}/members?limit=100&offset=0`)]);
      setSummary(s); setMembers(m);
      try { setGraph(await apiRequest<Graph>(`${base}/graph`)); }
      catch (e) { setGraph(null); setGraphError(getErrorMessage(e)); }
    } catch (e) { setError(getErrorMessage(e)); setSummary(null); setMembers(null); }
    finally { setLoading(false); }
  }, [campaignKey]);
  useEffect(() => { if (isAuthenticated && campaignKey) void refresh(); }, [isAuthenticated, campaignKey, refresh]);

  const linkedReviews = useMemo(() => (members?.items || []).flatMap(member => member.evidence.attack_review_keys.map((key, i) => ({
    key: key || `${member.reviewer_id}-${i}`, reviewer: member.external_reviewer_key,
    time: member.evidence.attack_review_times[i], rating: member.evidence.attack_review_ratings[i],
    text: member.evidence.attack_review_texts[i],
  }))), [members]);
  if (authLoading || !user) return <div className="session-loading">Loading workspace…</div>;
  return <AppShell>
    <header className="page-heading"><div><Link className="back-link inline-flex items-center gap-1" href="/"><ArrowLeft className="h-3 w-3" /> Risk overview</Link><p className="eyebrow">Campaign investigation</p><h1>{summary?.campaign_name || 'Campaign evidence'}</h1><p className="page-subtitle">{summary?.product.name || 'Product details load from the campaign API'}</p></div><button className="button-secondary" onClick={refresh} disabled={loading}>Refresh evidence</button></header>
    <div className="provenance-banner"><span className="provenance-mark" aria-hidden="true" />SYNTHETIC DEMO DATA <span>— not model output</span></div>
    {loading && <div className="notice-card">Loading campaign records and graph projection…</div>}
    {!loading && error && <div className="notice-card notice-error"><strong>Campaign evidence unavailable</strong><p>{error}</p><button className="text-action" onClick={refresh}>Try again</button></div>}
    {!loading && summary && members && <>
      <section className="campaign-summary panel"><div><p className="eyebrow">Scenario summary</p><h2>{summary.campaign_name}</h2><p className="muted">{summary.description}</p><p className="muted">{summary.interpretation}</p></div><div className="summary-tags"><span className="risk-tag">{summary.attack_review_count.toLocaleString()} linked reviews</span><span className="subtle-tag">{summary.provenance}</span></div></section>
      <section className="investigation-kpis"><Metric label="Attack window" value={`${date(summary.attack_window.start)} – ${date(summary.attack_window.end)}`} detail={`${summary.attack_reviews_per_day == null ? '—' : summary.attack_reviews_per_day.toFixed(2)} reviews per day`}/><Metric label="Rating evidence" value={summary.attack_mean_rating == null ? '—' : `${summary.attack_mean_rating.toFixed(2)} / 5`} detail={`${summary.one_star_review_count.toLocaleString()} one-star reviews`}/><Metric label="Reviewer overlap" value={summary.reviewers_overlapping_prior_campaign.toLocaleString()} detail={summary.linked_prior_campaign_key ? `Shared with ${summary.linked_prior_campaign_key}` : 'Prior campaign link not supplied'}/><Metric label="Campaign members" value={summary.campaign_member_count.toLocaleString()} detail={`${summary.distinct_attack_reviewers.toLocaleString()} reviewers with attack reviews`}/></section>
      <section className="panel"><PanelTitle kicker="Relationship evidence" title="Campaign graph" detail="Read-only Neo4j projection · synthetic scenario records"/>
        {graph ? <><div className="graph-meta"><span>{graph.nodes.length} nodes</span><span>{graph.relationships.length} relationships</span><span>{graph.source}</span><span>{graph.model_inference_used ? 'Model inference used' : 'No model inference used'}</span></div><CampaignGraph graph={graph}/></> : <div className="graph-unavailable"><strong>Graph projection unavailable</strong><p>{graphError || 'The graph API did not return a projection.'}</p><span>PostgreSQL campaign evidence below remains API-backed.</span></div>}
      </section>
      <section className="evidence-grid">
        <EvidencePanel title="Timing" value={`${summary.attack_review_count.toLocaleString()} reviews`} detail={`${summary.attack_window.start} through ${summary.attack_window.end}. The API reports ${summary.attack_reviews_per_day == null ? '—' : summary.attack_reviews_per_day.toFixed(2)} reviews per day in the attack window.`}/>
        <EvidencePanel title="Rating pattern" value={`${summary.one_star_review_count.toLocaleString()} one-star`} detail={`Mean attack-window rating: ${summary.attack_mean_rating == null ? '—' : summary.attack_mean_rating.toFixed(2)} / 5. These are stored review ratings, not predictions.`}/>
        <EvidencePanel title="Text evidence" value={`${linkedReviews.filter(r => Boolean(r.text)).length.toLocaleString()} review texts`} detail="Review text is shown directly from the persisted campaign member response; no similarity score is inferred in the UI."/>
        <EvidencePanel title="Reviewer overlap" value={`${summary.reviewers_overlapping_prior_campaign.toLocaleString()} shared reviewers`} detail={summary.linked_prior_campaign_key ? `The campaign API links this evidence to ${summary.linked_prior_campaign_key}.` : 'No prior campaign key was supplied by the API.'}/>
      </section>
      <section className="panel reviews-panel"><PanelTitle kicker="Persisted source records" title="Linked reviews" detail={`${linkedReviews.length.toLocaleString()} review rows returned in the current member page`}/>
        {linkedReviews.length ? <div className="table-scroll"><table className="evidence-table"><thead><tr><th>Review</th><th>Reviewer</th><th>Time</th><th>Rating</th><th>Text</th></tr></thead><tbody>{linkedReviews.map((r, i) => <tr key={`${r.key}-${i}`}><td className="mono-cell">{r.key}</td><td>{r.reviewer}</td><td>{r.time ? new Date(r.time).toLocaleString() : '—'}</td><td><span className={r.rating === 1 ? 'rating-risk' : ''}>{r.rating == null ? '—' : `${r.rating} / 5`}</span></td><td className="review-text-cell">{r.text || 'Review text not supplied'}</td></tr>)}</tbody></table></div> : <div className="empty-records">No linked review rows were returned by the campaign members endpoint.</div>}
        {members.total > members.items.length && <p className="table-footnote">Showing linked reviews associated with {members.items.length} returned campaign members; the API reports {members.total} members total.</p>}
      </section>
    </>}
  </AppShell>;
}

function date(s?: string) { return s ? new Date(s).toLocaleDateString() : '—'; }
function Metric({ label, value, detail }: { label: string; value: string; detail: string }) { return <article className="metric-card"><p>{label}</p><div><strong className="compact-metric">{value}</strong></div><small>{detail}</small></article>; }
function PanelTitle({ kicker, title, detail }: { kicker: string; title: string; detail: string }) { return <div className="panel-title"><div><p className="eyebrow">{kicker}</p><h2>{title}</h2></div><p>{detail}</p></div>; }
function EvidencePanel({ title, value, detail }: { title: string; value: string; detail: string }) { return <article className="panel evidence-detail"><p className="eyebrow">Evidence</p><h3>{title}</h3><strong>{value}</strong><p>{detail}</p></article>; }
