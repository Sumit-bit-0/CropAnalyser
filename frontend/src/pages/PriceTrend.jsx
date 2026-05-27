import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { getTrendFilters, getPriceTrend } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'

export default function PriceTrend() {
  const [filters, setFilters]     = useState({ states: [], commodities: [] })
  const [state, setState]         = useState('')
  const [commodity, setCommodity] = useState('')
  const [data, setData]           = useState([])
  const [loading, setLoading]     = useState(false)

  useEffect(() => {
    getTrendFilters().then(f => {
      setFilters(f)
      if (f.states.length)      setState(f.states[0])
      if (f.commodities.length) setCommodity(f.commodities[0])
    })
  }, [])

  useEffect(() => {
    if (!state || !commodity) return
    setLoading(true)
    getPriceTrend(state, commodity).then(setData).finally(() => setLoading(false))
  }, [state, commodity])

  return (
    <div>
      <h1 className="text-2xl font-bold text-green-800 mb-2">Price Trend Over Time</h1>
      <div className="flex gap-4 mb-4">
        <select className="border rounded px-3 py-2 text-sm" value={state} onChange={e => setState(e.target.value)}>
          {filters.states.map(s => <option key={s}>{s}</option>)}
        </select>
        <select className="border rounded px-3 py-2 text-sm" value={commodity} onChange={e => setCommodity(e.target.value)}>
          {filters.commodities.map(c => <option key={c}>{c}</option>)}
        </select>
      </div>
      {loading ? <LoadingSpinner /> : (
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={data}>
            <XAxis dataKey="period" tick={{ fontSize: 10 }} interval={3} />
            <YAxis unit="&#8377;" />
            <Tooltip formatter={v => `&#8377;${v}`} />
            <Legend />
            <Line type="monotone" dataKey="farm_gate_price" stroke="#16a34a" name="Farm Gate &#8377;" dot={false} />
            <Line type="monotone" dataKey="modal_price" stroke="#dc2626" name="Market Price &#8377;" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
