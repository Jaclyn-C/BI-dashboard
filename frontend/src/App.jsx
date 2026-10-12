// App — 路由表 + RequireAuth 守卫（DESIGN §2.3）

import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import useAuth from './auth/useAuth'
import DashboardPage from './pages/DashboardPage'
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

export default function App() {
  return (
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
            <DashboardPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
