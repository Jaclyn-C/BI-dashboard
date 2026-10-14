// ============================================================
// DatasetBar.jsx — 数据集分段控件 + CSV 双按钮（HTML:265-273，AC-D1/X1）
// REQ-20261014-01：三档全部启用（全部 / 已计入 / 剔除）——数据集是全局
// 视图切换，选中后下方全部内容只含该数据集订单（不适用卡片由后端置
// null、前端不渲染）。⤓ 字形照搬 HTML:271-272 实体（AC-V3 白名单）。
// ============================================================

import { useTranslation } from 'react-i18next'

/**
 * @param {{dataset: string, onDatasetChange: (ds: string) => void,
 *          onCsvView: () => void, onCsvAll: () => void, csvBusy: boolean}} props
 */
export default function DatasetBar({ dataset, onDatasetChange, onCsvView, onCsvAll, csvBusy }) {
  const { t } = useTranslation()

  const dsButton = (value, label) => (
    <button
      type="button"
      data-ds={value}
      aria-pressed={dataset === value}
      onClick={() => onDatasetChange(value)}
    >
      {label}
    </button>
  )

  return (
    <div className="dsbar">
      <div className="seg big" role="group" aria-label={t('dashboard.dsGroup')}>
        {dsButton('included', t('dashboard.dsIncluded'))}
        {dsButton('excluded', t('dashboard.dsExcluded'))}
        {dsButton('all', t('dashboard.dsAll'))}
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
