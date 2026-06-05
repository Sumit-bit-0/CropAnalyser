import { useTranslation } from 'react-i18next'

// Crop names arrive from the backend in English (canonical lowercase like "rice",
// or a verbose market commodity like "Bengal Gram (Gram)(Whole)"). Backend calls
// must keep the English value, so we only ever translate what is *shown*. The
// catalog key is the canonical crop stripped to lowercase alphanumerics; verbose
// market names that have no canonical key simply fall back to their raw string.
export const normCrop = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '')

// useCropName() -> (englishName) => localized display name (falls back to input).
export function useCropName() {
  const { t } = useTranslation()
  return (name) => t(`crop.name.${normCrop(name)}`, { defaultValue: name })
}
