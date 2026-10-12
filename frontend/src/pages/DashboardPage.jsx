// DashboardPage — 受保护占位页（DESIGN §5.1）：欢迎语 + 语言切换 + 退出；
// 看板本体归后续需求。

import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import useAuth from '../auth/useAuth'
import LangToggle from '../components/auth/LangToggle'
import usePageTitle from '../utils/usePageTitle'

export default function DashboardPage() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  usePageTitle('common.pageTitle.dashboard')

  function handleLogout() {
    // 登出 = 清 sessionStorage token + 跳登录（DESIGN §3.5，无服务端登出）；
    // 登录记忆（localStorage）不清（记住的是输入项，不是会话，§5.6）
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="dashpage">
      <h1>{t('common.appName')}</h1>
      <p className="sub">
        {t('dashboard.welcome', { nickname: user?.nickname ?? '', email: user?.email ?? '' })}
      </p>
      <p className="sub">{t('dashboard.placeholder')}</p>
      <div className="row">
        <button className="btn-filled" type="button" onClick={handleLogout}>
          {t('dashboard.signOut')}
        </button>
      </div>
      <LangToggle />
    </div>
  )
}
