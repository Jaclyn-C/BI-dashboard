// ============================================================
// Sidebar.jsx — 侧边栏导航（REQ-20261022-01 §1.1，DESIGN §1）
// 登录后页面左侧固定导航；条目按角色过滤（与 App.jsx RequireRole
// 路由守卫同一套可见性：admin+ 全见、customer 仅客户视图）。
// 当前项精确匹配路径（/ 前缀匹配会误命中全站，禁用 NavLink 默认）。
// 极简文字风：无图标，当前项文字强调 + 左侧标记线（红线 13）。
// ============================================================

import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'

import useAuth from '../auth/useAuth'

// 条目顺序固定：数据看板 → 客户订单 → Offer 管理 → 用户管理
// （REQ-20261022-01 §1.1 + REQ-20261022-02 §1.1/§1.3）
const ITEMS = [
  { key: 'nav.dashboard', to: '/' },
  { key: 'nav.customer', to: '/customer' },
  { key: 'nav.offers', to: '/offers' },
  { key: 'nav.users', to: '/users' },
]

// 与 App.jsx 路由守卫同源的可见性映射；pending 不接外壳（PendingPage 无侧边栏）
// Offer 管理仅 admin+（分成条款属内部商业数据，REQ-20261022-02）
const ALLOWED = {
  super_admin: ['/', '/customer', '/offers', '/users'],
  admin: ['/', '/customer', '/offers', '/users'],
  customer: ['/customer'],
}

export default function Sidebar() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { pathname } = useLocation()

  const items = ITEMS.filter((item) => (ALLOWED[user?.role] || []).includes(item.to))

  return (
    <nav className="sidebar" aria-label={t('nav.label')}>
      {items.map((item) => {
        const active = pathname === item.to
        return (
          <Link
            key={item.to}
            to={item.to}
            className={active ? 'sideitem active' : 'sideitem'}
            aria-current={active ? 'page' : undefined}
          >
            {t(item.key)}
          </Link>
        )
      })}
    </nav>
  )
}
