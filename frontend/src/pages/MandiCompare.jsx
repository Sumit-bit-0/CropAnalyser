import { useState, useEffect } from 'react'
import { compareMandis } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'

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
      <h1 className="text-2xl font-bold text-green-800 mb-1">Mandi Comparison</h1>
      <p className="text-gray-600 mb-4">Nearest markets for your crop, with net price after transport.</p>
      {error && <ErrorBanner message={error} />}

      {!crop && <p className="text-gray-500">Pick a crop above to see market prices.</p>}

      {crop && (
        <label className="text-sm inline-block mb-4">Transport ₹/km/quintal
          <input type="number" step="any" value={rate} onChange={(e) => setRate(e.target.value)}
            className="mt-1 block w-28 border rounded px-2 py-2" />
        </label>
      )}

      {result?.source === 'state_fallback' && (
        <div className="border border-amber-300 bg-amber-50 rounded-lg p-4 mb-3">
          <p className="text-lg">State-level estimate for <b className="capitalize">{result.crop}</b> in {result.state}:{' '}
            <span className="font-bold text-green-700">₹{result.state_avg}/q</span></p>
          <p className="text-xs text-amber-700 mt-1">No live mandi data for this crop in your area — showing the state average instead.</p>
        </div>
      )}

      {result?.source === 'none' && (
        <p className="text-gray-500">No market or state price data for <b className="capitalize">{crop}</b>.</p>
      )}

      {result?.source === 'mandi' && (
        <>
          {coords ? (
            <p className="text-xs text-gray-500 mb-3">Using {area || district || 'your location'} ({coords.lat.toFixed(3)}, {coords.lon.toFixed(3)}). Markets ranked by distance.</p>
          ) : (
            <p className="text-xs text-gray-500 mb-3">Set a pincode or use GPS above to rank markets by distance.</p>
          )}
          {best && (
            <p className="text-lg mb-3">Best net price near you:{' '}
              <span className="font-bold text-green-700">{best.market}</span>{' '}
              — ₹{best.net_price}/q{best.distance_km != null ? ` after ~${best.distance_km} km` : ''}.</p>
          )}
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm border">
              <thead className="bg-green-50 text-left">
                <tr>
                  <th className="px-3 py-2">Market</th><th className="px-3 py-2">District</th>
                  <th className="px-3 py-2">Modal ₹/q</th><th className="px-3 py-2">Distance</th>
                  <th className="px-3 py-2">Transport ₹/q</th><th className="px-3 py-2">Net ₹/q</th>
                </tr>
              </thead>
              <tbody>
                {markets.map((r, i) => (
                  <tr key={i} className={r.is_best_net ? 'bg-green-100 font-medium' : 'border-t'}>
                    <td className="px-3 py-2">{r.market}</td>
                    <td className="px-3 py-2">{r.district}, {r.state}</td>
                    <td className="px-3 py-2">₹{r.modal_price}</td>
                    <td className="px-3 py-2">{r.distance_km != null ? `${r.distance_km} km` : '—'}</td>
                    <td className="px-3 py-2">₹{r.transport_per_q}</td>
                    <td className="px-3 py-2">₹{r.net_price}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
