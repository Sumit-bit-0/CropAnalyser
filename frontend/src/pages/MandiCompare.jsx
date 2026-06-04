import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { compareMandis } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

export default function MandiCompare() {
  const { t } = useTranslation()
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
      <PageHeader title={t('pg.mandi.title')} subtitle={t('pg.mandi.subtitle')} />
      {error && <ErrorBanner message={error} />}

      {!crop && <p className="text-muted-foreground">{t('pg.mandi.pickCrop')}</p>}

      {crop && (
        <label className="text-sm inline-block mb-4 text-foreground">{t('pg.mandi.transport')}
          <Input type="number" step="any" value={rate} onChange={(e) => setRate(e.target.value)} className="mt-1 w-28" />
        </label>
      )}

      {result?.source === 'state_fallback' && (
        <Card className="border-accent/40 bg-accent/10 mb-3">
          <CardContent className="p-4">
            <p className="text-lg">State-level estimate for <b className="capitalize">{result.crop}</b> in {result.state}:{' '}
              <span className="font-bold text-primary">₹{result.state_avg}/q</span></p>
            <p className="text-xs text-accent mt-1">{t('pg.mandi.noLiveData')}</p>
          </CardContent>
        </Card>
      )}

      {result?.source === 'none' && (
        <p className="text-muted-foreground">{t('pg.mandi.noData')}</p>
      )}

      {result?.source === 'mandi' && (
        <>
          {coords ? (
            <p className="text-xs text-muted-foreground mb-3">Using {area || district || 'your location'} ({coords.lat.toFixed(3)}, {coords.lon.toFixed(3)}). Markets ranked by distance.</p>
          ) : (
            <p className="text-xs text-muted-foreground mb-3">{t('pg.mandi.setLoc')}</p>
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
                  <TableHead>{t('th.market')}</TableHead><TableHead>{t('th.district')}</TableHead>
                  <TableHead>{t('th.modalQ')}</TableHead><TableHead>{t('th.distance')}</TableHead>
                  <TableHead>{t('th.transportQ')}</TableHead><TableHead>{t('th.netQ')}</TableHead>
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
