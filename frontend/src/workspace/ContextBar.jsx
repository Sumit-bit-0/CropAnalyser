import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useWorkspace } from './WorkspaceContext'
import LocationPicker from './LocationPicker'
import SoilPanel from './SoilPanel'
import CropPicker from './CropPicker'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'

const SEASONS = ['Any', 'Kharif', 'Rabi', 'Summer', 'Winter', 'Autumn', 'Whole Year']

export default function ContextBar({ states }) {
  const { t } = useTranslation()
  const { season, setSeason, mode } = useWorkspace()
  const [showSoil, setShowSoil] = useState(false)
  // Reveal the soil panel automatically when Smart mode turns on.
  useEffect(() => { if (mode === 'smart') setShowSoil(true) }, [mode])
  return (
    <div className="sticky top-0 z-20 bg-secondary border-b border-border">
      <div className="mx-auto max-w-[1100px] px-6 py-3">
        <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
          <LocationPicker states={states} />
          <CropPicker />
          <label className="text-sm text-foreground">{t('season.label')}
            <Select value={season} onValueChange={setSeason}>
              <SelectTrigger className="mt-1 w-40 bg-card">
                <SelectValue placeholder={t('season.label')} />
              </SelectTrigger>
              <SelectContent>
                {SEASONS.map((s) => <SelectItem key={s} value={s}>{t(`season.${s}`)}</SelectItem>)}
              </SelectContent>
            </Select>
          </label>
          {mode === 'smart' && (
            <button type="button" onClick={() => setShowSoil((v) => !v)}
              className="text-sm text-primary hover:text-primary/80 pb-2">
              {showSoil ? '▾' : '▸'} {t('cb.soilDetails')}
            </button>
          )}
        </div>
        {mode === 'smart' && showSoil && <SoilPanel />}
      </div>
    </div>
  )
}
