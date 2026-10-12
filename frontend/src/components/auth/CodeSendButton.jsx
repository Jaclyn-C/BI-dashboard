// CodeSendButton — 发码按钮 + 倒计时状态机（DESIGN §5.1 F3）
// idle → sending → countdown；成功后 60s 倒计时；429 时用 Retry-After 校准。
// 邮箱非法时由父页面通过 validate 回调拦截（AC-R1：不合法不发请求）。

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../api/client'

const DEFAULT_COOLDOWN = 60

export default function CodeSendButton({ validate, onSend, onError, disabled = false }) {
  const { t } = useTranslation()
  const [sending, setSending] = useState(false)
  const [remaining, setRemaining] = useState(0)
  const timerRef = useRef(null)

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current)
    },
    [],
  )

  function startCountdown(seconds) {
    const total = Math.max(1, Math.ceil(seconds) || DEFAULT_COOLDOWN)
    setRemaining(total)
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setRemaining((n) => {
        if (n <= 1) {
          clearInterval(timerRef.current)
          timerRef.current = null
          return 0
        }
        return n - 1
      })
    }, 1000)
  }

  async function handleClick() {
    // 前端先校验邮箱（AC-R1）：不合法直接让父页面展示行内错误，不发请求
    if (validate && validate()) return
    setSending(true)
    try {
      await onSend()
      startCountdown(DEFAULT_COOLDOWN)
    } catch (err) {
      // 429：服务端冷却校准（Retry-After 头，秒）
      if (err instanceof ApiError && err.status === 429) {
        const ra = Number(err.retryAfter)
        startCountdown(Number.isFinite(ra) && ra > 0 ? ra : DEFAULT_COOLDOWN)
      }
      if (onError) onError(err)
    } finally {
      setSending(false)
    }
  }

  const busy = sending || remaining > 0
  const text = sending
    ? t('auth.common.sending')
    : remaining > 0
      ? t('auth.common.resend', { n: remaining })
      : t('auth.common.sendCode')

  return (
    <button className="btn-code" type="button" onClick={handleClick} disabled={busy || disabled}>
      {text}
    </button>
  )
}
