import { useState, useEffect } from 'react'
import { planProfit, getPriceReference, getTrendFilters } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'

const RISK_COLOR = { low: 'bg-green-100 text-green-800', medium: 'bg-yellow-100 text-yellow-800',
                     high: 'bg-red-100 text-red-800', unknown: 'bg-gray-100 text-gray-600' }
const NUM = ['area_acres', 'yield_q_per_acre', 'input_cost', 'labour_cost', 'transport_cost', 'market_price']
const LABELS = { area_acres: 'Area (acres)', yield_q_per_acre: 'Yield (quintal/acre)',
  input_cost: 'Input cost (₹)', labour_cost: 'Labour cost (₹)', transport_cost: 'Transport cost (₹)',
  market_price: 'Market price (₹/quintal)' }

export default function ProfitPlanner() {
  const { state, crop, setCrop } = useWorkspace()
  const [filters, setFilters] = useState({ states: [], commodities: [] })
  const commodity = crop
  const setCommodity = setCrop
  const [ref, setRef] = useState(null)
  const [form, setForm] = useState({ area_acres: 2, yield_q_per_acre: 20, input_cost: 10000,
    labour_cost: 5000, transport_cost: 3000, market_price: 1500 })
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => { getTrendFilters().then(setFilters).catch(() => {}) }, [])

  const loadPrice = async () => {
    if (!state || !commodity) return
    const r = await getPriceReference(state, commodity)
    setRef(r)
    if (r.latest_price) setForm((f) => ({ ...f, market_price: r.latest_price }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const body = Object.fromEntries(NUM.map((k) => [k, Number(form[k])]))
      setResult(await planProfit(body))
    } catch (err) {
      setError(err.response?.data?.detail || 'Calculation failed'); setResult(null)
    }
  }

  return (
    <div className="max-w-3xl w-full">
      <h1 className="text-2xl font-bold text-green-800 mb-1">Profit Planner</h1>
      <p className="text-gray-600 mb-4">Estimate profit, break-even price, and selling risk for your crop.</p>
      {error && <ErrorBanner message={error} />}

      <div className="flex flex-wrap gap-2 items-end mb-4">
        <label className="text-sm">Commodity
          <select className="mt-1 block border rounded px-2 py-2" value={commodity} onChange={(e) => setCommodity(e.target.value)}>
            <option value="">—</option>{filters.commodities.map((c) => <option key={c}>{c}</option>)}
          </select></label>
        <button type="button" onClick={loadPrice} className="bg-green-700 text-white rounded px-3 py-2 text-sm">Use market price</button>
        {ref && (
          <span className={`text-xs px-2 py-1 rounded ${RISK_COLOR[ref.risk_level]}`}>
            Price risk: {ref.risk_level}{ref.latest_price ? ` (latest ₹${ref.latest_price}/q)` : ''}
          </span>
        )}
      </div>

      <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
        {NUM.map((k) => (
          <label key={k} className="text-sm text-gray-700">{LABELS[k]}
            <input type="number" step="any" value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              className="mt-1 w-full border rounded px-2 py-2" /></label>
        ))}
        <button className="col-span-2 md:col-span-3 bg-green-700 text-white rounded py-3 font-medium hover:bg-green-800">Calculate</button>
      </form>

      {result && (
        <div className="border rounded p-4 space-y-2">
          <p className={`text-2xl font-bold ${result.profit >= 0 ? 'text-green-700' : 'text-red-600'}`}>
            {result.profit >= 0 ? 'Profit' : 'Loss'}: ₹{Math.abs(result.profit).toLocaleString('en-IN')}
          </p>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <span>Revenue: ₹{result.total_revenue.toLocaleString('en-IN')}</span>
            <span>Total cost: ₹{result.total_cost.toLocaleString('en-IN')}</span>
            <span>Break-even price: {result.break_even_price ? `₹${result.break_even_price}/q` : '—'}</span>
            <span>Target sale price: {result.target_sale_price ? `₹${result.target_sale_price}/q` : '—'}</span>
          </div>
          <p className="text-gray-800 bg-gray-50 rounded p-2">{result.recommendation}</p>
        </div>
      )}
    </div>
  )
}
