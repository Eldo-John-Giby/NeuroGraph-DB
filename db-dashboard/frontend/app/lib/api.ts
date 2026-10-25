/**
 * Central API client for NeuroGraph-DB frontend.
 *
 * All requests go through the Next.js proxy rewrite (/api/v1/* → localhost:8000/api/v1/*),
 * so we use a relative base path. This solves port mismatch and SameSite cookie restrictions.
 *
 * The backend returns errors in the shape:
 *   { error: { code: string, message: string, request_id: string, details: {} } }
 *
 * apiRequest reads `data.error.message` to produce a human-readable Error.
 */

const API_BASE = '';  // relative — Next.js rewrites proxy to backend

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

export async function apiRequest<T = unknown>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('neuro_token') : null;
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  // Let fetch add the multipart boundary when a caller uploads FormData.
  if (!(typeof FormData !== 'undefined' && options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',  // send cookies for refresh token
  });

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
