import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { planProfit, getPriceReference, getTrendFilters } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const RISK_COLOR = { low: 'bg-primary/15 text-primary', medium: 'bg-accent/15 text-accent',
                     high: 'bg-destructive/15 text-destructive', unknown: 'bg-muted text-muted-foreground' }
const NUM = ['area_acres', 'yield_q_per_acre', 'input_cost', 'labour_cost', 'transport_cost', 'market_price']
const FIELD_KEYS = { area_acres: 'pg.profit.fieldArea', yield_q_per_acre: 'pg.profit.fieldYield',
  input_cost: 'pg.profit.fieldInput', labour_cost: 'pg.profit.fieldLabour', transport_cost: 'pg.profit.fieldTransport',
  market_price: 'pg.profit.fieldMarketPrice' }

export default function ProfitPlanner() {
  const { t } = useTranslation()
  const { state, crop, setCrop } = useWorkspace()
  const [filters, setFilters] = useState({ states: [], commodities: [] })
  const commodity = crop
  const setCommodity = setCrop
  const [ref, setRef] = useState(null)
  const [form, setForm] = useState({ area_acres: 2, yield_q_per_acre: 20, input_cost: 10000,
    labour_cost: 5000, transport_cost: 3000, market_price: 1500 })
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => { getTrendFilters().then(setFilters).catch(() => {}) }, [])

  const loadPrice = async () => {
    if (!state || !commodity) return
    const r = await getPriceReference(state, commodity)
    setRef(r)
    if (r.latest_price) setForm((f) => ({ ...f, market_price: r.latest_price }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const body = Object.fromEntries(NUM.map((k) => [k, Number(form[k])]))
      setResult(await planProfit(body))
    } catch (err) {
      setError(err.response?.data?.detail || 'Calculation failed'); setResult(null)
    }
  }

  return (
    <div className="max-w-3xl w-full">
      <PageHeader title={t('pg.profit.title')} subtitle={t('pg.profit.subtitle')} />
      {error && <ErrorBanner message={error} />}

      <div className="flex flex-wrap gap-2 items-end mb-4">
        <label className="text-sm text-foreground">{t('pg.profit.commodity')}
          <Select value={commodity || ''} onValueChange={setCommodity}>
            <SelectTrigger className="mt-1 w-48"><SelectValue placeholder="—" /></SelectTrigger>
            <SelectContent>{filters.commodities.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
          </Select>
        </label>
        <Button type="button" variant="outline" size="sm" onClick={loadPrice}>{t('pg.profit.useMarketPrice')}</Button>
        {ref && (
          <span className={`text-xs px-2 py-1 rounded ${RISK_COLOR[ref.risk_level]}`}>
            Price risk: {ref.risk_level}{ref.latest_price ? ` (latest ₹${ref.latest_price}/q)` : ''}
          </span>
        )}
      </div>

      <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
        {NUM.map((k) => (
          <label key={k} className="text-sm text-foreground">{t(FIELD_KEYS[k])}
            <Input type="number" step="any" value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })} className="mt-1 w-full" /></label>
        ))}
        <Button className="col-span-2 md:col-span-3" size="lg">{t('pg.profit.calculate')}</Button>
      </form>

      {result && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <p className={`text-2xl font-bold ${result.profit >= 0 ? 'text-primary' : 'text-destructive'}`}>
              {result.profit >= 0 ? t('pg.profit.profit') : t('pg.profit.loss')}: ₹{Math.abs(result.profit).toLocaleString('en-IN')}
            </p>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <span>{t('pg.profit.revenue')}: ₹{result.total_revenue.toLocaleString('en-IN')}</span>
              <span>{t('pg.profit.totalCost')}: ₹{result.total_cost.toLocaleString('en-IN')}</span>
              <span>{t('pg.profit.breakEven')}: {result.break_even_price ? `₹${result.break_even_price}/q` : '—'}</span>
              <span>{t('pg.profit.targetPrice')}: {result.target_sale_price ? `₹${result.target_sale_price}/q` : '—'}</span>
            </div>
            <p className="text-foreground bg-muted rounded p-2">{result.recommendation}</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
