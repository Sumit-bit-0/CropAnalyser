import { useEffect, useState } from 'react'
import { getMandiCommodities } from '../api/client'
import { useWorkspace } from './WorkspaceContext'

export default function CropPicker() {
  const { crop, setCrop } = useWorkspace()
  const [crops, setCrops] = useState([])
  const [text, setText] = useState(crop || '')

  useEffect(() => { getMandiCommodities().then(setCrops).catch(() => {}) }, [])
  useEffect(() => { setText(crop || '') }, [crop])

  const commit = (value) => {
    setText(value)
    const match = crops.find((c) => c.display_name.toLowerCase() === value.toLowerCase())
    setCrop(match ? match.display_name : value)
  }

  return (
    <label className="text-sm text-foreground">Crop
      <input list="crop-options" value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        placeholder="e.g. Maize"
        className="mt-1 block w-44 border border-border rounded px-2 py-2" />
      <datalist id="crop-options">
        {crops.map((c) => (
          <option key={c.display_name} value={c.display_name}
            label={c.has_mandi ? c.display_name : `${c.display_name} (est.)`} />
        ))}
      </datalist>
    </label>
  )
}
