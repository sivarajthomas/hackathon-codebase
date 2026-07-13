import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import IdButton from './IdButton'

// Static, solid site header pinned to the top. The hero video plays as a
// section beneath it (no longer behind it).
export default function Navbar() {
  const scrollTo = (target) => (e) => {
    e.preventDefault()
    window.__lenis?.scrollTo(target, { offset: 0, duration: 1.4 })
  }

  return (
    <motion.header
      initial={{ y: -30, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className="fixed inset-x-0 top-0 z-50 border-b border-white/50 bg-gradient-to-b from-sky-200/60 to-white/45 shadow-sm backdrop-blur-md"
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 md:px-8">
        {/* Left: UPS logo */}
        <Link to="/" onClick={scrollTo(0)} className="group shrink-0">
          <img
            src="/ups-logo.png"
            alt="UPS"
            className="h-14 w-14 object-contain transition-transform group-hover:scale-105 md:h-16 md:w-16"
            draggable={false}
          />
        </Link>

        {/* Center: brand heading + tagline */}
        <div className="hidden flex-1 flex-col items-center text-center sm:flex">
          <h1 className="text-gradient-vibrant animate-shimmer font-display text-xl font-bold leading-tight tracking-tight md:text-3xl">
            One Invoice Intelligence
          </h1>
          <p className="text-[11px] font-medium text-brand-brown/60 md:text-sm">
            Agentic AI Command Center for Revenue Leakage Detection and Billing Intelligence
          </p>
        </div>

        {/* Right: nav actions */}
        <div className="flex shrink-0 items-center gap-2.5">
          <IdButton />
        </div>
      </div>
    </motion.header>
  )
}
