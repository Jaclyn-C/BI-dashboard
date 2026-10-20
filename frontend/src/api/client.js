// ============================================================
// client.js — 统一请求层（组件禁止裸 fetch / 硬编码地址）
// DESIGN §5.5：baseURL '/api/v1'；token 注入（sessionStorage 'pd_token'）；
// 错误信封 → ApiError{code,message,status,details,retryAfter}；
// 网络 → ApiError{code:'NETWORK'}；带 token 的请求收到 401 → 清 token 跳 /login?expired=1。
// 403（带 token）→ onForbidden 回调（角色变更后重拉 /me）。
// ============================================================

const BASE_URL = '/api/v1'
const TOKEN_KEY = 'pd_token'

export class ApiError extends Error {
  constructor({ code, message, status = 0, details = null, retryAfter = null }) {
    super(message || code)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
    this.retryAfter = retryAfter
  }
}

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch (e) {
    return null
  }
}

export function setToken(token) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token)
  } catch (e) {
    /* storage unavailable */
  }
}

export function clearToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
  } catch (e) {
    /* ignore */
  }
}

// 403 处理（REQ-20261020-01）：带 token 的请求被拒权限时通知会话层重拉 /me
// （角色可能已被管理员调整，路由守卫按新角色接管跳转）。/me 自身不会返回 403，无递归。
let onForbidden = null

export function setOnForbidden(fn) {
  onForbidden = typeof fn === 'function' ? fn : null
}

function redirectToExpiredLogin() {
  // 全页跳转（对标参考实现 401 分支：清 token → 重新弹出登录卡片 + 过期提示）
  if (!window.location.pathname.startsWith('/login')) {
    window.location.replace('/login?expired=1')
  }
}

/**
 * 发起 API 请求。
 * @param {string} path 以 '/' 开头，如 '/auth/login'
 * @param {{method?: string, body?: object, auth?: boolean}} options
 *   auth=true 显式带 token（默认：存在 token 即带）
 * @returns {Promise<object|null>} 解析后的 JSON；204 返回 null
 */
export async function request(path, { method = 'GET', body = null, auth = true } = {}) {
  const headers = {}
  if (body !== null) headers['Content-Type'] = 'application/json'
  const token = getToken()
  const withAuth = auth && token
  if (withAuth) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(BASE_URL + path, {
      method,
      headers,
      body: body !== null ? JSON.stringify(body) : null,
    })
  } catch (err) {
    throw new ApiError({ code: 'NETWORK', message: 'network error' })
  }

  if (res.status === 401 && withAuth) {
    clearToken()
    redirectToExpiredLogin()
    throw new ApiError({ code: 'UNAUTHORIZED', message: 'session expired', status: 401 })
  }

  if (!res.ok) {
    let payload = null
    try {
      payload = await res.json()
    } catch (e) {
      /* 非 JSON 响应体 */
    }
    const envelope = payload && payload.error ? payload.error : {}
    if (res.status === 403 && withAuth && onForbidden) onForbidden()
    throw new ApiError({
      code: envelope.code || 'HTTP_ERROR',
      message: envelope.message || `HTTP ${res.status}`,
      status: res.status,
      details: envelope.details || null,
      retryAfter: res.headers.get('Retry-After'),
    })
  }

  if (res.status === 204) return null
  return res.json()
}

/**
 * 带 token 的文件下载（DESIGN §5.4：orders.csv 以 Authorization fetch → blob → a[download] 落盘）。
 * 文件名优先取响应 Content-Disposition 的 filename=，缺失时用 fallbackFilename。
 * @param {string} path 以 '/' 开头的 API 路径（含 query）
 * @param {{filename: string}} options fallback 文件名
 */
export async function requestDownload(path, { filename }) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(BASE_URL + path, { headers })
  } catch (err) {
    throw new ApiError({ code: 'NETWORK', message: 'network error' })
  }

  if (res.status === 401 && token) {
    clearToken()
    redirectToExpiredLogin()
    throw new ApiError({ code: 'UNAUTHORIZED', message: 'session expired', status: 401 })
  }

  if (!res.ok) {
    let payload = null
    try {
      payload = await res.json()
    } catch (e) {
      /* 非 JSON 响应体 */
    }
    const envelope = payload && payload.error ? payload.error : {}
    if (res.status === 403 && token && onForbidden) onForbidden()
    throw new ApiError({
      code: envelope.code || 'HTTP_ERROR',
      message: envelope.message || `HTTP ${res.status}`,
      status: res.status,
      details: envelope.details || null,
    })
  }

  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^";]+)"?/i)
  saveBlob(blob, match ? match[1] : filename)
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

/**
 * 把 ApiError 映射为 i18n key（+ 插值变量）。
 * 错误码 → auth.error.<code>；映射缺失时兜底 FALLBACK（用 HTTP 状态）。
 */
export function apiErrorI18n(err) {
  if (!err || err.name !== 'ApiError') {
    return { key: 'auth.error.network' }
  }
  if (err.code === 'NETWORK') return { key: 'auth.error.network' }
  const key = `auth.error.${err.code}`
  return { key, fallbackKey: 'auth.error.FALLBACK', vars: { status: err.status } }
}
