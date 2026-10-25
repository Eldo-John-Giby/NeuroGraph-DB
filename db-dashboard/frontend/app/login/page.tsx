'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import { apiRequest, getErrorMessage } from '../lib/api';
import { LoadingSpinner } from '../components/ui';

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    user_id: number;
    email: string;
    username: string | null;
    role_key: 'ADMIN' | 'RESEARCHER';
    is_active: boolean;
  };
}

export default function LoginPage() {
  const router = useRouter();
  const { user, login, isLoading: authLoading } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (!authLoading && user) {
      router.push('/');
    }
  }, [authLoading, user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setError('Email address is required.');
      return;
    }
    if (!password) {
      setError('Password is required.');
      return;
    }

    setIsSubmitting(true);

    try {
      const res = await apiRequest<LoginResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: cleanEmail, password }),
      });

      login(res.access_token, res.user);
      router.push('/');
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickFill = (demoRole: 'ADMIN' | 'RESEARCHER') => {
    setError(null);
    if (demoRole === 'ADMIN') {
      setEmail('admin@neurograph.local');
      setPassword('Admin1234567!');
    } else {
      setEmail('researcher@neurograph.local');
      setPassword('Research1234567!');
    }
  };

  if (authLoading) {
    return (
      <div className="auth-page flex min-h-screen items-center justify-center">
        <LoadingSpinner text="Checking session..." />
      </div>
    );
  }

  return (
    <div className="auth-page flex min-h-screen items-center justify-center p-6">
      <div className="auth-card w-full max-w-md rounded-2xl border p-8 shadow-xl">
        {/* Brand Header */}
        <div className="mb-8 text-center">
          <div className="auth-brand-mark mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl border font-bold text-xl">
            N
          </div>
          <h1 className="auth-title text-2xl font-bold tracking-tight">
            NeuroGraph-DB
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Sign in to your product review integrity workspace
          </p>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="mb-6 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-400 flex items-start gap-2.5">
            <span className="auth-error-mark" aria-hidden="true">!</span>
            <div className="leading-snug">{error}</div>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="email-input"
              className="block text-xs font-semibold uppercase tracking-wider text-slate-300"
            >
              Email Address
            </label>
            <input
              id="email-input"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. admin@neurograph.local"
              disabled={isSubmitting}
              className="mt-1.5 block w-full rounded-lg border border-slate-700 bg-slate-800/80 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
            />
          </div>

          <div>
            <label
              htmlFor="password-input"
              className="block text-xs font-semibold uppercase tracking-wider text-slate-300"
            >
              Password
            </label>
            <input
              id="password-input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              disabled={isSubmitting}
              className="mt-1.5 block w-full rounded-lg border border-slate-700 bg-slate-800/80 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="auth-submit w-full mt-2 flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white shadow-md disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                <span>Signing in...</span>
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        {/* Quick Demo Credentials */}
        <div className="mt-8 rounded-xl bg-slate-950/70 p-4 border border-slate-800 text-xs text-slate-400">
          <p className="font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
            Quick demo credentials
          </p>
          <p className="text-slate-400 mb-3 text-[11px] leading-relaxed">
            Click a demo role below to automatically fill verified test credentials:
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => handleQuickFill('ADMIN')}
              className="auth-credential flex flex-col items-start gap-1 rounded-lg border p-2.5 text-left transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <span className="rounded bg-rose-500/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-rose-300 border border-rose-500/30">
                  Admin
                </span>
              </div>
              <span className="font-mono text-[11px] text-slate-300 truncate w-full">
                admin@neurograph.local
              </span>
              <span className="font-mono text-[10px] text-slate-500">
                Admin1234567!
              </span>
            </button>

            <button
              type="button"
              onClick={() => handleQuickFill('RESEARCHER')}
              className="auth-credential flex flex-col items-start gap-1 rounded-lg border p-2.5 text-left transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-300 border border-emerald-500/30">
                  Researcher
                </span>
              </div>
              <span className="font-mono text-[11px] text-slate-300 truncate w-full">
                researcher@neurograph.local
              </span>
              <span className="font-mono text-[10px] text-slate-500">
                Research1234567!
              </span>
            </button>
          </div>
        </div>

        {/* Security Policy Note */}
        <p className="mt-6 text-center text-[11px] text-slate-500 leading-relaxed">
          User registration is restricted to administrators. Contact your system admin for account provisioning.
        </p>
      </div>
    </div>
  );
}
