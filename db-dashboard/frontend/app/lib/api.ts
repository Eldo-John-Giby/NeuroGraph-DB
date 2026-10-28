/**
 * Central API client for NeuroGraph-DB frontend.
 *
 * All requests go through the Next.js proxy rewrite to the configured BACKEND_URL,
 * so we use a relative base path. This solves port mismatch and SameSite cookie restrictions.
 *
 * The backend returns errors in the shape:
 *   { error: { code: string, message: string, request_id: string, details: {} } }
 *
 * apiRequest reads `data.error.message` to produce a human-readable Error.
 */

const API_BASE = '';  // relative — Next.js rewrites proxy to backend
export const SESSION_EXPIRED_EVENT = 'neurograph:session-expired';
let sessionGeneration = 0;
let refreshInFlight: Promise<string> | null = null;

const storedToken = () => typeof window !== 'undefined' ? localStorage.getItem('neuro_token') : null;
const storedUser = () => typeof window !== 'undefined' ? localStorage.getItem('neuro_user') : null;

export function saveSession(accessToken: string, user: unknown): void {
  sessionGeneration += 1;
  localStorage.setItem('neuro_token', accessToken);
  localStorage.setItem('neuro_user', JSON.stringify(user));
}

export function clearSession(): void {
  sessionGeneration += 1;
  localStorage.removeItem('neuro_token');
  localStorage.removeItem('neuro_user');
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}

export class ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;
  details?: Record<string, unknown>;

  constructor(status: number, code: string, message: string, requestId?: string, details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

async function refreshAccessToken(failedToken: string, generation: number, user: string | null): Promise<string> {
  if (refreshInFlight) return refreshInFlight;
  const refresh = async () => {
    if (generation !== sessionGeneration || storedUser() !== user) throw new ApiError(401, 'session_changed', 'Please sign in again.');
    const latest = storedToken();
    if (latest && latest !== failedToken) return latest;
    const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST', credentials: 'include', cache: 'no-store',
    });
    const data = await response.json().catch(() => null);
    if (generation !== sessionGeneration || storedUser() !== user) throw new ApiError(401, 'session_changed', 'Please sign in again.');
    if (!response.ok || typeof data?.access_token !== 'string' || !data.access_token) {
      // A network/server failure must not erase a valid refresh session.
      if (response.status === 401 || response.status === 403) clearSession();
      throw new ApiError(response.status, data?.error?.code || 'refresh_failed',
        response.status === 401 || response.status === 403 ? 'Your session has ended. Please sign in again.' : 'Could not renew your session. Please try again.');
    }
    localStorage.setItem('neuro_token', data.access_token);
    return data.access_token as string;
  };
  // One refresh per browser origin, including parallel requests in other tabs.
  // Browsers without Web Locks still share one refresh within this tab.
  const operation = (async (): Promise<string> => {
    if (typeof navigator !== 'undefined' && navigator.locks) {
      return await navigator.locks.request('neurograph-session-refresh', refresh);
    }
    return refresh();
  })();
  refreshInFlight = operation;
  try {
    return await operation;
  } finally {
    if (refreshInFlight === operation) refreshInFlight = null;
  }
}

export async function apiRequest<T = unknown>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = storedToken();
  const generation = sessionGeneration;
  const user = storedUser();
  const headers = new Headers(options.headers);
  // Let fetch add the multipart boundary when a caller uploads FormData.
  if (!(typeof FormData !== 'undefined' && options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const send = () => fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',  // send cookies for refresh token
    cache: 'no-store',
  });
  let response = await send();
  const authEndpoint = /^\/api\/v1\/auth\/(login|refresh)(?:[/?]|$)/.test(endpoint);
  if (response.status === 401 && token && !authEndpoint && generation === sessionGeneration) {
    const freshToken = await refreshAccessToken(token, generation, user);
    if (generation !== sessionGeneration || storedUser() !== user) throw new ApiError(401, 'session_changed', 'Please sign in again.');
    headers.set('Authorization', `Bearer ${freshToken}`);
    response = await send();
    // Retry once only. A revoked session must not leave a cached admin visible.
    if (response.status === 401 && generation === sessionGeneration) clearSession();
  }

  // Handle 204 No Content (logout, etc.)
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    // Parse the structured error from the backend: { error: { code, message, request_id, details } }
    if (data && typeof data === 'object' && data.error && typeof data.error === 'object') {
      const err = data.error;
      throw new ApiError(
        response.status,
        err.code || 'unknown_error',
        err.message || response.statusText || 'Request failed',
        err.request_id,
        err.details,
      );
    }
    // Fallback for unexpected error shapes
    const fallbackMessage = typeof data === 'string' ? data : response.statusText || 'Request failed';
    throw new ApiError(response.status, 'unknown_error', fallbackMessage);
  }

  return data as T;
}

/**
 * Check if an error is a specific API error code.
 */
export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/**
 * Check if an error indicates a service-unavailable condition (503).
 */
export function isServiceUnavailable(error: unknown): boolean {
  return isApiError(error) && error.status === 503;
}

/**
 * Extract a human-readable error message from any error.
 */
export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    const reference = [error.status ? `HTTP ${error.status}` : '', error.code !== 'unknown_error' ? error.code : '', error.requestId ? `request ${error.requestId}` : '']
      .filter(Boolean).join(' · ');
    return reference ? `${error.message} (${reference})` : error.message;
  }
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'An unexpected error occurred';
}
