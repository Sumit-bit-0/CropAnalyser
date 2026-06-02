import { useState } from 'react'
import { useWorkspace } from './WorkspaceContext'
import LocationPicker from './LocationPicker'
import SoilPanel from './SoilPanel'

const SEASONS = ['Any', 'Kharif', 'Rabi', 'Summer', 'Winter', 'Autumn', 'Whole Year']

export default function ContextBar({ states }) {
  const { season, setSeason, mode } = useWorkspace()
  const [showSoil, setShowSoil] = useState(false)
  return (
    <div className="bg-white border-b px-4 md:px-6 py-3">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <LocationPicker states={states} />
        <label className="text-sm text-gray-700">Season
          <select value={season} onChange={(e) => setSeason(e.target.value)}
            className="mt-1 block border rounded px-2 py-2">
            {SEASONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        {mode === 'smart' && (
          <button type="button" onClick={() => setShowSoil((v) => !v)}
            className="text-sm text-green-700 hover:text-green-900 pb-2">
            {showSoil ? '▾' : '▸'} Soil details
          </button>
        )}
      </div>
      {mode === 'smart' && showSoil && <SoilPanel />}
    </div>
  )
}
