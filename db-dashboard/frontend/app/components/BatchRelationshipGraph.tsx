'use client';

import { useMemo, useState } from 'react';
import { apiRequest, getErrorMessage } from '../lib/api';

type ReviewNode = { key: string; review_key: string; rating: number; historical: boolean; risk_score?: number; predicted_label?: number };
type Graph = { source: string; graph_sha256: string; nodes: ReviewNode[]; relationships: Array<{ key: string; source: string; target: string; relation: string }> };

export function BatchRelationshipGraph({ batchId }: { batchId: number }) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [relation, setRelation] = useState('ALL');
  const [selected, setSelected] = useState<string | null>(null);
  const load = async () => {
    setLoading(true); setError(null);
    try { setGraph(await apiRequest<Graph>(`/api/v1/batch-analyses/${batchId}/graph`, { method: 'POST' })); }
    catch (err) { setError(getErrorMessage(err)); }
    finally { setLoading(false); }
  };
  const visible = useMemo(() => graph?.nodes.slice(0, 200) || [], [graph]);
  const positions = new Map(visible.map((node, index) => {
    const angle = (index / Math.max(visible.length, 1)) * Math.PI * 2 - Math.PI / 2;
    return [node.key, {x: 330 + Math.cos(angle) * 230, y: 270 + Math.sin(angle) * 220}];
  }));
  const links = graph?.relationships.filter(edge => (relation === 'ALL' || edge.relation === relation)
    && positions.has(edge.source) && positions.has(edge.target)
    && (!selected || edge.source === selected || edge.target === selected)) || [];
  const chosen = graph?.nodes.find(node => node.key === selected);
  return <section className="panel">
    <div className="panel-title"><div><p className="eyebrow">Your uploaded reviews</p><h2>Relationship graph</h2></div>
      <button type="button" className="button-secondary" disabled={loading} onClick={() => void load()}>{loading ? 'Loading Neo4j graph…' : graph ? 'Refresh graph' : 'Show relationship graph'}</button>
    </div>
    <p className="text-xs text-[#74817b]">Inspect the past-to-review links used in this analysis. A shared relationship is evidence to inspect, not proof of fraud.</p>
    {error && <div className="inline-error" role="alert">{error}</div>}
    {graph && <>
      <div className="flex flex-wrap items-center gap-3 my-3 text-xs">
        <span>Neo4j · {graph.nodes.length} reviews · {links.length} shown of {graph.relationships.length} context links</span>
        <label>Relation <select className="border rounded px-2 py-1 ml-1" value={relation} onChange={event => setRelation(event.target.value)}>
          <option value="ALL">All</option><option value="RUR">RUR · same reviewer</option><option value="RSR">RSR · same product and rating</option><option value="RTR">RTR · same product within 30 days</option>
        </select></label>
        {selected && <button type="button" className="text-action" onClick={() => setSelected(null)}>Show all reviews</button>}
      </div>
      {graph.nodes.length > visible.length && <p className="text-xs">Showing the first {visible.length} nodes of {graph.nodes.length}; use per-review evidence for complete neighbor lists.</p>}
      <svg viewBox="0 0 660 540" className="w-full max-h-[540px]" role="img" aria-label="Neo4j relationship graph for the uploaded review analysis">
        {links.map(edge => {
          const source = positions.get(edge.source), target = positions.get(edge.target);
          if (!source || !target) return null;
          return <line key={edge.key} x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke="#94a3b8" strokeOpacity={selected ? .75 : .22} strokeWidth={selected ? 1.5 : .8}><title>{edge.relation}: {edge.source} → {edge.target}</title></line>;
        })}
        {visible.map(node => {
          const point = positions.get(node.key)!;
          const pick = () => setSelected(node.key === selected ? null : node.key);
          return <g key={node.key} transform={`translate(${point.x},${point.y})`} onClick={pick} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); pick(); } }} role="button" tabIndex={0} aria-label={`Inspect review ${node.review_key}`} style={{cursor:'pointer'}}>
            <circle r={node.key === selected ? 11 : 8} fill={node.historical ? '#94a3b8' : node.predicted_label === 1 ? '#d34c5b' : '#167549'} stroke={node.key === selected ? '#1e293b' : '#fff'} strokeWidth={2}/>
            <text y={-14} textAnchor="middle" fontSize={10} fill="#475569">{node.review_key.slice(-8)}</text>
            <title>{node.review_key} · {node.rating}/5{node.risk_score == null ? ' · historical context' : ` · risk score ${node.risk_score.toFixed(4)}`}</title>
          </g>;
        })}
      </svg>
      <p className="text-xs text-[#74817b]">Green: not flagged · Red: flagged · Gray: stored historical context. Select a review to isolate its links.</p>
      {chosen && <p className="text-xs mt-2"><strong>{chosen.review_key}</strong> · {chosen.rating}/5 · {chosen.risk_score == null ? 'Historical context' : `Risk score ${chosen.risk_score.toFixed(4)}`} · {links.length} visible {relation === 'ALL' ? 'context' : relation} links</p>}
      <p className="text-[10px] font-mono break-all mt-3 text-[#74817b]">Verified graph SHA256: {graph.graph_sha256}</p>
    </>}
  </section>;
}
