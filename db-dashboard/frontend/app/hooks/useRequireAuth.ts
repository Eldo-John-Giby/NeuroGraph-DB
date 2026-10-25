'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../context/AuthContext';

/**
 * Hook that guards a page — redirects to /login if not authenticated.
 * Returns the user and loading state.
 */
export function useRequireAuth(adminOnly = false) {
  const router = useRouter();
  const { user, isLoading, isAdmin } = useAuth();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/login');
    }
    if (!isLoading && user && adminOnly && !isAdmin) {
      router.push('/');
    }
  }, [isLoading, user, adminOnly, isAdmin, router]);

  return { user, isLoading, isAdmin, isAuthenticated: !!user };
}
