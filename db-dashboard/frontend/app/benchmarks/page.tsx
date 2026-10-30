'use client';
import AppShell from '../components/AppShell';
import MatchedBenchmark from '../components/MatchedBenchmark';
import { useRequireAuth } from '../hooks/useRequireAuth';
export default function BenchmarksPage(){
  const {isLoading,isAuthenticated}=useRequireAuth();
  if(isLoading||!isAuthenticated)return <div className="session-loading">Loading benchmark evidence…</div>;
  return <AppShell><header className="page-heading"><div><p className="eyebrow">Real data · shared evaluation protocol</p><h1>Model comparison</h1><p className="page-subtitle">Compare text, graph and combined models on exactly the same later reviews. Inspect the measured results, repeated runs and original experiment records.</p></div></header><MatchedBenchmark/></AppShell>;
}
