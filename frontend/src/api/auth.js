// ============================================================
// auth.js — 认证契约函数（DESIGN §3.3 六接口，唯一真源）
// 邮箱入参统一 trim + 小写规范化（§3.1），在各页面调用前完成，
// 此处再做一次防御性规范化。
// ============================================================

import { request } from './client'
import { normalizeEmail } from '../utils/validation'

/** (1) 发送注册验证码 → 204 */
export function sendRegisterCode(email) {
  return request('/auth/register/code', {
    method: 'POST',
    body: { email: normalizeEmail(email) },
    auth: false,
  })
}

/** (2) 注册（成功即自动登录）→ 201 {access_token, token_type, expires_in, user} */
export function register({ email, nickname, password, code }) {
  return request('/auth/register', {
    method: 'POST',
    body: { email: normalizeEmail(email), nickname, password, code },
    auth: false,
  })
}

/** (3) 登录 → 200 {access_token, token_type, expires_in, user} */
export function login({ email, password }) {
  return request('/auth/login', {
    method: 'POST',
    body: { email: normalizeEmail(email), password },
    auth: false,
  })
}

/** (4) 发送重置验证码 → 204 */
export function sendResetCode(email) {
  return request('/auth/password/code', {
    method: 'POST',
    body: { email: normalizeEmail(email) },
    auth: false,
  })
}

/** (5) 重置密码 → 204 */
export function resetPassword({ email, code, newPassword }) {
  return request('/auth/password/reset', {
    method: 'POST',
    body: { email: normalizeEmail(email), code, new_password: newPassword },
    auth: false,
  })
}

/** (6) 当前用户 → 200 {id, email, nickname, created_at}（需 token） */
export function me() {
  return request('/auth/me')
}
