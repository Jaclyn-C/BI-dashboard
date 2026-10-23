// ============================================================
// OffersPage.jsx — Offer 管理页（REQ-20261022-02 §1.1/§1.5/§1.6，admin+）
// 布局 v2（2026-10-23 用户定稿）：收益总览条置顶（在用 offer 合计，
// 后端算好、前端零金额运算）+ 统一「Offer 一览」（在用/全部筛选、
// 列表/卡片切换、默认列表；在用行带收益列，不在用显示 —）。
// 数据来源等说明类文案不上界面（字段留库，仅不渲染）。
// ============================================================

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import useAuth from '../auth/useAuth'
import usePageTitle from '../utils/usePageTitle'
import { getOfferEarnings, listOffers } from '../api/offers'
import { buildFormatters, intNum } from '../dashboard/format'
import AppBar from '../components/dashboard/AppBar'
import Sidebar from '../components/Sidebar'

export default function OffersPage() {
  const { t, i18n } = useTranslation()
  const { logout } = useAuth()
  usePageTitle('common.pageTitle.offers')

  const [offers, setOffers] = useState(null)
  const [loadError, setLoadError] = useState(false)
  const [earnings, setEarnings] = useState(null)
  const [earnError, setEarnError] = useState(false)
  const [scope, setScope] = useState('inUse') // 'inUse' | 'all'（默认在用，与收益条同口径）
  const [view, setView] = useState('list') // 'list' | 'card'（默认列表，信息密度高）

  const locale = i18n.language === 'zh' ? 'zh-CN' : 'en-US'
  const fmt = useMemo(() => buildFormatters(locale), [locale])

  const reload = useCallback(async () => {
    setLoadError(false)
    try {
      const body = await listOffers()
      setOffers(body.offers)
    } catch (err) {
      setLoadError(true)
    }
  }, [])

  const reloadEarnings = useCallback(async () => {
    setEarnError(false)
    try {
      const body = await getOfferEarnings()
      setEarnings(body)
    } catch (err) {
      setEarnError(true)
    }
  }, [])

  useEffect(() => {
    reload()
    reloadEarnings()
  }, [reload, reloadEarnings])

  const earnMap = useMemo(
    () => (earnings ? new Map(earnings.earnings.map((e) => [e.code, e])) : null),
    [earnings],
  )
  const shown = useMemo(
    () => (offers ? (scope === 'inUse' ? offers.filter((o) => o.in_use) : offers) : []),
    [offers, scope],
  )

  const segBtn = (active) => `seg-btn${active ? ' on' : ''}`

  return (
    <div className="shell">
      <Sidebar />
      <div className="shell-main">
        <div className="wrap">
          <AppBar sub={t('offers.subBar')} onLogout={logout} />
          {loadError ? (
            <div className="banner error" role="alert">
              <div className="body">{t('offers.loadFailed')}</div>
            </div>
          ) : null}
          {earnError ? (
            <div className="banner error" role="alert">
              <div className="body">{t('offers.loadFailed')}</div>
            </div>
          ) : null}
          {offers === null && !loadError ? (
            <div className="statusline">
              <span className="dot" />
              <span>{t('offers.loading')}</span>
            </div>
          ) : null}

          {earnings ? (
            <div className="earn-total">
              <span className="earn-total-label">{t('offers.earnTotal')}</span>
              <span className="earn-total-value">{earnings.total_supplier_earnings_usd}</span>
              <span className="earn-total-sub">
                {t('offers.earnTotalMeta', {
                  n: intNum(fmt, earnings.total_order_count),
                  m: earnings.total_order_usd,
                })}
              </span>
              <span className="earn-total-note">{t('offers.earnNote')}</span>
            </div>
          ) : null}

          {offers !== null ? (
            <section className="offer-sec">
              <div className="offer-headrow">
                <h2>{t('offers.listTitle')}</h2>
                <div className="offer-controls">
                  <div className="seg" role="group" aria-label={t('offers.scopeLabel')}>
                    <button
                      type="button"
                      className={segBtn(scope === 'inUse')}
                      onClick={() => setScope('inUse')}
                    >
                      {t('offers.scopeInUse')}
                    </button>
                    <button type="button" className={segBtn(scope === 'all')} onClick={() => setScope('all')}>
                      {t('offers.scopeAll')}
                    </button>
                  </div>
                  <div className="seg" role="group" aria-label={t('offers.viewLabel')}>
                    <button type="button" className={segBtn(view === 'list')} onClick={() => setView('list')}>
                      {t('offers.viewList')}
                    </button>
                    <button type="button" className={segBtn(view === 'card')} onClick={() => setView('card')}>
                      {t('offers.viewCard')}
                    </button>
                  </div>
                </div>
              </div>

              {shown.length === 0 ? (
                <p className="offer-empty">{t('offers.emptyList')}</p>
              ) : view === 'list' ? (
                <div className="tablewrap">
                  <table className="offer-table">
                    <thead>
                      <tr>
                        <th>{t('offers.colStatus')}</th>
                        <th>{t('offers.colUpstream')}</th>
                        <th className="num">{t('offers.colShare')}</th>
                        <th className="num">{t('offers.colOrders')}</th>
                        <th className="num">{t('offers.colOrderTotal')}</th>
                        <th className="num">{t('offers.colEarnings')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shown.map((o) => {
                        const e = earnMap ? earnMap.get(o.code) : null
                        return (
                          <tr key={o.id}>
                            <td>
                              {o.in_use ? (
                                <span className="offer-badge">{t('offers.badgeInUse')}</span>
                              ) : (
                                <span className="offer-tag">{t('offers.stAvailable')}</span>
                              )}
                            </td>
                            <td>
                              <div className="offer-name">{o.name}</div>
                              <div className="offer-code">{o.code}</div>
                            </td>
                            <td className="num">{`${o.supplier_share_pct}%`}</td>
                            <td className="num">{e ? intNum(fmt, e.order_count) : '—'}</td>
                            <td className="num">{e ? e.order_total_usd : '—'}</td>
                            <td className="num offer-earn">{e ? e.supplier_earnings_usd : '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="offer-grid">
                  {shown.map((o) => {
                    const e = earnMap ? earnMap.get(o.code) : null
                    return (
                      <div key={o.id} className="offer-card">
                        <div className="offer-head">
                          <div className="offer-title">
                            <div className="offer-name">{o.name}</div>
                            <div className="offer-code">{o.code}</div>
                          </div>
                          {o.in_use ? (
                            <span className="offer-badge">{t('offers.badgeInUse')}</span>
                          ) : (
                            <span className="offer-tag">{t('offers.stAvailable')}</span>
                          )}
                        </div>
                        <div className="offer-share">
                          {o.supplier_share_pct}
                          <span className="pct">%</span>
                        </div>
                        <div className="offer-share-label">{t('offers.shareLabel')}</div>
                        {e ? (
                          <div className="offer-earn-line">
                            {t('offers.earnShort')} {e.supplier_earnings_usd}
                          </div>
                        ) : null}
                      </div>
                    )
                  })}
                </div>
              )}
            </section>
          ) : null}
        </div>
      </div>
    </div>
  )
}
