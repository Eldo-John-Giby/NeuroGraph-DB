'use client';
import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { CheckCircle2, FileSpreadsheet, UploadCloud } from 'lucide-react';
import AppShell from '../../components/AppShell';
import { useRequireAuth } from '../../hooks/useRequireAuth';
import { apiRequest, getErrorMessage } from '../../lib/api';

type Snapshot = { graph_snapshot_id:number; snapshot_key:string; batch_context_permitted:boolean; context_scope_key:string|null; relation_schema_version:string; storage_status:string; provenance:string };
type Receipt = {batch_analysis_id:number; status:string; row_count:number; accepted_count:number; rejected_count:number};
type ImportRow = {row_number:number; validation_errors:{message?:string;code?:string}[]};
function compatible(snapshot:Snapshot){return snapshot.batch_context_permitted&&snapshot.storage_status==='available'&&snapshot.provenance==='real'&&(snapshot.context_scope_key==='inductive-rur-rsr-rtr-v1'||snapshot.relation_schema_version==='inductive-rur-rsr-rtr-v1');}

export default function BatchAnalysisPage(){
  const {isLoading,isAuthenticated}=useRequireAuth();const router=useRouter();const input=useRef<HTMLInputElement>(null);
  const [snapshots,setSnapshots]=useState<Snapshot[]>([]),[snapshotId,setSnapshotId]=useState<number|null>(null),[contextLoading,setContextLoading]=useState(true),[contextError,setContextError]=useState('');
  const [file,setFile]=useState<File|null>(null),[dragging,setDragging]=useState(false),[phase,setPhase]=useState<'idle'|'saving'|'scoring'>('idle'),[error,setError]=useState(''),[receipt,setReceipt]=useState<Receipt|null>(null),[rejected,setRejected]=useState<ImportRow[]>([]);
  const loadContext=useCallback(async()=>{setContextLoading(true);setContextError('');try{const data=await apiRequest<{items:Snapshot[]}>('/api/v1/graph-snapshots');const choices=data.items.filter(compatible);setSnapshots(choices);setSnapshotId(choices[0]?.graph_snapshot_id??null);if(!choices.length)setContextError('No compatible history is available. An administrator needs to restore the verified model context.');}catch(e){setContextError(getErrorMessage(e));}finally{setContextLoading(false);}},[]);
  useEffect(()=>{if(isAuthenticated)void loadContext();},[isAuthenticated,loadContext]);
  const selectFile=(candidate?:File)=>{if(!candidate)return;setError('');setReceipt(null);setRejected([]);if(!candidate.name.toLowerCase().endsWith('.csv')){setFile(null);setError('Choose a CSV file.');return;}if(candidate.size>8*1024*1024){setFile(null);setError('The CSV must be no larger than 8 MiB.');return;}setFile(candidate);};
  const drop=(event:DragEvent<HTMLDivElement>)=>{event.preventDefault();setDragging(false);selectFile(event.dataTransfer.files[0]);};
  const upload=async()=>{
    if(!file||!snapshotId||phase!=='idle')return;setPhase('saving');setError('');setReceipt(null);setRejected([]);
    try{
      const form=new FormData();form.append('file',file);form.append('source_system',`csv-${file.name.replace(/[^a-zA-Z0-9_-]/g,'-').slice(0,80)}`);form.append('historic_graph_snapshot_id',String(snapshotId));
      const saved=await apiRequest<Receipt>('/api/v1/batch-analyses',{method:'POST',body:form});setReceipt(saved);
      if(!saved.accepted_count){const rows=await apiRequest<{items:ImportRow[]}>(`/api/v1/batch-analyses/${saved.batch_analysis_id}/results?limit=100`);setRejected(rows.items);return;}
      if(saved.status!=='completed'){setPhase('scoring');const options=new FormData();options.append('historic_graph_snapshot_id',String(snapshotId));await apiRequest(`/api/v1/batch-analyses/${saved.batch_analysis_id}/score`,{method:'POST',body:options});}
      router.push(`/products/${saved.batch_analysis_id}`);
    }catch(e){setError(getErrorMessage(e));}finally{setPhase('idle');}
  };
  if(isLoading||!isAuthenticated)return <div className="session-loading">Loading your workspace…</div>;
  return <AppShell>
    <header className="page-heading"><div><p className="eyebrow">Your reviews / new analysis</p><h1>From CSV to evidence.</h1><p className="page-subtitle">Upload product reviews once. Get model risk scores and relationship evidence, then reopen the saved results from your analysis library.</p></div><Link className="button-secondary" href="/products">Your analysis history →</Link></header>
    <div className="upload-workflow"><section className="panel upload-panel"><div className="section-heading"><div><p className="eyebrow">01 / Review file</p><h2>Upload a review batch</h2></div><FileSpreadsheet size={26}/></div>
      <input ref={input} type="file" accept=".csv,text/csv" className="hidden" onChange={(event:ChangeEvent<HTMLInputElement>)=>selectFile(event.target.files?.[0])}/>
      <div role="button" tabIndex={0} aria-label="Choose review CSV" className={`dropzone ${dragging?'dropzone-active':''}`} onClick={()=>phase==='idle'&&input.current?.click()} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();input.current?.click();}}} onDragOver={e=>{e.preventDefault();setDragging(true);}} onDragLeave={()=>setDragging(false)} onDrop={drop}><UploadCloud size={35}/><strong>{file?file.name:'Drop your CSV here or browse files'}</strong><small>{file?`${(file.size/1024).toFixed(1)} KB · ready to upload`:'Up to 5,000 rows · maximum 8 MiB · UTF-8 CSV'}</small></div>
      <div className="upload-context"><CheckCircle2 size={20}/><div><strong>{contextLoading?'Checking the analysis context…':contextError?'Analysis context unavailable':'Verified historical context ready'}</strong><p>{contextError||'The compatible graph is selected automatically for the final model. Your reviews will be scored as new arrivals.'}</p>{contextError&&<button className="text-action" onClick={loadContext}>Check again</button>}</div></div>
      {snapshots.length>1&&<label className="context-selector">Historical context<select value={snapshotId??''} onChange={e=>setSnapshotId(Number(e.target.value))}>{snapshots.map(s=><option key={s.graph_snapshot_id} value={s.graph_snapshot_id}>{s.snapshot_key}</option>)}</select></label>}
      <details className="proof-details"><summary>Why is the older graph not selectable?</summary><p>The older multimodal benchmark graph scores only its known reviews. New CSV reviews require the inductive model’s historical graph and its past-to-new-review relation policy. Using the older graph would invalidate the analysis.</p>{snapshotId&&<p>Selected context: snapshot #{snapshotId} · {snapshots.find(s=>s.graph_snapshot_id===snapshotId)?.snapshot_key}</p>}</details>
      <div className="upload-footer"><span>Your file and results will be saved to your account.</span><button className="button-primary" disabled={!file||!snapshotId||contextLoading||phase!=='idle'} onClick={upload}>{phase==='saving'?'Saving your reviews…':phase==='scoring'?'Analyzing reviews…':'Upload & analyze'}</button></div>
      {error&&<div className="notice-card notice-error" role="alert"><strong>Analysis needs attention</strong><p>{error}</p>{receipt&&<Link href={`/products/${receipt.batch_analysis_id}`} className="text-action">Open the saved batch to inspect or retry →</Link>}</div>}
      {receipt&&receipt.accepted_count===0&&<div className="notice-card notice-error"><strong>No rows could be imported</strong><p>{receipt.row_count} submitted · {receipt.rejected_count} import errors. No model predictions were generated.</p><ul>{rejected.map(row=><li key={row.row_number}>Row {row.row_number}: {row.validation_errors.map(e=>e.message||e.code).join('; ')}</li>)}</ul><Link href={`/products/${receipt.batch_analysis_id}`} className="text-action">Open this saved import receipt →</Link></div>}
    </section><aside className="upload-guide panel"><p className="eyebrow">02 / What you get</p><h2>A saved, inspectable analysis.</h2><ol><li><strong>Validation</strong><p>Checks the required fields and preserves import errors.</p></li><li><strong>Model predictions</strong><p>Text and graph context produce a risk score and a threshold-based decision for each accepted review.</p></li><li><strong>Relationship evidence</strong><p>Inspect the links, attention weights, and model identity behind the result.</p></li><li><strong>Your history</strong><p>Return to Products &amp; history to reopen a calculated result without rescoring.</p></li></ol><a className="button-secondary" href="/sample-reviews.csv" download>Download a sample CSV</a><details className="proof-details"><summary>CSV format</summary><code>review_id, reviewer_id, product_id, rating, review_date, review_text</code><p>Rating: 1–5. Dates: ISO format, for example 2026-10-20. Use a stable ID for each review. An unchanged review can be reused; conflicting content under an existing ID is rejected.</p></details><p className="prediction-caveat">A high model score is a signal to investigate, not proof that a review is fraudulent.</p></aside></div>
  </AppShell>;
}
