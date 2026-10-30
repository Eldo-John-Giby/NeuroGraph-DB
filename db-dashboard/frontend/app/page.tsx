'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, UploadCloud, Network, ShieldCheck } from 'lucide-react';
import AppShell from './components/AppShell';
import FinalModelResults from './components/FinalModelResults';
import { AnalysisCard, SavedAnalysis } from './components/AnalysisCard';
import { useRequireAuth } from './hooks/useRequireAuth';
import { apiRequest, getErrorMessage } from './lib/api';

export default function DashboardPage() {
  const {isLoading,isAuthenticated}=useRequireAuth();
  const [recent,setRecent]=useState<SavedAnalysis[]>([]),[error,setError]=useState('');
  useEffect(()=>{if(isAuthenticated)apiRequest<{items:SavedAnalysis[]}>('/api/v1/batch-analyses?limit=3&status=completed').then(data=>setRecent(data.items)).catch(e=>setError(getErrorMessage(e)));},[isAuthenticated]);
  if(isLoading||!isAuthenticated)return <div className="session-loading">Loading workspace…</div>;
  return <AppShell>
    <header className="results-hero"><div><p className="eyebrow">NeuroGraph / review intelligence</p><h1>Model results.<br/><em>Evidence you can inspect.</em></h1><p>From verified model performance to your own product reviews. Assess risk, inspect the relationships, and keep every analysis.</p><div className="hero-actions"><Link href="/reviews/submit" className="button-primary"><UploadCloud size={18}/> Analyze a CSV</Link><Link href="/products" className="button-secondary">Open your history <ArrowUpRight size={16}/></Link></div></div><div className="hero-signal" aria-hidden="true"><Network size={70} strokeWidth={1}/><span>TEXT + RELATIONSHIPS + TIME</span><small>Review intelligence, connected.</small></div></header>
    <FinalModelResults/>
    <section className="recent-section"><div className="section-heading"><div><p className="eyebrow">Your workspace</p><h2>Pick up where you left off.</h2></div><Link href="/products" className="text-action">All saved analyses →</Link></div>{error?<p className="notice-card notice-error">{error}</p>:recent.length?<div className="analysis-grid">{recent.map(batch=><AnalysisCard key={batch.batch_analysis_id} batch={batch}/>)}</div>:<div className="first-analysis"><p>Your completed analyses will appear here. Start with a CSV of product reviews.</p><Link href="/reviews/submit" className="text-action">Upload your first file →</Link></div>}</section>
    <section className="evidence-links" aria-label="Supporting model evidence"><Link href="/benchmarks"><ShieldCheck size={24}/><p className="eyebrow">Shared-test benchmark</p><h2>Compare all four models.</h2><p>Compare text-only, graph-only, concatenation and NeuroGraph on the same chronological test reviews, with repeated runs and recorded evidence.</p><span className="text-action">Open model comparison ↗</span></Link><Link href="/examples"><Network size={24}/><p className="eyebrow">Synthetic case study</p><h2>See an investigation unfold.</h2><p>A labelled example of coordinated reviews, timing patterns, and shared reviewers. A demonstration of the workflow, separate from model performance.</p><span className="text-action">Explore the example ↗</span></Link></section>
  </AppShell>;
}
