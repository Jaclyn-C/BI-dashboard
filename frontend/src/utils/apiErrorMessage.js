// apiErrorMessage — ApiError → 本地化文案（错误码映射骨架，DESIGN §5.4）
// 优先 auth.error.<code>；映射缺失兜底 auth.error.FALLBACK（带 HTTP 状态）。

import { apiErrorI18n } from '../api/client'

export function apiErrorMessage(t, err) {
  const { key, fallbackKey, vars } = apiErrorI18n(err)
  const fallback = t(fallbackKey || 'auth.error.FALLBACK', vars)
  return t(key, { ...vars, defaultValue: fallback })
}
