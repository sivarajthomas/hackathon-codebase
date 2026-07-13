import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useAuth } from '../../hooks/useAuth'

// A small floating "ID" button pinned to the corner of the site. Shows the
// signed-in user's name when a session exists, otherwise a generic ID icon.
// Reads identity straight from the auth context so it updates immediately on
// login / logout (no page refresh required). Signed-in users get a sign-out
// menu; signed-out users are routed to the login screen.
export default function IdButton() {
  const navigate = useNavigate()
  const { user, isAuthenticated, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)

  const label = user?.display_name || user?.username || null

  // Close the menu on outside click / Escape.
  useEffect(() => {
    if (!open) return
    const onDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const onClick = () => {
    if (isAuthenticated) setOpen((v) => !v)
    else navigate('/login')
  }

  const onSignOut = () => {
    setOpen(false)
    logout()
    navigate('/login')
  }

  return (
    <div ref={wrapRef} className="relative flex flex-col items-center gap-1">
      <motion.button
        onClick={onClick}
        initial={{ opacity: 0, scale: 0.6 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.94 }}
        data-cursor="hover"
        aria-label={label ? `Account: ${label}` : 'Sign in'}
        aria-haspopup={isAuthenticated ? 'menu' : undefined}
        aria-expanded={isAuthenticated ? open : undefined}
        title={label ? `Signed in as ${label}` : 'Sign in'}
        className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full border border-brand-brown/20 bg-white shadow-[0_10px_30px_-8px_rgba(43,24,16,0.5)] transition-colors hover:border-brand-gold"
      >
        <img src="/icon.png" alt="Account" className="h-full w-full object-cover" draggable={false} />
      </motion.button>
      {label && (
        <span className="max-w-[84px] truncate text-[11px] font-medium text-brand-brownDeep">
          {label}
        </span>
      )}

      <AnimatePresence>
        {isAuthenticated && open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.96 }}
            transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            role="menu"
            className="absolute right-0 top-14 z-50 w-44 overflow-hidden rounded-xl border border-brand-brown/15 bg-white shadow-[0_20px_50px_-20px_rgba(43,24,16,0.6)]"
          >
            <div className="border-b border-brand-brown/10 px-3 py-2.5">
              <div className="truncate text-xs font-semibold text-brand-brownDeep">{label}</div>
              {user?.role && (
                <div className="mt-0.5 truncate text-[10px] uppercase tracking-wide text-brand-brown/50">
                  {String(user.role).replace(/_/g, ' ').toLowerCase()}
                </div>
              )}
            </div>
            <button
              onClick={onSignOut}
              role="menuitem"
              className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm text-brand-brownDeep transition-colors hover:bg-brand-gold/10"
            >
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" className="shrink-0 text-brand-brown/60">
                <path d="M6 2H3.5A1.5 1.5 0 002 3.5v9A1.5 1.5 0 003.5 14H6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                <path d="M10 11l3-3-3-3M13 8H6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
