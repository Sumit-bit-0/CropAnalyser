import { useState } from 'react'
import { useWorkspace } from './WorkspaceContext'
import { resolvePincode, locateByGps } from '../api/client'

export default function LocationPicker({ states }) {
  const { state, district, area, pincode, setLocation } = useWorkspace()
  const [tab, setTab] = useState('pincode')   // 'pincode' | 'manual'
  const [pin, setPin] = useState(pincode || '')
  const [status, setStatus] = useState(null)  // {ok} | {err}
  const [busy, setBusy] = useState(false)

  const applyResolved = (r, fallbackCoords) => {
    setLocation({
      state: r.state, district: r.district, area: r.area || '',
      pincode: r.pincode || '',
      lat: r.lat ?? fallbackCoords?.lat ?? null,
      lon: r.lon ?? fallbackCoords?.lon ?? null,
    })
    setStatus({ ok: `${r.area || r.district || ''}, ${r.state}` })
  }

  const lookupPin = async () => {
    if (!/^\d{6}$/.test(pin)) { setStatus({ err: 'Enter a 6-digit pincode' }); return }
    setBusy(true); setStatus(null)
    try { applyResolved(await resolvePincode(pin)) }
    catch { setStatus({ err: "Couldn't find that PIN — pick your district" }) }
    finally { setBusy(false) }
  }

  const useGps = () => {
    if (!navigator.geolocation) { setStatus({ err: 'Geolocation not supported' }); return }
    setBusy(true); setStatus(null)
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const fallback = { lat: pos.coords.latitude, lon: pos.coords.longitude }
        try {
          const r = await locateByGps(fallback.lat, fallback.lon)
          setPin(r.pincode || '')
          applyResolved(r, fallback)
        } catch { setStatus({ err: 'Could not resolve your location' }) }
        finally { setBusy(false) }
      },
      () => { setStatus({ err: 'Location permission denied' }); setBusy(false) },
      { timeout: 8000 },
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex gap-1 text-xs">
          {['pincode', 'manual'].map((t) => (
            <button key={t} type="button" onClick={() => setTab(t)}
              className={`px-2 py-1 rounded ${tab === t ? 'bg-green-700 text-white' : 'bg-gray-100 text-gray-600'}`}>
              {t === 'pincode' ? 'Pincode' : 'State / District'}
            </button>
          ))}
        </div>

        {tab === 'pincode' ? (
          <>
            <label className="text-sm text-gray-700">Pincode
              <input value={pin} inputMode="numeric" maxLength={6} placeholder="e.g. 851101"
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
                className="mt-1 block w-32 border rounded px-2 py-2" />
            </label>
            <button type="button" onClick={lookupPin} disabled={busy}
              className="bg-green-700 text-white rounded px-3 py-2 text-sm disabled:opacity-50">
              {busy ? '…' : 'Find'}
            </button>
          </>
        ) : (
          <>
            <label className="text-sm text-gray-700">State
              <select value={state} onChange={(e) => setLocation({ state: e.target.value })}
                className="mt-1 block border rounded px-2 py-2">
                {states.length === 0 && <option>{state}</option>}
                {states.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="text-sm text-gray-700">District
              <input value={district} placeholder="e.g. Ludhiana"
                onChange={(e) => setLocation({ district: e.target.value })}
                className="mt-1 block border rounded px-2 py-2" />
            </label>
          </>
        )}

        <button type="button" onClick={useGps} disabled={busy}
          className="text-sm text-green-700 hover:text-green-900 disabled:opacity-50 pb-2">
          📍 Use my location
        </button>
      </div>

      <p className="text-xs">
        {status?.err && <span className="text-amber-600">{status.err}</span>}
        {status?.ok && <span className="text-gray-500">📍 {status.ok}</span>}
        {!status && (area || district) &&
          <span className="text-gray-500">📍 {area || district}, {state}
            {pincode ? ` · ${pincode}` : ''}</span>}
      </p>
    </div>
  )
}
