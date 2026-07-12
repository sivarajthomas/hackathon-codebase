import { motion } from 'framer-motion'
import UpsLogo from './UpsLogo'

// Full-screen boot loader shown while fonts / assets warm up.
export default function Loader({ progress = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8, ease: 'easeInOut' }}
      className="fixed inset-0 z-[200] flex flex-col items-center justify-center bg-white"
    >
      <div className="relative mb-8 flex h-16 w-16 items-center justify-center">
        <span className="absolute inset-0 animate-spin rounded-full border-2 border-brand-brown/10 border-t-brand-gold" />
        <UpsLogo className="h-9 w-8" />
      </div>

      <div className="font-display text-xs font-semibold uppercase tracking-[0.4em] text-brand-brown/60">
        One Invoice Intelligence
      </div>

      <div className="mt-5 h-px w-48 overflow-hidden bg-brand-brown/10">
        <motion.div
          className="h-full bg-gradient-to-r from-brand-gold to-ops-active"
          initial={{ width: '0%' }}
          animate={{ width: `${Math.min(100, progress)}%` }}
          transition={{ ease: 'easeOut' }}
        />
      </div>
      <div className="mt-3 font-mono text-[10px] tracking-widest text-brand-brown/40">
        {Math.round(Math.min(100, progress))}%
      </div>
    </motion.div>
  )
}
