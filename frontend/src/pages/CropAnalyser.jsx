import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { getCropMarkup, getTrendFilters } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'

export default function CropAnalyser() {
  const [crops, setCrops]       = useState([])
  const [selected, setSelected] = useState('')
  const [data, setData]         = useState([])
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    getTrendFilters().then(f => {
      setCrops(f.commodities)
      if (f.commodities.length) setSelected(f.commodities[0])
    })
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    getCropMarkup(selected).then(setData).finally(() => setLoading(false))
  }, [selected])

  return (
    <div>
      <h1 className="text-2xl font-bold text-green-800 mb-2">Crop Markup by State</h1>
      <select className="border rounded px-3 py-2 mb-4 text-sm"
        value={selected} onChange={e => setSelected(e.target.value)}>
        {crops.map(c => <option key={c}>{c}</option>)}
      </select>
      {loading ? <LoadingSpinner /> : (
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={data} layout="vertical" margin={{ left: 100 }}>
            <XAxis type="number" unit="%" />
            <YAxis dataKey="state" type="category" width={100} tick={{ fontSize: 12 }} />
            <Tooltip formatter={v => `${v}%`} />
            <Bar dataKey="avg_markup_pct" name="Markup %">
              {data.map((_, i) => <Cell key={i} fill={i < 5 ? '#dc2626' : '#16a34a'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
