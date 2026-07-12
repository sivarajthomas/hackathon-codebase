import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'

const TransitionCtx = createContext(null)

export const useTransition = () => useContext(TransitionCtx)

// Provides a cinematic "morph & zoom" transition. A card calls `launch()` with
// its screen-space origin and accent color; an overlay expands from that point,
// we navigate, then the overlay dissolves to reveal the destination.
export function TransitionProvider({ children }) {
  const navigate = useNavigate()
  const [state, setState] = useState(null) // { x, y, color, to } | null
  const busy = useRef(false)

  const launch = useCallback(
    (to, origin, color) => {
      if (busy.current) return
      busy.current = true
      setState({ to, color, x: origin.x, y: origin.y })

      // Navigate mid-expansion so the destination is ready behind the overlay.
      window.setTimeout(() => navigate(to), 300)
      // Clear overlay after it has dissolved.
      window.setTimeout(() => {
        setState(null)
        busy.current = false
      }, 750)
    },
    [navigate]
  )

  return (
    <TransitionCtx.Provider value={{ launch }}>
      {children}
      <AnimatePresence>
        {state && (
          <motion.div
            key="transition-overlay"
            className="pointer-events-none fixed inset-0 z-[150]"
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.35, ease: 'easeInOut' } }}
          >
            <motion.div
              className="absolute rounded-full"
              style={{
                left: state.x,
                top: state.y,
                background: `radial-gradient(circle, ${state.color} 0%, #ffffff 70%)`,
              }}
              initial={{ width: 0, height: 0, x: '-50%', y: '-50%', opacity: 0.9 }}
              animate={{
                width: '300vmax',
                height: '300vmax',
                opacity: 1,
                transition: { duration: 0.5, ease: [0.83, 0, 0.17, 1] },
              }}
            />
            <motion.div
              className="absolute inset-0 flex items-center justify-center"
              initial={{ opacity: 0 }}
              animate={{ opacity: [0, 1, 0], transition: { duration: 0.7, times: [0, 0.5, 1] } }}
            >
              <span className="h-3 w-3 animate-ping rounded-full bg-white" />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </TransitionCtx.Provider>
  )
}
