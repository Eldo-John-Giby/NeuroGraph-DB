'use client';

import { useEffect, useState } from 'react';

type Metric = 'roc_auc' | 'pr_auc' | 'f1_macro';
type Point = { x: number; y: number };
type Scores = Record<Metric | 'precision' | 'recall' | 'threshold', number>;
type Run = { seed: number; test: Scores; best_epoch: number; trainable_parameters: number; reused_deployed_checkpoint: boolean; curves: { roc: Point[]; pr: Point[] }; context_stress: { removed_fraction: number; test: Scores }[] };
type Model = { id: string; name: string; description: string; runs: Run[]; aggregate: Record<Metric | 'precision' | 'recall', { mean: number; std: number }> };
type Historical = { name: string; dataset: string; protocol: string; auc: number; f1: number; ap: number; threshold: number; record: string };
type Report = { generated_at: string; protocol_sha256: string; models: Model[]; historical: Historical[]; protocol: { protocol_id: string; dataset: string; source_sha256: string; evaluation_targets_sha256: string; source_manifest_sha256: string; source_run: string; seeds: number[]; split_counts: Record<string, number>; class_counts: Record<string, { spam: number; nonspam: number }>; limitations: string[] } };
const COLORS = ['#66778b', '#bc7042', '#6871ad', '#12685f'];
const SHORT: Record<string, string> = { text_only: 'Text only', graph_only: 'Graph only', concat: 'Concatenation', neurograph: 'NeuroGraph' };
const LABELS: Record<Metric, string> = { roc_auc: 'ROC-AUC', pr_auc: 'PR-AUC / average precision', f1_macro: 'Macro F1' };
const EXPLAIN: Record<Metric, string> = { roc_auc: 'Ranking labelled spam above labelled nonspam across cutoffs.', pr_auc: 'Precision and recall for the smaller spam class, summarized as average precision.', f1_macro: 'Precision–recall balance with equal weight for spam and nonspam, at each run’s validation-selected cutoff.' };
const format = (n: number) => n.toFixed(4);

function CurvePlot({ title, lines, xLabel, xMax = 1, stress = false }: { title: string; lines: { name: string; color: string; points: Point[] }[]; xLabel: string; xMax?: number; stress?: boolean }) {
  const width = 540, height = 310, left = 54, top = 18, plotW = 462, plotH = 236;
  const px = (x: number) => left + x / xMax * plotW;
  const py = (y: number) => top + (1 - y) * plotH;
  const xticks = stress ? [0, 0.1, 0.3, 0.5] : [0, 0.25, 0.5, 0.75, 1];
  return <figure className="comparison-figure"><figcaption>{title}</figcaption><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}. All model curves use the same test reviews. A numerical results table is provided above.`}>
    {[0, 0.25, 0.5, 0.75, 1].map(y => <g key={y}><line x1={left} x2={left + plotW} y1={py(y)} y2={py(y)} stroke="#e0e6e1"/><text x={left - 10} y={py(y) + 4} textAnchor="end">{y.toFixed(2)}</text></g>)}
    {xticks.map(x => <text key={x} x={px(x)} y={top + plotH + 20} textAnchor="middle">{stress ? `${Math.round(x * 100)}%` : x.toFixed(2)}</text>)}
    <line x1={left} x2={left} y1={top} y2={top + plotH} stroke="#7b8a83"/><line x1={left} x2={left + plotW} y1={top + plotH} y2={top + plotH} stroke="#7b8a83"/>
    {title.startsWith('ROC') && <line x1={px(0)} y1={py(0)} x2={px(1)} y2={py(1)} stroke="#b6beb9" strokeDasharray="5 5"/>}
    {lines.map(line => <path key={line.name} d={line.points.map((p, i) => `${i ? 'L' : 'M'}${px(p.x)},${py(p.y)}`).join(' ')} fill="none" stroke={line.color} strokeWidth="2.5"><title>{line.name}</title></path>)}
    <text x={left + plotW / 2} y={height - 10} textAnchor="middle">{xLabel}</text>
  </svg><div className="comparison-legend">{lines.map(line => <span key={line.name}><i style={{ background: line.color }}/>{line.name}</span>)}</div></figure>;
}

function MetricPlot({ rows, metric, average }: { rows: { id: string; value: number; std: number }[]; metric: Metric; average: boolean }) {
  const top = 25, left = 52, plotH = 218, plotW = 650, barW = 72;
  const py = (v: number) => top + (1 - v) * plotH;
  return <figure className="comparison-figure comparison-bar"><figcaption>{LABELS[metric]} · higher is better</figcaption><svg viewBox="0 0 730 300" role="img" aria-label={`${LABELS[metric]} comparison. ${average ? 'Error bars show sample standard deviation across three training seeds.' : 'Scores for the selected training seed.'} Exact values follow in the table.`}>
    {[0, 0.25, 0.5, 0.75, 1].map(v => <g key={v}><line x1={left} x2={left + plotW} y1={py(v)} y2={py(v)} stroke="#e0e6e1"/><text x={left - 10} y={py(v) + 4} textAnchor="end">{v.toFixed(2)}</text></g>)}
    {rows.map((row, i) => { const x = left + (i + 0.5) * plotW / rows.length; return <g key={row.id}><rect x={x - barW / 2} y={py(row.value)} width={barW} height={plotH * row.value} rx="5" fill={COLORS[i]}/>{average && <g stroke="#263a32" strokeWidth="2"><line x1={x} x2={x} y1={py(Math.min(1, row.value + row.std))} y2={py(Math.max(0, row.value - row.std))}/><line x1={x - 7} x2={x + 7} y1={py(Math.min(1, row.value + row.std))} y2={py(Math.min(1, row.value + row.std))}/></g>}<text x={x} y={py(Math.min(1, row.value + (average ? row.std : 0))) - 9} textAnchor="middle" className="comparison-value">{format(row.value)}</text><text x={x} y={top + plotH + 27} textAnchor="middle">{SHORT[row.id]}</text></g>; })}
  </svg></figure>;
}

export default function MatchedBenchmark() {
  const [report, setReport] = useState<Report | null>(null), [error, setError] = useState('');
  const [view, setView] = useState('42'), [metric, setMetric] = useState<Metric>('roc_auc');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    fetch('/benchmarks/comparison.json', { signal: abort.signal }).then(async response => { if (!response.ok) throw new Error('The recorded comparison could not be loaded.'); return response.json(); }).then((data: Report) => {
      if (data.protocol?.protocol_id !== 'yelpchi-temporal-matched-v1' || data.models?.length !== 4 || data.models.some(m => m.runs.length !== data.protocol.seeds.length)) throw new Error('The comparison record is incomplete.');
      setReport(data); setError('');
    }).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => abort.abort();
  }, [attempt]);
  if (error) return <div className="notice-card notice-error" role="alert"><p>{error}</p><button onClick={() => setAttempt(n => n + 1)} className="text-action">Retry</button></div>;
  if (!report) return <div className="notice-card" role="status">Loading recorded benchmark results…</div>;
  const average = view === 'mean';
  const selected = (model: Model) => model.runs.find(run => run.seed === Number(average ? 42 : view))!;
  const value = (model: Model, key: Metric) => average ? model.aggregate[key].mean : selected(model).test[key];
  const winners = (key: Metric) => { const best = Math.max(...report.models.map(model => value(model, key))); return report.models.filter(model => Math.abs(value(model, key) - best) < 1e-12).map(model => model.name).join(' and '); };
  const curveSeed = average ? 42 : Number(view);
  const lines = (kind: 'roc' | 'pr') => report.models.map((model, i) => ({ name: SHORT[model.id], color: COLORS[i], points: selected(model).curves[kind] }));
  const p = report.protocol;
  return <>
    <section className="comparison-protocol" aria-label="Shared evaluation conditions"><div className="comparison-facts">{[['Training reviews', p.split_counts.train], ['Validation reviews', p.split_counts.validation], ['Same test reviews', p.split_counts.test], ['Training seeds', p.seeds.length]].map(([label, count]) => <div key={label}><span>{label}</span><strong>{Number(count).toLocaleString()}</strong></div>)}</div>
      <p>All four approaches use the same real Yelp review identities, chronological split and test labels. Text-enabled models share the same frozen RoBERTa embeddings. Graph-enabled models share the same 14 numeric features and earlier-to-later relationship rules. Each run chooses its checkpoint and cutoff using validation data.</p>
      <p className="comparison-small">The held-out test includes {p.class_counts.test.spam.toLocaleString()} spam-labelled and {p.class_counts.test.nonspam.toLocaleString()} nonspam-labelled reviews. Labels follow the dataset’s Yelp-filtering convention and can be imperfect.</p>
    </section>
    <section className="comparison-section" aria-label="Matched model results"><div className="comparison-heading"><div><p className="eyebrow">Controlled architecture comparison</p><h2>Four models on the same test.</h2></div><label className="comparison-select">Recorded result<select value={view} onChange={e => setView(e.target.value)}>{p.seeds.map(seed => <option value={String(seed)} key={seed}>Seed {seed}{seed === 42 ? ' · deployed checkpoint' : ''}</option>)}<option value="mean">Mean ± SD · all three seeds</option></select></label></div>
      <p>{average ? 'Mean and sample standard deviation across three initializations of each architecture. The data split stays fixed. SD describes training variation; it is not a confidence interval.' : `Results for training seed ${view}. ${view === '42' ? 'The NeuroGraph row is the same verified checkpoint used for live CSV scoring and shown on Model results.' : 'This is a recorded repeat run; it does not replace the live checkpoint.'}`}</p>
      <div className="comparison-tabs" role="group" aria-label="Chart metric">{(['roc_auc', 'pr_auc', 'f1_macro'] as Metric[]).map(key => <button key={key} aria-pressed={metric === key} className={metric === key ? 'selected' : ''} onClick={() => setMetric(key)}>{LABELS[key]}</button>)}</div>
      <p className="comparison-small">{EXPLAIN[metric]} ROC-AUC and PR-AUC are not classification accuracy.</p>
      <MetricPlot metric={metric} average={average} rows={report.models.map(model => ({ id: model.id, value: value(model, metric), std: model.aggregate[metric].std }))}/>
      <div className="comparison-table-wrap"><table className="comparison-table"><caption>Exact {average ? 'mean ± sample SD' : `seed-${view}`} test metrics. Every row uses the same test reviews.</caption><thead><tr><th scope="col">Model</th><th scope="col">ROC-AUC</th><th scope="col">PR-AUC</th><th scope="col">Macro F1</th><th scope="col">Validation cutoff</th></tr></thead><tbody>{report.models.map((model, i) => <tr key={model.id} className={model.id === 'neurograph' ? 'comparison-proposed' : ''}><th scope="row"><span className="comparison-model-dot" style={{ background: COLORS[i] }}/>{model.name}{model.id === 'neurograph' && <small>Deployed architecture</small>}</th>{(['roc_auc', 'pr_auc', 'f1_macro'] as Metric[]).map(key => <td key={key}>{format(value(model, key))}{average && <small>± {format(model.aggregate[key].std)}</small>}</td>)}<td>{average ? 'Selected per run' : format(selected(model).test.threshold)}</td></tr>)}</tbody></table></div>
      <div className="comparison-finding"><strong>What performed best here?</strong><p>{winners('roc_auc')} has the highest observed ROC-AUC; {winners('pr_auc')} has the highest average precision; {winners('f1_macro')} has the highest macro F1 in this view. These results support metric-specific conclusions on this dataset, not a universal winner.</p></div>
      <div className="comparison-models">{report.models.map(model => <article key={model.id}><h3>{model.name}</h3><p>{model.description}</p><small>{selected(model).trainable_parameters.toLocaleString()} trainable parameters · selected epoch {selected(model).best_epoch} for seed {curveSeed}</small></article>)}</div>
    </section>
    <section className="comparison-section"><div className="comparison-heading"><div><p className="eyebrow">Recorded prediction curves</p><h2>How the scores separate reviews.</h2></div></div><p>Curves use seed {curveSeed} on the same test set. Points are reduced for display; the scores in the table are calculated from every test prediction.</p><div className="comparison-plots"><CurvePlot title="ROC curves · true positive rate" lines={lines('roc')} xLabel="False positive rate"/><CurvePlot title="Precision–recall curves · precision" lines={lines('pr')} xLabel="Recall"/></div></section>
    <section className="comparison-section"><p className="eyebrow">Missing-context sensitivity</p><h2>What happens when graph links are missing?</h2><p>We independently remove each graph link with probability 10%, 30% or 50%, using a fixed seed independent of the labels. Models stay frozen and keep their clean validation cutoff. Text-only models ignore graph links, so an unchanged text-only curve is expected.</p><CurvePlot title={`ROC-AUC after edge removal · seed ${curveSeed}`} xLabel="Link removal probability" xMax={0.5} stress lines={report.models.map((model, i) => ({ name: SHORT[model.id], color: COLORS[i], points: [{ x: 0, y: selected(model).test.roc_auc }, ...selected(model).context_stress.map(item => ({ x: item.removed_fraction, y: item.test.roc_auc }))] }))}/><p className="comparison-small">This is a missing-context stress test. It does not demonstrate resistance to real coordinated attacks or AI-written review camouflage.</p></section>
    <section className="comparison-section" aria-label="Historical experiment results"><p className="eyebrow">Earlier experiment records</p><h2>Three recorded research stages.</h2><p>These records use different data representations or evaluation rules. They are shown for transparency and excluded from the matched ranking above. The new graph-only baseline is retrained on the shared raw-data split; it is not the 32-feature MAT checkpoint.</p><div className="comparison-history">{report.historical.map(item => <article key={item.record}><span className="comparison-tag">Historical reference</span><h3>{item.name}</h3><p>{item.dataset}</p><p className="comparison-small">{item.protocol}</p><dl><div><dt>ROC-AUC</dt><dd>{format(item.auc)}</dd></div><div><dt>Macro F1</dt><dd>{format(item.f1)}</dd></div><div><dt>PR-AUC</dt><dd>{format(item.ap)}</dd></div><div><dt>Cutoff</dt><dd>{format(item.threshold)}</dd></div></dl><a className="text-action" href={`https://github.com/Eldo-John-Giby/NeuroGraph-DB/blob/main/docs/runs/${item.record}.json`} target="_blank" rel="noreferrer">Open recorded evidence ↗</a></article>)}</div></section>
    <section className="comparison-section comparison-evidence"><p className="eyebrow">Method and evidence</p><h2>Check what was measured.</h2><p>The comparison was recorded on {new Date(report.generated_at).toLocaleDateString('en-GB', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'long', year: 'numeric' })}. It reuses the existing chronological holdout and the sealed deployed seed-42 checkpoint. Added training runs use the same optimization budget and validation selection rule.</p><p>Temporal replay allows earlier arrivals to supply unlabelled context. A live upload’s selected snapshot and batch may provide a different amount of history; these test scores are not a measured accuracy guarantee for a user’s file.</p><ul>{p.limitations.map(item => <li key={item}>{item}</li>)}</ul><details><summary>Dataset and experiment fingerprints</summary><dl><dt>Protocol</dt><dd>{p.protocol_id}</dd><dt>Source CSV SHA-256</dt><dd>{p.source_sha256}</dd><dt>Saved labels and split membership SHA-256</dt><dd>{p.evaluation_targets_sha256}</dd><dt>Recorded protocol SHA-256</dt><dd>{report.protocol_sha256}</dd></dl></details><div className="comparison-downloads"><a className="button-secondary" href="/benchmarks/comparison.json" download>Download results and curves</a><a className="text-action" href="https://github.com/Eldo-John-Giby/NeuroGraph-DB/blob/main/docs/benchmarks/README.md" target="_blank" rel="noreferrer">Read the reproduction method ↗</a></div></section>
  </>;
}
