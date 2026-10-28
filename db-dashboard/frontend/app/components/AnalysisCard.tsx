import Link from 'next/link';
import { FileSpreadsheet, ArrowUpRight } from 'lucide-react';
export type SavedAnalysis = { batch_analysis_id:number; source_filename:string|null; source_system:string; status:string; row_count:number; accepted_count:number; rejected_count:number; scored_count?:number; flagged_count?:number; cleared_count?:number; created_at:string };
export function analysisName(batch:SavedAnalysis) { return batch.source_filename || `Imported CSV · Batch ${batch.batch_analysis_id}`; }
export function AnalysisCard({batch}:{batch:SavedAnalysis}) {
  return <Link className="analysis-card" href={`/products/${batch.batch_analysis_id}`}>
    <div className="analysis-card-top"><span className="file-symbol"><FileSpreadsheet size={22}/></span><span className={`analysis-status status-${batch.status}`}>{batch.status.replaceAll('_',' ')}</span></div>
    <h2>{analysisName(batch)}</h2><p className="muted">Uploaded {new Date(batch.created_at).toLocaleString()} · Batch #{batch.batch_analysis_id}</p>
    <div className="analysis-card-counts"><span><strong>{batch.row_count}</strong> submitted</span><span><strong>{batch.scored_count ?? 0}</strong> scored</span><span><strong>{batch.flagged_count ?? 0}</strong> flagged</span></div>
    <div className="analysis-card-footer"><span>{batch.status==='completed' ? 'Open saved results' : batch.accepted_count ? 'Open analysis' : 'Review import errors'}</span><ArrowUpRight size={17}/></div>
  </Link>;
}
