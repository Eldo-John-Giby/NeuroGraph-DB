'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  Cell,
} from 'recharts';
import { ArrowUpRight, ArrowRight } from 'lucide-react';
import AppShell from '../components/AppShell';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { apiRequest, getErrorMessage } from '../lib/api';

const CAMPAIGN_KEY = 'harbor-table-review-bombing-seed-42';
type Summary = { campaign_key: string; campaign_name: string; provenance: string; product: { product_id: number; name: string | null }; attack_window: { start: string; end: string }; comparison_window: { start: string; end: string }; attack_review_count: number; distinct_attack_reviewers: number; one_star_review_count: number; attack_mean_rating: number | null; attack_reviews_per_day: number | null; comparison_review_count: number; campaign_member_count: number; reviewers_overlapping_prior_campaign: number; linked_prior_campaign_key: string | null; interpretation: string };
type Timeline = { provenance: string; items: Array<{ day: string; review_count: number; observed_mean_rating: number | null }> };
type Comparison = { provenance: string; observed_attack_window: { review_count: number; mean_rating: number | null }; scenario_adjusted_attack_window: { review_count: number; mean_rating: number | null }; comparison_window: { review_count: number; mean_rating: number | null }; formula: string };
type Volume = { provenance: string; comparison_review_count: number; attack_review_count: number; comparison_reviews_per_day: number; attack_reviews_per_day: number; attack_to_comparison_daily_volume_ratio: number | null; items: Array<{ day: string; period: string; review_count: number; mean_rating: number | null }> };

function RatingTimeline({ items }: { items: Timeline['items'] }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const data = useMemo(
    () =>
      items
        .filter((x) => x.observed_mean_rating !== null)
        .map((x) => ({
          day: x.day,
          shortDay: x.day.slice(5),
          rating: Number(x.observed_mean_rating),
          review_count: x.review_count,
        })),
    [items]
  );

  if (!data.length) return <ChartEmpty />;
  if (!mounted) return <div className="h-[210px] w-full animate-pulse bg-[#f9faf7] rounded" />;

  return (
    <div className="w-full h-[210px] pt-1">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: -22, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#edf0eb" strokeDasharray="3 3" />
          <XAxis
            dataKey="shortDay"
            stroke="#b8c2bc"
            tick={{ fill: '#77827d', fontSize: 9 }}
            tickLine={false}
            axisLine={{ stroke: '#e2e5df' }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[1, 5]}
            ticks={[1, 2, 3, 4, 5]}
            stroke="#b8c2bc"
            tick={{ fill: '#77827d', fontSize: 9 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const d = payload[0].payload;
                return (
                  <div className="rounded-md border border-[#e2e5df] bg-[#fffefa] px-2.5 py-1.5 shadow-sm text-xs">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-[#74817b]">{d.day}</div>
                    <div className="text-[#12685f] font-bold text-sm mt-0.5">
                      {d.rating.toFixed(2)} <span className="text-[10px] font-normal text-[#839089]">/ 5</span>
                    </div>
                    <div className="text-[#839089] text-[10px] mt-0.5">
                      {d.review_count} {d.review_count === 1 ? 'review' : 'reviews'}
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
          <Line
            type="monotone"
            dataKey="rating"
            stroke="#12685f"
            strokeWidth={2.4}
            dot={{ r: 3, fill: '#12685f', stroke: '#fffefa', strokeWidth: 1.5 }}
            activeDot={{ r: 5, fill: '#0b514a', stroke: '#fffefa', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function VolumeChart({ items }: { items: Volume['items'] }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const data = useMemo(
    () =>
      items.map((x) => ({
        day: x.day,
        shortDay: x.day.slice(5),
        review_count: x.review_count,
        period: x.period,
        mean_rating: x.mean_rating,
      })),
    [items]
  );

  if (!items.length) return <ChartEmpty />;
  if (!mounted) return <div className="h-[210px] w-full animate-pulse bg-[#f9faf7] rounded" />;

  return (
    <div className="w-full h-[210px] pt-1">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, left: -22, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#edf0eb" strokeDasharray="3 3" />
          <XAxis
            dataKey="shortDay"
            stroke="#b8c2bc"
            tick={{ fill: '#77827d', fontSize: 9 }}
            tickLine={false}
            axisLine={{ stroke: '#e2e5df' }}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke="#b8c2bc"
            tick={{ fill: '#77827d', fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const d = payload[0].payload;
                const isAttack = d.period === 'attack';
                return (
                  <div className="rounded-md border border-[#e2e5df] bg-[#fffefa] px-2.5 py-1.5 shadow-sm text-xs">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-[#74817b]">{d.day}</div>
                    <div className={`font-bold text-sm mt-0.5 ${isAttack ? 'text-[#c66b30]' : 'text-[#1e2927]'}`}>
                      {d.review_count} <span className="text-[10px] font-normal text-[#839089]">{d.review_count === 1 ? 'review' : 'reviews'}</span>
                    </div>
                    <div className="text-[10px] mt-0.5 capitalize text-[#839089]">
                      {isAttack ? 'Attack window' : 'Comparison period'}
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
          <Bar dataKey="review_count" radius={[5, 5, 0, 0]} maxBarSize={16}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.period === 'attack' ? '#c66b30' : '#88a39b'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartEmpty() { return <div className="chart-empty">No chart observations were returned for this scenario.</div>; }
function formatRating(n: number | null | undefined) { return n == null ? '—' : n.toFixed(2); }
function dateRange(start?: string, end?: string) { if (!start || !end) return 'Dates not supplied'; return `${new Date(start).toLocaleDateString()} – ${new Date(end).toLocaleDateString()}`; }

export default function ExamplePage() {
  const { user, isLoading: authLoading, isAuthenticated } = useRequireAuth();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [volume, setVolume] = useState<Volume | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const root = `/api/v1/synthetic-campaigns/${CAMPAIGN_KEY}`;
      const [s, t, c, v] = await Promise.all([
        apiRequest<Summary>(`${root}/summary`), apiRequest<Timeline>(`${root}/rating-over-time`),
        apiRequest<Comparison>(`${root}/rating-comparison`), apiRequest<Volume>(`${root}/volume-by-day`),
      ]);
      setSummary(s); setTimeline(t); setComparison(c); setVolume(v);
    } catch (e) { setError(getErrorMessage(e)); setSummary(null); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { if (isAuthenticated) void refresh(); }, [isAuthenticated, refresh]);

  if (authLoading || !user) return <div className="session-loading">Loading workspace…</div>;
  return <AppShell>
    <header className="page-heading">
      <div><p className="eyebrow">Product review integrity workspace</p><h1>Example investigation</h1><p className="page-subtitle">A labelled synthetic case study showing how timing, ratings, and graph relationships support an investigation.</p></div>
      <button className="button-secondary" onClick={refresh} disabled={loading}>Refresh data</button>
    </header>
    {/* Synthetic case study */}
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-[#9b4e1e]">
          Synthetic case study
        </span>
      </div>
      <div className="provenance-banner">
        <span className="provenance-mark" aria-hidden="true" />
        SYNTHETIC DEMO DATA <span>— scenario evidence only; not model output</span>
      </div>
      {loading && <div className="notice-card">Loading synthetic product scenario from the API…</div>}
      {!loading && error && (
        <div className="notice-card notice-error">
          <strong>Scenario data unavailable</strong>
          <p>{error}</p>
          <button className="text-action" onClick={refresh}>Try again</button>
        </div>
      )}
      {!loading && summary && comparison && timeline && volume && (
        <>
          <section className="restaurant-intro">
            <div>
              <p className="eyebrow">Product under review</p>
              <h2>{summary.product.name || 'Product name not supplied'}</h2>
              <p>{summary.campaign_name} · {dateRange(summary.attack_window.start, summary.attack_window.end)}</p>
            </div>
            <Link className="button-primary" href={`/campaigns/${encodeURIComponent(summary.campaign_key)}`}>
              Investigate campaign <ArrowUpRight className="h-3.5 w-3.5 ml-1" />
            </Link>
          </section>
          <section className="metric-grid" aria-label="Product risk metrics">
            <Metric label="Observed rating" value={formatRating(comparison.observed_attack_window.mean_rating)} suffix="/ 5" detail={`${comparison.observed_attack_window.review_count.toLocaleString()} reviews in attack window`} />
            <Metric label="Flagged reviews" value={summary.attack_review_count.toLocaleString()} detail={`${summary.one_star_review_count.toLocaleString()} one-star · synthetic campaign membership`} tone="risk" />
          </section>
          <div className="content-grid overview-charts">
            <section className="panel chart-panel">
              <PanelTitle kicker="Product trend" title="Rating over time" detail="Daily observed mean rating for the product"/>
              <RatingTimeline items={timeline.items}/>
              <div className="chart-legend"><span className="legend-dot teal-dot"/>Observed rating</div>
            </section>
            <section className="panel chart-panel">
              <PanelTitle kicker="Review activity" title="Volume anomaly" detail="Daily reviews; campaign window highlighted"/>
              <VolumeChart items={volume.items}/>
              <div className="chart-legend"><span className="legend-box neutral-box"/>Comparison <span className="legend-box risk-box"/>Attack window</div>
              {volume.attack_to_comparison_daily_volume_ratio != null && (
                <p className="chart-note">Daily volume ratio, attack to comparison: <strong>{volume.attack_to_comparison_daily_volume_ratio.toFixed(2)}×</strong></p>
              )}
            </section>
          </div>
          <section className="panel evidence-card">
            <div className="evidence-main">
              <div>
                <p className="eyebrow risk-ink">Campaign evidence</p>
                <h2>{summary.campaign_name}</h2>
                <p className="muted">{summary.interpretation}</p>
              </div>
              <Link className="text-action inline-flex items-center gap-1" href={`/campaigns/${encodeURIComponent(summary.campaign_key)}`}>
                Open investigation <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            <div className="evidence-facts">
              <EvidenceFact label="Attack window" value={dateRange(summary.attack_window.start, summary.attack_window.end)}/>
              <EvidenceFact label="Reviews / day" value={summary.attack_reviews_per_day == null ? '—' : summary.attack_reviews_per_day.toFixed(2)}/>
              <EvidenceFact label="Connected reviewers" value={summary.distinct_attack_reviewers.toLocaleString()}/>
              <EvidenceFact label="Prior campaign overlap" value={`${summary.reviewers_overlapping_prior_campaign.toLocaleString()} reviewers`}/>
            </div>
          </section>
          <p className="formula-note">{comparison.formula}</p>
        </>
      )}
    </div>

    <p className="formula-note">This case study demonstrates the investigation workflow. Model performance is measured separately on the held-out YelpChi benchmark.</p>
  </AppShell>;
}

function Metric({ label, value, suffix, detail, tone }: { label: string; value: string; suffix?: string; detail: string; tone?: 'teal' | 'risk' }) { return <article className={`metric-card ${tone || ''}`}><p>{label}</p><div><strong>{value}</strong>{suffix && <span>{suffix}</span>}</div><small>{detail}</small></article>; }
function PanelTitle({ kicker, title, detail }: { kicker: string; title: string; detail: string }) { return <div className="panel-title"><div><p className="eyebrow">{kicker}</p><h2>{title}</h2></div><p>{detail}</p></div>; }
function EvidenceFact({ label, value }: { label: string; value: string }) { return <div className="evidence-fact"><span>{label}</span><strong>{value}</strong></div>; }
