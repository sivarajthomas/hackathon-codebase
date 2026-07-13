import { useEffect, useMemo, useState } from 'react'
import { getTables, getRows, getNextId, createInvoice, insertRow } from './api'

// Fields the server links/generates automatically — hidden from the form.
const HIDDEN_INVOICE_FIELDS = new Set(['InvoiceNumber', 'ShipmentID'])
const HIDDEN_SHIPMENT_FIELDS = new Set(['ShipmentID', 'InvoiceNumber'])

// Human-friendly guidance for each column: label, helper text, unit, example.
// Anything not listed falls back to sensible defaults derived from the schema.
const FIELD_META = {
  // Shipment
  ContractNumber: { label: 'Contract', help: 'Governing rate contract for this customer.', example: 'LOG-CON-2026-001' },
  ShipmentDate: { label: 'Shipment Date', help: 'Date the goods were shipped.' },
  Origin: { label: 'Origin City', help: 'City the shipment departs from.', example: 'Chennai' },
  Destination: { label: 'Destination City', help: 'City the shipment is delivered to.', example: 'Delhi' },
  ItemID: { label: 'Item', help: 'Contracted item being shipped.', example: 'ITM-002' },
  BookedWeightKg: { label: 'Booked Weight', unit: 'kg', help: 'Weight declared at booking.', example: '1880' },
  MeasuredWeightKg: { label: 'Measured Weight', unit: 'kg', help: 'Actual weighed value at the hub.', example: '1890' },
  VolumetricWeightKg: { label: 'Volumetric Weight', unit: 'kg', help: 'Dimensional weight = (L×W×H)/5000.', example: '2350' },
  BillableWeightKg: { label: 'Billable Weight', unit: 'kg', help: 'Higher of measured / volumetric — charges are based on this.', example: '2250' },
  ModeOfTransport: { label: 'Mode of Transport', help: 'Carrier mode used.' },
  ShipmentValueINR: { label: 'Declared Value', unit: '₹', help: 'Insured value of the goods (drives insurance = 1.5%).', example: '4807906' },
  RemoteAreaFlag: { label: 'Remote-Area Delivery?', help: 'Delivery to a remote / out-of-delivery-area location.' },
  ExpressFlag: { label: 'Express Delivery?', help: 'Priority / express service was requested.' },
  HazardousFlag: { label: 'Hazardous Material?', help: 'Shipment contains hazardous goods.' },
  // Invoice charges
  InvoiceDate: { label: 'Invoice Date', help: 'Date the carrier invoice was raised.' },
  FreightCharge: { label: 'Freight Charge', unit: '₹', help: 'Base freight billed by the carrier.', example: '27000' },
  FuelSurcharge: { label: 'Fuel Surcharge', unit: '₹', help: 'Fuel surcharge billed.', example: '1350' },
  OtherSurcharge: { label: 'Other Surcharges', unit: '₹', help: 'Remote / express / overweight / hazmat surcharges billed. Enter 0 if none.' },
  InsuranceCharge: { label: 'Insurance Charge', unit: '₹', help: 'Insurance billed. Policy expects 1.5% of declared value.' },
  DiscountAmount: { label: 'Discount', unit: '₹', help: 'Any discount applied. Enter 0 if none.' },
  TaxAmount: { label: 'Tax', unit: '₹', help: 'Tax billed. Enter 0 if none.' },
  TotalInvoiceAmount: { label: 'Total Invoice Amount', unit: '₹', help: 'Auto-calculated from the charges above; override only if the carrier total differs.' },
}

const todayStr = () => new Date().toISOString().slice(0, 10)

// Defaults so "optional-looking" required fields are never accidentally blank.
const SHIPMENT_DEFAULTS = { ShipmentDate: todayStr(), RemoteAreaFlag: '0', ExpressFlag: '0', HazardousFlag: '0' }
const INVOICE_DEFAULTS = { InvoiceDate: todayStr(), OtherSurcharge: '0', DiscountAmount: '0', TaxAmount: '0' }

export default function App() {
  const [tables, setTables] = useState([])
  const [tab, setTab] = useState('invoice')
  const [banner, setBanner] = useState(null)
  const [lastResult, setLastResult] = useState(null)
  const [refs, setRefs] = useState({})

  useEffect(() => {
    getTables().then(setTables).catch((e) => setBanner({ type: 'error', text: e.message }))
    loadRefs()
  }, [])

  // Load existing values used to power dropdown suggestions.
  const loadRefs = async () => {
    const names = ['contract_master', 'contracted_items', 'transport_rates', 'zone_master', 'shipment_transactions']
    const out = {}
    await Promise.all(names.map(async (n) => { try { out[n] = await getRows(n) } catch { out[n] = [] } }))
    setRefs(out)
  }

  const shipmentSpec = tables.find((t) => t.name === 'shipment_transactions')
  const invoiceSpec = tables.find((t) => t.name === 'invoice_records')

  // Column-name -> selectable suggestions built from existing rows.
  const optionsFor = useMemo(() => {
    const uniq = (rows, key) => [...new Set((rows || []).map((r) => r[key]).filter(Boolean))]
    const labelled = (rows, valueKey, descKey) =>
      (rows || [])
        .filter((r) => r[valueKey])
        .map((r) => ({ value: String(r[valueKey]), label: descKey && r[descKey] ? `${r[valueKey]} — ${r[descKey]}` : String(r[valueKey]) }))
    const modes = uniq(refs.transport_rates, 'TransportMode')
    return (col) => {
      switch (col) {
        case 'ContractNumber': return labelled(refs.contract_master, 'ContractNumber', 'CustomerName')
        case 'ItemID': return labelled(refs.contracted_items, 'ItemID', 'ItemDescription')
        case 'ShipmentID': return labelled(refs.shipment_transactions, 'ShipmentID', 'Destination')
        case 'ModeOfTransport':
        case 'TransportMode': return (modes.length ? modes : ['Roadways', 'Shipways', 'Airways']).map((m) => ({ value: m, label: m }))
        case 'Origin':
        case 'OriginCity': return uniq(refs.zone_master, 'OriginCity').map((c) => ({ value: c, label: c }))
        case 'Destination':
        case 'DestinationCity': return uniq(refs.zone_master, 'DestinationCity').map((c) => ({ value: c, label: c }))
        default: return null
      }
    }
  }, [refs])

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Invoice Intake</h1>
          <p className="subtitle">Fill the shipment &amp; charges → validated write to all tables → published to the <span className="accent">Prevent</span> agent.</p>
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
              optionsFor={optionsFor}
              onBanner={setBanner}
              onResult={(r) => { setLastResult(r); loadRefs() }}
            />
          )}

          {tab === 'tables' && (
            <ManageTables tables={tables} optionsFor={optionsFor} onBanner={setBanner} onSaved={loadRefs} />
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

function CreateInvoice({ shipmentSpec, invoiceSpec, optionsFor, onBanner, onResult }) {
  const shipmentCols = shipmentSpec.columns.filter((c) => !HIDDEN_SHIPMENT_FIELDS.has(c.name))
  const invoiceCols = invoiceSpec.columns.filter((c) => !HIDDEN_INVOICE_FIELDS.has(c.name))

  const [shipment, setShipment] = useState(SHIPMENT_DEFAULTS)
  const [invoice, setInvoice] = useState(INVOICE_DEFAULTS)
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [totalTouched, setTotalTouched] = useState(false)
  const [nextIds, setNextIds] = useState({ shipment: '', invoice: '' })

  const refreshNextIds = () => {
    getNextId('shipment_transactions').then((r) => setNextIds((s) => ({ ...s, shipment: r.next_id }))).catch(() => {})
    getNextId('invoice_records').then((r) => setNextIds((s) => ({ ...s, invoice: r.next_id }))).catch(() => {})
  }
  useEffect(() => { refreshNextIds() }, [])

  // Auto-calculate the billed total unless the user typed one in manually.
  const computedTotal = useMemo(() => {
    const n = (v) => Number(v) || 0
    return Math.round((n(invoice.FreightCharge) + n(invoice.FuelSurcharge) + n(invoice.OtherSurcharge) +
      n(invoice.InsuranceCharge) - n(invoice.DiscountAmount) + n(invoice.TaxAmount)) * 100) / 100
  }, [invoice.FreightCharge, invoice.FuelSurcharge, invoice.OtherSurcharge, invoice.InsuranceCharge, invoice.DiscountAmount, invoice.TaxAmount])

  const totalValue = totalTouched ? (invoice.TotalInvoiceAmount ?? '') : String(computedTotal)

  const setShip = (name, v) => setShipment((s) => ({ ...s, [name]: v }))
  const setInv = (name, v) => {
    if (name === 'TotalInvoiceAmount') setTotalTouched(true)
    setInvoice((s) => ({ ...s, [name]: v }))
  }

  const submit = async () => {
    setBusy(true)
    setErrors({})
    try {
      const payloadInvoice = { ...invoice, TotalInvoiceAmount: totalValue }
      const res = await createInvoice(shipment, payloadInvoice)
      setShipment(SHIPMENT_DEFAULTS)
      setInvoice(INVOICE_DEFAULTS)
      setTotalTouched(false)
      onResult(res)
      const published = res.published ? 'published to the Prevent agent' : 'staged (Pub/Sub not configured)'
      onBanner({ type: 'success', text: `Created ${res.invoice_number} (${res.shipment_id}) — ${published}.` })
      refreshNextIds()
    } catch (e) {
      applyErrors(e, setErrors)
      onBanner({ type: 'error', text: e.status === 409 ? e.message : 'Please correct the highlighted fields below.' })
    } finally {
      setBusy(false)
    }
  }

  const errorList = Object.entries(errors)
  const labelOf = (n) => (FIELD_META[n]?.label || n)

  return (
    <div className="card">
      {errorList.length > 0 && (
        <div className="error-summary">
          <strong>Please fix {errorList.length} field{errorList.length > 1 ? 's' : ''}:</strong>
          <ul>{errorList.map(([f, m]) => <li key={f}>{labelOf(f)} — {m}</li>)}</ul>
        </div>
      )}

      <section>
        <div className="section-head">
          <h3>Shipment</h3>
          {nextIds.shipment && <span className="id-preview">New ID: <code>{nextIds.shipment}</code></span>}
        </div>
        <div className="grid">
          {shipmentCols.map((c) => (
            <SmartField key={c.name} col={c} value={shipment[c.name] ?? ''} error={errors[c.name]}
              options={optionsFor(c.name)} onChange={(v) => setShip(c.name, v)} />
          ))}
        </div>
      </section>

      <section>
        <div className="section-head">
          <h3>Invoice Charges</h3>
          {nextIds.invoice && <span className="id-preview">New ID: <code>{nextIds.invoice}</code></span>}
        </div>
        <div className="grid">
          {invoiceCols.filter((c) => c.name !== 'TotalInvoiceAmount').map((c) => (
            <SmartField key={c.name} col={c} value={invoice[c.name] ?? ''} error={errors[c.name]}
              options={optionsFor(c.name)} onChange={(v) => setInv(c.name, v)} />
          ))}
          <SmartField
            col={{ name: 'TotalInvoiceAmount', type: 'float', required: true }}
            value={totalValue}
            error={errors.TotalInvoiceAmount}
            onChange={(v) => setInv('TotalInvoiceAmount', v)}
            badge={totalTouched ? 'manual' : 'auto'}
          />
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

function ManageTables({ tables, optionsFor, onBanner, onSaved }) {
  const [name, setName] = useState('')
  const [row, setRow] = useState({})
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [nextId, setNextId] = useState('')
  const spec = useMemo(() => tables.find((t) => t.name === name), [tables, name])

  useEffect(() => {
    setRow({}); setErrors({}); setNextId('')
    const s = tables.find((t) => t.name === name)
    if (s?.generates_key) getNextId(name).then((r) => setNextId(r.next_id)).catch(() => {})
  }, [name])

  const cols = spec ? spec.columns.filter((c) => !(c.name === spec.key_column && spec.generates_key)) : []

  const submit = async () => {
    setBusy(true); setErrors({})
    try {
      await insertRow(name, row, true)
      setRow({})
      onBanner({ type: 'success', text: `Row added to ${spec.label}.` })
      onSaved?.()
      if (spec?.generates_key) getNextId(name).then((r) => setNextId(r.next_id)).catch(() => {})
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
          {spec.generates_key && (
            <p className="muted">Key <code>{spec.key_column}</code> is auto-generated{nextId ? <> — next: <code>{nextId}</code></> : null}.</p>
          )}
          <div className="grid">
            {cols.map((c) => (
              <SmartField key={c.name} col={c} value={row[c.name] ?? ''} error={errors[c.name]}
                options={optionsFor(c.name)} onChange={(v) => setRow((s) => ({ ...s, [c.name]: v }))} />
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

function SmartField({ col, value, error, options, onChange, badge }) {
  const meta = FIELD_META[col.name] || {}
  const label = meta.label || col.name
  const isFlag = /Flag$/.test(col.name)
  const inputType = col.type === 'int' || col.type === 'float' ? 'number' : col.type === 'date' ? 'date' : 'text'
  const listId = `dl-${col.name}`

  return (
    <label className={`field ${error ? 'has-error' : ''}`}>
      <span className="field-label">
        {label}{col.required ? <em className="req">*</em> : null}
        {meta.unit ? <span className="field-unit">{meta.unit}</span> : null}
        {badge ? <span className={`mini-badge ${badge}`}>{badge}</span> : null}
      </span>

      {isFlag ? (
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="0">No</option>
          <option value="1">Yes</option>
        </select>
      ) : options ? (
        <>
          <input type="text" value={value} list={listId} placeholder={meta.example ? `e.g. ${meta.example}` : 'Select or type…'}
            onChange={(e) => onChange(e.target.value)} />
          <datalist id={listId}>
            {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </datalist>
        </>
      ) : (
        <input type={inputType} value={value} placeholder={meta.example ? `e.g. ${meta.example}` : ''}
          step={col.type === 'float' ? 'any' : undefined}
          onChange={(e) => onChange(e.target.value)} />
      )}

      {meta.help && !error && <small className="help">{meta.help}</small>}
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
