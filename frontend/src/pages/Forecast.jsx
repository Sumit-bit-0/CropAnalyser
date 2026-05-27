import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts'
import { getTrendFilters, getPriceTrend, getForecast } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function Forecast() {
  const [filters, setFilters]     = useState({ states: [], commodities: [] })
  const [state, setState]         = useState('')
  const [commodity, setCommodity] = useState('')
  const [combined, setCombined]   = useState([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)

  useEffect(() => {
    getTrendFilters()
      .then(f => {
        setFilters(f)
        if (f.states.length)      setState(f.states[0])
        if (f.commodities.length) setCommodity(f.commodities[0])
      })
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    if (!state || !commodity) return
    setLoading(true)
    setError(null)
    Promise.all([getPriceTrend(state, commodity), getForecast(state, commodity)])
      .then(([hist, forecast]) => {
        const history = hist.slice(-12).map(r => ({ ...r, is_forecast: false }))
        setCombined([...history, ...forecast])
      })
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [state, commodity])

  const splitPeriod = combined.find(r => r.is_forecast)?.period

  return (
    <div>
      <h1 className="text-2xl font-bold text-green-800 mb-2">Price Forecast (LSTM)</h1>
      <p className="text-gray-500 text-sm mb-4">Historical (last 12 months) + 6-month LSTM prediction. Dashed line marks forecast start.</p>
      <div className="flex gap-4 mb-4">
        <select className="border rounded px-3 py-2 text-sm" value={state} onChange={e => setState(e.target.value)}>
          {filters.states.map(s => <option key={s}>{s}</option>)}
        </select>
        <select className="border rounded px-3 py-2 text-sm" value={commodity} onChange={e => setCommodity(e.target.value)}>
          {filters.commodities.map(c => <option key={c}>{c}</option>)}
        </select>
      </div>
      {error ? (
        <ErrorBanner message={`No model trained for this combination yet. ${error}`} />
      ) : loading ? <LoadingSpinner /> : (
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={combined}>
            <XAxis dataKey="period" tick={{ fontSize: 10 }} />
            <YAxis unit="₹" />
            <Tooltip formatter={v => `₹${v}`} />
            <Legend />
            {splitPeriod && <ReferenceLine x={splitPeriod} stroke="#666" strokeDasharray="4 4" label="Forecast →" />}
            <Line type="monotone" dataKey="farm_gate_price" stroke="#16a34a" name="Farm Gate ₹" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="modal_price" stroke="#dc2626" name="Market Price ₹" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
