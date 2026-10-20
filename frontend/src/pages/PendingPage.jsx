// ============================================================
// PendingPage.jsx — 待分配提示页（REQ-20261020-01 §1.2）
// 新注册用户唯一可见页面：一句提示 + 退出登录，别无他物。
// ============================================================

import { useTranslation } from 'react-i18next'

import useAuth from '../auth/useAuth'
import usePageTitle from '../utils/usePageTitle'

export default function PendingPage() {
  const { t } = useTranslation()
  const { logout } = useAuth()
  usePageTitle('common.pageTitle.pending')

  return (
    <div className="authpage">
      <div className="logincard pendingcard">
        <h2>{t('pending.title')}</h2>
        <p className="loginsub">{t('pending.hint')}</p>
        <button type="button" className="chip" onClick={logout}>
          {t('dashboard.signOut')}
        </button>
      </div>
    </div>
  )
}
