// ============================================================
// UsersPage.jsx — 用户管理页（REQ-20261020-01 §1.6，admin+ 可达）
// 列表 + 行内角色操作。前端按等级规则只渲染可操作项（体验层），
// 真正的强制在后端（can_assign_role，REQ §1.5）。
// ============================================================

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import useAuth from '../auth/useAuth'
import usePageTitle from '../utils/usePageTitle'
import { listUsers, updateUserRole } from '../api/users'
import AppBar from '../components/dashboard/AppBar'

// 与后端 role_service 同源的展示用规则（REQ §1.3）
const LEVEL = { super_admin: 3, admin: 2, customer: 1, pending: 0 }
const ASSIGNABLE = ['admin', 'customer', 'pending']
const ROLE_KEY = {
  super_admin: 'users.roleSuperAdmin',
  admin: 'users.roleAdmin',
  customer: 'users.roleCustomer',
  pending: 'users.rolePending',
}
const ACTION_KEY = {
  admin: 'users.setAdmin',
  customer: 'users.setCustomer',
  pending: 'users.revoke',
}

export default function UsersPage() {
  const { t, i18n } = useTranslation()
  const { user: me, logout } = useAuth()
  const navigate = useNavigate()
  usePageTitle('common.pageTitle.users')

  const [users, setUsers] = useState(null)
  const [loadError, setLoadError] = useState(false)
  const [busyId, setBusyId] = useState(null)
  const [actionError, setActionError] = useState(false)

  const locale = i18n.language === 'zh' ? 'zh-CN' : 'en-US'

  const reload = useCallback(async () => {
    setLoadError(false)
    try {
      const body = await listUsers()
      setUsers(body.users)
    } catch (err) {
      setLoadError(true)
    }
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  // 只渲染等级规则允许的操作（后端同规则强制）
  const actionsFor = useCallback(
    (row) => {
      if (!me) return []
      if (row.id === me.id) return []
      if (LEVEL[me.role] <= LEVEL[row.role]) return []
      return ASSIGNABLE.filter(
        (role) => role !== row.role && LEVEL[role] <= LEVEL[me.role],
      )
    },
    [me],
  )

  const handleSetRole = useCallback(
    async (row, role) => {
      setBusyId(row.id)
      setActionError(false)
      try {
        await updateUserRole(row.id, role)
        await reload()
      } catch (err) {
        setActionError(true)
      } finally {
        setBusyId(null)
      }
    },
    [reload],
  )

  const fmtDateTime = (iso) =>
    iso
      ? new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
          new Date(iso),
        )
      : t('users.never')

  return (
    <div className="wrap">
      <AppBar
        sub={t('users.title')}
        navs={[
          { label: t('customer.navBack'), onClick: () => navigate('/') },
          { label: t('customer.navTo'), onClick: () => navigate('/customer') },
        ]}
        onLogout={logout}
      />
      <div className="card">
        {loadError ? (
          <div className="banner error" role="alert">
            <div className="body">{t('users.loadFailed')}</div>
          </div>
        ) : null}
        {actionError ? (
          <div className="banner error" role="alert">
            <div className="body">{t('users.actionFailed')}</div>
          </div>
        ) : null}
        {users === null && !loadError ? (
          <div className="statusline">
            <span className="dot" />
            <span>{t('users.loading')}</span>
          </div>
        ) : null}
        {users !== null && users.length === 0 ? (
          <p className="loginsub">{t('users.loadFailed')}</p>
        ) : null}
        {users !== null && users.length > 0 ? (
          <table className="users-table">
            <thead>
              <tr>
                <th>{t('users.colEmail')}</th>
                <th>{t('users.colNickname')}</th>
                <th>{t('users.colRole')}</th>
                <th>{t('users.colCreatedAt')}</th>
                <th>{t('users.colLastLogin')}</th>
                <th aria-label={t('users.colRole')} />
              </tr>
            </thead>
            <tbody>
              {users.map((row) => (
                <tr key={row.id}>
                  <td>{row.email}</td>
                  <td>{row.nickname}</td>
                  <td>{t(ROLE_KEY[row.role] || 'users.rolePending')}</td>
                  <td>{fmtDateTime(row.created_at)}</td>
                  <td>{fmtDateTime(row.last_login_at)}</td>
                  <td className="users-actions">
                    {actionsFor(row).map((role) => (
                      <button
                        key={role}
                        type="button"
                        className="chip"
                        disabled={busyId === row.id}
                        onClick={() => handleSetRole(row, role)}
                      >
                        {t(ACTION_KEY[role])}
                      </button>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
    </div>
  )
}
