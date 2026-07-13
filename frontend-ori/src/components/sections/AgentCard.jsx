import { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import AgentIcon from '../ui/AgentIcon'
import { useTransition } from '../ui/TransitionProvider'

// A premium floating agent card with cursor-tracked 3D tilt, an accent glow
// that follows the pointer, hover elevation and a cinematic launch transition.
export default function AgentCard({ agent, index }) {
  const cardRef = useRef(null)
  const [tilt, setTilt] = useState({ rx: 0, ry: 0 })
  const [glow, setGlow] = useState({ x: 50, y: 50 })
  const { launch } = useTransition()

  const handleMove = (e) => {
    const el = cardRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width
    const py = (e.clientY - r.top) / r.height
    setTilt({ ry: (px - 0.5) * 16, rx: -(py - 0.5) * 16 })
    setGlow({ x: px * 100, y: py * 100 })
  }

  const reset = () => {
    setTilt({ rx: 0, ry: 0 })
    setGlow({ x: 50, y: 50 })
  }

  const handleLaunch = () => {
    const el = cardRef.current
    const r = el?.getBoundingClientRect()
    const origin = r
      ? { x: r.left + r.width / 2, y: r.top + r.height / 2 }
      : { x: window.innerWidth / 2, y: window.innerHeight / 2 }
    launch(`/agent/${agent.slug}`, origin, agent.accent)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 60 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.8, delay: index * 0.1, ease: [0.22, 1, 0.36, 1] }}
      className="perspective-1000 h-full"
    >
      {/* Gentle continuous float, slightly out of sync per card. */}
      <motion.div
        className="h-full"
        animate={{ y: [0, -12, 0] }}
        transition={{
          duration: 4.5 + index * 0.5,
          repeat: Infinity,
          ease: 'easeInOut',
          delay: index * 0.4,
        }}
      >
      <motion.div
        ref={cardRef}
        onMouseMove={handleMove}
        onMouseLeave={reset}
        onClick={handleLaunch}
        data-cursor="hover"
        className="group preserve-3d relative flex h-full cursor-pointer flex-col overflow-hidden rounded-3xl border border-white/50 p-8 transition-shadow duration-300 will-change-transform"
        style={{
          transform: `rotateX(${tilt.rx}deg) rotateY(${tilt.ry}deg)`,
          background: `linear-gradient(150deg, #ffffff 0%, ${agent.accentSoft} 58%, ${agent.accent}33 100%)`,
          boxShadow: `0 18px 50px -20px rgba(43,24,16,0.45), 0 0 55px -6px ${agent.accent}99`,
        }}
        whileHover={{ y: -10 }}
      >
        {/* Accent glow following the cursor — always on, intensifies on hover */}
        <div
          className="pointer-events-none absolute inset-0 rounded-3xl opacity-70 transition-opacity duration-300 group-hover:opacity-100"
          style={{
            background: `radial-gradient(300px circle at ${glow.x}% ${glow.y}%, ${agent.accentSoft}, transparent 65%)`,
          }}
        />
        {/* Border glow — always on, intensifies on hover */}
        <div
          className="pointer-events-none absolute -inset-px rounded-3xl opacity-60 transition-opacity duration-500 group-hover:opacity-100"
          style={{ boxShadow: `0 0 60px -12px ${agent.accent}`, borderRadius: '1.5rem' }}
        />

        <div className="relative z-10 flex flex-1 flex-col" style={{ transform: 'translateZ(40px)' }}>
          <div
            className="mb-8 flex h-16 w-16 items-center justify-center rounded-2xl"
            style={{ background: agent.accentSoft, color: agent.accent }}
          >
            <AgentIcon name={agent.icon} className="h-8 w-8 animate-float" />
          </div>

          <div className="mb-1 text-[11px] uppercase tracking-[0.25em] text-brand-brown/45">
            {agent.role}
          </div>
          <h3 className="mb-3 font-display text-xl font-semibold leading-tight text-brand-brownDeep">{agent.name}</h3>
          <p className="mb-8 flex-1 text-sm leading-relaxed text-brand-brown/70">
            {agent.description}
          </p>

          <div className="mt-auto flex items-center justify-between">
            <span className="text-xs italic text-brand-brown/50">{agent.tagline}</span>
            <span
              className="inline-flex items-center gap-1.5 rounded-full border border-brand-brown/10 px-4 py-2 text-xs font-semibold text-brand-brownDeep transition-all group-hover:border-brand-brown/25"
              style={{ background: agent.accentSoft }}
            >
              Launch
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className="transition-transform group-hover:translate-x-0.5">
                <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </div>
        </div>
      </motion.div>
      </motion.div>
    </motion.div>
  )
}
