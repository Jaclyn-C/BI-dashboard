// ============================================================
// DailyCard.jsx — 每日收益双卡之一（est / usd，HTML:317-338，AC-E1–E8）
// 双卡共享：chart|table 切换（首卡渲染，AC-E1）与 yMax（父级算好传入，
// AC-E2）。B1：副标题 dailySubGross、表列=日期/订单数/毛额/广告/按币种
// 毛额（AC-E7）；类别堆叠切换不存在（AC-E4）。
// 判空独立（AC-E8）：orders 计数各卡各算。金额展示全部后端字符串。
// aria-label 合计（AC-V4）：est 卡=conv.legacy_total / usd 卡=conv.server_total，
// 均为后端合计，前端不落 money 运算。
// ============================================================

import { useTranslation } from 'react-i18next'

import ColumnChart from './charts/ColumnChart'
import { intNum, money } from '../../dashboard/format'

/**
 * @param {{variant: 'est'|'usd', days: string[], entries: Array<object>,
 *          adByDate: Object<string, string>, currencyRank: string[],
 *          totalDisplay: string, view: 'chart'|'table', yMax: number,
 *          onViewChange: (v: 'chart'|'table') => void, showToggle: boolean,
 *          fmt: object}} props
 */
export default function DailyCard({
  variant,
  days,
  entries,
  adByDate,
  currencyRank,
  totalDisplay,
  view,
  yMax,
  onViewChange,
  showToggle,
  fmt,
}) {
  const { t } = useTranslation()

  const title = `${t('dashboard.dailyTitle')} · ${t(variant === 'est' ? 'dashboard.dailyEst' : 'dashboard.dailyUsd')}`
  const sub = t('dashboard.dailySubGross')

  // 序列=currency_rank 前 6 + __other（后端预折叠；前端只按排序位配色，DESIGN §5.2）
  const foldedCount = Math.max(0, currencyRank.length - 6)
  const series = currencyRank.slice(0, 6).map((key, i) => ({
    key,
    label: key,
    color: `var(--cat${i + 1})`,
  }))
  if (foldedCount > 0) {
    series.push({ key: '__other', label: t('dashboard.other', { n: foldedCount }), color: 'var(--muted)' })
  }

  const byDate = new Map(entries.map((e) => [e.date, e]))
  const chartRows = days.map((date) => {
    const e = byDate.get(date) || {
      date,
      orders: 0,
      total: '0.00',
      by_currency: [],
      series: series.map((sr) => ({ key: sr.key, amount: '0.00' })),
    }
    return {
      date,
      total: Number(e.total), // 几何缩放专用（约束 3）
      count: e.orders,
      totalDisplay: money(fmt, e.total),
      countDisplay: intNum(fmt, e.orders),
      segs: series.map((sr) => {
        const seg = e.series.find((x) => x.key === sr.key)
        const amount = seg ? seg.amount : '0.00'
        return { label: sr.label, color: sr.color, amount: Number(amount), display: money(fmt, amount) }
      }),
    }
  })

  const hasData = entries.some((e) => e.orders > 0) // AC-E8：口径独立判空

  return (
    <section className="card">
      <div className="cardhead">
        <h2>{title}</h2>
        <span className="sub">{sub}</span>
        {showToggle ? (
          <div className="right">
            <div className="seg" role="group" aria-label={t('dashboard.view')}>
              <button type="button" aria-pressed={String(view === 'chart')} onClick={() => onViewChange('chart')}>
                {t('dashboard.chart')}
              </button>
              <button type="button" aria-pressed={String(view === 'table')} onClick={() => onViewChange('table')}>
                {t('dashboard.table')}
              </button>
            </div>
          </div>
        ) : null}
      </div>
      {view === 'chart' ? (
        <ColumnChart
          rows={chartRows}
          series={series}
          yMax={yMax}
          ariaLabel={`${title} ${totalDisplay}`}
          totalLabel={t('dashboard.grossLbl')}
          ordersLabel={t('dashboard.ordersLbl')}
          fmt={fmt}
          emptyLabel={hasData ? '' : t('dashboard.empty')}
        />
      ) : (
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>{t('dashboard.hDate')}</th>
                <th className="num">{t('dashboard.hOrders')}</th>
                <th className="num">{t('dashboard.hGross')}</th>
                <th className="num">{t('dashboard.hAdRevenue')}</th>
                <th>{t('dashboard.hByCurrencyGross')}</th>
              </tr>
            </thead>
            <tbody>
              {days.map((date) => {
                const e = byDate.get(date)
                const byCur = e
                  ? e.by_currency.map((bc) => `${bc.currency} ${money(fmt, bc.amount)}`).join(' · ')
                  : ''
                return (
                  <tr key={date}>
                    <td>{date}</td>
                    <td className="num">{intNum(fmt, e ? e.orders : 0)}</td>
                    <td className="num">{money(fmt, e ? e.total : '0.00')}</td>
                    <td className="num">{money(fmt, adByDate[date] || '0.00')}</td>
                    <td className="muted">{byCur || '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
