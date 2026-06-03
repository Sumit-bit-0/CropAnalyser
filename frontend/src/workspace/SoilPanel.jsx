import { useWorkspace } from './WorkspaceContext'

const SOIL_FIELDS = [
  ['N', 'Nitrogen (N)', 90], ['P', 'Phosphorus (P)', 42], ['K', 'Potassium (K)', 43],
  ['temperature', 'Temp (°C)', 26], ['humidity', 'Humidity (%)', 80],
  ['ph', 'Soil pH', 6.5], ['rainfall', 'Rainfall (mm)', 180],
]

const DEFAULT_SOIL = Object.fromEntries(SOIL_FIELDS.map(([k, , v]) => [k, v]))

export default function SoilPanel() {
  const { soil, setSoil } = useWorkspace()
  const s = soil || DEFAULT_SOIL
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
      {SOIL_FIELDS.map(([k, label]) => (
        <label key={k} className="text-sm text-foreground">{label}
          <input type="number" step="any" value={s[k]}
            onChange={(e) => setSoil({ ...s, [k]: Number(e.target.value) })}
            className="mt-1 w-full border border-border rounded px-2 py-2" />
        </label>
      ))}
    </div>
  )
}

export { DEFAULT_SOIL }
