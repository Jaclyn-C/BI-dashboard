// App — 路由表 + RequireAuth 守卫（DESIGN §2.3）

import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import useAuth from './auth/useAuth'
import CalculatorWidget from './components/Calculator'
import DashboardPage from './pages/DashboardPage'
import CustomerViewPage from './pages/CustomerViewPage'
import OffersPage from './pages/OffersPage'
import PendingPage from './pages/PendingPage'
import UsersPage from './pages/UsersPage'
import ForgotPage from './pages/auth/ForgotPage'
import LoginPage from './pages/auth/LoginPage'
import RegisterPage from './pages/auth/RegisterPage'

function RequireAuth({ children }) {
  const { user, booting } = useAuth()
  const location = useLocation()
  if (booting) return null // 启动恢复会话期间不闪跳（AC-L3）
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return children
}

/** 已登录访问认证页 → 跳 '/'；booting 期间等待会话恢复结果，避免误跳 */
function RedirectIfAuthed({ children }) {
  const { user, booting } = useAuth()
  if (booting) return null
  if (user) return <Navigate to="/" replace />
  return children
}

/** 角色归属主页（REQ-20261020-01）：pending→提示页，customer→客户视图，其余→看板 */
function homePathFor(role) {
  if (!role || role === 'pending') return '/pending'
  if (role === 'customer') return '/customer'
  return '/'
}

/** 角色守卫：角色不在 allow 内 → 跳该角色主页（不渲染受限内容） */
function RequireRole({ allow, children }) {
  const { user } = useAuth()
  if (!user) return children // 未登录由外层 RequireAuth 处理
  if (!allow.includes(user.role)) return <Navigate to={homePathFor(user.role)} replace />
  return children
}

/** /pending 专属：非 pending 角色跳自己主页。role 未知（如后端旧版本）按 pending 渲染，防重定向死循环 */
function PendingOnly({ children }) {
  const { user } = useAuth()
  if (user && user.role && user.role !== 'pending') {
    return <Navigate to={homePathFor(user.role)} replace />
  }
  return children
}

export default function App() {
  return (
    <>
      {/* 悬浮计算器挂在路由外（REQ-20261023-01）：不绑定页面，切换路由不消失 */}
      <CalculatorWidget />
      <Routes>
      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <LoginPage />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/register"
        element={
          <RedirectIfAuthed>
            <RegisterPage />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/forgot"
        element={
          <RedirectIfAuthed>
            <ForgotPage />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <RequireRole allow={['admin', 'super_admin']}>
              <DashboardPage />
            </RequireRole>
          </RequireAuth>
        }
      />
      <Route
        path="/customer"
        element={
          <RequireAuth>
            <RequireRole allow={['admin', 'super_admin', 'customer']}>
              <CustomerViewPage />
            </RequireRole>
          </RequireAuth>
        }
      />
      <Route
        path="/offers"
        element={
          <RequireAuth>
            <RequireRole allow={['admin', 'super_admin']}>
              <OffersPage />
            </RequireRole>
          </RequireAuth>
        }
      />
      <Route
        path="/users"
        element={
          <RequireAuth>
            <RequireRole allow={['admin', 'super_admin']}>
              <UsersPage />
            </RequireRole>
          </RequireAuth>
        }
      />
      <Route
        path="/pending"
        element={
          <RequireAuth>
            <PendingOnly>
              <PendingPage />
            </PendingOnly>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
