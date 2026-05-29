import { useState, useEffect } from 'react'
import { getMandiCommodities, compareMandis } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'

export default function MandiCompare() {
  const [commodities, setCommodities] = useState([])
  const [commodity, setCommodity] = useState('')
  const [coords, setCoords] = useState(null)
  const [rate, setRate] = useState(2)
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)
  const [locMsg, setLocMsg] = useState('')

  useEffect(() => { getMandiCommodities().then(setCommodities).catch(() => {}) }, [])

  const useLocation = () => {
    if (!navigator.geolocation) { setLocMsg('Geolocation not supported on this device.'); return }
    setLocMsg('Getting your location…')
    navigator.geolocation.getCurrentPosition(
      (pos) => { setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }); setLocMsg('') },
      () => setLocMsg('Location permission denied — showing markets by price instead.'),
    )
  }

  const compare = async (e) => {
    e?.preventDefault()
    setError(null)
    if (!commodity) { setError('Please pick a commodity.'); return }
    try {
      const params = { commodity, top: 10 }
      if (coords) { params.lat = coords.lat; params.lon = coords.lon; params.rate_per_km = Number(rate) }
      setRows(await compareMandis(params))
    } catch (err) {
      setError(err.response?.data?.detail || 'Comparison failed'); setRows(null)
    }
  }

  const best = rows?.find((r) => r.is_best_net)

  return (
    <div className="max-w-4xl w-full">
      <h1 className="text-2xl font-bold text-green-800 mb-1">Mandi Comparison</h1>
      <p className="text-gray-600 mb-4">Find the nearest markets for your crop and compare net price after transport.</p>
      {error && <ErrorBanner message={error} />}

      <form onSubmit={compare} className="flex flex-wrap gap-2 items-end mb-4">
        <label className="text-sm">Commodity
          <select className="mt-1 block border rounded px-2 py-2" value={commodity} onChange={(e) => setCommodity(e.target.value)}>
            <option value="">—</option>{commodities.map((c) => <option key={c}>{c}</option>)}
          </select></label>
        <label className="text-sm">Transport ₹/km/quintal
          <input type="number" step="any" value={rate} onChange={(e) => setRate(e.target.value)}
            className="mt-1 block w-28 border rounded px-2 py-2" /></label>
        <button type="button" onClick={useLocation} className="bg-green-700 text-white rounded px-3 py-2 text-sm">📍 Use my location</button>
        <button className="bg-green-800 text-white rounded px-4 py-2 text-sm font-medium">Compare</button>
      </form>
      {(locMsg || coords) && (
        <p className="text-xs text-gray-500 mb-3">
          {coords ? `Using your location (${coords.lat.toFixed(3)}, ${coords.lon.toFixed(3)}). Markets ranked by distance.` : locMsg}
        </p>
      )}

      {best && (
        <p className="text-lg mb-3">Best net price near you:{' '}
          <span className="font-bold text-green-700">{best.market}</span>{' '}
          — ₹{best.net_price}/q{best.distance_km != null ? ` after ~${best.distance_km} km` : ''}.</p>
      )}

      {rows && rows.length > 0 && (
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
              {rows.map((r, i) => (
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
      )}
      {rows && rows.length === 0 && <p className="text-gray-500">No market data for that crop.</p>}
    </div>
  )
}
