import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { getStateMarkup } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'

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
    <div className="max-w-5xl w-full">
      <PageHeader title="Farm-to-Market Markup by State"
        subtitle="Darker shading marks a wider gap between farm-gate and market price. Click a state for details." />
      <div className="flex flex-col md:flex-row gap-6">
        <div className="rounded-lg overflow-hidden border border-border" style={{ width: '65%', minWidth: 0 }}>
          <MapContainer center={[22, 82]} zoom={5} style={{ height: '500px', width: '100%' }}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org">OpenStreetMap</a>' />
            {geoData && <GeoJSON data={geoData} style={styleFeature} onEachFeature={onEachFeature} />}
          </MapContainer>
        </div>
        {selected ? (
          <div className="bg-card border border-border rounded-lg p-5 w-64 h-fit">
            <h3 className="font-display font-semibold text-foreground text-lg">{selected.state}</h3>
            <dl className="mt-3 space-y-1.5 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Avg markup</dt>
                <dd className="font-semibold text-destructive tabular-nums">{selected.avg_markup_pct ?? 'N/A'}%</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Farm gate</dt>
                <dd className="tabular-nums text-foreground">₹{selected.avg_farm_gate ?? 'N/A'}/q</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Market price</dt>
                <dd className="tabular-nums text-foreground">₹{selected.avg_modal ?? 'N/A'}/q</dd>
              </div>
            </dl>
          </div>
        ) : (
          <div className="bg-secondary border border-border rounded-lg p-5 w-64 h-fit text-sm text-muted-foreground">
            Click any state on the map to see its markup, farm-gate, and market price.
          </div>
        )}
      </div>
    </div>
  )
}
