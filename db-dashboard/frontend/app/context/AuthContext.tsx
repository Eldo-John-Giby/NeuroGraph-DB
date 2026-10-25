'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiRequest, isApiError } from '../lib/api';

export interface User {
  user_id: number;
  username: string | null;
  email: string;
  role_key: 'ADMIN' | 'RESEARCHER';
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  login: (accessToken: string, user: User) => void;
  logout: () => void;
  isLoading: boolean;
  isAdmin: boolean;
}

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

  const isAdmin = user?.role_key === 'ADMIN';

  const login = useCallback((accessToken: string, newUser: User) => {
    localStorage.setItem('neuro_token', accessToken);
    localStorage.setItem('neuro_user', JSON.stringify(newUser));
    setUser(newUser);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiRequest('/api/v1/auth/logout', { method: 'POST' });
    } catch {
      // Ignore errors during logout
    }
    localStorage.removeItem('neuro_token');
    localStorage.removeItem('neuro_user');
    setUser(null);
  }, []);

  useEffect(() => {
    const savedToken = localStorage.getItem('neuro_token');
    const savedUser = localStorage.getItem('neuro_user');
    if (savedToken && savedUser) {
      try {
        const parsed = JSON.parse(savedUser) as User;
        setUser(parsed);
        // Validate the session is still alive by calling /auth/me
        apiRequest<User>('/api/v1/auth/me')
          .then((freshUser) => {
            setUser(freshUser);
            localStorage.setItem('neuro_user', JSON.stringify(freshUser));
          })
          .catch(() => {
            // Session is invalid, clear everything
            localStorage.removeItem('neuro_token');
            localStorage.removeItem('neuro_user');
            setUser(null);
          })
          .finally(() => setIsLoading(false));
        return;
      } catch {
        localStorage.removeItem('neuro_token');
        localStorage.removeItem('neuro_user');
      }
    }
    setIsLoading(false);
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading, isAdmin }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
