const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
let csrfToken = sessionStorage.getItem('checkin_csrf') || ''

type RequestOptions = RequestInit & { csrf?: boolean }

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (options.csrf) headers.set('X-CSRF-Token', csrfToken)
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  })
  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    try {
      const payload = await response.json()
      if (payload.detail) message = String(payload.detail)
    } catch {
      // Keep the status-based message for non-JSON gateway errors.
    }
    const error = new Error(message) as Error & { status?: number }
    error.status = response.status
    throw error
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  async login(username: string, password: string) {
    const session = await request<{ username: string; csrf_token: string }>('/api/auth/login', {
      method: 'POST', body: JSON.stringify({ username, password }),
    })
    csrfToken = session.csrf_token
    sessionStorage.setItem('checkin_csrf', csrfToken)
    return session
  },
  async session() {
    const session = await request<{ username: string; csrf_token: string }>('/api/auth/session')
    csrfToken = session.csrf_token
    sessionStorage.setItem('checkin_csrf', csrfToken)
    return session
  },
  async logout() {
    await request('/api/auth/logout', { method: 'POST', csrf: true })
    csrfToken = ''
    sessionStorage.removeItem('checkin_csrf')
  },
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, {
    method: 'POST', csrf: true, body: body === undefined ? undefined : JSON.stringify(body),
  }),
  publicPost: <T>(path: string, body: unknown) => request<T>(path, {
    method: 'POST', body: JSON.stringify(body),
  }),
  put: <T>(path: string, body: unknown) => request<T>(path, {
    method: 'PUT', csrf: true, body: JSON.stringify(body),
  }),
  patch: <T>(path: string, body: unknown) => request<T>(path, {
    method: 'PATCH', csrf: true, body: JSON.stringify(body),
  }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE', csrf: true }),
}
