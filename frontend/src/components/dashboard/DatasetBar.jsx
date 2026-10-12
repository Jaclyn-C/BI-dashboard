// ============================================================
// DatasetBar.jsx — 数据集分段控件 + CSV 双按钮（HTML:265-273，AC-D1/X1）
// B1 降级（DESIGN §6.8）：included/excluded 置灰（disabled 不可聚焦）+
// 「待规则确认」标注；all 恒为选中；CSV 两档均可用。
// ⤓(⤓) 字形照搬 HTML:271-272 实体（AC-V3 白名单）。
// ============================================================

import { useTranslation } from 'react-i18next'

/**
 * @param {{onCsvView: () => void, onCsvAll: () => void, csvBusy: boolean}} props
 */
export default function DatasetBar({ onCsvView, onCsvAll, csvBusy }) {
  const { t } = useTranslation()

  return (
    <div className="dsbar">
      <div className="seg big" role="group" aria-label={t('dashboard.dsGroup')}>
        <button type="button" data-ds="included" disabled aria-pressed="false">
          {t('dashboard.dsIncluded')}
          <span className="pending-note">{t('dashboard.pendingRule')}</span>
        </button>
        <button type="button" data-ds="excluded" disabled aria-pressed="false">
          {t('dashboard.dsExcluded')}
          <span className="pending-note">{t('dashboard.pendingRule')}</span>
        </button>
        <button type="button" data-ds="all" aria-pressed="true">
          {t('dashboard.dsAll')}
        </button>
      </div>
      <button type="button" className="btn-tonal push" onClick={onCsvView} disabled={csvBusy}>
        {'⤓'} <span>{t('dashboard.csvView')}</span>
      </button>
      <button type="button" className="btn-tonal" onClick={onCsvAll} disabled={csvBusy}>
        {'⤓'} <span>{t('dashboard.csvAll')}</span>
      </button>
    </div>
  )
}
