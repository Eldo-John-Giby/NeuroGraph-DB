'use client';

import React from 'react';

/** Page header with title and optional subtitle */
export function PageHeader({ title, subtitle, actions }: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

/** Stat card for dashboard counters */
export function StatCard({ label, value, color = 'white', subtext }: {
  label: string;
  value: string | number;
  color?: 'white' | 'indigo' | 'emerald' | 'rose' | 'sky' | 'amber';
  subtext?: string;
}) {
  const colorClass = {
    white: 'text-white',
    indigo: 'text-indigo-400',
    emerald: 'text-emerald-400',
    rose: 'text-rose-400',
    sky: 'text-sky-400',
    amber: 'text-amber-400',
  }[color];

  return (
    <div className="rounded-xl border border-slate-700/50 bg-slate-800/50 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${colorClass}`}>{value}</p>
      {subtext && <p className="mt-0.5 text-xs text-slate-500">{subtext}</p>}
    </div>
  );
}

/** Loading spinner */
export function LoadingSpinner({ text = 'Loading...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-slate-500">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-indigo-500 mb-3" />
      <p className="text-sm">{text}</p>
    </div>
  );
}

/** Table loading skeleton */
export function TableSkeleton({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
      <div className="bg-slate-800/80 px-4 py-3 flex gap-8">
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="h-3 w-20 rounded bg-slate-700 animate-pulse" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-8 px-4 py-3 border-t border-slate-800/40">
          {Array.from({ length: cols }).map((_, j) => (
            <div key={j} className="h-3 w-16 rounded bg-slate-800 animate-pulse" />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Empty state placeholder */
export function EmptyState({ title, message, action, icon }: {
  icon?: React.ReactNode;
  title: string;
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-slate-800 bg-slate-900/40 py-16 px-6">
      {icon ? (
        <div className="mb-3 text-slate-500 flex items-center justify-center">{icon}</div>
      ) : (
        <span className="ui-state-mark mb-3" aria-hidden="true" />
      )}
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      <p className="mt-1 text-sm text-slate-400 max-w-sm text-center">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Error state with retry */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-rose-500/30 bg-rose-500/5 py-12 px-6">
      <span className="ui-state-mark ui-state-mark-risk mb-3" aria-hidden="true">!</span>
      <h3 className="text-lg font-semibold text-rose-400">Something went wrong</h3>
      <p className="mt-1 text-sm text-slate-400 max-w-md text-center">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-lg bg-rose-600/20 border border-rose-500/30 px-4 py-2 text-sm font-semibold text-rose-400 hover:bg-rose-600/30 transition-colors"
        >
          Try Again
        </button>
      )}
    </div>
  );
}

/** Warning banner (e.g., for model verification pending) */
export function WarningBanner({ title, message }: {
  title: string;
  message: string;
  icon?: string;
}) {
  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
      <div className="flex items-start gap-3">
        <span className="ui-state-mark ui-state-mark-risk" aria-hidden="true">!</span>
        <div>
          <h3 className="text-sm font-bold text-amber-300">{title}</h3>
          <p className="text-xs text-slate-400 mt-0.5">{message}</p>
        </div>
      </div>
    </div>
  );
}

/** Info banner */
export function InfoBanner({ title, message }: {
  title: string;
  message: string;
  icon?: string;
}) {
  return (
    <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/5 p-4">
      <div className="flex items-start gap-3">
        <span className="ui-state-mark" aria-hidden="true">i</span>
        <div>
          <h3 className="text-sm font-bold text-indigo-300">{title}</h3>
          <p className="text-xs text-slate-400 mt-0.5">{message}</p>
        </div>
      </div>
    </div>
  );
}

/** Badge for status indicators */
export function StatusBadge({ status, variant }: {
  status: string;
  variant?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
}) {
  const auto = (() => {
    switch (status.toLowerCase()) {
      case 'verified': case 'completed': case 'available': case 'succeeded': case 'active': return 'success';
      case 'registered': case 'queued': case 'running': case 'retry_wait': return 'warning';
      case 'failed': case 'cancelled': case 'retired': case 'unavailable': case 'missing': return 'error';
      default: return 'neutral';
    }
  })();
  const v = variant || auto;

  const cls = {
    success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    error: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    info: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30',
    neutral: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
  }[v];

  return (
    <span className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${cls}`}>
      {status}
    </span>
  );
}

/** Pagination controls */
export function Pagination({ offset, limit, total, onPageChange }: {
  offset: number;
  limit: number;
  total: number;
  onPageChange: (newOffset: number) => void;
}) {
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900/80 px-4 py-3 text-xs text-slate-400">
      <div>
        Showing {Math.min(offset + 1, total)}–{Math.min(offset + limit, total)} of {total} (Page {currentPage} of {totalPages})
      </div>
      <div className="flex gap-2">
        <button
          disabled={offset <= 0}
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          className="rounded border border-slate-700 bg-slate-800 px-3 py-1 font-semibold text-slate-300 disabled:opacity-40 hover:bg-slate-700"
        >
          Previous
        </button>
        <button
          disabled={offset + limit >= total}
          onClick={() => onPageChange(offset + limit)}
          className="rounded border border-slate-700 bg-slate-800 px-3 py-1 font-semibold text-slate-300 disabled:opacity-40 hover:bg-slate-700"
        >
          Next
        </button>
      </div>
    </div>
  );
}

/** Confirmation dialog */
export function ConfirmDialog({ isOpen, title, message, confirmLabel = 'Confirm', onConfirm, onCancel }: {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
        <h3 className="text-lg font-bold text-white">{title}</h3>
        <p className="mt-2 text-sm text-slate-400">{message}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onCancel} className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-300 hover:bg-slate-700">Cancel</button>
          <button onClick={onConfirm} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-500">{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
