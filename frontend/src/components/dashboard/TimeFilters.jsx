// ============================================================
// TimeFilters.jsx — 时间筛选（HTML:253-263，AC-T1–T5）
// 四预设 chip（aria-pressed + ✓ 前缀由 CSS ::before 提供）+ 起止日期输入
// （max=今天；变更即生效；钳制逻辑在 dashboard/range.js customRange）。
// ============================================================

import { useTranslation } from 'react-i18next'

import { matchesPreset, PRESETS } from '../../dashboard/range'

const PRESET_LABEL_KEY = { today: 'today', '7d': 'd7', '14d': 'd14', '30d': 'd30' }

/**
 * @param {{range: {preset: string, from: string, to: string}, today: string,
 *          onPreset: (preset: string) => void, onCustom: (from: string, to: string) => void}} props
 */
export default function TimeFilters({ range, today, onPreset, onCustom }) {
  const { t } = useTranslation()

  return (
    <nav className="filters" aria-label={t('dashboard.tfLabel')}>
      {PRESETS.map((preset) => (
        <button
          key={preset}
          type="button"
          className="chip"
          aria-pressed={String(matchesPreset(range, preset, today))}
          onClick={() => onPreset(preset)}
        >
          {t(`dashboard.${PRESET_LABEL_KEY[preset]}`)}
        </button>
      ))}
      <span className="gap" />
      <label htmlFor="fromDate">{t('dashboard.from')}</label>
      <input
        className="field"
        type="date"
        id="fromDate"
        value={range.from}
        max={today}
        onChange={(e) => onCustom(e.target.value, range.to)}
      />
      <label htmlFor="toDate">{t('dashboard.to')}</label>
      <input
        className="field"
        type="date"
        id="toDate"
        value={range.to}
        max={today}
        onChange={(e) => onCustom(range.from, e.target.value)}
      />
    </nav>
  )
}
