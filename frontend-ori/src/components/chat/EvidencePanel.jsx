import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

// Expandable proof panel (Option C) — enterprise-grade source attribution
// rendered inline under an assistant message. Keeps the evidence bound to the
// answer it supports without cluttering the transcript.
export default function EvidencePanel({ evidence, accent = '#2b1810' }) {
  const [open, setOpen] = useState(false)
  const items = Array.isArray(evidence) ? evidence : []
  if (!items.length) return null

  return (
    <div className="mt-2 border-t border-brand-brown/10 pt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-[11px] font-semibold text-brand-brown/60 transition-colors hover:text-brand-brownDeep"
        aria-expanded={open}
      >
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
          <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M11 11l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        Evidence ({items.length})
        <svg
          width="10"
          height="10"
          viewBox="0 0 16 16"
          fill="none"
          className={`transition-transform ${open ? 'rotate-90' : ''}`}
        >
          <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-2">
              {items.map((ev, i) => {
                const confidence = Math.max(0, Math.min(100, Number(ev.confidence ?? 100)))
                return (
                  <div
                    key={i}
                    className="rounded-lg border border-brand-brown/10 bg-white/70 p-2.5 text-[11px] text-brand-brown/70"
                    style={{ borderColor: `${accent}22` }}
                  >
                    <Row label="Source Object" value={ev.source_object} mono />
                    {ev.record_id && <Row label="Record ID" value={ev.record_id} mono />}
                    {ev.retrieved_fields?.length > 0 && (
                      <Row label="Retrieved Fields" value={ev.retrieved_fields.join(', ')} />
                    )}
                    <div className="mt-1.5 flex items-center gap-2">
                      <span className="w-24 shrink-0 text-brand-brown/50">Confidence</span>
                      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-brand-brown/10">
                        <span
                          className="block h-full rounded-full"
                          style={{ width: `${confidence}%`, background: accent }}
                        />
                      </span>
                      <span className="w-9 shrink-0 text-right font-semibold text-brand-brownDeep">
                        {confidence}%
                      </span>
                    </div>
                    {ev.last_updated && <Row label="Last Updated" value={formatDate(ev.last_updated)} />}
                    <Row label="Source System" value={ev.source_system || 'BigQuery'} />
                    {ev.tool && <Row label="Tool" value={ev.tool} mono />}
                    {ev.tables?.length > 0 && (
                      <Row label={ev.source_system === 'GCS' ? 'Bucket / Object' : 'Tables'} value={ev.tables.join(', ')} mono />
                    )}
                    {ev.query && (
                      <div className="mt-1.5">
                        <span className="text-brand-brown/50">Query</span>
                        <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-brand-brown/[0.06] px-2 py-1 font-mono text-[10px] leading-relaxed text-brand-brown/70">
                          {ev.query}
                        </pre>
                      </div>
                    )}
                    {ev.snippet && (
                      <p className="mt-1.5 rounded bg-brand-brown/[0.04] px-2 py-1 font-mono text-[10px] text-brand-brown/60">
                        {ev.snippet}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Row({ label, value, mono }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="w-24 shrink-0 text-brand-brown/50">{label}</span>
      <span className={`text-brand-brownDeep ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  )
}

function formatDate(value) {
  try {
    return new Date(value).toISOString().slice(0, 10)
  } catch {
    return String(value)
  }
}
