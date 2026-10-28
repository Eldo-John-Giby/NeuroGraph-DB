'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { apiRequest, clearSession, isApiError, saveSession, SESSION_EXPIRED_EVENT } from '../lib/api';

export interface User {
  user_id: number;
  username: string | null;
  email: string;
  role_key: 'ADMIN' | 'RESEARCHER' | string;
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  login: (accessToken: string, user: User) => void;
  logout: () => void;
  isLoading: boolean;
  isAdmin: boolean;
}

export const isUserAdmin = (u: User | null | undefined): boolean => {
  return typeof u?.role_key === 'string' && u.role_key.trim().toUpperCase() === 'ADMIN';
};

const AuthContext = createContext<AuthContextType>({
  user: null,
  login: () => {},
  logout: () => {},
  isLoading: true,
  isAdmin: false,
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const authEpoch = useRef(0);

  // Administration access requires verified ADMIN role and completed auth loading
  const isAdmin = !isLoading && Boolean(user?.role_key?.trim().toUpperCase() === 'ADMIN');

  const login = useCallback((accessToken: string, newUser: User) => {
    authEpoch.current += 1;
    saveSession(accessToken, newUser);
    setUser(newUser);
    setIsLoading(false);
  }, []);

  const logout = useCallback(async () => {
    authEpoch.current += 1;
    try {
      await apiRequest('/api/v1/auth/logout', { method: 'POST' });
    } catch {
      // Ignore errors during logout
    }
    clearSession();
    setUser(null);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    let active = true;
    const epoch = authEpoch.current;
    const sessionEnded = () => {
      authEpoch.current += 1;
      setUser(null);
      setIsLoading(false);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, sessionEnded);
    const cleanup = () => {
      active = false;
      window.removeEventListener(SESSION_EXPIRED_EVENT, sessionEnded);
    };
    const savedToken = localStorage.getItem('neuro_token');
    const savedUser = localStorage.getItem('neuro_user');
    if (savedToken && savedUser) {
      try {
        const parsed = JSON.parse(savedUser) as User;
        // Verify the role before exposing protected pages. apiRequest renews
        // expired access tokens using the HttpOnly refresh cookie.
        apiRequest<User>('/api/v1/auth/me')
          .then((freshUser) => {
            if (!active || epoch !== authEpoch.current) return;
            setUser(freshUser);
            localStorage.setItem('neuro_user', JSON.stringify(freshUser));
          })
          .catch((error: unknown) => {
            if (!active || epoch !== authEpoch.current) return;
            if (isApiError(error) && error.status === 401) {
              if (error.code !== 'session_changed') clearSession();
              setUser(null);
            } else {
              // A temporary network failure is not proof of session expiry.
              setUser(parsed);
            }
          })
          .finally(() => { if (active && epoch === authEpoch.current) setIsLoading(false); });
        return cleanup;
      } catch {
        clearSession();
      }
    }
    setIsLoading(false);
    return cleanup;
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading, isAdmin }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
