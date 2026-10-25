'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { RefreshCw, Package, TrendingUp, Scale, Network } from 'lucide-react';
import AppShell from '../components/AppShell';
import { PageHeader, StatCard, LoadingSpinner, TableSkeleton, EmptyState, InfoBanner, StatusBadge } from '../components/ui';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { apiRequest, isApiError } from '../lib/api';

interface Product {
  product_id: number;
  source_system: string;
  external_product_key: string;
  display_name: string | null;
  created_at: string;
  total_reviews?: number;
  average_rating?: number;
  risk_status?: string;
}

interface ProductsResponse {
  items?: Product[];
  total?: number;
  limit?: number;
  offset?: number;
}

export default function ProductsPage() {
  const { isLoading: authLoading, isAuthenticated } = useRequireAuth();
  const [loading, setLoading] = useState<boolean>(true);
  const [products, setProducts] = useState<Product[] | null>(null);
  const [isNotImplemented, setIsNotImplemented] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    setIsNotImplemented(false);

    try {
      const data = await apiRequest<ProductsResponse | Product[]>('/api/v1/products');
      if (Array.isArray(data)) {
        setProducts(data);
      } else if (data && Array.isArray(data.items)) {
        setProducts(data.items);
      } else {
        setProducts([]);
      }
    } catch (err: unknown) {
      if (isApiError(err) && (err.status === 404 || err.code === 'not_found' || err.status === 405)) {
        setIsNotImplemented(true);
      } else {
        setIsNotImplemented(true);
        if (err instanceof Error) {
          setFetchError(err.message);
        }
      }
      setProducts(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchProducts();
    }
  }, [isAuthenticated, fetchProducts]);

  if (authLoading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <LoadingSpinner text="Authenticating session..." />
      </div>
    );
  }

  return (
    <AppShell>
      <PageHeader
        title="Product Management"
        subtitle="Catalog inventory, target product anomaly detection, and co-review graph clustering"
        actions={
          <button
            onClick={fetchProducts}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5 text-teal-400" />
            {loading ? 'Checking...' : 'Refresh Endpoint'}
          </button>
        }
      />

      {loading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-24 rounded-xl border border-slate-800 bg-slate-900/60 animate-pulse" />
            ))}
          </div>
          <TableSkeleton rows={6} cols={5} />
        </div>
      ) : isNotImplemented ? (
        <div className="space-y-6">
          {/* Info Banner specified in requirements */}
          <InfoBanner
            title="Product Management Endpoint Status"
            message="Product management endpoints are not yet implemented on the backend. This page will be functional once the /api/v1/products routes are deployed."
          />

          {fetchError && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs font-mono text-slate-400">
              <span className="text-slate-500">API Response Detail:</span> {fetchError}
            </div>
          )}

          {/* Conceptual Description & Architecture */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 text-lg">
                <Package className="h-5 w-5 text-indigo-400" />
              </div>
              <div className="space-y-2">
                <h3 className="text-base font-bold text-white">
                  Conceptual Architecture: Target Product Modeling & Camouflage Defense
                </h3>
                <p className="text-sm leading-relaxed text-slate-300">
                  Products serve as the focal recipient entities in the NeuroGraph bipartite graph{' '}
                  <code className="text-indigo-400 font-mono text-xs">(:Reviewer)-[:REVIEWED]→(:Product)</code>. Analyzing product graph subgraphs enables high-precision detection of coordinated astroturfing campaigns, review bombing, and burst rating manipulation.
                </p>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                <div className="flex items-center gap-2 text-indigo-400 mb-2 font-semibold text-sm">
                  <TrendingUp className="h-4 w-4 text-indigo-400" /> Velocity & Burst Spike Profiling
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Fraudulent promotions typically inject massive rating volumes within compressed time windows. Temporal graph indexing measures first-order review rate derivatives across product lifecycles.
                </p>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                <div className="flex items-center gap-2 text-emerald-400 mb-2 font-semibold text-sm">
                  <Scale className="h-4 w-4 text-emerald-400" /> Bimodal Rating Entropy
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Targeted manipulation generates extreme polarization (1-star attacks vs 5-star incentivized praise). Entropy metrics identify statistical deviance from natural Poisson rating spreads.
                </p>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                <div className="flex items-center gap-2 text-amber-400 mb-2 font-semibold text-sm">
                  <Network className="h-4 w-4 text-amber-400" /> Cross-Product Infiltration
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Camouflaged bot networks often review high-volume popular items to disguise fraudulent reviews on obscure target merchandise. Bipartite graph projection highlights these bridge anomalies.
                </p>
              </div>
            </div>

            {/* Planned Schema Preview */}
            <div className="mt-6 border-t border-slate-800/80 pt-5">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                Target Schema Specification (<code className="text-slate-300 font-mono">products</code> table)
              </h4>
              <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/80">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-800 bg-slate-900/80 text-slate-400">
                    <tr>
                      <th className="px-4 py-2.5 font-semibold">Column</th>
                      <th className="px-4 py-2.5 font-semibold">SQL Type</th>
                      <th className="px-4 py-2.5 font-semibold">Constraint</th>
                      <th className="px-4 py-2.5 font-semibold">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                    <tr>
                      <td className="px-4 py-2 text-indigo-400">product_id</td>
                      <td className="px-4 py-2 text-slate-400">BigInteger</td>
                      <td className="px-4 py-2 text-emerald-400">PRIMARY KEY</td>
                      <td className="px-4 py-2 font-sans text-slate-400">Synthetic surrogate sequence ID</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 text-indigo-400">source_system</td>
                      <td className="px-4 py-2 text-slate-400">VARCHAR(100)</td>
                      <td className="px-4 py-2 text-amber-400">NOT NULL, UQ(source, key)</td>
                      <td className="px-4 py-2 font-sans text-slate-400">Origin catalog source (e.g. amazon, target)</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 text-indigo-400">external_product_key</td>
                      <td className="px-4 py-2 text-slate-400">VARCHAR(255)</td>
                      <td className="px-4 py-2 text-amber-400">NOT NULL, UQ(source, key)</td>
                      <td className="px-4 py-2 font-sans text-slate-400">External ASIN, SKU, or platform product identifier</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 text-indigo-400">display_name</td>
                      <td className="px-4 py-2 text-slate-400">VARCHAR(500)</td>
                      <td className="px-4 py-2 text-slate-500">NULLABLE</td>
                      <td className="px-4 py-2 font-sans text-slate-400">Item title or catalog product name</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 text-indigo-400">created_at</td>
                      <td className="px-4 py-2 text-slate-400">TIMESTAMPTZ</td>
                      <td className="px-4 py-2 text-slate-500">DEFAULT NOW()</td>
                      <td className="px-4 py-2 font-sans text-slate-400">Catalog ingestion timestamp</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-slate-800/80 pt-5">
              <p className="text-xs text-slate-400">
                You can currently filter and inspect individual reviews submitted for any product ID in the review history stream.
              </p>
              <Link
                href="/reviews"
                className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                Explore Review History →
              </Link>
            </div>
          </div>
        </div>
      ) : products && products.length > 0 ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard label="Total Products" value={products.length} color="indigo" />
            <StatCard
              label="Catalog Items"
              value={products.filter((p) => p.display_name).length}
              color="emerald"
            />
            <StatCard
              label="Source Platforms"
              value={Array.from(new Set(products.map((p) => p.source_system))).length}
              color="sky"
            />
            <StatCard
              label="Monitored Clusters"
              value={products.length > 0 ? 'Active' : 'Idle'}
              color="amber"
            />
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/80 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Product ID</th>
                    <th className="px-4 py-3">Display Name</th>
                    <th className="px-4 py-3">External Key</th>
                    <th className="px-4 py-3">Source System</th>
                    <th className="px-4 py-3">Created At</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                  {products.map((product) => (
                    <tr key={product.product_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 font-semibold text-indigo-400">#{product.product_id}</td>
                      <td className="px-4 py-3 text-white font-sans max-w-xs truncate">
                        {product.display_name || '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-300 font-mono">{product.external_product_key}</td>
                      <td className="px-4 py-3">
                        <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300 border border-slate-700">
                          {product.source_system}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-400 font-sans">
                        {product.created_at ? new Date(product.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3 text-right font-sans">
                        <Link
                          href={`/reviews?product_id=${product.product_id}`}
                          className="rounded bg-indigo-600/20 px-2.5 py-1 text-xs font-semibold text-indigo-400 hover:bg-indigo-600/30 transition-colors"
                        >
                          View Reviews
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <EmptyState
          icon={<Package className="h-8 w-8 text-slate-500" />}
          title="No Products Found"
          message="No product entities have been recorded in the database yet."
          action={
            <button
              onClick={fetchProducts}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
            >
              Reload
            </button>
          }
        />
      )}
    </AppShell>
  );
}
