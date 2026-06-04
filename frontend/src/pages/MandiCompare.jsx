import { useState, useEffect } from 'react'
import { compareMandis } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

export default function MandiCompare() {
  const { crop, state, lat, lon, area, district } = useWorkspace()
  const coords = lat != null && lon != null ? { lat, lon } : null
  const [rate, setRate] = useState(2)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!crop) { setResult(null); return }
    const params = { commodity: crop, top: 10 }
    if (state) params.state = state
    if (coords) { params.lat = coords.lat; params.lon = coords.lon; params.rate_per_km = Number(rate) }
    let live = true
    compareMandis(params)
      .then((r) => { if (live) { setResult(r); setError(null) } })
      .catch((err) => { if (live) { setError(err.response?.data?.detail || 'Comparison failed'); setResult(null) } })
    return () => { live = false }
  }, [crop, state, lat, lon, rate])

  const markets = result?.markets || []
  const best = markets.find((r) => r.is_best_net)

  return (
    <div className="max-w-4xl w-full">
      <PageHeader title="Mandi Comparison" subtitle="Nearest markets for your crop, with net price after transport." />
      {error && <ErrorBanner message={error} />}

      {!crop && <p className="text-muted-foreground">Pick a crop above to see market prices.</p>}

      {crop && (
        <label className="text-sm inline-block mb-4 text-foreground">Transport ₹/km/quintal
          <Input type="number" step="any" value={rate} onChange={(e) => setRate(e.target.value)} className="mt-1 w-28" />
        </label>
      )}

      {result?.source === 'state_fallback' && (
        <Card className="border-accent/40 bg-accent/10 mb-3">
          <CardContent className="p-4">
            <p className="text-lg">State-level estimate for <b className="capitalize">{result.crop}</b> in {result.state}:{' '}
              <span className="font-bold text-primary">₹{result.state_avg}/q</span></p>
            <p className="text-xs text-accent mt-1">No live mandi data for this crop in your area — showing the state average instead.</p>
          </CardContent>
        </Card>
      )}

      {result?.source === 'none' && (
        <p className="text-muted-foreground">No market or state price data for <b className="capitalize">{crop}</b>.</p>
      )}

      {result?.source === 'mandi' && (
        <>
          {coords ? (
            <p className="text-xs text-muted-foreground mb-3">Using {area || district || 'your location'} ({coords.lat.toFixed(3)}, {coords.lon.toFixed(3)}). Markets ranked by distance.</p>
          ) : (
            <p className="text-xs text-muted-foreground mb-3">Set a pincode or use GPS above to rank markets by distance.</p>
          )}
          {best && (
            <p className="text-lg mb-3">Best net price near you:{' '}
              <span className="font-bold text-primary">{best.market}</span>{' '}
              — ₹{best.net_price}/q{best.distance_km != null ? ` after ~${best.distance_km} km` : ''}.</p>
          )}
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Market</TableHead><TableHead>District</TableHead>
                  <TableHead>Modal ₹/q</TableHead><TableHead>Distance</TableHead>
                  <TableHead>Transport ₹/q</TableHead><TableHead>Net ₹/q</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {markets.map((r, i) => (
                  <TableRow key={i} className={r.is_best_net ? 'bg-primary/5 font-medium' : ''}>
                    <TableCell className={r.is_best_net ? 'text-primary font-medium' : ''}>{r.market}</TableCell>
                    <TableCell>{r.district}, {r.state}</TableCell>
                    <TableCell className="tabular-nums">₹{r.modal_price}</TableCell>
                    <TableCell className="tabular-nums text-muted-foreground">{r.distance_km != null ? `${r.distance_km} km` : '—'}</TableCell>
                    <TableCell className="tabular-nums text-muted-foreground">−₹{r.transport_per_q}</TableCell>
                    <TableCell className={`tabular-nums font-semibold ${r.is_best_net ? 'text-primary' : 'text-accent'}`}>₹{r.net_price}</TableCell>
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
