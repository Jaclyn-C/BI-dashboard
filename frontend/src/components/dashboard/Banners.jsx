// ============================================================
// Banners.jsx — 五类横幅（HTML:1289-1310，AC-S5/S7/S9/C8）
// 错误（含重试=重载）、同步失败（重试=POST /sync）、广告不可用、
// 窗口截断（列出截断日期）、缺美元金额币种。
// ⚠(⚠) 字形照搬参考实现（AC-V3 白名单）。
// ============================================================

import { useTranslation } from 'react-i18next'

function WarnBanner({ title, body, action, onAction, actionLabel }) {
  return (
    <div className="banner warn" role="alert">
      <span className="ic">{'⚠'}</span>
      <span className="body">
        <span className="t">{title}</span>
        {body}
      </span>
      {action ? (
        <button type="button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  )
}

/**
 * @param {{error: Error|null, syncFailed: boolean, adError: string|null,
 *          truncatedDays: string[], noUsdCurrencies: string[],
 *          onRetryError: () => void, onRetrySync: () => void}} props
 */
export default function Banners({
  error,
  syncFailed,
  adError,
  truncatedDays,
  noUsdCurrencies,
  onRetryError,
  onRetrySync,
}) {
  const { t } = useTranslation()
  const boxes = []

  if (error) {
    boxes.push(
      <div key="error" className="banner error" role="alert">
        <span className="ic">{'⚠'}</span>
        <span className="body">
          <span className="t">{t('dashboard.errTitle')}</span>
          {error.name === 'ApiError' && error.code === 'NETWORK'
            ? t('dashboard.connFailed')
            : error.message || ''}
        </span>
        <button type="button" onClick={onRetryError}>
          {t('dashboard.retry')}
        </button>
      </div>,
    )
  }

  if (syncFailed) {
    boxes.push(
      <WarnBanner
        key="sync"
        title={t('dashboard.upstreamFailTitle')}
        body={t('dashboard.upstreamFailBodySync')}
        action
        onAction={onRetrySync}
        actionLabel={t('dashboard.retry')}
      />,
    )
  }

  if (adError !== null) {
    boxes.push(
      <WarnBanner key="ad" title={t('dashboard.adFailTitle')} body={adError} />,
    )
  }

  if (truncatedDays && truncatedDays.length) {
    boxes.push(
      <WarnBanner
        key="truncated"
        title={t('dashboard.partialTitle')}
        body={`${truncatedDays.join(', ')}${t('dashboard.partialBody')}`}
      />,
    )
  }

  if (noUsdCurrencies && noUsdCurrencies.length) {
    boxes.push(
      <WarnBanner
        key="nousd"
        title={t('dashboard.noRateTitle')}
        body={`${[...noUsdCurrencies].sort().join(', ')}${t('dashboard.noRateBody')}`}
      />,
    )
  }

  if (!boxes.length) return null
  return <div>{boxes}</div>
}
