// ============================================================
// users.js — 用户管理契约函数（REQ-20261020-01，唯一真源）
// ============================================================

import { request } from './client'

/** 用户列表 → 200 {users:[{id,email,nickname,role,created_at,last_login_at}]} */
export function listUsers() {
  return request('/users')
}

/** 调整角色 → 200 UserPublic；role ∈ admin|customer|pending */
export function updateUserRole(userId, role) {
  return request(`/users/${userId}/role`, { method: 'PATCH', body: { role } })
}
