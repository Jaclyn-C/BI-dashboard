// ============================================================
// ConvCard.jsx — 按币种收入卡（REQ-20261015-01：仅上游美元口径）。
// 单环（server=上游美元）+ 图例 + 全量表 + TOTAL 行 + 缺上游美元尾注。
// 折叠与色分配：排序位 i<7 → --cat{i+1}，__other 与第 8+ 币种 → --muted
// （DESIGN §5.2 说明⑥）。切片占比仅几何归一（弧长/提示行）。
// ============================================================

import { useTranslation } from 'react-i18next'

import DonutChart from './charts/DonutChart'
import { intNum, money, moneyWhole, nativeMoney } from '../../dashboard/format'

const MAX_SLICES = 7

/**
 * @param {{conv: object, fmt: object}} props
 */
export default function ConvCard({ conv, fmt }) {
  const { t } = useTranslation()
  const rows = conv.rows

  // 整卡空态（convEmpty）
  if (conv.empty || !rows.length) {
    return (
      <section className="card">
        <div className="cardhead">
          <h2>{t('dashboard.convTitle')}</h2>
          <span className="sub">{t('dashboard.convSub')}</span>
        </div>
        <div className="chartbox">
          <div className="empty">{t('dashboard.convEmpty')}</div>
        </div>
      </section>
    )
  }

  // 色：排序位（rows 已按 server_usd 降序，DESIGN §5.2）
  const colorOfRow = (i) => (i < MAX_SLICES ? `var(--cat${i + 1})` : 'var(--muted)')

  // 切片：后端预折叠（前 7 + __other）；占比仅几何归一
  const tailCount = Math.max(0, rows.length - MAX_SLICES)
  const sliceLabel = (key) =>
    key === '__other' ? t('dashboard.other', { n: tailCount }) : key
  const slices = conv.slices.map((sl, i) => {
    const value = Number(sl.server_usd) // 几何归一专用
    return {
      key: sl.key,
      label: sliceLabel(sl.key),
      color: sl.key === '__other' ? 'var(--muted)' : `var(--cat${i + 1})`,
      value,
      display: money(fmt, sl.server_usd),
    }
  })
  const total = slices.reduce((a, sl) => a + sl.value, 0)
  const slicesWithShare = slices.map((sl) => ({
    ...sl,
    shareDisplay: `${(total ? (sl.value / total) * 100 : 0).toFixed(1)}%`,
  }))

  return (
    <section className="card">
      <div className="cardhead">
        <h2>{t('dashboard.convTitle')}</h2>
        <span className="sub">{t('dashboard.convSub')}</span>
      </div>
      <div className="convpie">
        <div className="convpie-cap">{t('dashboard.convServerCap')}</div>
        <DonutChart
          slices={slicesWithShare}
          centerDisplay={moneyWhole(fmt, conv.server_total)}
          ariaLabel={t('dashboard.convServerCap')}
          shareLabel={t('dashboard.shareLbl')}
        />
      </div>
      <div className="legend">
        {conv.slices.map((sl, i) => (
          <span key={sl.key} className="li">
            <span
              className="sw"
              style={{ background: sl.key === '__other' ? 'var(--muted)' : `var(--cat${i + 1})` }}
            />
            {sliceLabel(sl.key)}
          </span>
        ))}
      </div>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th aria-label={t('dashboard.hColor')} />
              <th>{t('dashboard.hCurrency')}</th>
              <th className="num">{t('dashboard.hOrders')}</th>
              <th className="num">{t('dashboard.convHNative')}</th>
              <th className="num">{t('dashboard.convHServer')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.currency}>
                <td>
                  <span className="sw" style={{ background: colorOfRow(i) }} />
                </td>
                <td>{r.currency}</td>
                <td className="num">{intNum(fmt, r.orders)}</td>
                <td className="num">{`${nativeMoney(fmt, r.native)} ${r.currency}`}</td>
                <td className="num">{money(fmt, r.server_usd)}</td>
              </tr>
            ))}
            <tr>
              <td />
              <td>
                <strong>{t('dashboard.convTotalRow')}</strong>
              </td>
              <td className="num" />
              <td className="num" />
              <td className="num">
                <strong>{money(fmt, conv.server_total)}</strong>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="convnote">
        {conv.no_usd_order_count ? (
          <div>{t('dashboard.convNoServerNote', { n: intNum(fmt, conv.no_usd_order_count) })}</div>
        ) : null}
      </div>
    </section>
  )
}
