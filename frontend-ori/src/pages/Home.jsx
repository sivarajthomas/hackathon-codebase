import Hero from '../components/sections/Hero'
import AgentsSection from '../components/sections/AgentsSection'

// Single landing page: cinematic UPS hero video + the four AI agents.
export default function Home() {
  return (
    <main className="relative z-10">
      <Hero />
      <AgentsSection />

      <footer className="relative z-10 border-t border-brand-brown/10 bg-white px-6 py-12 text-center">
        <p className="font-display text-sm font-semibold tracking-[0.2em] text-brand-brownDeep">
          ONE INVOICE INTELLIGENCE
        </p>
        <p className="mt-2 text-xs text-brand-brown/50">
          Moving our world forward by delivering what matters.
        </p>
      </footer>
    </main>
  )
}
