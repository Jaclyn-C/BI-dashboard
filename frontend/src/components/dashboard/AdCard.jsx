// ============================================================
// AdCard.jsx — 广告收益柱状卡（HTML:341-347/1487-1540，AC-A1–A3）
// 单序列 --ad 色复用 ColumnChart；plotH=180、无十字准线、无订单行、
// 无表格/切换（HTML adChart 仅 chartbox）。仅有数据日入图，
// yMax 自算（niceCeil）。ad_available=false 时由 Banners 提示，
// 本卡照常渲染（空则 empty 态）。
// ============================================================

import { useTranslation } from 'react-i18next'

import ColumnChart from './charts/ColumnChart'
import { money } from '../../dashboard/format'
import { niceCeil } from './charts/chartMath'

/**
 * @param {{ad: Array<{date: string, amount: string}>, fmt: object}} props
 */
export default function AdCard({ ad, fmt }) {
  const { t } = useTranslation()

  const hasData = ad.length > 0

  const chartRows = ad.map((a) => ({
    date: a.date,
    total: Number(a.amount), // 几何缩放专用（约束 3）
    count: 0,
    totalDisplay: money(fmt, a.amount),
    countDisplay: '',
    segs: [
      {
        label: t('dashboard.adRevenueLbl'),
        color: 'var(--ad)',
        amount: Number(a.amount),
        display: money(fmt, a.amount),
      },
    ],
  }))

  const maxVal = chartRows.reduce((m, r) => Math.max(m, r.total), 0)
  const yMax = niceCeil(maxVal || 1)

  return (
    <section className="card">
      <div className="cardhead">
        <h2>{t('dashboard.adTitle')}</h2>
        <span className="sub">{t('dashboard.adSub')}</span>
      </div>
      <ColumnChart
        rows={chartRows}
        series={[{ key: 'ad', label: t('dashboard.adRevenueLbl'), color: 'var(--ad)' }]}
        yMax={yMax}
        plotH={180}
        crosshair={false}
        showOrders={false}
        ariaLabel={t('dashboard.adTitle')}
        totalLabel={t('dashboard.adRevenueLbl')}
        fmt={fmt}
        emptyLabel={hasData ? '' : t('dashboard.empty')}
      />
    </section>
  )
}
