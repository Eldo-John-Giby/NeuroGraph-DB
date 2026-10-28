'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import { apiRequest, getErrorMessage } from '../lib/api';
import { LoadingSpinner } from '../components/ui';
import BrandMark from '../components/BrandMark';

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
          <BrandMark className="auth-brand-symbol mx-auto mb-3"/>
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

        {/* Security Policy Note */}
        <p className="mt-6 text-center text-[11px] text-slate-500 leading-relaxed">
          User registration is restricted to administrators. Contact your system admin for account provisioning.
        </p>
      </div>
    </div>
  );
}
