'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { UserPlus, ShieldCheck, X, AlertCircle, Check } from 'lucide-react';
import AppShell from '../../components/AppShell';
import {
  PageHeader,
  StatCard,
  LoadingSpinner,
  TableSkeleton,
  EmptyState,
  ErrorState,
  StatusBadge,
} from '../../components/ui';
import { useRequireAuth } from '../../hooks/useRequireAuth';
import { apiRequest, isApiError, getErrorMessage } from '../../lib/api';

interface UserRecord {
  user_id: number;
  email: string;
  username: string | null;
  role_key: 'ADMIN' | 'RESEARCHER';
  is_active: boolean;
}

interface ListUsersResponse {
  items: UserRecord[];
  limit: number;
  offset: number;
}

export default function UserAdministrationPage() {
  const { user: currentUser, isLoading: authLoading, isAdmin, isAuthenticated } = useRequireAuth(true);

  // Users list state
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState<number>(0);
  const limit = 10;

  // Create User Modal & Form State
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [email, setEmail] = useState<string>('');
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [roleKey, setRoleKey] = useState<'RESEARCHER' | 'ADMIN'>('RESEARCHER');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);

  const fetchUsers = useCallback(async (currentOffset = offset) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiRequest<ListUsersResponse>(
        `/api/v1/users?limit=${limit}&offset=${currentOffset}`
      );
      setUsers(data?.items || []);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [offset, limit]);

  useEffect(() => {
    if (isAuthenticated && isAdmin) {
      fetchUsers(offset);
    }
  }, [isAuthenticated, isAdmin, offset, fetchUsers]);

  // Form Validation & Submission
  const validateForm = (): boolean => {
    setFormError(null);
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setFormError('Email address is required.');
      return false;
    }
    if (trimmedEmail.indexOf('@') <= 0 || trimmedEmail.lastIndexOf('.') <= trimmedEmail.indexOf('@') + 1) {
      setFormError('Please provide a valid email address.');
      return false;
    }
    if (username.trim() && (username.trim().length < 2 || username.trim().length > 80)) {
      setFormError('Username must be between 2 and 80 characters if provided.');
      return false;
    }
    if (!password || password.length < 12) {
      setFormError('Password must be at least 12 characters long according to security policy.');
      return false;
    }
    if (password.length > 256) {
      setFormError('Password must not exceed 256 characters.');
      return false;
    }
    return true;
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setSubmitting(true);
    setFormError(null);
    setFormSuccess(null);

    try {
      await apiRequest<UserRecord>('/api/v1/users', {
        method: 'POST',
        body: JSON.stringify({
          email: email.trim(),
          username: username.trim() || undefined,
          password,
          role_key: roleKey,
        }),
      });

      setFormSuccess(`User ${email.trim()} created successfully with role ${roleKey}.`);
      // Reset form
      setEmail('');
      setUsername('');
      setPassword('');
      setRoleKey('RESEARCHER');

      // Refresh users list
      await fetchUsers(offset);

      // Close modal after brief delay
      setTimeout(() => {
        setIsModalOpen(false);
        setFormSuccess(null);
      }, 1500);
    } catch (err: unknown) {
      setFormError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenModal = () => {
    setEmail('');
    setUsername('');
    setPassword('');
    setRoleKey('RESEARCHER');
    setFormError(null);
    setFormSuccess(null);
    setIsModalOpen(true);
  };

  const handlePageChange = (newOffset: number) => {
    setOffset(newOffset);
  };

  if (authLoading || !isAuthenticated || !isAdmin) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <LoadingSpinner text="Verifying administrator credentials..." />
      </div>
    );
  }

  // Calculate statistics from loaded dataset
  const activeCount = users.filter((u) => u.is_active).length;
  const adminCount = users.filter((u) => u.role_key === 'ADMIN').length;
  const researcherCount = users.filter((u) => u.role_key === 'RESEARCHER').length;
  const hasMore = users.length === limit;

  return (
    <AppShell>
      <PageHeader
        title="User Administration"
        subtitle="Manage authenticated identities, assign RBAC access roles, and provision researcher credentials"
        actions={
          <button
            onClick={handleOpenModal}
            className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-indigo-500 transition-colors"
          >
            <UserPlus className="h-3.5 w-3.5" />
            Provision New User
          </button>
        }
      />

      {/* Stats Cards */}
      <div className="mb-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Current Page Accounts" value={users.length} color="white" />
        <StatCard label="Active Accounts" value={activeCount} color="emerald" />
        <StatCard label="Administrators" value={adminCount} color="rose" />
        <StatCard label="Researchers" value={researcherCount} color="sky" />
      </div>

      {/* Main Content Area */}
      {loading ? (
        <TableSkeleton rows={limit} cols={6} />
      ) : error ? (
        <ErrorState message={error} onRetry={() => fetchUsers(offset)} />
      ) : users.length === 0 ? (
        <EmptyState
          icon={<ShieldCheck className="h-8 w-8 text-slate-500" />}
          title="No Users Registered"
          message="No user records matched your current query range."
          action={
            <button
              onClick={handleOpenModal}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
            >
              Create First User
            </button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-800/80 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-4 py-3">User ID</th>
                  <th className="px-4 py-3">Email Address</th>
                  <th className="px-4 py-3">Username</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Account Status</th>
                  <th className="px-4 py-3 text-right">Identifier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                {users.map((item) => {
                  const isCurrent = currentUser?.user_id === item.user_id;
                  return (
                    <tr key={item.user_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 font-semibold text-indigo-400">#{item.user_id}</td>
                      <td className="px-4 py-3 font-sans text-white font-medium">
                        <div className="flex items-center gap-2">
                          <span>{item.email}</span>
                          {isCurrent && (
                            <span className="rounded bg-indigo-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-300 border border-indigo-500/30 font-sans">
                              You
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-300 font-sans">
                        {item.username ? (
                          <span>@{item.username}</span>
                        ) : (
                          <span className="text-slate-500 italic">None</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${
                            item.role_key === 'ADMIN'
                              ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                              : 'bg-sky-500/15 text-sky-400 border-sky-500/30'
                          }`}
                        >
                          {item.role_key}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          status={item.is_active ? 'Active' : 'Inactive'}
                          variant={item.is_active ? 'success' : 'error'}
                        />
                      </td>
                      <td className="px-4 py-3 text-right font-sans text-slate-500 text-[11px]">
                        ID:{item.user_id}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900/80 px-4 py-3 text-xs text-slate-400">
            <div>
              Showing items {offset + 1}–{offset + users.length}
            </div>
            <div className="flex gap-2">
              <button
                disabled={offset <= 0}
                onClick={() => handlePageChange(Math.max(0, offset - limit))}
                className="rounded border border-slate-700 bg-slate-800 px-3 py-1 font-semibold text-slate-300 disabled:opacity-40 hover:bg-slate-700 transition-colors"
              >
                Previous
              </button>
              <button
                disabled={!hasMore}
                onClick={() => handlePageChange(offset + limit)}
                className="rounded border border-slate-700 bg-slate-800 px-3 py-1 font-semibold text-slate-300 disabled:opacity-40 hover:bg-slate-700 transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create User Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 font-bold">
                  <UserPlus className="h-4 w-4 text-indigo-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Provision New User Account</h3>
                  <p className="text-xs text-slate-400">Create an authenticated system account with role privileges</p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {formError && (
              <div className="mt-4 flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-400">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            {formSuccess && (
              <div className="mt-4 flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-400">
                <Check className="h-4 w-4 shrink-0" />
                <span>{formSuccess}</span>
              </div>
            )}

            <form onSubmit={handleCreateUser} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Email Address <span className="text-rose-400">*</span>
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst@neurograph.io"
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Username <span className="text-slate-500 lowercase">(optional, 2-80 chars)</span>
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. data_scientist_01"
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Password <span className="text-rose-400">*</span>
                  </label>
                  <span className="text-[10px] text-slate-400">Min 12 characters</span>
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
                <p className="mt-1 text-[11px] text-slate-500">
                  Must meet backend policy: 12-256 characters with bcrypt hashing.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Role Assignment
                </label>
                <select
                  value={roleKey}
                  onChange={(e) => setRoleKey(e.target.value as 'RESEARCHER' | 'ADMIN')}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="RESEARCHER">RESEARCHER (Submit reviews, run inferences, view metrics)</option>
                  <option value="ADMIN">ADMIN (Full RBAC, user creation, graph sync, audit control)</option>
                </select>
              </div>

              <div className="mt-6 flex justify-end gap-3 border-t border-slate-800 pt-4">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  disabled={submitting}
                  className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow hover:bg-indigo-500 transition-colors disabled:opacity-50"
                >
                  {submitting ? (
                    <>
                      <div className="h-3 w-3 animate-spin rounded-full border border-white border-t-transparent" />
                      Provisioning...
                    </>
                  ) : (
                    'Create Account'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
