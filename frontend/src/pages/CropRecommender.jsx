import { useState } from 'react'
import { recommendCrop } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'

const FIELDS = [
  ['N', 'Nitrogen (N)', 90], ['P', 'Phosphorus (P)', 42], ['K', 'Potassium (K)', 43],
  ['temperature', 'Temperature (°C)', 21], ['humidity', 'Humidity (%)', 82],
  ['ph', 'Soil pH', 6.5], ['rainfall', 'Rainfall (mm)', 203],
]

export default function CropRecommender() {
  const [form, setForm] = useState(Object.fromEntries(FIELDS.map(([k, , v]) => [k, v])))
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, Number(v)]))
      setResult(await recommendCrop(body))
    } catch (err) {
      setError(err.response?.data?.detail || 'Recommendation failed')
      setResult(null)
    }
  }

  return (
    <div className="max-w-3xl w-full">
      <h1 className="text-2xl font-bold text-green-800 mb-1">Crop Advisor</h1>
      <p className="text-gray-600 mb-4">Enter your soil and climate values to find the best crops to grow.</p>
      {error && <ErrorBanner message={error} />}
      <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {FIELDS.map(([k, label]) => (
          <label key={k} className="text-sm text-gray-700">
            {label}
            <input type="number" step="any" value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              className="mt-1 w-full border rounded px-2 py-2" />
          </label>
        ))}
        <button className="col-span-2 md:col-span-4 bg-green-700 text-white rounded py-3 font-medium hover:bg-green-800">
          Recommend crops
        </button>
      </form>
      {result && (
        <div>
          <p className="text-lg mb-3">Best pick for your soil:{' '}
            <span className="font-bold text-green-700 capitalize">{result.top.crop}</span>{' '}
            ({result.top.confidence_pct}% match)</p>
          <div className="space-y-2">
            {result.recommendations.map((r, i) => (
              <div key={r.crop} className={`p-3 rounded border ${i === 0 ? 'border-green-500 bg-green-50' : 'border-gray-200'}`}>
                <div className="flex justify-between text-sm font-medium">
                  <span className="capitalize">{r.crop}</span><span>{r.confidence_pct}%</span>
                </div>
                <div className="h-2 bg-gray-200 rounded mt-1">
                  <div className="h-2 bg-green-600 rounded" style={{ width: `${r.confidence_pct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
