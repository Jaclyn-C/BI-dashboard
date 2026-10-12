// ============================================================
// OrdersCard.jsx — 订单明细卡（HTML:379-394/1804-1876，AC-O1–O9）
// 三筛选（B1：类别置灰；币种动态；状态三档）+ 四列排序（aria-sort +
// ▲/▼）+ 25/页分页（‹ › + pageOf）。空态区分：区间无订单 empty /
// 筛选无匹配 noMatch（AC-O6）。类别列置灰 classPending（AC-O1）；
// 状态 chip ✓/↩ 前缀（AC-O7）；无剔除行斜纹（AC-O8）。
// 排序/筛选/翻页状态由 DashboardPage 持有（本组件纯受控）。
// ============================================================

import { useTranslation } from 'react-i18next'

import { countryName, intNum, money, nativeMoney } from '../../dashboard/format'

/**
 * @param {{data: object|null, fmt: object,
 *          filters: {currency: string, status: string},
 *          sort: {key: string, dir: string}, page: number,
 *          onFilterChange: (patch: object) => void,
 *          onSort: (key: string) => void, onPageChange: (page: number) => void}} props
 */
export default function OrdersCard({ data, fmt, filters, sort, page, onFilterChange, onSort, onPageChange }) {
  const { t } = useTranslation()
  const unknownLabel = t('dashboard.unknownCountry')

  const sortTh = (label, key, numeric) => {
    const active = sort.key === key
    return (
      <th
        key={key}
        className={`sortable${numeric ? ' num' : ''}`}
        aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
        onClick={() => onSort(key)}
      >
        {label} {active ? <span className="arrow">{sort.dir === 'asc' ? '▲' : '▼'}</span> : null}
      </th>
    )
  }

  const rows = data ? data.rows : []
  const total = data ? data.total : 0
  const totalInRange = data ? data.total_in_range : 0
  const pages = data ? data.pages : 1
  const safePage = data ? data.page : page

  let body
  if (!data) {
    body = <div className="tablewrap" />
  } else if (totalInRange === 0) {
    body = (
      <div className="tablewrap">
        <div className="empty">{t('dashboard.empty')}</div>
      </div>
    )
  } else if (!rows.length) {
    body = (
      <div className="tablewrap">
        <div className="empty">{t('dashboard.noMatch')}</div>
      </div>
    )
  } else {
    body = (
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>{t('dashboard.hOrderId')}</th>
              {sortTh(t('dashboard.hCreateTime'), 'date', false)}
              <th>{t('dashboard.hCountry')}</th>
              {sortTh(t('dashboard.hCurrency'), 'currency', false)}
              {sortTh(t('dashboard.hAmount'), 'amount', true)}
              {sortTh(t('dashboard.hEstUsd'), 'usd', true)}
              <th>{t('dashboard.hClass')}</th>
              <th>{t('dashboard.hStatus')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.order_id}>
                <td className="mono">{o.order_id}</td>
                <td>{o.create_time}</td>
                <td>{countryName(o.country_key, fmt, unknownLabel)}</td>
                <td>{o.currency}</td>
                <td className="num">{nativeMoney(fmt, o.amount)}</td>
                <td className="num">{o.usd == null ? '—' : money(fmt, o.usd)}</td>
                <td className="muted">{t('dashboard.classPending')}</td>
                <td>
                  {o.status === 'returned' ? (
                    <span className="chip-status returned">{`↩ ${t('dashboard.stReturned')}`}</span>
                  ) : (
                    <span className="chip-status completed">{`✓ ${t('dashboard.stCompleted')}`}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const first = total ? (safePage - 1) * (data ? data.page_size : 25) + 1 : 0
  const last = total ? Math.min(total, safePage * (data ? data.page_size : 25)) : 0

  return (
    <section className="card">
      <div className="cardhead">
        <h2>{t('dashboard.ordersTitle')}</h2>
        <span className="sub">{t('dashboard.ordersSub', { n: intNum(fmt, total), m: intNum(fmt, totalInRange) })}</span>
        <div className="right">
          <label className="visually-hidden" htmlFor="typeFilter">
            {t('dashboard.hClass')}
          </label>
          <select className="field" id="typeFilter" disabled value="all" onChange={() => {}}>
            <option value="all">{t('dashboard.fAllClasses')}</option>
            <option value="included">{t('dashboard.clIncluded')}</option>
            <option value="excluded">{t('dashboard.clExcluded')}</option>
          </select>
          <label className="visually-hidden" htmlFor="currencyFilter">
            {t('dashboard.hCurrency')}
          </label>
          <select
            className="field"
            id="currencyFilter"
            value={filters.currency}
            onChange={(e) => onFilterChange({ currency: e.target.value })}
          >
            <option value="all">{t('dashboard.fAllCurrencies')}</option>
            {(data ? data.currencies : []).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <label className="visually-hidden" htmlFor="statusFilter">
            {t('dashboard.hStatus')}
          </label>
          <select
            className="field"
            id="statusFilter"
            value={filters.status}
            onChange={(e) => onFilterChange({ status: e.target.value })}
          >
            <option value="all">{t('dashboard.fAllStatuses')}</option>
            <option value="completed">{t('dashboard.stCompleted')}</option>
            <option value="returned">{t('dashboard.stReturned')}</option>
          </select>
        </div>
      </div>
      {body}
      <div className="tablefoot">
        {total ? (
          <>
            <span>
              {t('dashboard.pageOf', {
                a: intNum(fmt, first),
                b: intNum(fmt, last),
                n: intNum(fmt, total),
              })}
            </span>
            <button
              type="button"
              className="pagebtn"
              aria-label={t('dashboard.prevPage')}
              disabled={safePage <= 1}
              onClick={() => onPageChange(safePage - 1)}
            >
              ‹
            </button>
            <button
              type="button"
              className="pagebtn"
              aria-label={t('dashboard.nextPage')}
              disabled={safePage >= pages}
              onClick={() => onPageChange(safePage + 1)}
            >
              ›
            </button>
          </>
        ) : null}
      </div>
    </section>
  )
}
