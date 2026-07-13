// Backend API client for the agent chat workspace.
//
// The base URL is injected at build time via VITE_API_BASE_URL (see
// .env.example). When empty, requests are made relative to the current origin
// (useful when a reverse proxy fronts the backend under the same host).

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

const url = (path) => `${API_BASE}${path}`

/**
 * Send a single chat turn to the backend and return the agent's text reply.
 *
 * @param {Object} params
 * @param {string} params.agent   Agent slug: explain | resolve | simulate | prevent
 * @param {string} params.message Free-text user message
 * @param {string} [params.invoiceNumber] Optional explicit invoice number
 * @param {string} [params.traceId] Set to resume a pending clarification turn
 * @param {Array<{role: string, content: string}>} [params.history] Prior turns (oldest first)
 * @param {AbortSignal} [params.signal]    Optional abort signal
 * @returns {Promise<{reply: string, status: string, verb: string|null,
 *                     requiresHumanReview: boolean, traceId: string,
 *                     output: object|null}>}
 */
export async function sendChatMessage({ agent, message, invoiceNumber, traceId, history, signal } = {}) {
  const res = await fetch(url('/v1/chat'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent,
      message,
      ...(invoiceNumber ? { invoice_number: invoiceNumber } : {}),
      ...(traceId ? { trace_id: traceId } : {}),
      ...(history && history.length ? { history } : {}),
    }),
    signal,
  })

  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : detail
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail)
  }

  const data = await res.json()
  return {
    reply: data.reply,
    status: data.status,
    verb: data.verb ?? null,
    requiresHumanReview: Boolean(data.requires_human_review),
    traceId: data.trace_id,
    output: data.output ?? null,
  }
}

/**
 * Fetch the invoices currently flagged with a billing issue (Prevent agent).
 * These come from the live BigQuery findings store; only unreviewed findings
 * are returned so a reviewed invoice drops off the list.
 *
 * @param {Object} [params]
 * @param {string} [params.userId='cs']
 * @param {boolean} [params.onlyUnreviewed=true]
 * @param {AbortSignal} [params.signal]
 * @returns {Promise<Array<Object>>} Flagged invoice records.
 */
export async function getFlaggedInvoices({ userId = 'cs', onlyUnreviewed = true, signal } = {}) {
  const params = new URLSearchParams({
    user_id: userId,
    only_unreviewed: String(onlyUnreviewed),
  })
  const res = await fetch(url(`/v1/prevent/flagged?${params.toString()}`), { signal })
  if (!res.ok) {
    throw new Error(`Failed to load flagged invoices (${res.status})`)
  }
  return res.json()
}

/**
 * Mark a flagged invoice as reviewed. Updates the BigQuery findings store so the
 * invoice no longer appears in the flagged list.
 *
 * @param {string} findingId
 * @param {Object} [params]
 * @param {string} [params.reviewerId='cs']
 * @param {string} [params.status='resolved']
 * @param {string} [params.comment]
 * @param {AbortSignal} [params.signal]
 * @returns {Promise<Object>} The reviewed invoice record.
 */
export async function reviewFlaggedInvoice(findingId, { reviewerId = 'cs', status = 'resolved', comment, signal } = {}) {
  const res = await fetch(url(`/v1/prevent/flagged/${encodeURIComponent(findingId)}/review`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reviewer_id: reviewerId,
      status,
      ...(comment ? { comment } : {}),
    }),
    signal,
  })
  if (!res.ok) {
    let detail = `Review failed (${res.status})`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : detail
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail)
  }
  return res.json()
}
