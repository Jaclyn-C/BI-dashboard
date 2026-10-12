// ============================================================
// remember.js — 登录记忆（DESIGN §5.6 / AC-L5，纯前端 localStorage）
// - 邮箱始终记住（key pd_remember_email）：任一次登录成功即写入。
// - 密码按勾选（key pd_remember_pass）：encodeURIComponent + base64
//   编码混淆 —— 仅防肉眼直读，【非加密】，等价于本机明文级暴露。
// - token 走 sessionStorage，与记忆 key 分离、互不影响；退出登录不清记忆。
// 组件不直接操作 localStorage，一律经本模块。
// ============================================================

const EMAIL_KEY = 'pd_remember_email'
const PASS_KEY = 'pd_remember_pass'

/** 登录成功后：邮箱必记；密码按勾选状态存或清 */
export function rememberEmail(email) {
  try {
    localStorage.setItem(EMAIL_KEY, String(email ?? ''))
  } catch (e) {
    /* storage unavailable */
  }
}

/** 勾选「记住密码」且登录成功时：写入编码混淆后的密码（非加密，见文件头注释） */
export function rememberPassword(password) {
  try {
    // encodeURIComponent → btoa：把任意字符安全映射到 base64 字母表，防肉眼直读
    localStorage.setItem(PASS_KEY, btoa(encodeURIComponent(String(password ?? ''))))
  } catch (e) {
    /* storage unavailable */
  }
}

/** 未勾选登录成功 / 取消勾选后再登录：清除已存密码（邮箱记忆保留） */
export function clearPassword() {
  try {
    localStorage.removeItem(PASS_KEY)
  } catch (e) {
    /* ignore */
  }
}

/**
 * 打开登录页时回填。
 * @returns {{ email: string, password: string, rememberedPassword: boolean }}
 * - email：上次成功登录的邮箱（始终回填，默认行为）
 * - password：历史勾选记住时回填；rememberedPassword 表示当时是否勾选（用于勾选框初始态）
 */
export function loadRemembered() {
  let email = ''
  let encoded = null
  try {
    email = localStorage.getItem(EMAIL_KEY) || ''
    encoded = localStorage.getItem(PASS_KEY)
  } catch (e) {
    /* storage unavailable */
  }
  if (!encoded) return { email, password: '', rememberedPassword: false }
  try {
    return {
      email,
      password: decodeURIComponent(atob(encoded)),
      rememberedPassword: true,
    }
  } catch (e) {
    // 损坏数据：视为无记忆密码
    return { email, password: '', rememberedPassword: false }
  }
}
