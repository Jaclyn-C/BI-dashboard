// LangToggle — EN/中文切换（localStorage 记忆，默认 en；即时生效，AC-U1）

import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'

import { setLang } from '../../i18n'

export default function LangToggle({ className = 'langtoggle' }) {
  const { i18n, t } = useTranslation()

  const toggle = useCallback(() => {
    setLang(i18n.language === 'zh' ? 'en' : 'zh')
  }, [i18n])

  return (
    <div className={className}>
      <button type="button" onClick={toggle}>
        {t('common.languageSwitch')}
      </button>
    </div>
  )
}
