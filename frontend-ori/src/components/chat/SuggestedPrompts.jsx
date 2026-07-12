import { motion } from 'framer-motion'

// Horizontal row of tappable suggested prompts. Fades out once used.
export default function SuggestedPrompts({ prompts, accent, onSelect }) {
  return (
    <div className="flex flex-wrap gap-2">
      {prompts.map((p, i) => (
        <motion.button
          key={p}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 + i * 0.08 }}
          onClick={() => onSelect(p)}
          className="rounded-full border border-brand-brown/12 bg-white px-3.5 py-2 text-xs text-brand-brown/80 shadow-sm transition-all hover:text-brand-brownDeep"
          style={{ borderColor: `${accent}33` }}
          whileHover={{ scale: 1.04, borderColor: accent }}
          whileTap={{ scale: 0.97 }}
        >
          {p}
        </motion.button>
      ))}
    </div>
  )
}
