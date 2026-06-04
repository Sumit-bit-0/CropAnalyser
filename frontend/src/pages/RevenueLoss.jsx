import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { getRevenueLoss } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const AXIS = '#78716C'
const LOSS = '#B3261E'

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
    <div className="max-w-4xl w-full">
      <PageHeader title="Estimated Revenue Loss to Farmers"
        subtitle={`About ₹${total} Cr in total annual loss across all states (proxy volume model).`} />
      {error && <ErrorBanner message={error} />}
      {loading ? <LoadingSpinner /> : (
        <>
          <Card className="mb-6">
            <CardContent className="p-4">
              <ResponsiveContainer width="100%" height={350}>
                <BarChart data={data.slice(0, 15)}>
                  <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="state" tick={{ fontSize: 10, fill: AXIS }} stroke={AXIS} />
                  <YAxis unit=" Cr" tick={{ fontSize: 11, fill: AXIS }} stroke={AXIS} />
                  <Tooltip formatter={v => `₹${v} Cr`} cursor={{ fill: 'hsl(var(--muted))' }} />
                  <Bar dataKey="estimated_loss_cr" fill={LOSS} name="Est. Loss (₹ Cr)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>State</TableHead>
                  <TableHead className="text-right">Avg Gap (₹/q)</TableHead>
                  <TableHead className="text-right">Est. Loss (₹ Cr)</TableHead>
                  <TableHead className="text-right">Crops Tracked</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((r) => (
                  <TableRow key={r.state}>
                    <TableCell className="font-medium">{r.state}</TableCell>
                    <TableCell className="text-right tabular-nums">₹{r.avg_gap_per_quintal}</TableCell>
                    <TableCell className="text-right tabular-nums font-semibold text-destructive">₹{r.estimated_loss_cr} Cr</TableCell>
                    <TableCell className="text-right tabular-nums">{r.crop_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  )
}
