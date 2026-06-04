import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import en from './locales/en.json'
import hi from './locales/hi.json'

// Major farming-state languages. Codes with a JSON catalog below are fully
// translated; the rest are selectable and fall back to English until native
// translations are added (drop a `<code>.json` in ./locales and register it).
export const LANGUAGES = [
  { code: 'en', native: 'English' },
  { code: 'hi', native: 'हिन्दी' },
  { code: 'pa', native: 'ਪੰਜਾਬੀ' },
  { code: 'mr', native: 'मराठी' },
  { code: 'gu', native: 'ગુજરાતી' },
  { code: 'bn', native: 'বাংলা' },
  { code: 'te', native: 'తెలుగు' },
  { code: 'ta', native: 'தமிழ்' },
  { code: 'kn', native: 'ಕನ್ನಡ' },
  { code: 'ml', native: 'മലയാളം' },
  { code: 'or', native: 'ଓଡ଼ିଆ' },
  { code: 'as', native: 'অসমীয়া' },
]

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      hi: { translation: hi },
    },
    fallbackLng: 'en',
    supportedLngs: LANGUAGES.map((l) => l.code),
    nonExplicitSupportedLngs: true,
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'lang',
    },
  })

export default i18n
