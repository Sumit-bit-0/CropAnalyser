import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { getStateMarkup } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

function getColor(pct) {
  if (pct > 150) return '#800026'
  if (pct > 100) return '#BD0026'
  if (pct > 70)  return '#E31A1C'
  if (pct > 50)  return '#FC4E2A'
  if (pct > 30)  return '#FD8D3C'
  if (pct > 15)  return '#FEB24C'
  return '#FED976'
}

export default function StateMap() {
  const [markupMap, setMarkupMap] = useState({})
  const [geoData, setGeoData]     = useState(null)
  const [selected, setSelected]   = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)

  useEffect(() => {
    Promise.all([
      getStateMarkup(),
      fetch('/india-states.geojson').then(r => r.json())
    ])
      .then(([markup, geo]) => {
        const map = {}
        markup.forEach(r => { map[r.state.toLowerCase()] = r })
        setMarkupMap(map)
        setGeoData(geo)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner />
  if (error)   return <ErrorBanner message={error} />

  const styleFeature = (feature) => {
    const name = (feature.properties.NAME_1 || feature.properties.name || '').toLowerCase()
    const data = markupMap[name]
    return {
      fillColor: data ? getColor(data.avg_markup_pct) : '#ccc',
      weight: 1, color: '#fff', fillOpacity: 0.8
    }
  }

  const onEachFeature = (feature, layer) => {
    const name = (feature.properties.NAME_1 || feature.properties.name || '').toLowerCase()
    const data = markupMap[name]
    layer.on('click', () => setSelected(data || { state: feature.properties.NAME_1 || feature.properties.name }))
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-green-800 mb-2">Farm-to-Market Markup by State</h1>
      <p className="text-gray-500 mb-4 text-sm">Darker red = higher markup. Click a state for details.</p>
      <div className="flex gap-6">
        <MapContainer center={[22, 82]} zoom={5} style={{ height: '500px', width: '65%' }}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org">OpenStreetMap</a>' />
          {geoData && <GeoJSON data={geoData} style={styleFeature} onEachFeature={onEachFeature} />}
        </MapContainer>
        {selected && (
          <div className="bg-green-50 border border-green-200 rounded p-4 w-64 h-fit">
            <h3 className="font-bold text-green-800 text-lg">{selected.state}</h3>
            <p className="text-sm text-gray-600 mt-2">
              Avg Markup: <span className="font-bold text-red-600">{selected.avg_markup_pct ?? 'N/A'}%</span>
            </p>
            <p className="text-sm text-gray-600">Farm Gate: &#8377;{selected.avg_farm_gate ?? 'N/A'}/q</p>
            <p className="text-sm text-gray-600">Market Price: &#8377;{selected.avg_modal ?? 'N/A'}/q</p>
          </div>
        )}
      </div>
    </div>
  )
}
