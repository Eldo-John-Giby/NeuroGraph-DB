'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import { apiRequest } from '../lib/api';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'RESEARCHER' | 'ADMIN'>('RESEARCHER');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        const res = await apiRequest('/api/auth/register', {
          method: 'POST',
          body: JSON.stringify({ username, email, password, role }),
        });
        login(res.token, res.user);
        router.push('/');
      } else {
        const res = await apiRequest('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({ username, password }),
        });
        login(res.token, res.user);
        router.push('/');
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = (demoRole: 'ADMIN' | 'RESEARCHER') => {
    if (demoRole === 'ADMIN') {
      setUsername('admin');
      setPassword('admin123');
    } else {
      setUsername('researcher');
      setPassword('researcher123');
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6 bg-slate-950">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/90 p-8 shadow-2xl backdrop-blur-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 font-bold text-2xl">
            ⬡
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            NeuroGraph-DB
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            {isRegister ? 'Create researcher or admin account' : 'Sign in to access ML & Graph Database'}
          </p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-400">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Username
            </label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. admin or researcher"
              className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {isRegister && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="researcher@neurograph.io"
                className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {isRegister && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                RBAC Role Assignment
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as any)}
                className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="RESEARCHER">Researcher (Read & Write Runs)</option>
                <option value="ADMIN">Admin (Full RBAC + Delete + Stored Procs + Audit Logs)</option>
              </select>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Processing...' : isRegister ? 'Register Account' : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 flex items-center justify-between border-t border-slate-800 pt-4 text-xs text-slate-400">
          <button
            type="button"
            onClick={() => setIsRegister(!isRegister)}
            className="text-indigo-400 hover:text-indigo-300 font-medium"
          >
            {isRegister ? 'Already registered? Sign in' : "Don't have an account? Register"}
          </button>
        </div>

        <div className="mt-4 rounded-lg bg-slate-950/60 p-3 text-xs text-slate-400 border border-slate-800/80">
          <p className="font-semibold text-slate-300 mb-1">Quick Demo Credentials:</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleQuickLogin('ADMIN')}
              className="rounded bg-slate-800 px-2.5 py-1 text-indigo-300 hover:bg-slate-700 font-mono transition-colors"
            >
              Fill Admin (admin123)
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin('RESEARCHER')}
              className="rounded bg-slate-800 px-2.5 py-1 text-emerald-300 hover:bg-slate-700 font-mono transition-colors"
            >
              Fill Researcher (researcher123)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
