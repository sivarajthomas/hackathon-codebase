import { useEffect, useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'
import { platformStats } from '../../data/agents'

// Formats a number for display, supporting compact notation (1.2M) and
// fixed decimals for small values.
function formatValue(n, { format, prefix = '', suffix = '' }) {
  let out
  if (format === 'compact') {
    out = Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(n)
  } else if (!Number.isInteger(n)) {
    out = n.toFixed(1)
  } else {
    out = Intl.NumberFormat('en').format(Math.round(n))
  }
  return `${prefix}${out}${suffix}`
}

// A single KPI card whose value counts up when scrolled into view.
function StatCard({ stat, index }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    if (!inView) return
    let raf
    const start = performance.now()
    const duration = 1600
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration)
      // easeOutExpo
      const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t)
      setDisplay(stat.value * eased)
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [inView, stat.value])

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.7, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
      className="group relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-xl"
    >
      {/* light sweep */}
      <div className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/[0.06] to-transparent transition-transform duration-1000 group-hover:translate-x-full" />
      <div
        className="pointer-events-none absolute -inset-px rounded-2xl opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ boxShadow: `0 0 50px -18px ${stat.accent}` }}
      />
      <div className="relative">
        <div
          className="mb-3 h-1 w-8 rounded-full"
          style={{ background: stat.accent, boxShadow: `0 0 12px ${stat.accent}` }}
        />
        <div className="font-display text-3xl font-semibold tracking-tight text-white md:text-4xl">
          {formatValue(display, stat)}
        </div>
        <div className="mt-2 text-xs uppercase tracking-[0.15em] text-white/45">
          {stat.label}
        </div>
      </div>
    </motion.div>
  )
}

// Live operations dashboard: a grid of animated enterprise KPIs.
export default function Dashboard() {
  return (
    <section id="dashboard" className="relative mx-auto max-w-6xl px-6 py-28 md:py-36">
      <div className="mb-14 flex flex-col items-start justify-between gap-6 md:flex-row md:items-end">
        <div>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
            className="mb-4 text-xs uppercase tracking-[0.35em] text-brand-gold/80"
          >
            Live Operations
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 30, filter: 'blur(10px)' }}
            whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            viewport={{ once: true }}
            transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
            className="max-w-2xl font-display text-4xl font-semibold tracking-tight md:text-5xl"
          >
            The billing network, <span className="text-gradient">in real time.</span>
          </motion.h2>
        </div>
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="glass flex items-center gap-2 rounded-full px-4 py-2 text-xs text-white/60"
        >
          <span className="h-2 w-2 animate-pulseGlow rounded-full bg-ops-done" />
          All systems operational
        </motion.div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {platformStats.map((stat, i) => (
          <StatCard key={stat.label} stat={stat} index={i} />
        ))}
      </div>
    </section>
  )
}
