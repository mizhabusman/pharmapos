import { useState } from 'react'
import { login } from './auth'
import { LogoIcon } from './Logo'

// Login.jsx — isolated login screen. Renders when there is no valid token.
// Calls onSuccess() after a successful login so the parent can proceed.
export default function Login({ apiBase, onSuccess }) {
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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
    <div className="h-screen bg-app-canvas flex items-center justify-center font-sans px-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="flex flex-col items-center mb-8">
          <div className="relative mb-4">
            <div className="relative bg-white border border-slate-200 p-3 rounded-2xl shadow-md">
              <LogoIcon className="w-12 h-12" />
            </div>
          </div>
          <h1 className="text-2xl font-black text-slate-800 tracking-tight">Pharmacy Management</h1>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] mt-1.5">
            <span className="text-green-600">AI-Powered</span>
            <span className="text-slate-500"> Point of Sale</span>
          </p>
        </div>

        {/* Card */}
        <form
          onSubmit={handleSubmit}
          className="bg-white border border-slate-200 rounded-2xl p-7 shadow-card-lg relative overflow-hidden"
        >
          {/* indeterminate loading bar */}
          {busy && (
            <div className="absolute top-0 left-0 right-0 h-1 bg-slate-100 overflow-hidden">
              <div className="h-full w-1/3 bg-green-600 rounded-full animate-indeterminate" />
            </div>
          )}

          <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">
            Password
          </label>

          <div className="flex items-center bg-slate-50 border border-slate-200 rounded-xl overflow-hidden focus-within:border-green-600 focus-within:ring-2 focus-within:ring-green-600/25 focus-within:bg-white transition-all">
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoFocus
              disabled={busy}
              placeholder="Enter password"
              className="flex-1 bg-transparent px-4 py-3 text-sm font-semibold text-slate-800 placeholder:text-slate-400 focus:outline-none disabled:opacity-60"
            />
            <button
              type="button"
              onClick={() => setShowPassword(s => !s)}
              tabIndex={-1}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="px-3 text-slate-400 hover:text-green-600 transition-colors"
            >
              {showPassword ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.542-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.542 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              )}
            </button>
          </div>

          {error && (
            <p className="mt-3 text-sm font-semibold text-rose-500">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy || !password}
            className="mt-5 w-full btn-green text-white font-bold py-3 rounded-xl text-sm tracking-wide flex items-center justify-center gap-2"
          >
            {busy ? (
              <>
                <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Signing in…
              </>
            ) : 'Sign In'}
          </button>
        </form>

        <p className="text-center text-slate-400 text-[11px] font-medium mt-6">
          Secure pharmacist access
        </p>
      </div>
    </div>
  )
}
