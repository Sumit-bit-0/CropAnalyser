import { useState } from 'react'
import { recommendCrop } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import { DEFAULT_SOIL } from '../workspace/SoilPanel'
import ErrorBanner from '../components/ErrorBanner'

export default function CropRecommender() {
  const { mode, soil, setMode } = useWorkspace()
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      setResult(await recommendCrop(soil || DEFAULT_SOIL))
    } catch (err) {
      setError(err.response?.data?.detail || 'Recommendation failed'); setResult(null)
    }
  }

  return (
    <div className="max-w-3xl w-full">
      <h1 className="text-2xl font-bold text-green-800 mb-1">Soil Match</h1>
      <p className="text-gray-600 mb-4">
        Pure soil/climate model: enter your soil values in the <b>Soil details</b> panel
        (Smart mode) above, then match the best crops.
      </p>
      {error && <ErrorBanner message={error} />}

      {mode !== 'smart' ? (
        <div className="border border-dashed rounded-lg p-6 text-center text-gray-500">
          Turn on <b>Smart</b> mode (top-right) to enter soil details, then come back here.
          <div className="mt-3">
            <button onClick={() => setMode('smart')}
              className="bg-green-700 text-white rounded px-4 py-2 text-sm">Switch to Smart</button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="mb-6">
          <button className="bg-green-700 text-white rounded px-5 py-3 font-medium hover:bg-green-800">
            Match crops {soil ? '' : '(using defaults — fill Soil details for accuracy)'}
          </button>
        </form>
      )}

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
