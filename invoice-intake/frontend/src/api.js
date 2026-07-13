// Thin API client for the Invoice-Intake backend (Prevent producer).
// The backend base URL is injected at build time via VITE_API_BASE.
const BASE = (import.meta.env.VITE_API_BASE || 'http://localhost:8080').replace(/\/$/, '')

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const err = new Error((data && (data.detail?.errors ? 'Validation failed' : data.detail)) || `Request failed (${res.status})`)
    err.status = res.status
    err.detail = data && data.detail
    throw err
  }
  return data
}

export const getTables = () => req('/tables')
export const getNextId = (table) => req(`/tables/${table}/next-id`)
export const getRows = (table, limit = 500) => req(`/tables/${table}/rows?limit=${limit}`)
export const insertRow = (table, row, autoId = true) =>
  req(`/tables/${table}`, { method: 'POST', body: JSON.stringify({ row, auto_id: autoId }) })
export const createInvoice = (shipment, invoice) =>
  req('/invoices', { method: 'POST', body: JSON.stringify({ shipment, invoice, auto_id: true, run_prevent: true }) })
