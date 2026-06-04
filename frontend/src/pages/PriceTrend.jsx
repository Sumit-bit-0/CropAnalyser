import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'
import { getTrendFilters, getPriceTrend } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const AXIS = '#78716C'
const GREEN = '#2E6B43'
const CLAY = '#B5611F'

export default function PriceTrend() {
  const { state, crop, setCrop } = useWorkspace()
  const [filters, setFilters]     = useState({ states: [], commodities: [] })
  const commodity = crop
  const setCommodity = setCrop
  const [data, setData]           = useState([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)

  useEffect(() => {
    getTrendFilters()
      .then(f => {
        setFilters(f)
        if (!crop && f.commodities.length) setCrop(f.commodities[0])
      })
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    if (!state || !commodity) return
    setLoading(true)
    setError(null)
    getPriceTrend(state, commodity)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [state, commodity])

  return (
    <div className="max-w-4xl w-full">
      <PageHeader title="Price Trend Over Time"
        subtitle="Farm-gate versus market price month by month for your selected crop and state." />
      {error && <ErrorBanner message={error} />}
      <div className="flex gap-3 mb-4">
        <Select value={commodity || ''} onValueChange={setCommodity}>
          <SelectTrigger className="w-48 bg-card"><SelectValue placeholder="Commodity" /></SelectTrigger>
          <SelectContent>{filters.commodities.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      {loading ? <LoadingSpinner /> : (
        <Card>
          <CardContent className="p-4">
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={data}>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="period" tick={{ fontSize: 10, fill: AXIS }} stroke={AXIS} interval={3} />
                <YAxis unit="₹" tick={{ fontSize: 11, fill: AXIS }} stroke={AXIS} />
                <Tooltip formatter={v => `₹${v}`} />
                <Legend />
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
