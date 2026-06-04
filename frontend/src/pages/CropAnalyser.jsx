import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from 'recharts'
import { getCropMarkup, getTrendFilters } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const AXIS = '#78716C'
const GREEN = '#2E6B43'
const HIGH = '#B3261E'

export default function CropAnalyser() {
  const { crop, setCrop } = useWorkspace()
  const selected = crop
  const setSelected = setCrop
  const [crops, setCrops]       = useState([])
  const [data, setData]         = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  useEffect(() => {
    getTrendFilters()
      .then(f => {
        setCrops(f.commodities)
        if (!crop && f.commodities.length) setCrop(f.commodities[0])
      })
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    setError(null)
    getCropMarkup(selected)
      .then(d => setData([...d].sort((a, b) => b.avg_markup_pct - a.avg_markup_pct)))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selected])

  return (
    <div className="max-w-4xl w-full">
      <PageHeader title="Crop Markup by State"
        subtitle="How far farm-gate prices sit below market prices, state by state. The highest markups (worst for farmers) are flagged." />
      {error && <ErrorBanner message={error} />}
      <div className="flex gap-3 mb-4">
        <Select value={selected || ''} onValueChange={setSelected}>
          <SelectTrigger className="w-48 bg-card"><SelectValue placeholder="Crop" /></SelectTrigger>
          <SelectContent>{crops.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      {loading ? <LoadingSpinner /> : (
        <Card>
          <CardContent className="p-4">
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={data} layout="vertical" margin={{ left: 100 }}>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" unit="%" tick={{ fontSize: 11, fill: AXIS }} stroke={AXIS} />
                <YAxis dataKey="state" type="category" width={100} tick={{ fontSize: 12, fill: AXIS }} stroke={AXIS} />
                <Tooltip formatter={v => `${v}%`} cursor={{ fill: 'hsl(var(--muted))' }} />
                <Bar dataKey="avg_markup_pct" name="Markup %" radius={[0, 3, 3, 0]}>
                  {data.map((_, i) => <Cell key={i} fill={i < 5 ? HIGH : GREEN} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
