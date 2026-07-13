import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import UpsLogo from '../components/ui/UpsLogo'
import { useAuth } from '../hooks/useAuth'

// A branded login screen: users sign in with a username and password. On a
// valid submit we exchange credentials for a JWT (role-based), persist the
// session, and route into the app.
export default function Login() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!userId.trim() || !password.trim()) {
      setError('Please enter both your user ID and password.')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      await login(userId.trim(), password)
      navigate('/')
    } catch (err) {
      setError(err?.message || 'Sign in failed. Please check your credentials.')
      setSubmitting(false)
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-[#fdf6ec] via-white to-[#f6e4c4] px-4">
      {/* Soft brand glows */}
      <div className="pointer-events-none absolute -left-40 -top-40 h-96 w-96 rounded-full bg-brand-gold/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-brand-brown/15 blur-3xl" />

      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="rounded-3xl border border-white/60 bg-white/80 p-8 shadow-[0_30px_80px_-30px_rgba(43,24,16,0.5)] backdrop-blur-xl sm:p-10">
          {/* Brand */}
          <div className="mb-8 flex flex-col items-center text-center">
            <UpsLogo className="h-14 w-12" />
            <h1 className="mt-4 font-display text-2xl font-semibold text-brand-brownDeep">Welcome back</h1>
            <p className="mt-1 text-sm text-brand-brown/60">Sign in to Invoice Intelligence</p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            {/* User ID */}
            <div>
              <label htmlFor="userId" className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.15em] text-brand-brown/60">
                User ID
              </label>
              <div className="flex items-center gap-2 rounded-xl border border-brand-brown/15 bg-white px-3 py-2.5 transition-colors focus-within:border-brand-gold">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 text-brand-brown/40">
                  <circle cx="8" cy="5" r="3" stroke="currentColor" strokeWidth="1.5" />
                  <path d="M2.5 13.5c0-2.5 2.5-4 5.5-4s5.5 1.5 5.5 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
                <input
                  id="userId"
                  type="text"
                  autoComplete="username"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="Enter your user ID"
                  className="w-full bg-transparent text-sm text-brand-brownDeep placeholder:text-brand-brown/40 focus:outline-none"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.15em] text-brand-brown/60">
                Password
              </label>
              <div className="flex items-center gap-2 rounded-xl border border-brand-brown/15 bg-white px-3 py-2.5 transition-colors focus-within:border-brand-gold">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 text-brand-brown/40">
                  <rect x="3" y="7" width="10" height="6.5" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
                  <path d="M5.5 7V5a2.5 2.5 0 015 0v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full bg-transparent text-sm text-brand-brownDeep placeholder:text-brand-brown/40 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="shrink-0 text-brand-brown/40 transition-colors hover:text-brand-brownDeep"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <path d="M2 2l12 12M6.5 6.6A2 2 0 008 10a2 2 0 001.4-.6M4.2 4.5C2.9 5.4 2 8 2 8s2.2 3.5 6 3.5c1 0 1.9-.2 2.6-.6M8 4.5c3.8 0 6 3.5 6 3.5s-.5.8-1.4 1.7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <path d="M2 8s2.2-3.5 6-3.5S14 8 14 8s-2.2 3.5-6 3.5S2 8 2 8Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
                      <circle cx="8" cy="8" r="1.8" stroke="currentColor" strokeWidth="1.4" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {error && <p className="text-xs font-medium text-red-500">{error}</p>}

            <div className="flex items-center justify-between text-xs">
              <label className="flex cursor-pointer items-center gap-2 text-brand-brown/60">
                <input type="checkbox" className="h-3.5 w-3.5 rounded border-brand-brown/30 text-brand-gold focus:ring-brand-gold" />
                Remember me
              </label>
              <a href="#" className="font-medium text-brand-brownDeep transition-colors hover:text-brand-gold">
                Forgot password?
              </a>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-brownDeep px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-brand-gold hover:text-brand-brownDeep disabled:cursor-not-allowed disabled:opacity-70"
            >
              {submitting ? 'Signing in…' : 'Sign in'}
              {!submitting && (
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                  <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-xs text-brand-brown/50">
            Don&apos;t have an account?{' '}
            <Link to="/" className="font-semibold text-brand-brownDeep transition-colors hover:text-brand-gold">
              Contact your administrator
            </Link>
          </p>
        </div>

        <p className="mt-6 text-center text-[11px] tracking-[0.15em] text-brand-brown/40">
          ONE INVOICE INTELLIGENCE
        </p>
      </motion.div>
    </main>
  )
}
