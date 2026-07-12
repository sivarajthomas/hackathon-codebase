import { motion } from 'framer-motion'
import { agents } from '../../data/agents'
import AgentCard from './AgentCard'

// The interactive selection stage: four floating agent cards in a responsive
// grid, introduced by a scroll-revealed heading.
export default function AgentsSection() {
  return (
    <section id="agents" className="relative mx-auto max-w-6xl px-6 py-32 md:py-40">
      <div className="mb-16 text-center">
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7 }}
          className="mb-4 text-xs font-semibold uppercase tracking-[0.35em] text-brand-brown/60"
        >
          AI Agents
        </motion.p>
        <motion.h2
          initial={{ opacity: 0, y: 30, filter: 'blur(10px)' }}
          whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          viewport={{ once: true }}
          transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
          className="font-display text-4xl font-semibold tracking-tight text-brand-brownDeep md:text-6xl"
        >
          Four specialists. <span className="text-gradient">One platform.</span>
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.9, delay: 0.2 }}
          className="mx-auto mt-5 max-w-lg text-sm text-brand-brown/60 md:text-base"
        >
          Select an agent to enter its workspace. Each opens a dedicated
          console for explaining, resolving, simulating or preventing billing.
        </motion.p>
      </div>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {agents.map((agent, i) => (
          <AgentCard key={agent.id} agent={agent} index={i} />
        ))}
      </div>
    </section>
  )
}
