// ============================================================
// KpiSection.jsx — KPI 卡组（REQ-20261014-01 口径，替代 AC-K1–K8 旧七卡）
// 11 张金额/计数卡 + 国家数；每张卡右上角灰色「?」，悬停/聚焦显示含义与
// 计算公式（i18n kpiXxxHelp，文案取自需求 §五的「? 文案」）。
// 数据集切换：不适用卡片的值由后端置 null → 本组件直接不渲染（前端零
// 口径判断）。金额全部来自后端字符串（零金额运算，约束 3）。
// ============================================================

import { useTranslation } from 'react-i18next'

import { countryName, intNum, money } from '../../dashboard/format'

function HelpDot({ help }) {
  const { t } = useTranslation()
  return (
    <span className="infodot">
      <button type="button" className="dot" aria-label={t('dashboard.kpiHelpAria')}>
        ?
      </button>
      <span className="helptip" role="tooltip">
        {t(help)}
      </span>
    </span>
  )
}

function Tile({ label, value, aux, help }) {
  // 长金额自动缩字号（仅取字符串长度，不做任何金额运算）
  const long = String(value ?? '').length >= 9
  return (
    <div className="card tile">
      <div className="label-row">
        <div className="label">{label}</div>
        {help ? <HelpDot help={help} /> : null}
      </div>
      <div className={`value${long ? ' small' : ''}`}>{value}</div>
      {aux ? <div className="aux">{aux}</div> : null}
    </div>
  )
}

/**
 * @param {{kpis: object, fmt: object}} props
 */
export default function KpiSection({ kpis, fmt }) {
  const { t } = useTranslation()
  if (!kpis) return null

  const ordersAux = t('dashboard.kpiOrdersAux', {
    n: intNum(fmt, kpis.orders_completed),
    m: intNum(fmt, kpis.orders_returned),
    k: intNum(fmt, kpis.no_usd_order_count),
  })

  return (
    <section className="kpis">
      <Tile
        label={t('dashboard.kpiOrdersTotal')}
        value={intNum(fmt, kpis.orders_total)}
        aux={ordersAux}
        help="dashboard.kpiOrdersTotalHelp"
      />
      <Tile
        label={t('dashboard.kpiTotalAmount')}
        value={money(fmt, kpis.total_usd)}
        help="dashboard.kpiTotalAmountHelp"
      />
      <Tile
        label={t('dashboard.kpiMyShare')}
        value={money(fmt, kpis.my_share_usd)}
        help="dashboard.kpiMyShareHelp"
      />
      {kpis.supplier_payable_usd != null ? (
        <Tile
          label={t('dashboard.kpiPayable')}
          value={money(fmt, kpis.supplier_payable_usd)}
          help="dashboard.kpiPayableHelp"
        />
      ) : null}
      {kpis.supplier_paid_usd != null ? (
        <Tile
          label={t('dashboard.kpiPaid')}
          value={money(fmt, kpis.supplier_paid_usd)}
          help="dashboard.kpiPaidHelp"
        />
      ) : null}
      {kpis.hidden_saving_usd != null ? (
        <Tile
          label={t('dashboard.kpiHidden')}
          value={money(fmt, kpis.hidden_saving_usd)}
          help="dashboard.kpiHiddenHelp"
        />
      ) : null}
      {kpis.net_expected_usd != null ? (
        <Tile
          label={t('dashboard.kpiNetExpected')}
          value={money(fmt, kpis.net_expected_usd)}
          help="dashboard.kpiNetExpectedHelp"
        />
      ) : null}
      {kpis.net_actual_usd != null ? (
        <Tile
          label={t('dashboard.kpiNetActual')}
          value={money(fmt, kpis.net_actual_usd)}
          help="dashboard.kpiNetActualHelp"
        />
      ) : null}
      <Tile
        label={t('dashboard.kpiRefunded')}
        value={money(fmt, kpis.refunded_usd)}
        help="dashboard.kpiRefundedHelp"
      />
      {kpis.included != null ? (
        <Tile
          label={t('dashboard.kpiIncludedCard')}
          value={money(fmt, kpis.included.usd)}
          aux={t('dashboard.kpiCountUnit', { n: intNum(fmt, kpis.included.count) })}
          help="dashboard.kpiIncludedCardHelp"
        />
      ) : null}
      {kpis.excluded != null ? (
        <Tile
          label={t('dashboard.kpiExcludedCard')}
          value={money(fmt, kpis.excluded.usd)}
          aux={t('dashboard.kpiCountUnit', { n: intNum(fmt, kpis.excluded.count) })}
          help="dashboard.kpiExcludedCardHelp"
        />
      ) : null}
      <Tile
        label={t('dashboard.kpiAdRev')}
        value={money(fmt, kpis.ad_total)}
        aux={t('dashboard.kpiAdRevAux', { n: intNum(fmt, kpis.ad_days_reported) })}
        help="dashboard.kpiAdRevHelp"
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
