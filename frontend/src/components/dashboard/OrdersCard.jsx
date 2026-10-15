// ============================================================
// OrdersCard.jsx — 订单明细卡（HTML:379-394/1804-1876，AC-O1–O9）
// 三筛选（类别 REQ-20261014-01 §六 / 币种动态 / 状态三档）+ 四列排序
// （aria-sort + ▲/▼）+ 25/页分页（‹ › + pageOf）。空态区分：区间无订单
// empty / 筛选无匹配 noMatch（AC-O6）。类别列显示已计入/被剔除；
// 状态 chip ✓/↩ 前缀（AC-O7）；剔除行斜纹（AC-O8）。
// 排序/筛选/翻页状态由 DashboardPage 持有（本组件纯受控）。
// ============================================================

import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { countryName, intNum, money, nativeMoney } from '../../dashboard/format'

const classLabel = (t, value) => {
  if (value === 'included') return t('dashboard.clIncluded')
  if (value === 'excluded') return t('dashboard.clExcluded')
  return '—'
}

/**
 * @param {{data: object|null, fmt: object,
 *          filters: {klass: string, currency: string, status: string},
 *          classValue: string, classLocked: boolean,
 *          sort: {key: string, dir: string}, page: number,
 *          onFilterChange: (patch: object) => void,
 *          onSort: (key: string) => void, onPageChange: (page: number) => void,
 *          hideClass?: boolean, title?: string, sub?: string}} props
 * hideClass=true → 客户视图变体（REQ-20261015-02）：无类别列、无类别筛选；
 * title/sub 可覆盖默认标题与副标题。
 */
export default function OrdersCard({ data, fmt, filters, classValue, classLocked, sort, page, onFilterChange, onSort, onPageChange, hideClass = false, title, sub }) {
  const { t } = useTranslation()
  const [pageInput, setPageInput] = useState('')
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
              {hideClass ? null : <th>{t('dashboard.hClass')}</th>}
              <th>{t('dashboard.hStatus')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.order_id} className={o.order_class === 'excluded' ? 'row-excluded' : undefined}>
                <td className="mono">{o.order_id}</td>
                <td>{o.create_time}</td>
                <td>{countryName(o.country_key, fmt, unknownLabel)}</td>
                <td>{o.currency}</td>
                <td className="num">{nativeMoney(fmt, o.amount)}</td>
                <td className="num">{o.usd == null ? '—' : money(fmt, o.usd)}</td>
                {hideClass ? null : <td className="muted">{classLabel(t, o.order_class)}</td>}
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

  // 页码跳转：输入 → 钳制到 [1, pages] → 翻页（无效输入忽略）
  const jumpToPage = () => {
    const target = Number.parseInt(pageInput, 10)
    if (Number.isFinite(target)) {
      const clamped = Math.min(Math.max(1, target), pages)
      if (clamped !== safePage) onPageChange(clamped)
    }
    setPageInput('')
  }

  return (
    <section className="card">
      <div className="cardhead">
        <h2>{title || t('dashboard.ordersTitle')}</h2>
        <span className="sub">
          {sub || t('dashboard.ordersSub', { n: intNum(fmt, total), m: intNum(fmt, totalInRange) })}
        </span>
        <div className="right">
          {hideClass ? null : (
            <>
              <label className="visually-hidden" htmlFor="typeFilter">
                {t('dashboard.hClass')}
              </label>
              <select
                className="field"
                id="typeFilter"
                value={classValue}
                disabled={classLocked}
                onChange={(e) => onFilterChange({ klass: e.target.value })}
              >
                <option value="all">{t('dashboard.fAllClasses')}</option>
                <option value="included">{t('dashboard.clIncluded')}</option>
                <option value="excluded">{t('dashboard.clExcluded')}</option>
              </select>
            </>
          )}
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
            <span className="pager">
              <input
                className="pageinput"
                type="text"
                inputMode="numeric"
                aria-label={t('dashboard.pageInputAria')}
                placeholder={String(safePage)}
                value={pageInput}
                onChange={(e) => setPageInput(e.target.value.replace(/[^\d]/g, ''))}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') jumpToPage()
                }}
              />
              <span className="pagerof">
                {t('dashboard.pageIndicator', { n: intNum(fmt, pages) })}
              </span>
            </span>
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
