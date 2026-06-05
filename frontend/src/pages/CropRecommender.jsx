import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { recommendCrop } from '../api/client'
import { useCropName } from '../i18n/cropName'
import { useWorkspace } from '../workspace/WorkspaceContext'
import { DEFAULT_SOIL } from '../workspace/SoilPanel'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '@/components/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export default function CropRecommender() {
  const { t } = useTranslation()
  const cropName = useCropName()
  const { mode, soil, setMode } = useWorkspace()
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      setResult(await recommendCrop(soil || DEFAULT_SOIL))
    } catch (err) {
      setError(err.response?.data?.detail || 'Recommendation failed'); setResult(null)
    }
  }

  return (
    <div className="max-w-3xl w-full">
      <PageHeader title={t('pg.soil.title')} subtitle={t('pg.soil.subtitle')} />
      {error && <ErrorBanner message={error} />}

      {mode !== 'smart' ? (
        <div className="border border-dashed border-border rounded-lg p-6 text-center text-muted-foreground">
          {t('pg.soil.needSmart')}
          <div className="mt-3">
            <Button onClick={() => setMode('smart')} size="sm">{t('pg.soil.switchSmart')}</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="mb-6">
          <Button size="lg">
            {soil ? t('pg.soil.match') : t('pg.soil.matchDefaults')}
          </Button>
        </form>
      )}

      {result && (
        <div>
          <p className="text-lg mb-3">{t('pg.soil.bestPick')}{' '}
            <span className="font-bold text-primary capitalize">{cropName(result.top.crop)}</span>{' '}
            ({t('pg.soil.matchPct', { pct: result.top.confidence_pct })})</p>
          <div className="space-y-2">
            {result.recommendations.map((r, i) => (
              <Card key={r.crop} className={i === 0 ? 'border-primary bg-secondary' : ''}>
                <CardContent className="p-3">
                  <div className="flex justify-between text-sm font-medium">
                    <span className="capitalize">{cropName(r.crop)}</span><span>{r.confidence_pct}%</span>
                  </div>
                  <div className="h-2 bg-muted rounded mt-1">
                    <div className="h-2 bg-primary rounded" style={{ width: `${r.confidence_pct}%` }} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
