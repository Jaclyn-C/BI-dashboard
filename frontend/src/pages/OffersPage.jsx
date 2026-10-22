// ============================================================
// OffersPage.jsx — Offer 管理页（REQ-20261022-02 §1.1，admin+ 可达）
// 全部上游合作 offer 卡片，分「在用」「全部可选」两板块，在用项在
// 全部板块带「在用」标记。数据为本系统自有配置（GET /offers，上游
// 接口不提供）；前端零运算：分成直接用后端预格式百分比字符串拼 %。
// ============================================================

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import useAuth from '../auth/useAuth'
import usePageTitle from '../utils/usePageTitle'
import { listOffers } from '../api/offers'
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

  const reload = useCallback(async () => {
    setLoadError(false)
    try {
      const body = await listOffers()
      setOffers(body.offers)
    } catch (err) {
      setLoadError(true)
    }
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  const inUse = offers ? offers.filter((o) => o.in_use) : []

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
        </div>
      </div>
    </div>
  )
}
