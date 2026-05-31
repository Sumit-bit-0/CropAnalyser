import { useState, useEffect } from 'react'
import { getTrendFilters, recommendSmart } from '../api/client'
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
const MODULE_LABELS = { suitability: 'Soil/Climate', regional: 'Regional', market: 'Market' }
const MODULE_ORDER = ['suitability', 'regional', 'market']

export default function CropAdvisor() {
  const [states, setStates] = useState([])
  const [form, setForm] = useState({ state: 'Punjab', district: 'Ludhiana', season: 'Any', goal: '' })
  const [useSoil, setUseSoil] = useState(false)
  const [soil, setSoil] = useState(Object.fromEntries(SOIL_FIELDS.map(([k, , v]) => [k, v])))
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { getTrendFilters().then((d) => setStates(d.states)).catch(() => {}) }, [])

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
      <h1 className="text-2xl font-bold text-green-800 mb-1">Crop Advisor</h1>
      <p className="text-gray-600 mb-4">
        Pick the best crops for your field by combining regional history, market prices, and
        (optionally) your soil & climate. Add soil details for a sharper, agronomic match.
      </p>
      {error && <ErrorBanner message={error} />}

      <form onSubmit={submit} className="bg-white border rounded p-4 mb-6 space-y-3">
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
          Add soil &amp; climate details (Smart Mode)
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
          {loading ? 'Analyzing…' : 'Recommend crops'}
        </button>
      </form>

      {result && (
        <div>
          <p className="text-xs text-gray-500 mb-3">
            {isSmart ? 'Smart Mode' : 'Simple Mode'} · {result.method} fusion ·{' '}
            weights: {Object.entries(result.weights_used).map(([m, w]) =>
              `${MODULE_LABELS[m]} ${Math.round(w * 100)}%`).join(' · ')}
          </p>
          <div className="space-y-3">
            {result.recommendations.map((r, i) => (
              <div key={r.crop}
                className={`p-4 rounded border ${i === 0 ? 'border-green-500 bg-green-50' : 'border-gray-200'}`}>
                <div className="flex justify-between items-baseline mb-2">
                  <span className="font-bold capitalize text-green-800">
                    {i + 1}. {r.crop}
                  </span>
                  <span className="text-sm text-gray-500">match score {r.score}</span>
                </div>
                <div className="space-y-1 mb-2">
                  {MODULE_ORDER.filter((m) => m in r.breakdown).map((m) => (
                    <div key={m} className="flex items-center gap-2 text-xs text-gray-600">
                      <span className="w-24 shrink-0">{MODULE_LABELS[m]}</span>
                      <div className="flex-1 h-2 bg-gray-200 rounded">
                        <div className="h-2 bg-green-600 rounded"
                          style={{ width: `${Math.round(r.breakdown[m] * 100)}%` }} />
                      </div>
                      <span className="w-8 text-right">{Math.round(r.breakdown[m] * 100)}</span>
                    </div>
                  ))}
                </div>
                {r.why.map((w) => (
                  <p key={w} className="text-sm text-green-700">✓ {w}</p>
                ))}
                {r.cautions.map((c) => (
                  <p key={c} className="text-sm text-amber-600">! {c}</p>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
