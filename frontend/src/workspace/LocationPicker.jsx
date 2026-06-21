import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useWorkspace } from './WorkspaceContext'
import { resolvePincode, locateByGps } from '../api/client'

export default function LocationPicker({ states, statesLoading }) {
  const { t } = useTranslation()
  const { state, district, area, pincode, setLocation } = useWorkspace()
  const [tab, setTab] = useState('pincode')   // 'pincode' | 'manual'
  const [pin, setPin] = useState(pincode || '')
  const [status, setStatus] = useState(null)  // {ok} | {err}
  const [busy, setBusy] = useState(null)       // null | 'pin' | 'gps' (which action is running)

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
    if (!/^\d{6}$/.test(pin)) { setStatus({ err: t('loc.errSixDigit') }); return }
    setBusy('pin'); setStatus(null)
    try { applyResolved(await resolvePincode(pin)) }
    catch { setStatus({ err: t('loc.errNotFound') }) }
    finally { setBusy(null) }
  }

  const useGps = () => {
    if (!navigator.geolocation) { setStatus({ err: t('loc.errGeoUnsupported') }); return }
    setBusy('gps'); setStatus(null)
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const fallback = { lat: pos.coords.latitude, lon: pos.coords.longitude }
        try {
          const r = await locateByGps(fallback.lat, fallback.lon)
          setPin(r.pincode || '')
          applyResolved(r, fallback)
        } catch { setStatus({ err: t('loc.errResolve') }) }
        finally { setBusy(null) }
      },
      (e) => {
        // Distinct message per error code (was: every error reported as "denied").
        const key = e.code === e.PERMISSION_DENIED ? 'loc.errDenied'
          : e.code === e.TIMEOUT ? 'loc.errTimeout'
          : 'loc.errUnavailable'
        setStatus({ err: t(key) }); setBusy(null)
      },
      { timeout: 15000, enableHighAccuracy: true, maximumAge: 0 },
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex gap-1 text-xs">
          {['pincode', 'manual'].map((tb) => (
            <button key={tb} type="button" onClick={() => setTab(tb)}
              className={`px-2 py-1 rounded ${tab === tb ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground'}`}>
              {tb === 'pincode' ? t('loc.pincode') : t('loc.manual')}
            </button>
          ))}
        </div>

        {tab === 'pincode' ? (
          <>
            <label className="text-sm text-foreground">{t('loc.pincode')}
              <input value={pin} inputMode="numeric" maxLength={6} placeholder="851101"
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
                className="mt-1 block w-32 border border-border rounded px-2 py-2" />
            </label>
            <button type="button" onClick={lookupPin} disabled={!!busy}
              className="bg-primary text-primary-foreground rounded px-3 py-2 text-sm disabled:opacity-50">
              {busy === 'pin' ? '…' : t('loc.find')}
            </button>
          </>
        ) : (
          <>
            <label className="text-sm text-foreground">{t('loc.state')}
              <select value={state} onChange={(e) => setLocation({ state: e.target.value })}
                disabled={statesLoading && states.length === 0}
                className="mt-1 block border border-border rounded px-2 py-2 disabled:opacity-60">
                {states.length === 0 && <option>{state}</option>}
                {states.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              {statesLoading && states.length === 0 && (
                <span className="mt-1 block text-xs text-muted-foreground">⏳ {t('loc.loadingStates')}</span>
              )}
            </label>
            <label className="text-sm text-foreground">{t('loc.district')}
              <input value={district} placeholder="Ludhiana"
                onChange={(e) => setLocation({ district: e.target.value })}
                className="mt-1 block border border-border rounded px-2 py-2" />
            </label>
          </>
        )}

        <button type="button" onClick={useGps} disabled={!!busy}
          className="text-sm text-primary hover:text-primary/80 disabled:opacity-50 pb-2">
          {busy === 'gps' ? `⏳ ${t('loc.locating')}` : `📍 ${t('loc.useMyLocation')}`}
        </button>
      </div>

      <p className="text-xs">
        {status?.err && <span className="text-amber-600">{status.err}</span>}
        {status?.ok && <span className="text-muted-foreground">📍 {status.ok}</span>}
        {!status && (area || district) &&
          <span className="text-muted-foreground">📍 {area || district}, {state}
            {pincode ? ` · ${pincode}` : ''}</span>}
      </p>
    </div>
  )
}
