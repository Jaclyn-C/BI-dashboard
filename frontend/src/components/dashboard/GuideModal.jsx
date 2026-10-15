// ============================================================
// GuideModal.jsx — 数据说明弹窗：页面结构 / 指标口径 / 计算方式速览。
// 内容全部走 i18n（guide.*，en/zh 同源），组件只负责渲染结构。
// 极简规范：纯文字、无图标；Esc / 遮罩 / 关闭按钮三种关闭方式。
// ============================================================

import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'

export default function GuideModal({ open, onClose }) {
  const { t } = useTranslation()
  const closeRef = useRef(null)

  // Esc 关闭 + 打开期间锁定背景滚动 + 焦点移入弹窗
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [open, onClose])

  if (!open) return null

  // i18n 数组结构（returnObjects）：[{h, rows: [[term, desc], …]}, …]
  const sections = t('guide.sections', { returnObjects: true })

  return (
    <div className="guide-overlay" onClick={onClose}>
      <div
        className="guide-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="guide-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="guide-head">
          <div>
            <h2 id="guide-title">{t('guide.title')}</h2>
            <div className="guide-sub">{t('guide.sub')}</div>
          </div>
          <button ref={closeRef} type="button" className="chip" onClick={onClose}>
            {t('guide.close')}
          </button>
        </header>
        <div className="guide-body">
          {Array.isArray(sections) &&
            sections.map((sec) => (
              <section key={sec.h} className="guide-section">
                <h3>{sec.h}</h3>
                {sec.rows.map(([term, desc]) => (
                  <div className="guide-row" key={term}>
                    <div className="guide-term">{term}</div>
                    <div className="guide-desc">{desc}</div>
                  </div>
                ))}
              </section>
            ))}
        </div>
      </div>
    </div>
  )
}
