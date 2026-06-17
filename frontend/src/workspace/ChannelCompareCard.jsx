import { useEffect, useState } from 'react'
import { compareChannels } from '../api/client'

const fmt = (n) => (n == null ? '—' : `₹${Math.round(n).toLocaleString('en-IN')}`)

function Channel({ title, data, win }) {
  if (!data?.available) {
    return (
      <div className="cc-col cc-unavailable">
        <h4>{title}</h4>
        <p className="cc-reason">{data?.reason || 'unavailable'}</p>
      </div>
    )
  }
  return (
    <div className={`cc-col${win ? ' cc-win' : ''}`}>
      <h4>{title}{win ? ' ✓' : ''}</h4>
      <div className="cc-line">Price {fmt(data.processor_price ?? data.modal_price)}</div>
      <div className="cc-line">− transport {fmt(data.transport_per_q)}</div>
      <div className="cc-net">Net {fmt(data.net_price)}/q</div>
      {data.premium_pct != null && (
        <div className="cc-note">incl. est. {data.premium_pct}% premium</div>
      )}
    </div>
  )
}

export default function ChannelCompareCard({ crop, lat, lon, state, district, season, area }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!crop || lat == null || lon == null) return
    setData(null); setErr(null)
    compareChannels({ crop, lat, lon, state, district, season, area })
      .then(setData)
      .catch(() => setErr('Comparison unavailable'))
  }, [crop, lat, lon, state, district, season, area])

  if (err) return <div className="cc-card">{err}</div>
  if (!data) return <div className="cc-card">Comparing channels…</div>

  return (
    <div className="cc-card">
      <p className="cc-explain">{data.explanation}</p>
      <div className="cc-cols">
        <Channel title="Sell to processor" data={data.processor} win={data.winner === 'processor'} />
        <Channel title="Sell at mandi" data={data.mandi} win={data.winner === 'mandi'} />
      </div>
      {data.total_advantage && (
        <p className="cc-total">
          Est. advantage on {data.total_advantage.area_ha} ha: {fmt(data.total_advantage.value)}
        </p>
      )}
    </div>
  )
}
