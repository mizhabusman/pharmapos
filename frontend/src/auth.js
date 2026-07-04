// auth.js — isolated auth helpers (token storage + authenticated fetch).
//
// Keeping this separate from App.jsx means the login mechanism can change
// (e.g. per-user accounts, refresh tokens) without touching UI code — callers
// only use login(), logout(), getToken() and authFetch().

const TOKEN_KEY = 'pharmapos_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY)
}

// Exchange a password for a token. Throws with a readable message on failure.
export async function login(apiBase, password, username = '') {
  const res = await fetch(`${apiBase}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.detail || 'Login failed. Please check your password.')
  }
  const data = await res.json()
  setToken(data.access_token)
  return data
}

// fetch() wrapper that injects the bearer token. On a 401 it clears the token
// and emits a window event so the app can drop back to the login screen.
export async function authFetch(url, options = {}) {
  const token = getToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(url, { ...options, headers })
  if (res.status === 401) {
    logout()
    window.dispatchEvent(new Event('pharmapos:unauthorized'))
  }
  return res
}
