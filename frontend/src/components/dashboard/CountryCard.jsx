// ============================================================
// CountryCard.jsx — 国家分布卡（HTML:369-377/1709-1793，AC-N1–N4）
// .two 双栏：CountryBars（后端预折叠前 9+__other）+ 全量表。
// 表列：国家 / 币种·原币金额 / USD / 占比（后端 share 字符串）。
// 国家名：region 码 → Intl.DisplayNames（AC-N2）。
// ============================================================

import { useTranslation } from 'react-i18next'

import CountryBars from './charts/CountryBars'
import { countryName, intNum, money, moneyWhole, nativeMoney } from '../../dashboard/format'

/**
 * @param {{countries: {table: Array, bars: Array}, fmt: object}} props
 */
export default function CountryCard({ countries, fmt }) {
  const { t } = useTranslation()
  const unknownLabel = t('dashboard.unknownCountry')
  const label = (key) =>
    key === '__other'
      ? t('dashboard.other', { n: Math.max(0, countries.table.length - 9) })
      : countryName(key, fmt, unknownLabel)

  if (!countries.table.length) {
    return (
      <section className="card">
        <div className="cardhead">
          <h2>{t('dashboard.countryTitle')}</h2>
          <span className="sub">{t('dashboard.countrySub')}</span>
        </div>
        <div className="chartbox">
          <div className="empty">{t('dashboard.empty')}</div>
        </div>
      </section>
    )
  }

  const barRows = countries.bars.map((r) => ({
    label: label(r.key),
    usd: Number(r.usd), // 几何缩放专用（约束 3）
    usdDisplay: moneyWhole(fmt, r.usd),
    ordersDisplay: intNum(fmt, r.orders),
    byCurrency: r.by_currency.map((bc) => ({ currency: bc.currency, display: nativeMoney(fmt, bc.amount) })),
  }))

  return (
    <section className="card">
      <div className="cardhead">
        <h2>{t('dashboard.countryTitle')}</h2>
        <span className="sub">{t('dashboard.countrySub')}</span>
      </div>
      <div className="two">
        <CountryBars
          rows={barRows}
          ariaLabel={t('dashboard.countryTitle')}
          usdLabel={t('dashboard.hEstUsd')}
        />
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>{t('dashboard.hCountry')}</th>
                <th>{t('dashboard.hCurAmount')}</th>
                <th className="num">{t('dashboard.hEstUsd')}</th>
                <th className="num">{t('dashboard.hShare')}</th>
              </tr>
            </thead>
            <tbody>
              {countries.table.map((r) => (
                <tr key={r.key}>
                  <td>{countryName(r.key, fmt, unknownLabel)}</td>
                  <td>
                    {r.by_currency
                      .map((bc) => `${bc.currency} ${nativeMoney(fmt, bc.amount)}`)
                      .join(' · ') || '—'}
                  </td>
                  <td className="num">{money(fmt, r.usd)}</td>
                  <td className="num">{`${r.share}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
