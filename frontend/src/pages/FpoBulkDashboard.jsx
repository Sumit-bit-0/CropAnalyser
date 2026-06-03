import { useState, useEffect } from 'react'
import { fpoBulkPlan } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const DEFAULT_TRANSPORT = {
  truck_capacity_q: 100, fixed_hire_per_truck: 2000,
  per_km_per_truck: 30, per_q_local_rate: 2,
}

export default function FpoBulkDashboard() {
  const { crop, state, lat, lon } = useWorkspace()
  const firstRow = { lat: lat ?? '', lon: lon ?? '', state: state || '', quantity_q: '' }
  const [rows, setRows] = useState([firstRow])
  const [transport, setTransport] = useState(DEFAULT_TRANSPORT)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setRows((rs) => {
      const [first, ...rest] = rs
      if (first.lat === '' && first.lon === '' && (lat != null || lon != null)) {
        return [{ ...first, lat: lat ?? '', lon: lon ?? '', state: first.state || state || '' }, ...rest]
      }
      return rs
    })
  }, [lat, lon, state])

  const setRow = (i, key, val) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [key]: val } : r)))
  const addRow = () => setRows((rs) => [...rs, { lat: '', lon: '', state: state || '', quantity_q: '' }])
  const removeRow = (i) => setRows((rs) => rs.filter((_, j) => j !== i))
  const setT = (key, val) => setTransport((t) => ({ ...t, [key]: val }))

  const submit = async () => {
    setError(null)
    const invalid = rows.some((r) => r.lat === '' || r.lon === '' || !(Number(r.quantity_q) > 0))
    if (invalid) {
      setError('Each farmer row needs latitude, longitude, and a positive quantity.')
      setResult(null)
      return
    }
    try {
      const farmers = rows.map((r) => ({
        lat: Number(r.lat), lon: Number(r.lon),
        state: r.state || null, quantity_q: Number(r.quantity_q),
      }))
      const body = {
        crop, farmers,
        transport: Object.fromEntries(
          Object.entries(transport).map(([k, v]) => [k, Number(v)])),
      }
      setResult(await fpoBulkPlan(body))
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail
        : 'Check each farmer row: latitude, longitude, and a positive quantity are required.')
      setResult(null)
    }
  }

  return (
    <div className="max-w-4xl w-full">
      <PageHeader title="FPO Bulk Selling"
        subtitle="Pool members' harvest and see if trucking it together beats selling alone." />
      {error && <ErrorBanner message={error} />}
      {!crop && <p className="text-muted-foreground mb-3">Pick a crop above first.</p>}

      <div className="overflow-x-auto">
        <Table className="mb-3">
          <TableHeader>
            <TableRow>
              <TableHead>Lat</TableHead><TableHead>Lon</TableHead>
              <TableHead>State</TableHead><TableHead>Quantity (q)</TableHead><TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* key by index: rows are append/remove-by-position, no reordering */}
            {rows.map((r, i) => (
              <TableRow key={i}>
                <TableCell><Input className="w-24" value={r.lat} onChange={(e) => setRow(i, 'lat', e.target.value)} /></TableCell>
                <TableCell><Input className="w-24" value={r.lon} onChange={(e) => setRow(i, 'lon', e.target.value)} /></TableCell>
                <TableCell><Input className="w-28" value={r.state} onChange={(e) => setRow(i, 'state', e.target.value)} /></TableCell>
                <TableCell><Input className="w-24" value={r.quantity_q} onChange={(e) => setRow(i, 'quantity_q', e.target.value)} /></TableCell>
                <TableCell>{rows.length > 1 && <Button variant="ghost" size="sm" className="text-destructive" onClick={() => removeRow(i)}>✕</Button>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <Button variant="link" size="sm" className="px-0 mb-4" onClick={addRow}>+ Add farmer</Button>

      <div className="flex gap-3 flex-wrap mb-4 text-sm">
        {Object.keys(DEFAULT_TRANSPORT).map((k) => (
          <label key={k} className="capitalize text-foreground">{k.replace(/_/g, ' ')}
            <Input type="number" step="any" min="0" value={transport[k]} onChange={(e) => setT(k, e.target.value)} className="mt-1 w-32" />
          </label>
        ))}
      </div>

      <Button onClick={submit} disabled={!crop}>Compute plan</Button>

      {result && (
        <div className="mt-5">
          {result.price_basis !== 'mandi' ? (
            <Card className="border-accent/40 bg-accent/10">
              <CardContent className="p-4"><p>{result.message}</p></CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-4">
                {result.spread_warning && (
                  <p className="text-accent text-sm mb-2">⚠ {result.spread_warning}</p>
                )}
                <p className="text-lg mb-1">{result.message}</p>
                <ul className="text-sm text-foreground space-y-1 mt-2">
                  <li>Selling individually: <b>₹{result.baseline}</b></li>
                  <li>Pooled &amp; trucked{result.chosen_mandi ? ` to ${result.chosen_mandi.market}` : ''}: <b>₹{result.aggregated_rev}</b>
                    {result.chosen_mandi ? ` (${result.chosen_mandi.trucks} truck(s), ₹${result.chosen_mandi.transport_cost} transport)` : ''}</li>
                  <li className={result.extra_income > 0 ? 'text-primary font-semibold' : 'text-muted-foreground'}>
                    Extra income from pooling: ₹{result.extra_income}</li>
                </ul>
                <p className="text-xs text-muted-foreground mt-3">
                  Assumes the harvest is aggregated at a central collection point (the members' geographic centre); v1 does not plan multi-stop pickup routes.
                </p>
                {result.per_farmer?.length > 0 && (
                  <div className="overflow-x-auto mt-4">
                    <p className="text-sm font-medium text-foreground mb-1">If each member sold on their own:</p>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Member (lat, lon)</TableHead><TableHead>Qty (q)</TableHead>
                          <TableHead>Best market</TableHead><TableHead>Revenue ₹</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {result.per_farmer.map((f, i) => (
                          <TableRow key={i}>
                            <TableCell>{f.lat}, {f.lon}</TableCell>
                            <TableCell>{f.quantity_q}</TableCell>
                            <TableCell>{f.best_market ?? '—'}</TableCell>
                            <TableCell>₹{f.revenue}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
