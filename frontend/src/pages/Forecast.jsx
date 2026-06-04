import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ReferenceLine, CartesianGrid } from 'recharts'
import { getForecastAvailable, getPriceTrend, getForecast } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const AXIS = '#78716C'
const GREEN = '#2E6B43'
const CLAY = '#B5611F'

export default function Forecast() {
  const { state: ctxState } = useWorkspace()
  const [avail, setAvail]         = useState({})   // { state: [commodities] } — only trained models
  const [state, setState]         = useState('')
  const [commodity, setCommodity] = useState('')
  const [combined, setCombined]   = useState([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)

  const states = Object.keys(avail)
  const commodities = avail[state] || []

  useEffect(() => {
    getForecastAvailable()
      .then(map => {
        setAvail(map)
        const sts = Object.keys(map)
        const s0 = map[ctxState] ? ctxState : map['Punjab'] ? 'Punjab' : sts[0] || ''
        const c0 = s0 ? (map[s0].includes('Wheat') ? 'Wheat' : map[s0][0]) : ''
        setState(s0)
        setCommodity(c0)
      })
      .catch(e => setError(e.message))
  }, [])

  const onStateChange = (s) => {
    setState(s)
    const list = avail[s] || []
    if (!list.includes(commodity)) setCommodity(list[0] || '')
  }

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
    <div className="max-w-4xl w-full">
      <PageHeader title="Price Forecast (LSTM)"
        subtitle={`Historical (last 12 months) plus 6-month LSTM prediction. The dashed line marks where the forecast begins. Only states and crops with a trained model are listed (${states.length} states).`} />

      <div className="flex flex-wrap gap-3 mb-4">
        <Select value={state} onValueChange={onStateChange}>
          <SelectTrigger className="w-48 bg-card"><SelectValue placeholder="State" /></SelectTrigger>
          <SelectContent>{states.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={commodity} onValueChange={setCommodity}>
          <SelectTrigger className="w-48 bg-card"><SelectValue placeholder="Commodity" /></SelectTrigger>
          <SelectContent>{commodities.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      {error ? (
        <ErrorBanner message={error} />
      ) : loading ? <LoadingSpinner /> : (
        <Card>
          <CardContent className="p-4">
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={combined}>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="period" tick={{ fontSize: 10, fill: AXIS }} stroke={AXIS} />
                <YAxis unit="₹" tick={{ fontSize: 11, fill: AXIS }} stroke={AXIS} />
                <Tooltip formatter={v => `₹${v}`} />
                <Legend />
                {splitPeriod && <ReferenceLine x={splitPeriod} stroke={AXIS} strokeDasharray="4 4" label="Forecast →" />}
                <Line type="monotone" dataKey="farm_gate_price" stroke={GREEN} name="Farm Gate ₹" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="modal_price" stroke={CLAY} name="Market Price ₹" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
