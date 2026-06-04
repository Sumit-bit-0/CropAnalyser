import { useTranslation } from 'react-i18next'
import { Globe } from 'lucide-react'
import { LANGUAGES } from '@/i18n'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export default function LanguageSwitcher() {
  const { i18n, t } = useTranslation()
  // Reflect the user's chosen language (not the resolved fallback), so picking
  // an untranslated language still shows that language as selected.
  const current = (i18n.language || 'en').split('-')[0]

  return (
    <Select value={current} onValueChange={(v) => i18n.changeLanguage(v)}>
      <SelectTrigger className="w-auto gap-2 h-9 bg-card" aria-label={t('lang.label')}>
        <Globe className="h-4 w-4 text-muted-foreground" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {LANGUAGES.map((l) => (
          <SelectItem key={l.code} value={l.code}>{l.native}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
