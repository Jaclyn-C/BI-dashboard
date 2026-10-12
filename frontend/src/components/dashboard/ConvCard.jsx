// ============================================================
// ConvCard.jsx — 新旧美元口径对比卡（HTML:350-367/1638-1708，AC-C1–C8）
// 双环（legacy=固定汇率估算 / server=上游美元）+ 图例 + 全量表 + TOTAL 行
// + 尾注（一致/差异 + 缺汇率币种 + 缺上游美元订单数）。
// 折叠与色分配：排序位 i<7 → --cat{i+1}，__other 与第 8+ 币种 → --muted
// （DESIGN §5.2 说明⑥）。切片占比仅几何归一（弧长/提示行）。
// Δ 展示：后端 delta/delta_pct 字符串 + 首字符判号（非金额运算）。
// ============================================================

import { useTranslation } from 'react-i18next'

import DonutChart from './charts/DonutChart'
import { intNum, money, moneyWhole, nativeMoney } from '../../dashboard/format'

const MAX_SLICES = 7

const isNeg = (s) => String(s).trim().startsWith('-')
const isZero = (s) => /^-?0+(\.0+)?$/.test(String(s).trim())

function DeltaCell({ delta, pct, fmt, strong }) {
  const neg = isNeg(delta)
  const zero = isZero(delta)
  const sign = neg || zero ? '' : '+'
  const cls = `num ${neg ? 'delta-neg' : zero ? '' : 'delta-pos'}`
  const text = `${sign}${money(fmt, delta)} (${sign}${pct}%)`
  return <td className={cls}>{strong ? <strong>{text}</strong> : text}</td>
}

/**
 * @param {{conv: object, fmt: object}} props
 */
export default function ConvCard({ conv, fmt }) {
  const { t } = useTranslation()
  const rows = conv.rows

  // 整卡空态（AC-C?：convEmpty，HTML 1640-1643 同形）
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

  // 色：排序位（rows 已按 max(server,legacy) 降序，DESIGN §5.2）
  const colorOfRow = (i) => (i < MAX_SLICES ? `var(--cat${i + 1})` : 'var(--muted)')

  // 切片：后端预折叠（前 7 + __other）
  const tailCount = Math.max(0, rows.length - MAX_SLICES)
  const sliceLabel = (key) =>
    key === '__other' ? t('dashboard.other', { n: tailCount }) : key
  const slicesFor = (pick) => {
    const arr = conv.slices.map((sl, i) => {
      const value = Number(sl[pick]) // 几何归一专用
      return {
        key: sl.key,
        label: sliceLabel(sl.key),
        color: sl.key === '__other' ? 'var(--muted)' : `var(--cat${i + 1})`,
        value,
        display: money(fmt, sl[pick]),
      }
    })
    const total = arr.reduce((a, sl) => a + sl.value, 0)
    return {
      arr: arr.map((sl) => ({
        ...sl,
        shareDisplay: `${(total ? (sl.value / total) * 100 : 0).toFixed(1)}%`,
      })),
      total,
    }
  }

  const legacy = slicesFor('legacy_usd')
  const server = slicesFor('server_usd')

  return (
    <section className="card">
      <div className="cardhead">
        <h2>{t('dashboard.convTitle')}</h2>
        <span className="sub">{t('dashboard.convSub')}</span>
      </div>
      <div className="convtwo">
        <div className="convpie">
          <div className="convpie-cap">{t('dashboard.convLegacyCap')}</div>
          <DonutChart
            slices={legacy.arr}
            centerDisplay={moneyWhole(fmt, conv.legacy_total)}
            ariaLabel={t('dashboard.convLegacyCap')}
            shareLabel={t('dashboard.shareLbl')}
          />
        </div>
        <div className="convpie">
          <div className="convpie-cap">{t('dashboard.convServerCap')}</div>
          <DonutChart
            slices={server.arr}
            centerDisplay={moneyWhole(fmt, conv.server_total)}
            ariaLabel={t('dashboard.convServerCap')}
            shareLabel={t('dashboard.shareLbl')}
          />
        </div>
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
              <th className="num">{t('dashboard.convRate')}</th>
              <th className="num">{t('dashboard.hOrders')}</th>
              <th className="num">{t('dashboard.convHNative')}</th>
              <th className="num">{t('dashboard.convHLegacy')}</th>
              <th className="num">{t('dashboard.convHServer')}</th>
              <th className="num">{t('dashboard.convHDelta')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.currency} className={r.flagged ? 'delta-flag' : undefined}>
                <td>
                  <span className="sw" style={{ background: colorOfRow(i) }} />
                </td>
                <td>{r.currency}</td>
                <td className="num">{r.has_rate ? r.rate : t('dashboard.convNoRate')}</td>
                <td className="num">{intNum(fmt, r.orders)}</td>
                <td className="num">{`${nativeMoney(fmt, r.native)} ${r.currency}`}</td>
                <td className="num">{r.has_rate ? money(fmt, r.legacy_usd) : '–'}</td>
                <td className="num">{money(fmt, r.server_usd)}</td>
                <DeltaCell delta={r.delta} pct={r.delta_pct} fmt={fmt} />
              </tr>
            ))}
            <tr className="delta-flag">
              <td />
              <td>
                <strong>{t('dashboard.convTotalRow')}</strong>
              </td>
              <td className="num" />
              <td className="num" />
              <td className="num" />
              <td className="num">
                <strong>{money(fmt, conv.legacy_total)}</strong>
              </td>
              <td className="num">
                <strong>{money(fmt, conv.server_total)}</strong>
              </td>
              <DeltaCell delta={conv.delta_total} pct={conv.delta_pct} fmt={fmt} strong />
            </tr>
          </tbody>
        </table>
      </div>
      <div className="convnote">
        <div>
          {conv.agree
            ? t('dashboard.convMatch', { d: money(fmt, conv.delta_total) })
            : t('dashboard.convDiff', {
                d: `${isNeg(conv.delta_total) || isZero(conv.delta_total) ? '' : '+'}${money(fmt, conv.delta_total)}`,
                p: `${isNeg(conv.delta_total) || isZero(conv.delta_total) ? '' : '+'}${conv.delta_pct}%`,
              })}
        </div>
        {conv.no_rate_currencies && conv.no_rate_currencies.length ? (
          <div>
            {t('dashboard.convNoRateNote')}
            {conv.no_rate_currencies.join(', ')}
            {t('dashboard.convNoRateNoteBody')}
          </div>
        ) : null}
        {conv.no_usd_order_count ? (
          <div>{t('dashboard.convNoServerNote', { n: intNum(fmt, conv.no_usd_order_count) })}</div>
        ) : null}
      </div>
    </section>
  )
}
