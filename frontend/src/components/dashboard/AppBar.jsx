// ============================================================
// AppBar.jsx — 应用栏（HTML:241-251）：标题 + 副标题（B1 毛额口径 AC-D2）+
// 状态行 + 数据说明 + 语言切换 + 刷新 + 退出（2026-10-15 用户定稿：
// 刷新/退出由参考 HTML 的 ↻/⮑ 字形改为文字按钮，与其余 chip 统一）。
// ============================================================

import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'

import { setLang } from '../../i18n'

/** 状态行（HTML statusline/dot）：dot: 'ok' | 'err' | null（中性加载态） */
export function StatusLine({ dot, text, note }) {
  const dotClass = dot === 'ok' ? 'dot ok' : dot === 'err' ? 'dot err' : 'dot'
  return (
    <div className="statusline">
      <span className={dotClass} />
      <span>{text}</span>
      {note ? <span className="note">{note}</span> : null}
    </div>
  )
}

export default function AppBar({ sub, status, navs = [], onGuide, onRefresh, onLogout }) {
  const { t, i18n } = useTranslation()

  const toggleLang = useCallback(() => {
    setLang(i18n.language === 'zh' ? 'en' : 'zh')
  }, [i18n])

  return (
    <header className="appbar">
      <div>
        <h1>{t('common.appName')}</h1>
        <div className="sub">{sub}</div>
      </div>
      <div className="spacer" />
      {status}
      {navs.map((item) => (
        <button key={item.label} type="button" className="chip" onClick={item.onClick}>
          {item.label}
        </button>
      ))}
      {onGuide ? (
        <button type="button" className="chip" onClick={onGuide}>
          {t('guide.open')}
        </button>
      ) : null}
      <button type="button" className="chip" onClick={toggleLang} aria-label={t('common.languageSwitch')}>
        {t('common.languageSwitch')}
      </button>
      {onRefresh ? (
        <button type="button" className="chip" onClick={onRefresh}>
          {t('dashboard.refresh')}
        </button>
      ) : null}
      <button type="button" className="chip" onClick={onLogout}>
        {t('dashboard.signOut')}
      </button>
    </header>
  )
}
