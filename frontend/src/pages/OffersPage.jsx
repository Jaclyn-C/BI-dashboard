// ============================================================
// OffersPage.jsx — Offer 管理页（REQ-20261022-02 §1.1/§1.5，admin+ 可达）
// 三板块：「在用」「全部可选」「供应商收益」。收益 = 后端按 offer 分成
// 比例算好的真值字符串（Σ已计入订单 USD × 比例，真实/mock 订单分表聚合），
// 前端零金额运算：只按选择过滤展示，不做任何求和。
// ============================================================

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import useAuth from '../auth/useAuth'
import usePageTitle from '../utils/usePageTitle'
import { getOfferEarnings, listOffers } from '../api/offers'
import AppBar from '../components/dashboard/AppBar'
import Sidebar from '../components/Sidebar'

function OfferCard({ offer, showBadge }) {
  const { t } = useTranslation()
  return (
    <div className="offer-card">
      <div className="offer-head">
        <div className="offer-title">
          <div className="offer-name">{offer.name}</div>
          <div className="offer-code">{offer.code}</div>
        </div>
        {showBadge && offer.in_use ? <span className="offer-badge">{t('offers.badgeInUse')}</span> : null}
      </div>
      <div className="offer-share">
        {offer.supplier_share_pct}
        <span className="pct">%</span>
      </div>
      <div className="offer-share-label">{t('offers.shareLabel')}</div>
      {offer.description ? <p className="offer-desc">{offer.description}</p> : null}
    </div>
  )
}

export default function OffersPage() {
  const { t } = useTranslation()
  const { logout } = useAuth()
  usePageTitle('common.pageTitle.offers')

  const [offers, setOffers] = useState(null)
  const [loadError, setLoadError] = useState(false)

  // 供应商收益（§1.5）：后端算好，前端只做选择过滤（零金额运算）
  const [earnings, setEarnings] = useState(null)
  const [earnError, setEarnError] = useState(false)
  // 选择器：null = 全部（默认，含合计行）；Set = 选中的 offer code 子集
  const [selected, setSelected] = useState(null)

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

  const inUse = offers ? offers.filter((o) => o.in_use) : []

  /** 切换选中 offer：从全集起切，全选时回落「全部」（null），取消到空集允许（显示空态） */
  const toggleEarning = (code) => {
    if (!earnings) return
    const next = new Set(selected ?? earnings.earnings.map((e) => e.code))
    if (next.has(code)) next.delete(code)
    else next.add(code)
    setSelected(next.size === earnings.earnings.length ? null : next)
  }

  const visibleEarnings = earnings
    ? selected
      ? earnings.earnings.filter((e) => selected.has(e.code))
      : earnings.earnings
    : []

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
          {offers === null && !loadError ? (
            <div className="statusline">
              <span className="dot" />
              <span>{t('offers.loading')}</span>
            </div>
          ) : null}
          {offers !== null ? (
            <>
              <section className="offer-sec">
                <h2>{t('offers.secInUse')}</h2>
                {inUse.length ? (
                  <div className="offer-grid">
                    {inUse.map((offer) => (
                      <OfferCard key={offer.id} offer={offer} showBadge={false} />
                    ))}
                  </div>
                ) : (
                  <p className="offer-empty">{t('offers.emptyInUse')}</p>
                )}
              </section>
              <section className="offer-sec">
                <h2>{t('offers.secAll')}</h2>
                {offers.length ? (
                  <div className="offer-grid">
                    {offers.map((offer) => (
                      <OfferCard key={offer.id} offer={offer} showBadge />
                    ))}
                  </div>
                ) : (
                  <p className="offer-empty">{t('offers.emptyAll')}</p>
                )}
              </section>
            </>
          ) : null}
          <section className="offer-sec">
            <h2>{t('offers.secEarnings')}</h2>
            {earnError ? (
              <div className="banner error" role="alert">
                <div className="body">{t('offers.loadFailed')}</div>
              </div>
            ) : null}
            {earnings === null && !earnError ? (
              <div className="statusline">
                <span className="dot" />
                <span>{t('offers.loading')}</span>
              </div>
            ) : null}
            {earnings ? (
              <>
                <div className="earn-select">
                  <button
                    type="button"
                    className={selected === null ? 'earn-chip on' : 'earn-chip'}
                    onClick={() => setSelected(null)}
                  >
                    {t('offers.earnSelectAll')}
                  </button>
                  {earnings.earnings.map((e) => (
                    <button
                      key={e.code}
                      type="button"
                      className={
                        selected === null || selected.has(e.code) ? 'earn-chip on' : 'earn-chip'
                      }
                      onClick={() => toggleEarning(e.code)}
                    >
                      {e.code}
                    </button>
                  ))}
                </div>
                {selected === null ? (
                  <div className="earn-total">
                    <span className="earn-total-label">{t('offers.earnTotal')}</span>
                    <span className="earn-total-value">{earnings.total_supplier_earnings_usd}</span>
                    <span className="earn-total-sub">
                      {t('offers.earnTotalMeta', {
                        n: earnings.total_order_count,
                        m: earnings.total_order_usd,
                      })}
                    </span>
                  </div>
                ) : null}
                {visibleEarnings.length ? (
                  <div className="offer-grid">
                    {visibleEarnings.map((e) => (
                      <div key={e.code} className="offer-card">
                        <div className="offer-head">
                          <div className="offer-title">
                            <div className="offer-name">{e.name}</div>
                            <div className="offer-code">{e.code}</div>
                          </div>
                          <span className="offer-badge">{`${e.supplier_share_pct}%`}</span>
                        </div>
                        <div className="offer-share">{e.supplier_earnings_usd}</div>
                        <div className="offer-share-label">{t('offers.earnAmount')}</div>
                        <p className="offer-desc">
                          {t('offers.earnMeta', { n: e.order_count, m: e.order_total_usd })}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="offer-empty">{t('offers.emptyEarnings')}</p>
                )}
                <p className="earn-note">{t('offers.earnNote')}</p>
              </>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  )
}
