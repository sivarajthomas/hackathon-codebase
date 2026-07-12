import { motion } from 'framer-motion'

// A single chat bubble with a smooth spring entrance. `role` is 'user' | 'ai'.
export default function Message({ role, text, accent }) {
  const isUser = role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', stiffness: 320, damping: 26 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'rounded-br-sm bg-brand-brownDeep text-white'
            : 'rounded-bl-sm border border-brand-brown/10 bg-white text-brand-brownDeep shadow-sm'
        }`}
        style={
          !isUser
            ? { boxShadow: `0 6px 24px -16px ${accent}`, borderColor: `${accent}33` }
            : undefined
        }
      >
        {text}
      </div>
    </motion.div>
  )
}
