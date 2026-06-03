import { useState, useEffect } from 'react'
import { fpoBulkPlan } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'

const DEFAULT_TRANSPORT = {
  truck_capacity_q: 100, fixed_hire_per_truck: 2000,
  per_km_per_truck: 30, per_q_local_rate: 2,
}

export default function FpoBulkDashboard() {
  const { crop, state, lat, lon } = useWorkspace()
  const firstRow = {
    lat: lat ?? '', lon: lon ?? '', state: state || '', quantity_q: '',
  }
  const [rows, setRows] = useState([firstRow])
  const [transport, setTransport] = useState(DEFAULT_TRANSPORT)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setRows((rs) => {
      const [first, ...rest] = rs
      if (first.lat === '' && first.lon === '' && (lat != null || lon != null)) {
        return [{ ...first, lat: lat ?? '', lon: lon ?? '', state: first.state || state || '' }, ...rest]
      }
      return rs
    })
  }, [lat, lon, state])

  const setRow = (i, key, val) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [key]: val } : r)))
  const addRow = () => setRows((rs) => [...rs, { lat: '', lon: '', state: state || '', quantity_q: '' }])
  const removeRow = (i) => setRows((rs) => rs.filter((_, j) => j !== i))
  const setT = (key, val) => setTransport((t) => ({ ...t, [key]: val }))

  const submit = async () => {
    setError(null)
    const invalid = rows.some((r) => r.lat === '' || r.lon === '' || !(Number(r.quantity_q) > 0))
    if (invalid) {
      setError('Each farmer row needs latitude, longitude, and a positive quantity.')
      setResult(null)
      return
    }
    try {
      const farmers = rows.map((r) => ({
        lat: Number(r.lat), lon: Number(r.lon),
        state: r.state || null, quantity_q: Number(r.quantity_q),
      }))
      const body = {
        crop,
        farmers,
        transport: Object.fromEntries(
          Object.entries(transport).map(([k, v]) => [k, Number(v)])),
      }
      setResult(await fpoBulkPlan(body))
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail
        : 'Check each farmer row: latitude, longitude, and a positive quantity are required.')
      setResult(null)
    }
  }

  return (
    <div className="max-w-4xl w-full">
      <h1 className="text-2xl font-bold text-green-800 mb-1">FPO Bulk Selling</h1>
      <p className="text-gray-600 mb-4">
        Pool members' harvest and see if trucking it together beats selling alone.
      </p>
      {error && <ErrorBanner message={error} />}
      {!crop && <p className="text-gray-500 mb-3">Pick a crop above first.</p>}

      <div className="overflow-x-auto">
      <table className="min-w-full text-sm border mb-3">
        <thead className="bg-green-50 text-left">
          <tr>
            <th className="px-2 py-2">Lat</th><th className="px-2 py-2">Lon</th>
            <th className="px-2 py-2">State</th><th className="px-2 py-2">Quantity (q)</th>
            <th className="px-2 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {/* key by index: rows are append/remove-by-position, no reordering */}
          {rows.map((r, i) => (
            <tr key={i} className="border-t">
              <td className="px-2 py-1"><input className="w-24 border rounded px-1 py-1" value={r.lat} onChange={(e) => setRow(i, 'lat', e.target.value)} /></td>
              <td className="px-2 py-1"><input className="w-24 border rounded px-1 py-1" value={r.lon} onChange={(e) => setRow(i, 'lon', e.target.value)} /></td>
              <td className="px-2 py-1"><input className="w-28 border rounded px-1 py-1" value={r.state} onChange={(e) => setRow(i, 'state', e.target.value)} /></td>
              <td className="px-2 py-1"><input className="w-24 border rounded px-1 py-1" value={r.quantity_q} onChange={(e) => setRow(i, 'quantity_q', e.target.value)} /></td>
              <td className="px-2 py-1">{rows.length > 1 && <button onClick={() => removeRow(i)} className="text-red-600">✕</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      <button onClick={addRow} className="text-green-700 text-sm mb-4">+ Add farmer</button>

      <div className="flex gap-3 flex-wrap mb-4 text-sm">
        {Object.keys(DEFAULT_TRANSPORT).map((k) => (
          <label key={k} className="capitalize">{k.replace(/_/g, ' ')}
            <input type="number" step="any" min="0" value={transport[k]} onChange={(e) => setT(k, e.target.value)}
              className="mt-1 block w-32 border rounded px-2 py-1" />
          </label>
        ))}
      </div>

      <button onClick={submit} disabled={!crop}
        className="bg-green-700 text-white px-4 py-2 rounded disabled:opacity-50">
        Compute plan
      </button>

      {result && (
        <div className="mt-5">
          {result.price_basis !== 'mandi' ? (
            <div className="border border-amber-300 bg-amber-50 rounded-lg p-4">
              <p>{result.message}</p>
            </div>
          ) : (
            <div className="border rounded-lg p-4">
              {result.spread_warning && (
                <p className="text-amber-700 text-sm mb-2">⚠ {result.spread_warning}</p>
              )}
              <p className="text-lg mb-1">{result.message}</p>
              <ul className="text-sm text-gray-700 space-y-1 mt-2">
                <li>Selling individually: <b>₹{result.baseline}</b></li>
                <li>Pooled &amp; trucked{result.chosen_mandi ? ` to ${result.chosen_mandi.market}` : ''}: <b>₹{result.aggregated_rev}</b>
                  {result.chosen_mandi ? ` (${result.chosen_mandi.trucks} truck(s), ₹${result.chosen_mandi.transport_cost} transport)` : ''}</li>
                <li className={result.extra_income > 0 ? 'text-green-700 font-semibold' : 'text-gray-600'}>
                  Extra income from pooling: ₹{result.extra_income}</li>
              </ul>
              <p className="text-xs text-gray-500 mt-3">
                Assumes the harvest is aggregated at a central collection point (the members' geographic centre); v1 does not plan multi-stop pickup routes.
              </p>
              {result.per_farmer?.length > 0 && (
                <div className="overflow-x-auto mt-4">
                  <p className="text-sm font-medium text-gray-700 mb-1">If each member sold on their own:</p>
                  <table className="min-w-full text-sm border">
                    <thead className="bg-green-50 text-left">
                      <tr>
                        <th className="px-2 py-1">Member (lat, lon)</th>
                        <th className="px-2 py-1">Qty (q)</th>
                        <th className="px-2 py-1">Best market</th>
                        <th className="px-2 py-1">Revenue ₹</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.per_farmer.map((f, i) => (
                        <tr key={i} className="border-t">
                          <td className="px-2 py-1">{f.lat}, {f.lon}</td>
                          <td className="px-2 py-1">{f.quantity_q}</td>
                          <td className="px-2 py-1">{f.best_market ?? '—'}</td>
                          <td className="px-2 py-1">₹{f.revenue}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
