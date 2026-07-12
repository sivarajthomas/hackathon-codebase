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
