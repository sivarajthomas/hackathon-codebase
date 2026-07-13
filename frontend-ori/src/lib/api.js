// Backend API client for the agent chat workspace.
//
// The base URL is injected at build time via VITE_API_BASE_URL (see
// .env.example). When empty, requests are made relative to the current origin
// (useful when a reverse proxy fronts the backend under the same host).

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

const url = (path) => `${API_BASE}${path}`

// Read the bearer token straight from storage so the client stays framework-free.
function authHeaders(extra = {}) {
  let token = null
  try {
    const raw = localStorage.getItem('ii_auth')
    token = raw ? JSON.parse(raw)?.token : null
  } catch {
    token = null
  }
  return {
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function parseError(res, fallback) {
  let detail = fallback
  try {
    const body = await res.json()
    if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : detail
  } catch {
    /* ignore non-JSON error bodies */
  }
  return new Error(detail)
}

// --- Auth -----------------------------------------------------------------

/** Exchange credentials for a JWT + user profile. */
export async function login(username, password) {
  const res = await fetch(url('/v1/auth/login'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) throw await parseError(res, `Login failed (${res.status})`)
  return res.json()
}

/** Return the current user profile for the stored token (or null). */
export async function getMe() {
  const res = await fetch(url('/v1/auth/me'), { headers: authHeaders() })
  if (res.status === 401) return null
  if (!res.ok) throw await parseError(res, `Failed to load profile (${res.status})`)
  return res.json()
}

// --- Invoice context (replaces LLM discovery) -----------------------------

/** Validate an invoice exists (and is in scope); returns its denormalised context. */
export async function getInvoiceContext(invoiceNumber, { signal } = {}) {
  const res = await fetch(url(`/v1/invoices/${encodeURIComponent(invoiceNumber)}/context`), {
    headers: authHeaders(),
    signal,
  })
  if (!res.ok) throw await parseError(res, `Invoice lookup failed (${res.status})`)
  return res.json()
}

// --- Conversations / history ----------------------------------------------

export async function listConversations({ q, agent, invoiceNumber, signal } = {}) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (agent) params.set('agent', agent)
  if (invoiceNumber) params.set('invoice_number', invoiceNumber)
  const res = await fetch(url(`/v1/conversations?${params.toString()}`), {
    headers: authHeaders(),
    signal,
  })
  if (!res.ok) throw await parseError(res, `Failed to load history (${res.status})`)
  return res.json()
}

export async function getConversation(conversationId, { signal } = {}) {
  const res = await fetch(url(`/v1/conversations/${encodeURIComponent(conversationId)}`), {
    headers: authHeaders(),
    signal,
  })
  if (!res.ok) throw await parseError(res, `Failed to load conversation (${res.status})`)
  return res.json()
}

export async function deleteConversation(conversationId) {
  const res = await fetch(url(`/v1/conversations/${encodeURIComponent(conversationId)}`), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok && res.status !== 204) throw await parseError(res, `Delete failed (${res.status})`)
  return true
}

export async function deleteAllConversations() {
  const res = await fetch(url('/v1/conversations'), { method: 'DELETE', headers: authHeaders() })
  if (!res.ok) throw await parseError(res, `Delete failed (${res.status})`)
  return res.json()
}

/**
 * Send a single chat turn to the backend and return the agent's text reply.
 *
 * @param {Object} params
 * @param {string} params.agent   Agent slug: explain | resolve | simulate | prevent
 * @param {string} params.message Free-text user message
 * @param {string} [params.invoiceNumber] Invoice number (required by the UI)
 * @param {string} [params.invoiceDate] Optional invoice date (YYYY-MM-DD)
 * @param {string} [params.conversationId] Multi-session thread id
 * @param {string} [params.traceId] Set to resume a pending clarification turn
 * @param {Array<{role: string, content: string}>} [params.history] Prior turns (oldest first)
 * @param {AbortSignal} [params.signal]    Optional abort signal
 * @returns {Promise<{reply: string, status: string, verb: string|null, evidence: Array,
 *                     requiresHumanReview: boolean, traceId: string, conversationId: string|null,
 *                     output: object|null}>}
 */
export async function sendChatMessage({ agent, message, invoiceNumber, invoiceDate, conversationId, traceId, history, signal } = {}) {
  const res = await fetch(url('/v1/chat'), {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      agent,
      message,
      ...(invoiceNumber ? { invoice_number: invoiceNumber } : {}),
      ...(invoiceDate ? { as_of_date: invoiceDate } : {}),
      ...(conversationId ? { conversation_id: conversationId } : {}),
      ...(traceId ? { trace_id: traceId } : {}),
      ...(history && history.length ? { history } : {}),
    }),
    signal,
  })

  if (!res.ok) {
    throw await parseError(res, `Request failed (${res.status})`)
  }

  const data = await res.json()
  return {
    reply: data.reply,
    status: data.status,
    verb: data.verb ?? null,
    evidence: Array.isArray(data.evidence) ? data.evidence : [],
    requiresHumanReview: Boolean(data.requires_human_review),
    traceId: data.trace_id,
    conversationId: data.conversation_id ?? null,
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
  const res = await fetch(url(`/v1/prevent/flagged?${params.toString()}`), { headers: authHeaders(), signal })
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
    headers: authHeaders({ 'Content-Type': 'application/json' }),
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
