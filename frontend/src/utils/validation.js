// ============================================================
// validation.js — 前端表单校验（DESIGN §5.2，与后端 schemas/auth.py 同源；
// 正则改动必须双侧同步，R7）。返回值为 i18n 错误 key 或 null（合法）。
// ============================================================

// 邮箱：常规格式 + ≤254 字符
const EMAIL_RE = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/

// 密码：8–64 字符，同时含字母与数字（Q1）
const PASSWORD_RE = /^(?=.*[A-Za-z])(?=.*\d)[\s\S]{8,64}$/

// 昵称：2–30 字符，A-Za-z0-9_- 与中文（U+4E00–U+9FFF）（Q5，正则与后端逐字一致）
const NICKNAME_RE = /^[A-Za-z0-9_\-一-鿿]{2,30}$/

// 验证码：恰好 6 位数字（Q3）
const CODE_RE = /^\d{6}$/

/** 邮箱规范化：去首尾空白 + 转小写（§3.1，两端统一） */
export function normalizeEmail(email) {
  return String(email ?? '')
    .trim()
    .toLowerCase()
}

export function validateEmail(email) {
  const v = normalizeEmail(email)
  if (!v) return 'auth.common.fieldRequired'
  if (v.length > 254 || !EMAIL_RE.test(v)) return 'auth.validation.emailInvalid'
  return null
}

export function validatePassword(password) {
  const v = String(password ?? '')
  if (!v) return 'auth.common.fieldRequired'
  if (!PASSWORD_RE.test(v)) return 'auth.validation.passwordInvalid'
  return null
}

export function validateNickname(nickname) {
  const v = String(nickname ?? '').trim()
  if (!v) return 'auth.common.fieldRequired'
  if (!NICKNAME_RE.test(v)) return 'auth.validation.nicknameInvalid'
  return null
}

export function validateCode(code) {
  const v = String(code ?? '').trim()
  if (!v) return 'auth.common.fieldRequired'
  if (!CODE_RE.test(v)) return 'auth.validation.codeInvalid'
  return null
}
