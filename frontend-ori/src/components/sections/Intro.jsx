import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'

const features = [
  {
    n: '01',
    title: 'Automated',
    body: 'AI validates invoices, prices shipments and resolves disputes end-to-end — cutting manual billing work to a fraction.',
  },
  {
    n: '02',
    title: 'Intelligent',
    body: 'Every agent is tuned to a logistics discipline, surfacing anomalies, ETAs and savings your team would otherwise miss.',
  },
  {
    n: '03',
    title: 'Unified',
    body: 'Invoices, rates, shipments and disputes in one command center — no context-switching, no lost threads.',
  },
]

// The narrative bridge between the hero and the agent selection. Scroll-linked
// parallax + staggered reveals tell the story of the system.
export default function Intro() {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  })

  const y = useTransform(scrollYProgress, [0, 1], ['12%', '-12%'])
  const opacity = useTransform(scrollYProgress, [0, 0.25, 0.75, 1], [0, 1, 1, 0.3])

  return (
    <section id="intro" ref={ref} className="relative mx-auto max-w-6xl px-6 py-40 md:py-56">
      <motion.div style={{ y, opacity }}>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.8 }}
          className="mb-4 text-xs uppercase tracking-[0.35em] text-brand-gold/80"
        >
          The Platform
        </motion.p>

        <motion.h2
          initial={{ opacity: 0, y: 30, filter: 'blur(10px)' }}
          whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
          className="max-w-3xl font-display text-4xl font-semibold leading-tight tracking-tight md:text-6xl"
        >
          A command center for
          <span className="text-gradient"> logistics billing.</span>
        </motion.h2>

        <div className="mt-20 grid gap-10 md:grid-cols-3">
          {features.map((f, i) => (
            <motion.div
              key={f.n}
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.8, delay: i * 0.12, ease: [0.22, 1, 0.36, 1] }}
              className="glass rounded-2xl p-7 transition-colors hover:border-white/20"
            >
              <div className="mb-6 font-mono text-sm text-brand-gold/70">{f.n}</div>
              <h3 className="mb-3 font-display text-xl font-medium">{f.title}</h3>
              <p className="text-sm leading-relaxed text-white/55">{f.body}</p>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </section>
  )
}
