import { useState } from 'react'
import { motion } from 'framer-motion'
import { recommendSmart } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { MODULE_COLORS } from '@/lib/chartColors'

const GOALS = [
  ['', 'Balanced'], ['max_profit', 'Max Profit'], ['low_risk', 'Low Risk'],
  ['sustainable', 'Sustainable'], ['water_efficient', 'Water Efficient'],
]
const MODULES = [
  ['suitability', 'Soil/Climate'], ['regional', 'Regional'],
  ['market', 'Market'], ['weather', 'Weather'],
]
const TREND = { rising: '↗', flat: '→', falling: '↘' }
const trendColor = (t) => (t === 'rising' ? 'text-primary' : t === 'falling' ? 'text-destructive' : 'text-muted-foreground')

export default function CropAdvisor() {
  const { state, district, season, lat, lon, mode, soil, setCrop } = useWorkspace()
  const [goal, setGoal] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(null); setLoading(true)
    try {
      const body = { state, top_k: 5 }
      if (district?.trim()) body.district = district.trim()
      if (season && season !== 'Any') body.season = season
      if (goal) body.goal = goal
      if (lat != null && lon != null) { body.lat = lat; body.lon = lon }
      if (mode === 'smart' && soil) body.soil = soil
      setResult(await recommendSmart(body))
    } catch (err) {
      setError(err.response?.data?.detail || 'Recommendation failed'); setResult(null)
    } finally { setLoading(false) }
  }

  const isSmart = result?.modules_used?.includes('suitability')

  return (
    <div className="max-w-3xl w-full">
      <PageHeader title="🌱 Crop Advisor"
        subtitle="Best crops for your field — regional history, market prices, and live seasonal weather. Switch to Smart mode and add soil details for a sharper agronomic match." />
      {error && <ErrorBanner message={error} />}

      <Card className="mb-6">
        <CardContent className="p-4 flex flex-wrap items-end gap-3">
          <label className="text-sm text-foreground">Goal
            <Select value={goal || 'balanced'} onValueChange={(v) => setGoal(v === 'balanced' ? '' : v)}>
              <SelectTrigger className="mt-1 w-44"><SelectValue placeholder="Balanced" /></SelectTrigger>
              <SelectContent>
                {GOALS.map(([v, l]) => <SelectItem key={v || 'balanced'} value={v || 'balanced'}>{l}</SelectItem>)}
              </SelectContent>
            </Select>
          </label>
          <Button onClick={submit} disabled={loading} size="lg">
            {loading ? 'Analyzing…' : 'Recommend crops'}
          </Button>
          {mode !== 'smart' && (
            <span className="text-xs text-muted-foreground">Simple Mode · turn on Smart for soil suitability</span>
          )}
        </CardContent>
      </Card>

      {!result && !loading && (
        <div className="text-center text-muted-foreground border border-dashed border-border rounded-lg py-10">
          Set your location above, then hit <span className="font-medium text-foreground">Recommend crops</span>.
        </div>
      )}

      {result && (
        <div>
          <p className="text-xs text-muted-foreground mb-3 flex items-center gap-2 flex-wrap">
            <Badge variant={isSmart ? 'default' : 'secondary'}>{isSmart ? 'Smart Mode' : 'Simple Mode'}</Badge>
            <span>{result.method} fusion ·{' '}
            {Object.entries(result.weights_used).map(([m, w]) =>
              `${MODULES.find((x) => x[0] === m)?.[1] || m} ${Math.round(w * 100)}%`).join(' · ')}</span>
          </p>
          <div className="space-y-3">
            {result.recommendations.map((r, i) => (
              <motion.div key={r.crop}
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05, duration: 0.2 }}>
              <Card className={i === 0 ? 'border-primary bg-secondary' : ''}>
                <CardContent className="p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-primary-foreground text-sm font-bold">
                      {i + 1}
                    </span>
                    <span className="font-bold capitalize text-foreground text-lg">{r.crop}</span>
                    {i === 0 && <Badge>Best pick</Badge>}
                    <span className="ml-auto text-xs text-muted-foreground">match {r.score}</span>
                  </div>
                  <Button type="button" variant="link" size="sm" className="px-0 h-auto mb-2"
                    onClick={() => setCrop(r.crop)}>
                    See market &amp; prices for {r.crop} →
                  </Button>
                  {r.traditional?.years_grown > 0 && (
                    <p className="text-sm text-primary font-medium mb-1">
                      ✓ Traditional here — grown {r.traditional.years_grown} yr
                      {r.traditional.years_grown > 1 ? 's' : ''} on record
                      {r.traditional.level === 'state' && ' (state-wide)'}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-foreground mb-2">
                    {r.yield?.predicted_yield != null ? (
                      <span>
                        Predicted yield: <b>~{r.yield.predicted_yield} {r.yield.unit}</b>{' '}
                        <span className={trendColor(r.yield.trend)}>{TREND[r.yield.trend]}</span>
                        {r.yield.traditional_yield != null &&
                          <span className="text-muted-foreground"> (was ~{r.yield.traditional_yield})</span>}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">No reliable yield estimate</span>
                    )}
                    {r.price_outlook?.price != null && (
                      <span>
                        Price outlook: <b>₹{r.price_outlook.price}/q</b>{' '}
                        <span className={trendColor(r.price_outlook.trend)}>{TREND[r.price_outlook.trend]}</span>
                        <span className="text-muted-foreground text-xs">
                          {' '}{r.price_outlook.source === 'forecast' ? '(forecast)' : '(recent)'}
                        </span>
                      </span>
                    )}
                  </div>
                  <div className="space-y-1 mb-3 opacity-80">
                    {MODULES.filter(([m]) => m in r.breakdown).map(([m, label]) => (
                      <div key={m} className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="w-24 shrink-0">{label}</span>
                        <div className="flex-1 h-2.5 bg-muted rounded-full overflow-hidden">
                          <div className="h-2.5 rounded-full"
                            style={{ width: `${Math.round(r.breakdown[m] * 100)}%`, backgroundColor: MODULE_COLORS[m] }} />
                        </div>
                        <span className="w-8 text-right tabular-nums">{Math.round(r.breakdown[m] * 100)}</span>
                      </div>
                    ))}
                  </div>
                  {r.why.map((w) => <p key={w} className="text-sm text-primary">✓ {w}</p>)}
                  {r.cautions.map((c) => <p key={c} className="text-sm text-accent">⚠ {c}</p>)}
                </CardContent>
              </Card>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
