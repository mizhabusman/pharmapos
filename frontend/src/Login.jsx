import { useState } from 'react'
import { login } from './auth'

// Login.jsx — isolated login screen. Renders when there is no valid token.
// Calls onSuccess() after a successful login so the parent can proceed.
export default function Login({ apiBase, onSuccess }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await login(apiBase, password)
      onSuccess()
    } catch (err) {
      setError(err.message || 'Login failed')
      setBusy(false)
    }
  }

  return (
    <div className="h-screen bg-[#0F172A] flex items-center justify-center font-sans px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="bg-[#2563EB] text-white p-3 rounded-2xl shadow-lg shadow-[#2563EB]/30 mb-4">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
          </div>
          <h1 className="text-2xl font-black text-white tracking-tight">PharmaPOS</h1>
          <p className="text-slate-400 text-[10px] font-bold uppercase tracking-widest mt-1">Prescription Intelligence</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-[#1E293B] border border-[#334155] rounded-2xl p-7 shadow-2xl">
          <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-widest mb-2">
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            autoFocus
            placeholder="Enter password"
            className="w-full bg-[#0F172A] border border-[#334155] rounded-xl px-4 py-3 text-sm font-semibold text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/30 transition-all"
          />

          {error && (
            <p className="mt-3 text-sm font-semibold text-rose-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy || !password}
            className="mt-5 w-full bg-[#2563EB] text-white font-bold py-3 rounded-xl hover:bg-[#1D4ED8] disabled:opacity-40 transition-all shadow-lg shadow-[#2563EB]/20 text-sm tracking-wide"
          >
            {busy ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
