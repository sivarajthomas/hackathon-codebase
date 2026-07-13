import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'

// A small floating "ID" button pinned to the corner of the site. Shows the
// signed-in user's initial when a session exists, otherwise a generic ID icon.
// Clicking it opens the login / account screen.
export default function IdButton() {
  const navigate = useNavigate()
  const [userId, setUserId] = useState(null)

  useEffect(() => {
    try {
      const raw = localStorage.getItem('ii_user')
      if (raw) setUserId(JSON.parse(raw)?.userId || null)
    } catch {
      // Ignore malformed/unavailable storage.
    }
  }, [])

  return (
    <div className="flex flex-col items-center gap-1">
      <motion.button
        onClick={() => navigate('/login')}
        initial={{ opacity: 0, scale: 0.6 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.94 }}
        data-cursor="hover"
        aria-label={userId ? `Account: ${userId}` : 'Sign in'}
        title={userId ? `Signed in as ${userId}` : 'Sign in'}
        className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full border border-brand-brown/20 bg-white shadow-[0_10px_30px_-8px_rgba(43,24,16,0.5)] transition-colors hover:border-brand-gold"
      >
        <img src="/icon.png" alt="Account" className="h-full w-full object-cover" draggable={false} />
      </motion.button>
      {userId && (
        <span className="max-w-[84px] truncate text-[11px] font-medium text-brand-brownDeep">
          {userId}
        </span>
      )}
    </div>
  )
}
