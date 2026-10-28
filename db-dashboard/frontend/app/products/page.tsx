'use client';
import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { FileSpreadsheet, Search, UploadCloud } from 'lucide-react';
import AppShell from '../components/AppShell';
import { AnalysisCard, SavedAnalysis } from '../components/AnalysisCard';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { apiRequest, getErrorMessage } from '../lib/api';

type History = { items:SavedAnalysis[]; total:number; summary:{completed:number; submitted_rows:number} };

export default function ProductsPage() {
  const {isLoading:authLoading,isAuthenticated,isAdmin}=useRequireAuth();
  const [data,setData]=useState<History|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
  const [query,setQuery]=useState(''),[search,setSearch]=useState(''),[status,setStatus]=useState(''),[page,setPage]=useState(0),[scope,setScope]=useState('mine');
  useEffect(()=>{ const timer=setTimeout(()=>{setSearch(query);setPage(0);},300); return()=>clearTimeout(timer); },[query]);
  const load=useCallback(async()=>{setLoading(true);setError('');try{const params=new URLSearchParams({limit:'12',offset:String(page*12),q:search,scope});if(status)params.set('status',status);setData(await apiRequest<History>(`/api/v1/batch-analyses?${params}`));}catch(e){setError(getErrorMessage(e));}finally{setLoading(false);}},[page,search,status,scope]);
  useEffect(()=>{if(isAuthenticated)void load();},[isAuthenticated,load]);
  if(authLoading||!isAuthenticated)return <div className="session-loading">Loading your workspace…</div>;
  return <AppShell>
    <header className="page-heading"><div><p className="eyebrow">Products / saved analyses</p><h1>Your analysis library</h1><p className="page-subtitle">Every CSV you upload, with its saved predictions and relationship evidence. Open a result without running the model again.</p></div><Link href="/reviews/submit" className="button-primary"><UploadCloud size={17}/> Upload a CSV</Link></header>
    <div className="history-toolbar"><label className="history-search"><Search size={17}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search uploaded filenames" aria-label="Search uploaded filenames"/></label><select aria-label="Analysis status" value={status} onChange={e=>{setStatus(e.target.value);setPage(0);}}><option value="">All statuses</option>{['completed','queued','running','blocked','failed','partial','validation_failed'].map(s=><option key={s} value={s}>{s.replaceAll('_',' ')}</option>)}</select>{isAdmin&&<select aria-label="Upload visibility" value={scope} onChange={e=>{setScope(e.target.value);setPage(0);}}><option value="mine">My uploads</option><option value="all">All users · administrator</option></select>}<button className="button-secondary" onClick={load} disabled={loading}>Refresh</button></div>
    {error&&<div className="notice-card notice-error" role="alert">{error}</div>}
    {loading&&<div className="notice-card" role="status">Loading saved analyses…</div>}
    {!loading&&!error&&data&&<><div className="library-summary"><span><strong>{data.total}</strong> matching uploads</span><span><strong>{data.summary.completed}</strong> completed</span><span><strong>{data.summary.submitted_rows}</strong> rows across uploads</span><span>{scope==='mine'?'Only your uploads':'Administrator view of all uploads'}</span></div>{data.items.length?<div className="analysis-grid">{data.items.map(batch=><AnalysisCard key={batch.batch_analysis_id} batch={batch}/>)}</div>:<section className="empty-library"><FileSpreadsheet size={38}/><h2>{search||status?'No matching analyses':'Your first analysis starts here.'}</h2><p>{search||status?'Try another filename or status.':'Upload a product review CSV. Its results will stay here, ready to reopen.'}</p><Link href="/reviews/submit" className="button-primary">Upload a review batch</Link></section>}<div className="history-pagination"><button className="button-secondary" disabled={page===0} onClick={()=>setPage(p=>p-1)}>Previous</button><span>Page {page+1} of {Math.max(1,Math.ceil(data.total/12))}</span><button className="button-secondary" disabled={(page+1)*12>=data.total} onClick={()=>setPage(p=>p+1)}>Next</button></div></>}
  </AppShell>;
}
