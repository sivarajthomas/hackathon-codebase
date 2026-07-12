import { motion } from 'framer-motion'

// Three-dot typing indicator shown while the agent "thinks".
export default function TypingIndicator({ accent }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="flex justify-start"
    >
      <div
        className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm border border-brand-brown/10 bg-white px-4 py-3.5 shadow-sm"
        style={{ borderColor: `${accent}33` }}
      >
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: accent }}
            animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
          />
        ))}
      </div>
    </motion.div>
  )
}
