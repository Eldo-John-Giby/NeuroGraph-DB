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
      // A full transition drops cached protected route state after sign-out
      // and remains reliable across production deployments and role switches.
      if (window.location.pathname !== '/login') window.location.replace('/login');
    }
    if (!isLoading && user && adminOnly && !isAdmin) {
      router.replace('/');
    }
  }, [isLoading, user, adminOnly, isAdmin, router]);

  return { user, isLoading, isAdmin, isAuthenticated: !!user };
}
