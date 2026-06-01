import { useState, useEffect } from 'react'
import { getTrendFilters, recommendSmart, locateByGps } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'

const SEASONS = ['Any', 'Kharif', 'Rabi', 'Summer', 'Winter', 'Autumn', 'Whole Year']
const GOALS = [
  ['', 'Balanced'],
  ['max_profit', 'Max Profit'],
  ['low_risk', 'Low Risk'],
  ['sustainable', 'Sustainable'],
  ['water_efficient', 'Water Efficient'],
]
const SOIL_FIELDS = [
  ['N', 'Nitrogen (N)', 90], ['P', 'Phosphorus (P)', 42], ['K', 'Potassium (K)', 43],
  ['temperature', 'Temp (°C)', 26], ['humidity', 'Humidity (%)', 80],
  ['ph', 'Soil pH', 6.5], ['rainfall', 'Rainfall (mm)', 180],
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
  const [states, setStates] = useState([])
  const [form, setForm] = useState({ state: 'Punjab', district: 'Ludhiana', season: 'Any', goal: '' })
  const [useSoil, setUseSoil] = useState(false)
  const [soil, setSoil] = useState(Object.fromEntries(SOIL_FIELDS.map(([k, , v]) => [k, v])))
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [locating, setLocating] = useState(false)

  useEffect(() => { getTrendFilters().then((d) => setStates(d.states)).catch(() => {}) }, [])

  const useMyLocation = () => {
    if (!navigator.geolocation) { setError('Geolocation is not supported by this browser.'); return }
    setLocating(true); setError(null)
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const loc = await locateByGps(pos.coords.latitude, pos.coords.longitude)
          setForm((f) => ({
            ...f,
            state: states.find((s) => s.toLowerCase() === (loc.state || '').toLowerCase()) || f.state,
            district: loc.district || f.district,
          }))
        } catch { setError('Could not resolve your location.') }
        finally { setLocating(false) }
      },
      () => { setError('Location permission denied.'); setLocating(false) },
      { timeout: 8000 },
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    setError(null); setLoading(true)
    try {
      const body = { state: form.state, top_k: 5 }
      if (form.district.trim()) body.district = form.district.trim()
      if (form.season !== 'Any') body.season = form.season
      if (form.goal) body.goal = form.goal
      if (useSoil) body.soil = Object.fromEntries(Object.entries(soil).map(([k, v]) => [k, Number(v)]))
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
        Best crops for your field — combining regional history, market prices, and (optionally)
        your soil &amp; climate. Add soil details for a sharper agronomic match.
      </p>
      {error && <ErrorBanner message={error} />}

      <form onSubmit={submit} className="bg-white border rounded-lg p-4 mb-6 space-y-3 shadow-sm">
        <div className="flex justify-end">
          <button type="button" onClick={useMyLocation} disabled={locating}
            className="text-sm text-green-700 hover:text-green-900 disabled:opacity-50">
            📍 {locating ? 'Locating…' : 'Use my location'}
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <label className="text-sm text-gray-700">State
            <select value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })}
              className="mt-1 w-full border rounded px-2 py-2">
              {states.length === 0 && <option>{form.state}</option>}
              {states.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="text-sm text-gray-700">District
            <input value={form.district} placeholder="e.g. Ludhiana"
              onChange={(e) => setForm({ ...form, district: e.target.value })}
              className="mt-1 w-full border rounded px-2 py-2" />
          </label>
          <label className="text-sm text-gray-700">Season
            <select value={form.season} onChange={(e) => setForm({ ...form, season: e.target.value })}
              className="mt-1 w-full border rounded px-2 py-2">
              {SEASONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="text-sm text-gray-700">Goal
            <select value={form.goal} onChange={(e) => setForm({ ...form, goal: e.target.value })}
              className="mt-1 w-full border rounded px-2 py-2">
              {GOALS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={useSoil} onChange={(e) => setUseSoil(e.target.checked)} />
          Add soil &amp; climate details <span className="text-gray-400">(Smart Mode)</span>
        </label>
        {useSoil && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-1">
            {SOIL_FIELDS.map(([k, label]) => (
              <label key={k} className="text-sm text-gray-700">{label}
                <input type="number" step="any" value={soil[k]}
                  onChange={(e) => setSoil({ ...soil, [k]: e.target.value })}
                  className="mt-1 w-full border rounded px-2 py-2" />
              </label>
            ))}
          </div>
        )}

        <button disabled={loading}
          className="w-full bg-green-700 text-white rounded py-3 font-medium hover:bg-green-800 disabled:opacity-60">
          {loading ? 'Analyzing your field…' : 'Recommend crops'}
        </button>
      </form>

      {!result && !loading && (
        <div className="text-center text-gray-400 border border-dashed rounded-lg py-10">
          Set your location and goal, then hit <span className="font-medium text-gray-500">Recommend crops</span>.
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
                {r.why.map((w) => (
                  <p key={w} className="text-sm text-green-700">✓ {w}</p>
                ))}
                {r.cautions.map((c) => (
                  <p key={c} className="text-sm text-amber-600">⚠ {c}</p>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
