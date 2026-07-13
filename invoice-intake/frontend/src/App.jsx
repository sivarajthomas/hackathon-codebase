import { useEffect, useMemo, useState } from 'react'
import { getTables, createInvoice, insertRow } from './api'

// Fields the server links/generates automatically — hidden from the form.
const HIDDEN_INVOICE_FIELDS = new Set(['InvoiceNumber', 'ShipmentID'])
const HIDDEN_SHIPMENT_FIELDS = new Set(['ShipmentID', 'InvoiceNumber'])

export default function App() {
  const [tables, setTables] = useState([])
  const [tab, setTab] = useState('invoice')
  const [banner, setBanner] = useState(null)
  const [lastResult, setLastResult] = useState(null)

  useEffect(() => {
    getTables().then(setTables).catch((e) => setBanner({ type: 'error', text: e.message }))
  }, [])

  const shipmentSpec = tables.find((t) => t.name === 'shipment_transactions')
  const invoiceSpec = tables.find((t) => t.name === 'invoice_records')

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Invoice Intake</h1>
          <p className="subtitle">Enter invoice details → validated write to all tables → published to the <span className="accent">Prevent</span> agent.</p>
        </div>
      </header>

      {banner && (
        <div className={`banner ${banner.type}`} onClick={() => setBanner(null)}>
          {banner.text}
        </div>
      )}

      <div className="layout">
        <main className="main">
          <nav className="tabs">
            <button className={tab === 'invoice' ? 'active' : ''} onClick={() => setTab('invoice')}>Create Invoice</button>
            <button className={tab === 'tables' ? 'active' : ''} onClick={() => setTab('tables')}>Manage Tables</button>
          </nav>

          {tab === 'invoice' && shipmentSpec && invoiceSpec && (
            <CreateInvoice
              shipmentSpec={shipmentSpec}
              invoiceSpec={invoiceSpec}
              onBanner={setBanner}
              onResult={setLastResult}
            />
          )}

          {tab === 'tables' && (
            <ManageTables tables={tables} onBanner={setBanner} />
          )}
        </main>

        <aside className="sidebar">
          <div className="sidebar-head">
            <span className="dot" />
            <h2>Prevent hand-off</h2>
          </div>
          {!lastResult && (
            <p className="empty">Submit an invoice to publish it to the Prevent agent. Flagged issues appear in the Prevent section of the main app for CS review.</p>
          )}
          {lastResult && <ResultCard result={lastResult} />}
        </aside>
      </div>
    </div>
  )
}

function CreateInvoice({ shipmentSpec, invoiceSpec, onBanner, onResult }) {
  const shipmentCols = shipmentSpec.columns.filter((c) => !HIDDEN_SHIPMENT_FIELDS.has(c.name))
  const invoiceCols = invoiceSpec.columns.filter((c) => !HIDDEN_INVOICE_FIELDS.has(c.name))

  const [shipment, setShipment] = useState({})
  const [invoice, setInvoice] = useState({})
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    setErrors({})
    try {
      const res = await createInvoice(shipment, invoice)
      setShipment({})
      setInvoice({})
      onResult(res)
      const published = res.published ? 'published to the Prevent agent' : 'staged (Pub/Sub not configured)'
      onBanner({ type: 'success', text: `Created ${res.invoice_number} (${res.shipment_id}) — ${published}.` })
    } catch (e) {
      applyErrors(e, setErrors)
      onBanner({ type: 'error', text: e.status === 409 ? e.message : 'Please correct the highlighted fields.' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <section>
        <h3>Shipment</h3>
        <div className="grid">
          {shipmentCols.map((c) => (
            <Field key={c.name} col={c} value={shipment[c.name] ?? ''} error={errors[c.name]}
              onChange={(v) => setShipment((s) => ({ ...s, [c.name]: v }))} />
          ))}
        </div>
      </section>
      <section>
        <h3>Invoice Charges</h3>
        <div className="grid">
          {invoiceCols.map((c) => (
            <Field key={c.name} col={c} value={invoice[c.name] ?? ''} error={errors[c.name]}
              onChange={(v) => setInvoice((s) => ({ ...s, [c.name]: v }))} />
          ))}
        </div>
      </section>
      <div className="actions">
        <button className="primary" disabled={busy} onClick={submit}>
          {busy ? 'Submitting…' : 'Create Invoice & Publish'}
        </button>
      </div>
    </div>
  )
}

function ManageTables({ tables, onBanner }) {
  const [name, setName] = useState('')
  const [row, setRow] = useState({})
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const spec = useMemo(() => tables.find((t) => t.name === name), [tables, name])

  useEffect(() => { setRow({}); setErrors({}) }, [name])

  const cols = spec ? spec.columns.filter((c) => !(c.name === spec.key_column && spec.generates_key)) : []

  const submit = async () => {
    setBusy(true); setErrors({})
    try {
      await insertRow(name, row, true)
      setRow({})
      onBanner({ type: 'success', text: `Row added to ${spec.label}.` })
    } catch (e) {
      applyErrors(e, setErrors)
      onBanner({ type: 'error', text: e.status === 409 ? e.message : 'Please correct the highlighted fields.' })
    } finally { setBusy(false) }
  }

  return (
    <div className="card">
      <label className="select-label">Table
        <select value={name} onChange={(e) => setName(e.target.value)}>
          <option value="">Select a table…</option>
          {tables.map((t) => <option key={t.name} value={t.name}>{t.label}</option>)}
        </select>
      </label>
      {spec && (
        <>
          {spec.generates_key && <p className="muted">Key <code>{spec.key_column}</code> auto-generated ({spec.key_prefix}…).</p>}
          <div className="grid">
            {cols.map((c) => (
              <Field key={c.name} col={c} value={row[c.name] ?? ''} error={errors[c.name]}
                onChange={(v) => setRow((s) => ({ ...s, [c.name]: v }))} />
            ))}
          </div>
          <div className="actions">
            <button className="primary" disabled={busy} onClick={submit}>{busy ? 'Saving…' : `Add to ${spec.label}`}</button>
          </div>
        </>
      )}
    </div>
  )
}

function Field({ col, value, error, onChange }) {
  const type = col.type === 'int' || col.type === 'float' ? 'number' : col.type === 'date' ? 'date' : 'text'
  return (
    <label className={`field ${error ? 'has-error' : ''}`}>
      <span>{col.name}{col.required ? ' *' : ''}</span>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={col.ref_table ? `ref: ${col.ref_table}` : ''} />
      {error && <em className="err">{error}</em>}
    </label>
  )
}

function ResultCard({ result }) {
  const anomaly = !!result.anomaly
  const sev = (result.severity || 'low').toLowerCase()
  return (
    <div className={`finding ${anomaly ? `sev-${sev}` : 'sev-low'}`}>
      <div className="finding-top">
        <strong>{result.invoice_number}</strong>
        <span className={`badge ${result.published ? 'low' : 'medium'}`}>{result.published ? 'published' : 'staged'}</span>
      </div>
      {anomaly ? (
        <>
          <div className="finding-type">{result.leakage_type}</div>
          <div className="finding-amt">₹ {Number(result.leakage_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
          <span className={`badge ${sev}`}>{sev}</span>
          <p className="finding-cause">Flagged for the Prevent agent. The detected issue will appear in the Prevent section of the main app for customer-support review.</p>
        </>
      ) : (
        <p className="finding-cause">No leakage detected. The invoice was published to the Prevent agent for record.</p>
      )}
    </div>
  )
}

// Map a 422 validation error payload to a {field: message} map.
function applyErrors(e, setErrors) {
  const items = e.detail && e.detail.errors
  if (Array.isArray(items)) {
    const map = {}
    for (const it of items) if (it.field) map[it.field] = it.message
    setErrors(map)
  }
}
