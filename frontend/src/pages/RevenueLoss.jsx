import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { getRevenueLoss } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function RevenueLoss() {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    getRevenueLoss()
      .then(d => setData([...d].sort((a, b) => b.estimated_loss_cr - a.estimated_loss_cr)))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const total = data.reduce((s, r) => s + r.estimated_loss_cr, 0).toFixed(2)

  return (
    <div>
      <h1 className="text-2xl font-bold text-green-800 mb-1">Estimated Revenue Loss to Farmers</h1>
      <p className="text-gray-500 text-sm mb-4">Estimated ₹{total} Cr total annual loss across all states (proxy volume model)</p>
      {error && <ErrorBanner message={error} />}
      {loading ? <LoadingSpinner /> : (
        <>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={data.slice(0, 15)}>
              <XAxis dataKey="state" tick={{ fontSize: 10 }} />
              <YAxis unit=" Cr" />
              <Tooltip formatter={v => `₹${v} Cr`} />
              <Bar dataKey="estimated_loss_cr" fill="#dc2626" name="Est. Loss (₹ Cr)" />
            </BarChart>
          </ResponsiveContainer>
          <table className="mt-6 w-full text-sm border-collapse">
            <thead><tr className="bg-green-800 text-white">
              <th className="p-2 text-left">State</th>
              <th className="p-2">Avg Gap (₹/q)</th>
              <th className="p-2">Est. Loss (₹ Cr)</th>
              <th className="p-2">Crops Tracked</th>
            </tr></thead>
            <tbody>{data.map((r, i) => (
              <tr key={r.state} className={i % 2 === 0 ? 'bg-gray-50' : ''}>
                <td className="p-2 font-medium">{r.state}</td>
                <td className="p-2 text-center">₹{r.avg_gap_per_quintal}</td>
                <td className="p-2 text-center text-red-600 font-bold">₹{r.estimated_loss_cr} Cr</td>
                <td className="p-2 text-center">{r.crop_count}</td>
              </tr>
            ))}</tbody>
          </table>
        </>
      )}
    </div>
  )
}
