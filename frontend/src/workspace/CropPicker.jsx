import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getMandiCommodities } from '../api/client'
import { useCropName } from '../i18n/cropName'
import { useWorkspace } from './WorkspaceContext'

export default function CropPicker() {
  const { t, i18n } = useTranslation()
  const cropName = useCropName()
  const { crop, setCrop } = useWorkspace()
  const [crops, setCrops] = useState([])
  const [text, setText] = useState(crop ? cropName(crop) : '')

  useEffect(() => { getMandiCommodities().then(setCrops).catch(() => {}) }, [])
  // Show the crop in the active language; the stored value stays English.
  useEffect(() => { setText(crop ? cropName(crop) : '') }, [crop, i18n.language])

  const commit = (value) => {
    setText(value)
    const v = value.trim().toLowerCase()
    // Accept either the English name the backend uses or its localized label.
    const match = crops.find((c) =>
      c.display_name.toLowerCase() === v || cropName(c.display_name).toLowerCase() === v)
    setCrop(match ? match.display_name : value)
  }

  return (
    <label className="text-sm text-foreground">{t('crop.label')}
      <input list="crop-options" value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        placeholder={t('crop.placeholder')}
        className="mt-1 block w-44 border border-border rounded px-2 py-2" />
      <datalist id="crop-options">
        {crops.map((c) => (
          <option key={c.display_name} value={cropName(c.display_name)}
            label={c.has_mandi ? cropName(c.display_name) : `${cropName(c.display_name)} (est.)`} />
        ))}
      </datalist>
    </label>
  )
}
