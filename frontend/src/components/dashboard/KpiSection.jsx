// ============================================================
// KpiSection.jsx — KPI 七卡（HTML:278-314/1312-1351，AC-K1–K8）
// B1 降级（DESIGN §6.8）：2/3 卡不出金额——值 –、aux 待规则确认、置灰；
// hero aux 附 kpiGrossNote 毛额标注（AC-K1）。金额全部来自后端字符串。
// ============================================================

import { useTranslation } from 'react-i18next'

import { countryName, dayLabel, intNum, money } from '../../dashboard/format'

function Tile({ label, value, aux, pending }) {
  // 长金额自动缩字号（仅取字符串长度，不做任何金额运算）
  const long = String(value ?? '').length >= 9
  return (
    <div className={`card tile${pending ? ' pending' : ''}`}>
      <div className="label">{label}</div>
      <div className={`value${long ? ' small' : ''}`}>{value}</div>
      {aux ? <div className="aux">{aux}</div> : null}
    </div>
  )
}

/**
 * @param {{kpis: object, fmt: object, range: {from: string, to: string}}} props
 */
export default function KpiSection({ kpis, fmt, range }) {
  const { t } = useTranslation()
  if (!kpis) return null

  const heroAux = [
    t('dashboard.kpiTotalAux', {
      o: money(fmt, kpis.orders_gross_usd),
      a: money(fmt, kpis.ad_total),
      from: dayLabel(fmt, range.from),
      to: dayLabel(fmt, range.to),
    }),
    t('dashboard.kpiGrossNote'),
  ].join(' · ')

  return (
    <section className="kpis">
      <div className="card tile hero">
        <div className="label">{t('dashboard.kpiTotal')}</div>
        <div className={`value${String(money(fmt, kpis.total_revenue)).length >= 10 ? ' small' : ''}`}>
          {money(fmt, kpis.total_revenue)}
        </div>
        <div className="aux">{heroAux}</div>
      </div>
      <Tile
        label={t('dashboard.kpiOrderRevName')}
        value="–"
        aux={t('dashboard.pendingRule')}
        pending
      />
      <Tile
        label={t('dashboard.kpiExcludedRevName')}
        value="–"
        aux={t('dashboard.pendingRule')}
        pending
      />
      <Tile
        label={t('dashboard.kpiAdRev')}
        value={money(fmt, kpis.ad_total)}
        aux={t('dashboard.kpiAdRevAux', { n: intNum(fmt, kpis.ad_days_reported) })}
      />
      <Tile label={t('dashboard.kpiGross')} value={money(fmt, kpis.gross_usd)} aux={t('dashboard.kpiGrossAux')} />
      <Tile
        label={t('dashboard.kpiOrders')}
        value={intNum(fmt, kpis.orders_completed)}
        aux={
          kpis.orders_returned > 0
            ? t('dashboard.plusReturned', { n: intNum(fmt, kpis.orders_returned) })
            : t('dashboard.noReturns')
        }
      />
      <Tile
        label={t('dashboard.kpiCountries')}
        value={intNum(fmt, kpis.countries)}
        aux={
          kpis.top_country
            ? t('dashboard.topCountry', {
                n: countryName(kpis.top_country, fmt, t('dashboard.unknownCountry')),
              })
            : ''
        }
      />
    </section>
  )
}
