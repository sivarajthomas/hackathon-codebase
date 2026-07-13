import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import Message from './Message'
import TypingIndicator from './TypingIndicator'
import SuggestedPrompts from './SuggestedPrompts'
import AgentIcon from '../ui/AgentIcon'
import UpsLogo from '../ui/UpsLogo'
import { useTransition } from '../ui/TransitionProvider'
import { agents } from '../../data/agents'
import { sendChatMessage, getFlaggedInvoices, reviewFlaggedInvoice } from '../../lib/api'

// Fallback, agent-flavored responses used only when the backend is unreachable
// so the demo stays usable offline. Live replies come from the backend API.
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
  // Live flagged invoices for the Prevent agent, pulled from BigQuery via the
  // backend. Replaces the previous hard-coded `agent.issues` sample data.
  const [liveIssues, setLiveIssues] = useState([])
  const [issuesLoading, setIssuesLoading] = useState(false)
  const [issuesError, setIssuesError] = useState('')
  const [reviewingId, setReviewingId] = useState(null)
  // Which flagged-invoice card is expanded to reveal its actions.
  const [expandedId, setExpandedId] = useState(null)
  const scrollRef = useRef(null)
  const timers = useRef([])
  // Per-session trace_id awaiting a clarification answer (Simulate round-trip).
  const pendingTrace = useRef({})

  // Prompt-box targets the courier drone flies to. The drone (owned by the
  // TransitionProvider) writes its instruction here via `setDroneText`.
  const { registerPrompt } = useTransition()
  const inputWrapRef = useRef(null)
  const sendBtnRef = useRef(null)
  const [droneText, setDroneText] = useState('')
  // True while the drone is dropping letters — hides the default placeholder
  // so it doesn't sit behind the incoming bold text.
  const [droneWriting, setDroneWriting] = useState(false)

  const active = sessions.find((s) => s.id === activeId) || sessions[0]

  // Reset the workspace when navigating to a different agent.
  useEffect(() => {
    const s = makeSession(agent)
    setSessions([s])
    setActiveId(s.id)
    setInput('')
    setTyping(false)
    pendingTrace.current = {}
    // Clear any previously written instruction; the drone rewrites it.
    setDroneText('')
    setDroneWriting(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent.slug])

  // Load live flagged invoices from BigQuery for the Prevent agent. Only
  // unreviewed findings are returned, so reviewed items drop off automatically.
  useEffect(() => {
    if (agent.slug !== 'prevent') {
      setLiveIssues([])
      setIssuesError('')
      return
    }
    const controller = new AbortController()
    setIssuesLoading(true)
    setIssuesError('')
    getFlaggedInvoices({ signal: controller.signal })
      .then((rows) => setLiveIssues(Array.isArray(rows) ? rows : []))
      .catch((err) => {
        if (err?.name !== 'AbortError') setIssuesError(err.message || 'Failed to load flagged invoices.')
      })
      .finally(() => setIssuesLoading(false))
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent.slug])

  // Register the prompt box + send button so the incoming drone knows where to
  // fly and where to drop its letters.
  useEffect(() => {
    registerPrompt({
      inputEl: inputWrapRef.current,
      sendEl: sendBtnRef.current,
      setPlaceholder: setDroneText,
      onWriteStart: () => setDroneWriting(true),
    })
    return () => registerPrompt(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent.slug])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [active?.messages, typing])

  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const updateSession = (id, updater) =>
    setSessions((prev) => prev.map((s) => (s.id === id ? updater(s) : s)))

  // Turn the session's rendered messages into conversation memory the backend
  // can replay (role/content, oldest first). Drops the leading AI greeting and
  // caps the window so the prompt stays bounded.
  const MAX_HISTORY_TURNS = 20
  const toHistory = (messages) => {
    const turns = []
    let seenUser = false
    for (const m of messages || []) {
      if (m.role === 'user') seenUser = true
      if (!seenUser) continue // skip the canned greeting before the first user turn
      const content = (m.text || '').trim()
      if (!content) continue
      turns.push({ role: m.role === 'user' ? 'user' : 'assistant', content })
    }
    return turns.slice(-MAX_HISTORY_TURNS)
  }

  const respondTo = async (id, text, history = []) => {
    setTyping(true)
    try {
      const res = await sendChatMessage({
        agent: agent.slug,
        message: text,
        traceId: pendingTrace.current[id],
        history,
      })
      // Remember the trace_id while a clarification is pending so the next
      // message resumes that run; clear it once the turn is resolved.
      if (res.status === 'clarification_needed') {
        pendingTrace.current[id] = res.traceId
      } else {
        delete pendingTrace.current[id]
      }
      updateSession(id, (s) => ({
        ...s,
        messages: [...s.messages, { id: uid(), role: 'ai', text: res.reply }],
      }))
    } catch {
      // Backend unreachable — fall back to a canned reply so the demo continues.
      delete pendingTrace.current[id]
      const bank = CANNED[agent.slug] || CANNED.explain
      const reply = bank[Math.floor(Math.random() * bank.length)]
      updateSession(id, (s) => ({
        ...s,
        messages: [...s.messages, { id: uid(), role: 'ai', text: reply }],
      }))
    } finally {
      setTyping(false)
    }
  }

  const send = (text) => {
    const value = text.trim()
    if (!value || typing) return
    const id = activeId
    // Capture prior turns BEFORE appending the new user message so the backend
    // gets the conversation memory that led up to this question.
    const priorSession = sessions.find((s) => s.id === id) || active
    const history = toHistory(priorSession?.messages)
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
    respondTo(id, value, history)
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
    delete pendingTrace.current[s.id]
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

  // Normalize the live BigQuery findings into the shape the panel renders.
  const normalizedIssues = liveIssues.map((r) => {
    const amountNum = Number.parseFloat(r.amount) || 0
    return {
      id: r.finding_id,
      invoice: r.invoice_number || '',
      problem: r.problem || 'Billing anomaly',
      account: r.invoice_number || r.contract_number || r.shipment_id || '—',
      amount: `$${amountNum.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      rawAmount: amountNum,
      severity: (r.severity || 'low').toLowerCase(),
      recommendation: r.recommendation || '',
    }
  })

  const hasIssues = normalizedIssues.length > 0
  const flaggedTotal = normalizedIssues.reduce(
    (sum, i) => sum + (Number.parseFloat(i.rawAmount) || 0),
    0,
  )

  // Confirm a review: persist to BigQuery, then drop the invoice from the list.
  const reviewIssue = async (inv) => {
    if (reviewingId) return
    setReviewingId(inv.id)
    try {
      await reviewFlaggedInvoice(inv.id, { comment: `Reviewed via ${agent.name}` })
      setLiveIssues((prev) => prev.filter((r) => r.finding_id !== inv.id))
      send(`Reviewed flagged invoice ${inv.invoice || inv.id} — ${inv.problem} (${inv.amount}).`)
      setIssuesOpen(false)
    } catch (err) {
      setIssuesError(err.message || 'Failed to review invoice.')
    } finally {
      setReviewingId(null)
    }
  }

  // Ask the agent to explain a specific flagged invoice and its issue.
  const explainIssue = (inv) => {
    const parts = [
      `Explain flagged invoice ${inv.invoice || inv.id}`,
      `${inv.problem} (${inv.amount})`,
    ]
    if (inv.recommendation) parts.push(`recommended action: ${inv.recommendation}`)
    send(`${parts.join(' — ')}. Why was it flagged and what should we do?`)
    setIssuesOpen(false)
  }

  const filteredIssues = normalizedIssues.filter((inv) => {
    const q = issueQuery.trim().toLowerCase()
    if (!q) return true
    return (
      inv.id.toLowerCase().includes(q) ||
      inv.problem.toLowerCase().includes(q) ||
      inv.account.toLowerCase().includes(q) ||
      inv.severity.toLowerCase().includes(q)
    )
  })

  const IssuesPanel = agent.slug === 'prevent' ? (
    <div className="flex h-full flex-col">
      <div className="border-b border-brand-brown/10 px-4 py-4">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 animate-pulseGlow rounded-full bg-red-500" />
          <h3 className="text-sm font-semibold text-brand-brownDeep">Invoices with issues</h3>
        </div>
        <p className="mt-1 text-[11px] text-brand-brown/50">
          {issuesLoading
            ? 'Loading from BigQuery…'
            : `${normalizedIssues.length} flagged · $${flaggedTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} at risk`}
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
        {issuesLoading && (
          <p className="px-2 py-6 text-center text-xs text-brand-brown/40">Loading flagged invoices…</p>
        )}
        {!issuesLoading && issuesError && (
          <p className="px-2 py-6 text-center text-xs text-red-500">{issuesError}</p>
        )}
        {!issuesLoading && !issuesError && filteredIssues.length === 0 && (
          <p className="px-2 py-6 text-center text-xs text-brand-brown/40">
            {normalizedIssues.length === 0 ? 'No invoices flagged. All clear.' : 'No matching invoices.'}
          </p>
        )}
        {!issuesLoading && filteredIssues.map((inv) => {
          const s = severityStyle[inv.severity] || severityStyle.low
          const isReviewing = reviewingId === inv.id
          const isExpanded = expandedId === inv.id
          return (
            <div
              key={inv.id}
              className={`w-full rounded-xl border bg-white p-3 text-left shadow-sm transition-colors ${
                isExpanded ? 'border-brand-gold' : 'border-brand-brown/10 hover:border-brand-gold/60'
              }`}
            >
              <button
                type="button"
                onClick={() => setExpandedId(isExpanded ? null : inv.id)}
                className="w-full text-left"
                aria-expanded={isExpanded}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-brand-brownDeep">{inv.invoice || inv.id}</span>
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
              {isExpanded && (
                <div className="mt-3 border-t border-brand-brown/10 pt-3">
                  {inv.recommendation && (
                    <p className="mb-2 text-[11px] text-brand-brown/60">
                      <span className="font-semibold text-brand-brownDeep">Recommended: </span>
                      {inv.recommendation}
                    </p>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={() => explainIssue(inv)}
                      className="flex-1 rounded-lg border border-brand-brown/15 bg-white px-3 py-2 text-xs font-semibold text-brand-brownDeep transition-colors hover:border-brand-gold hover:bg-brand-gold/10"
                    >
                      Explain
                    </button>
                    <button
                      onClick={() => reviewIssue(inv)}
                      disabled={isReviewing}
                      className="flex-1 rounded-lg bg-brand-brownDeep px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-brand-gold hover:text-brand-brownDeep disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isReviewing ? 'Confirming…' : 'Review & confirm'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
      <div className="border-t border-brand-brown/10 px-4 py-3 text-center text-[10px] text-brand-brown/40">
        Tap an invoice to explain it or confirm a review (updates BigQuery)
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
                  {normalizedIssues.length}
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
          <div
            ref={inputWrapRef}
            className="mx-auto flex max-w-3xl items-center gap-2 rounded-2xl border border-brand-brown/15 bg-white px-3 py-2 shadow-sm transition-colors focus-within:border-brand-gold"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={droneText || (droneWriting ? '' : agent.placeholder || `Message ${agent.name}…`)}
              className={`flex-1 bg-transparent px-2 py-2.5 text-sm text-brand-brownDeep focus:outline-none ${
                droneText
                  ? 'placeholder:font-bold placeholder:text-black'
                  : 'placeholder:text-brand-brown/40'
              }`}
            />
            <button
              ref={sendBtnRef}
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
            AI-generated responses may be inaccurate — please verify important information.
          </div>
        </form>
      </div>

      {/* Right sidebar: flagged invoices (Prevent Agent). Static on xl+. */}
      {agent.slug === 'prevent' && (
        <aside className="hidden w-80 shrink-0 border-l border-brand-brown/10 bg-white/90 backdrop-blur-2xl xl:block">
          {IssuesPanel}
        </aside>
      )}

      {/* Right sidebar as a slide-in drawer on smaller screens */}
      <AnimatePresence>
        {agent.slug === 'prevent' && issuesOpen && (
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
