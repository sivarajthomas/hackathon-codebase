import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import Message from './Message'
import TypingIndicator from './TypingIndicator'
import SuggestedPrompts from './SuggestedPrompts'
import AgentIcon from '../ui/AgentIcon'
import UpsLogo from '../ui/UpsLogo'
import { agents } from '../../data/agents'

// Canned, agent-flavored responses. This is a front-end demo — swap `respond`
// with a real API call to wire up a backend.
const CANNED = {
  explain: [
    "Here's the breakdown: the $1,204.50 invoice includes base freight $980.00, fuel surcharge $148.50 (15.15%), and a residential delivery fee $76.00. The fuel surcharge is calculated as a percentage of the base rate per the current weekly index. Want the full line-item export?",
    "The DIM weight on this shipment was 18kg vs actual 12kg — the carrier billed the higher value per the volumetric formula (L×W×H ÷ 5000). I can show the exact calculation and whether a re-weigh would change the charge.",
  ],
  resolve: [
    "Investigated INV-2210: the charge was based on zone 8 but the delivery address maps to zone 6. That's a $46.80 overcharge. I recommend a credit — want me to draft the resolution and flag it for approval?",
    "Claim CLM-8842 validated. The rate card at the time of shipment shows a $0.22/kg lower base rate than what was billed. Evidence supports the customer — suggested action is a full re-rate and $38.40 credit.",
  ],
  simulate: [
    "Recalculated with 8kg: Ground $14.20 (was $18.40), 2-Day Air $33.60 (was $41.10). Reducing weight by 2kg saves $4.20 on Ground — $5.50 on Air. Want me to model additional weight or service changes?",
    "Comparison ready: Ground $18.40 / 5 days, 2-Day Air $41.10 / 2 days, Next Day Air $68.90 / 1 day. Based on your SLA, 2-Day Air gives the best cost-per-day ratio. Shall I save this scenario?",
  ],
  prevent: [
    "Scanned 214 invoices in this batch — flagged 3 anomalies: 2 duplicate line items on account 7741 ($92 each) and 1 DIM weight discrepancy on shipment SHP-9928 ($44 overcharge). Recommend holding those 3 for review before issuance.",
    "Pre-validation complete on the upcoming billing cycle: 99.2% clean. Found 1 at-risk charge — a surcharge applied to an account with a contractual waiver. Correcting now would prevent a likely dispute. Want me to flag it for the billing team?",
  ],
}

let idc = 0
const uid = () => `${Date.now()}-${idc++}`

const makeSession = (agent) => ({
  id: uid(),
  title: 'New conversation',
  time: 'Just now',
  messages: [{ id: uid(), role: 'ai', text: agent.greeting }],
  showPrompts: true,
})

// A full-screen chat workspace: a persistent sidebar (new chat, history,
// agent switcher) plus a large conversation area — designed to feel like a
// real production AI assistant.
export default function ChatPanel({ agent }) {
  const [sessions, setSessions] = useState(() => [makeSession(agent)])
  const [activeId, setActiveId] = useState(() => sessions[0].id)
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [issuesOpen, setIssuesOpen] = useState(false)
  const [issueQuery, setIssueQuery] = useState('')
  const scrollRef = useRef(null)
  const timers = useRef([])

  const active = sessions.find((s) => s.id === activeId) || sessions[0]

  // Reset the workspace when navigating to a different agent.
  useEffect(() => {
    const s = makeSession(agent)
    setSessions([s])
    setActiveId(s.id)
    setInput('')
    setTyping(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent.slug])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [active?.messages, typing])

  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const updateSession = (id, updater) =>
    setSessions((prev) => prev.map((s) => (s.id === id ? updater(s) : s)))

  const respondTo = (id) => {
    setTyping(true)
    const bank = CANNED[agent.slug] || CANNED.explain
    const reply = bank[Math.floor(Math.random() * bank.length)]
    const t = setTimeout(() => {
      setTyping(false)
      updateSession(id, (s) => ({
        ...s,
        messages: [...s.messages, { id: uid(), role: 'ai', text: reply }],
      }))
    }, 500 + Math.random() * 350)
    timers.current.push(t)
  }

  const send = (text) => {
    const value = text.trim()
    if (!value || typing) return
    const id = activeId
    updateSession(id, (s) => ({
      ...s,
      title: s.messages.some((m) => m.role === 'user')
        ? s.title
        : value.length > 38
          ? value.slice(0, 38) + '…'
          : value,
      showPrompts: false,
      messages: [...s.messages, { id: uid(), role: 'user', text: value }],
    }))
    setInput('')
    respondTo(id)
  }

  const onSubmit = (e) => {
    e.preventDefault()
    send(input)
  }

  const newChat = () => {
    const s = makeSession(agent)
    setSessions((prev) => [s, ...prev])
    setActiveId(s.id)
    setInput('')
    setTyping(false)
    setSidebarOpen(false)
  }

  const selectSession = (id) => {
    setActiveId(id)
    setSidebarOpen(false)
  }

  // Color mapping for issue severity badges.
  const severityStyle = {
    high: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
    medium: { color: '#ff8a3d', bg: 'rgba(255,138,61,0.14)' },
    low: { color: '#22c55e', bg: 'rgba(34,197,94,0.14)' },
  }

  const hasIssues = Array.isArray(agent.issues) && agent.issues.length > 0
  const flaggedTotal = hasIssues
    ? agent.issues.reduce((sum, i) => sum + parseFloat(i.amount.replace(/[^0-9.]/g, '')), 0)
    : 0

  const reviewIssue = (inv) => {
    send(`Review flagged invoice ${inv.id} — ${inv.problem} (${inv.amount}) on account ${inv.account}.`)
    setIssuesOpen(false)
  }

  const filteredIssues = hasIssues
    ? agent.issues.filter((inv) => {
        const q = issueQuery.trim().toLowerCase()
        if (!q) return true
        return (
          inv.id.toLowerCase().includes(q) ||
          inv.problem.toLowerCase().includes(q) ||
          inv.account.toLowerCase().includes(q) ||
          inv.severity.toLowerCase().includes(q)
        )
      })
    : []

  const IssuesPanel = hasIssues ? (
    <div className="flex h-full flex-col">
      <div className="border-b border-brand-brown/10 px-4 py-4">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 animate-pulseGlow rounded-full bg-red-500" />
          <h3 className="text-sm font-semibold text-brand-brownDeep">Invoices with issues</h3>
        </div>
        <p className="mt-1 text-[11px] text-brand-brown/50">
          {agent.issues.length} flagged · ${flaggedTotal.toFixed(2)} at risk
        </p>
        {/* Search */}
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-brand-brown/12 bg-white px-2.5 py-1.5 focus-within:border-brand-gold">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="shrink-0 text-brand-brown/40">
            <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M11 11l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            value={issueQuery}
            onChange={(e) => setIssueQuery(e.target.value)}
            placeholder="Search invoice, account, issue…"
            className="w-full bg-transparent text-xs text-brand-brownDeep placeholder:text-brand-brown/40 focus:outline-none"
          />
          {issueQuery && (
            <button
              onClick={() => setIssueQuery('')}
              className="text-brand-brown/40 hover:text-brand-brownDeep"
              aria-label="Clear search"
            >
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </button>
          )}
        </div>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {filteredIssues.length === 0 && (
          <p className="px-2 py-6 text-center text-xs text-brand-brown/40">No matching invoices.</p>
        )}
        {filteredIssues.map((inv) => {
          const s = severityStyle[inv.severity] || severityStyle.low
          return (
            <button
              key={inv.id}
              onClick={() => reviewIssue(inv)}
              className="w-full rounded-xl border border-brand-brown/10 bg-white p-3 text-left shadow-sm transition-colors hover:border-brand-gold"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-semibold text-brand-brownDeep">{inv.id}</span>
                <span
                  className="rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide"
                  style={{ color: s.color, background: s.bg }}
                >
                  {inv.severity}
                </span>
              </div>
              <div className="mt-1.5 text-xs text-brand-brown/70">{inv.problem}</div>
              <div className="mt-2 flex items-center justify-between text-[11px] text-brand-brown/50">
                <span>Account {inv.account}</span>
                <span className="font-semibold text-brand-brownDeep">{inv.amount}</span>
              </div>
            </button>
          )
        })}
      </div>
      <div className="border-t border-brand-brown/10 px-4 py-3 text-center text-[10px] text-brand-brown/40">
        Tap an invoice to review it with {agent.name}
      </div>
    </div>
  ) : null

  const Sidebar = (
    <div className="flex h-full flex-col">
      {/* Brand / back */}
      <div className="flex items-center gap-2.5 px-4 py-4">
        <Link to="/" className="flex items-center gap-2.5 text-brand-brownDeep transition-opacity hover:opacity-80">
          <UpsLogo className="h-8 w-7 shrink-0" />
          <span className="flex flex-col leading-tight">
            <span className="font-display text-xs font-bold tracking-[0.12em]">UPS</span>
            <span className="text-[9px] font-medium text-brand-brown/60">Invoice Intelligence</span>
          </span>
        </Link>
      </div>

      {/* New chat */}
      <div className="px-3">
        <button
          onClick={newChat}
          className="flex w-full items-center gap-2 rounded-xl border border-brand-brown/12 bg-white px-4 py-3 text-sm font-semibold text-brand-brownDeep shadow-sm transition-all hover:border-brand-gold hover:bg-brand-gold/10"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
          New chat
        </button>
      </div>

      {/* History */}
      <div className="mt-6 flex-1 overflow-y-auto px-3">
        <div className="px-1 pb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-brand-brown/40">Recent</div>
        <div className="space-y-1">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => selectSession(s.id)}
              className={`group flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                s.id === activeId
                  ? 'bg-brand-gold/15 font-medium text-brand-brownDeep'
                  : 'text-brand-brown/60 hover:bg-brand-brown/[0.05] hover:text-brand-brownDeep'
              }`}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="shrink-0 opacity-60">
                <path d="M2 3h12v8H6l-3 3V3Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
              </svg>
              <span className="truncate">{s.title}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Agent switcher */}
      <div className="border-t border-brand-brown/10 px-3 py-4">
        <div className="px-1 pb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-brand-brown/40">Agents</div>
        <div className="space-y-1">
          {agents.map((a) => (
            <Link
              key={a.slug}
              to={`/agent/${a.slug}`}
              className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                a.slug === agent.slug
                  ? 'bg-brand-brown/[0.06] font-medium text-brand-brownDeep'
                  : 'text-brand-brown/60 hover:bg-brand-brown/[0.05] hover:text-brand-brownDeep'
              }`}
            >
              <span
                className="flex h-6 w-6 items-center justify-center rounded-md"
                style={{ background: a.accentSoft, color: a.accent }}
              >
                <AgentIcon name={a.icon} className="h-3.5 w-3.5" strokeWidth={1.6} />
              </span>
              <span className="truncate">{a.name}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )

  return (
    <div className="flex h-full w-full overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden w-72 shrink-0 border-r border-brand-brown/10 bg-white/90 backdrop-blur-2xl lg:block">
        {Sidebar}
      </aside>

      {/* Mobile sidebar drawer */}
      <AnimatePresence>
        {sidebarOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSidebarOpen(false)}
              className="fixed inset-0 z-40 bg-brand-brownDeep/40 backdrop-blur-sm lg:hidden"
            />
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 320, damping: 34 }}
              className="fixed inset-y-0 left-0 z-50 w-72 border-r border-brand-brown/10 bg-white lg:hidden"
            >
              {Sidebar}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main conversation */}
      <div className="flex min-w-0 flex-1 flex-col bg-white/75 backdrop-blur-xl">
        {/* Top bar */}
        <div className="flex items-center justify-between border-b border-brand-brown/10 bg-white/60 px-5 py-3.5">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-brand-brown/12 text-brand-brown/70 lg:hidden"
              aria-label="Open menu"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
            <span
              className="flex h-10 w-10 items-center justify-center rounded-xl"
              style={{ background: agent.accentSoft, color: agent.accent }}
            >
              <AgentIcon name={agent.icon} className="h-5 w-5" strokeWidth={1.6} />
            </span>
            <div>
              <div className="text-sm font-semibold text-brand-brownDeep">{agent.name}</div>
              <div className="flex items-center gap-1.5 text-[11px] text-brand-brown/50">
                <span className="h-1.5 w-1.5 rounded-full bg-ops-done" />
                Online · {agent.role}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {hasIssues && (
              <button
                onClick={() => setIssuesOpen(true)}
                className="flex items-center gap-1.5 rounded-full border border-red-400/40 bg-red-500/10 px-3.5 py-2 text-xs font-medium text-red-600 transition-colors hover:bg-red-500/15 xl:hidden"
              >
                <span className="h-1.5 w-1.5 animate-pulseGlow rounded-full bg-red-500" />
                Issues
                <span className="rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
                  {agent.issues.length}
                </span>
              </button>
            )}
            <button
              onClick={newChat}
              className="hidden items-center gap-1.5 rounded-full border border-brand-brown/12 px-3.5 py-2 text-xs font-medium text-brand-brown/70 transition-colors hover:border-brand-gold hover:text-brand-brownDeep sm:flex"
            >
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
              New chat
            </button>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {active?.messages.map((m) => (
              <Message key={m.id} role={m.role} text={m.text} accent={agent.accent} />
            ))}
            <AnimatePresence>{typing && <TypingIndicator accent={agent.accent} />}</AnimatePresence>
          </div>
        </div>

        {/* Suggested prompts */}
        <AnimatePresence>
          {active?.showPrompts && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="px-4 md:px-8"
            >
              <div className="mx-auto max-w-3xl pb-3">
                <SuggestedPrompts prompts={agent.prompts} accent={agent.accent} onSelect={send} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Input */}
        <form onSubmit={onSubmit} className="px-4 pb-6 pt-2 md:px-8">
          <div className="mx-auto flex max-w-3xl items-center gap-2 rounded-2xl border border-brand-brown/15 bg-white px-3 py-2 shadow-sm transition-colors focus-within:border-brand-gold">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={agent.placeholder || `Message ${agent.name}…`}
              className="flex-1 bg-transparent px-2 py-2.5 text-sm text-brand-brownDeep placeholder:text-brand-brown/40 focus:outline-none"
            />
            <button
              type="submit"
              disabled={!input.trim() || typing}
              className="flex h-10 w-10 items-center justify-center rounded-xl text-brand-brownDeep transition-transform hover:scale-105 disabled:opacity-30"
              style={{ background: agent.accent }}
              aria-label="Send message"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M2 8h11M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          <div className="mx-auto mt-2 max-w-3xl text-center text-[10px] text-brand-brown/40">
            One Invoice Intelligence · responses are simulated for demo purposes
          </div>
        </form>
      </div>

      {/* Right sidebar: flagged invoices (Prevent Agent). Static on xl+. */}
      {hasIssues && (
        <aside className="hidden w-80 shrink-0 border-l border-brand-brown/10 bg-white/90 backdrop-blur-2xl xl:block">
          {IssuesPanel}
        </aside>
      )}

      {/* Right sidebar as a slide-in drawer on smaller screens */}
      <AnimatePresence>
        {hasIssues && issuesOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIssuesOpen(false)}
              className="fixed inset-0 z-40 bg-brand-brownDeep/40 backdrop-blur-sm xl:hidden"
            />
            <motion.aside
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', stiffness: 320, damping: 34 }}
              className="fixed inset-y-0 right-0 z-50 w-80 max-w-[85vw] border-l border-brand-brown/10 bg-white xl:hidden"
            >
              {IssuesPanel}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
