import { useState } from 'react'
import { recommendSmart } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'

const GOALS = [
  ['', 'Balanced'], ['max_profit', 'Max Profit'], ['low_risk', 'Low Risk'],
  ['sustainable', 'Sustainable'], ['water_efficient', 'Water Efficient'],
]
const MODULES = [
  ['suitability', 'Soil/Climate', 'bg-emerald-500'],
  ['regional', 'Regional', 'bg-sky-500'],
  ['market', 'Market', 'bg-amber-500'],
  ['weather', 'Weather', 'bg-cyan-500'],
]
const RANK_BADGE = ['bg-green-600', 'bg-green-500', 'bg-green-400', 'bg-gray-400', 'bg-gray-400']
const TREND = { rising: '↗', flat: '→', falling: '↘' }
const trendColor = (t) => (t === 'rising' ? 'text-green-600' : t === 'falling' ? 'text-red-500' : 'text-gray-400')

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
      <h1 className="text-2xl font-bold text-green-800 mb-1">🌱 Crop Advisor</h1>
      <p className="text-gray-600 mb-4">
        Best crops for your field — regional history, market prices, and live seasonal
        weather. Switch to Smart mode and add soil details for a sharper agronomic match.
      </p>
      {error && <ErrorBanner message={error} />}

      <form onSubmit={submit} className="bg-white border rounded-lg p-4 mb-6 flex flex-wrap items-end gap-3 shadow-sm">
        <label className="text-sm text-gray-700">Goal
          <select value={goal} onChange={(e) => setGoal(e.target.value)}
            className="mt-1 block w-44 border rounded px-2 py-2">
            {GOALS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <button disabled={loading}
          className="bg-green-700 text-white rounded px-5 py-3 font-medium hover:bg-green-800 disabled:opacity-60">
          {loading ? 'Analyzing…' : 'Recommend crops'}
        </button>
        {mode !== 'smart' && (
          <span className="text-xs text-gray-400">Simple Mode · turn on Smart for soil suitability</span>
        )}
      </form>

      {!result && !loading && (
        <div className="text-center text-gray-400 border border-dashed rounded-lg py-10">
          Set your location above, then hit <span className="font-medium text-gray-500">Recommend crops</span>.
        </div>
      )}

      {result && (
        <div>
          <p className="text-xs text-gray-500 mb-3">
            <span className={`inline-block px-2 py-0.5 rounded-full mr-2 ${isSmart ? 'bg-emerald-100 text-emerald-700' : 'bg-sky-100 text-sky-700'}`}>
              {isSmart ? 'Smart Mode' : 'Simple Mode'}
            </span>
            {result.method} fusion ·{' '}
            {Object.entries(result.weights_used).map(([m, w]) =>
              `${MODULES.find((x) => x[0] === m)?.[1] || m} ${Math.round(w * 100)}%`).join(' · ')}
          </p>
          <div className="space-y-3">
            {result.recommendations.map((r, i) => (
              <div key={r.crop}
                className={`p-4 rounded-lg border shadow-sm ${i === 0 ? 'border-green-500 bg-green-50' : 'border-gray-200 bg-white'}`}>
                <div className="flex items-center gap-3 mb-3">
                  <span className={`flex items-center justify-center w-7 h-7 rounded-full text-white text-sm font-bold ${RANK_BADGE[i] || 'bg-gray-400'}`}>
                    {i + 1}
                  </span>
                  <span className="font-bold capitalize text-green-800 text-lg">{r.crop}</span>
                  {i === 0 && <span className="text-xs bg-green-600 text-white px-2 py-0.5 rounded-full">Best pick</span>}
                  <span className="ml-auto text-xs text-gray-400">match {r.score}</span>
                </div>
                <button type="button" onClick={() => setCrop(r.crop)}
                  className="text-xs text-green-700 hover:text-green-900 underline mb-2">
                  See market &amp; prices for {r.crop} →
                </button>
                {r.traditional?.years_grown > 0 && (
                  <p className="text-sm text-green-800 font-medium mb-1">
                    ✓ Traditional here — grown {r.traditional.years_grown} yr
                    {r.traditional.years_grown > 1 ? 's' : ''} on record
                    {r.traditional.level === 'state' && ' (state-wide)'}
                  </p>
                )}
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-700 mb-2">
                  {r.yield?.predicted_yield != null ? (
                    <span>
                      Predicted yield: <b>~{r.yield.predicted_yield} {r.yield.unit}</b>{' '}
                      <span className={trendColor(r.yield.trend)}>{TREND[r.yield.trend]}</span>
                      {r.yield.traditional_yield != null &&
                        <span className="text-gray-400"> (was ~{r.yield.traditional_yield})</span>}
                    </span>
                  ) : (
                    <span className="text-gray-400">No reliable yield estimate</span>
                  )}
                  {r.price_outlook?.price != null && (
                    <span>
                      Price outlook: <b>₹{r.price_outlook.price}/q</b>{' '}
                      <span className={trendColor(r.price_outlook.trend)}>{TREND[r.price_outlook.trend]}</span>
                      <span className="text-gray-400 text-xs">
                        {' '}{r.price_outlook.source === 'forecast' ? '(forecast)' : '(recent)'}
                      </span>
                    </span>
                  )}
                </div>
                <div className="space-y-1 mb-3 opacity-70">
                  {MODULES.filter(([m]) => m in r.breakdown).map(([m, label, color]) => (
                    <div key={m} className="flex items-center gap-2 text-xs text-gray-600">
                      <span className="w-24 shrink-0">{label}</span>
                      <div className="flex-1 h-2.5 bg-gray-200 rounded-full overflow-hidden">
                        <div className={`h-2.5 rounded-full ${color}`}
                          style={{ width: `${Math.round(r.breakdown[m] * 100)}%` }} />
                      </div>
                      <span className="w-8 text-right tabular-nums">{Math.round(r.breakdown[m] * 100)}</span>
                    </div>
                  ))}
                </div>
                {r.why.map((w) => <p key={w} className="text-sm text-green-700">✓ {w}</p>)}
                {r.cautions.map((c) => <p key={c} className="text-sm text-amber-600">⚠ {c}</p>)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
