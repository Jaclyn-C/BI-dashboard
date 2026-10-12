import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './en.json'
import zh from './zh.json'

// DESIGN §5.4：fallback en，默认 en，选择持久化 localStorage（key pd_lang）
const LANG_KEY = 'pd_lang'

function initialLang() {
  try {
    const saved = localStorage.getItem(LANG_KEY)
    if (saved === 'zh' || saved === 'en') return saved
  } catch (e) {
    /* storage unavailable */
  }
  return 'en'
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    zh: { translation: zh },
  },
  lng: initialLang(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false }, // React 已防 XSS
})

export function setLang(lang) {
  i18n.changeLanguage(lang)
  try {
    localStorage.setItem(LANG_KEY, lang)
  } catch (e) {
    /* storage unavailable */
  }
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en'
}

document.documentElement.lang = i18n.language === 'zh' ? 'zh-CN' : 'en'

export default i18n
