'use client';
import AppShell from '../components/AppShell';
import { VerifiedBenchmarkSection } from '../components/VerifiedBenchmarkSection';
import { useRequireAuth } from '../hooks/useRequireAuth';
export default function BenchmarksPage(){
  const {isLoading,isAuthenticated}=useRequireAuth();
  if(isLoading||!isAuthenticated)return <div className="session-loading">Loading benchmark evidence…</div>;
  return <AppShell><header className="page-heading"><div><p className="eyebrow">Supporting research</p><h1>Benchmark evidence</h1><p className="page-subtitle">The earlier multimodal model scores known nodes in a fixed graph. The final inductive model on the home page evaluates newly arriving reviews. Scores across these protocols are not a direct comparison.</p></div></header><VerifiedBenchmarkSection/></AppShell>;
}
