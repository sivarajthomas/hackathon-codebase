import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import DroneFlight from './DroneFlight'

const TransitionCtx = createContext(null)

export const useTransition = () => useContext(TransitionCtx)

// The instruction the drone "writes" into the prompt box on arrival.
const DRONE_TEXT = 'Enter Invoice and date to start'

// Provides a cinematic "morph & zoom" transition. A card calls `launch()` with
// its screen-space origin and accent color; an overlay expands from that point,
// we navigate, then the overlay dissolves to reveal the destination. On launch
// a courier drone also lifts off from the card, survives the route change, and
// writes an instruction into the destination prompt box.
export function TransitionProvider({ children }) {
  const navigate = useNavigate()
  const [state, setState] = useState(null) // { x, y, color, to } | null
  const [drone, setDrone] = useState(null) // { origin, accent } | null
  const busy = useRef(false)
  // Populated by the agent page so the drone knows where to fly & drop letters.
  const promptRef = useRef({ inputEl: null, sendEl: null, setPlaceholder: null })

  const registerPrompt = useCallback((api) => {
    promptRef.current = api || { inputEl: null, sendEl: null, setPlaceholder: null }
  }, [])

  const launch = useCallback(
    (to, origin, color) => {
      if (busy.current) return
      busy.current = true
      // Drone lifts off from the card immediately, before the transition.
      promptRef.current = { inputEl: null, sendEl: null, setPlaceholder: null }
      setDrone({ origin, accent: color })
      setState({ to, color, x: origin.x, y: origin.y })

      // Navigate mid-expansion so the destination is ready behind the overlay.
      window.setTimeout(() => navigate(to), 300)
      // Clear overlay after it has dissolved (drone clears itself on finish).
      window.setTimeout(() => {
        setState(null)
        busy.current = false
      }, 750)
    },
    [navigate]
  )

  // Send the drone in without a page transition (e.g. when switching agents
  // from the sidebar). No-op if a drone is already flying.
  const summonDrone = useCallback((color) => {
    const origin = { x: window.innerWidth / 2, y: 90 }
    setDrone((prev) => prev || { origin, accent: color })
  }, [])

  return (
    <TransitionCtx.Provider value={{ launch, registerPrompt, summonDrone }}>
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

      {/* Courier drone — starts at click, flies through the transition, and
          writes the instruction into the destination prompt box. */}
      {drone && (
        <DroneFlight
          key={`${drone.origin.x}-${drone.origin.y}-${drone.accent}`}
          origin={drone.origin}
          accent={drone.accent}
          text={DRONE_TEXT}
          promptRef={promptRef}
          onComplete={() => setDrone(null)}
        />
      )}
    </TransitionCtx.Provider>
  )
}
