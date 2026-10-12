// ============================================================
// AuthProvider.jsx — 会话状态（DESIGN §2.3）
// login/logout；启动时用 GET /auth/me 恢复会话（token 在 sessionStorage）。
// ============================================================

import { useCallback, useEffect, useMemo, useState } from 'react'

import * as authApi from '../api/auth'
import { clearToken, getToken, setToken } from '../api/client'
import AuthContext from './AuthContext'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [booting, setBooting] = useState(true)

  // 启动恢复：有 token 才调 me；401 由 client 统一处理（清 token + 跳 /login?expired=1）
  useEffect(() => {
    let cancelled = false
    async function boot() {
      if (!getToken()) {
        setBooting(false)
        return
      }
      try {
        const meUser = await authApi.me()
        if (!cancelled) setUser(meUser)
      } catch (err) {
        // token 无效/过期：client 已清理并跳转，这里仅复位状态
        if (!cancelled) setUser(null)
      } finally {
        if (!cancelled) setBooting(false)
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [])

  /** 保存登录态响应（login / register 自动登录共用形状） */
  const saveSession = useCallback((payload) => {
    setToken(payload.access_token)
    setUser(payload.user)
    return payload.user
  }, [])

  const login = useCallback(
    async ({ email, password }) => saveSession(await authApi.login({ email, password })),
    [saveSession],
  )

  const registerAndLogin = useCallback(
    async ({ email, nickname, password, code }) =>
      saveSession(await authApi.register({ email, nickname, password, code })),
    [saveSession],
  )

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, booting, login, registerAndLogin, logout }),
    [user, booting, login, registerAndLogin, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
