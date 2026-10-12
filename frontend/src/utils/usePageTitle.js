// ============================================================
// usePageTitle.js — document.title 跟随页面与当前语言
// 语言切换（i18n.language 变化）时自动按新语言重设标题。
// ============================================================

import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

/** @param {string} titleKey locale 中的标题 key（如 common.pageTitle.login） */
export default function usePageTitle(titleKey) {
  const { t, i18n } = useTranslation()
  useEffect(() => {
    document.title = t(titleKey)
  }, [t, i18n.language, titleKey])
}
