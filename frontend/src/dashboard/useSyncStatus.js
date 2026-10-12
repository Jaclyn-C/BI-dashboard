// ============================================================
// useSyncStatus.js — 手动刷新 ↻ 与同步进度（DESIGN §5.5/§6.3，S7）
// POST /dashboard/sync（202 立返；accepted=false 不报错，继续轮询）→
// GET /dashboard/sync/status 每 1s 轮询 → idle 后回调 onDone 重拉数据。
// 进度（days_done/days_total）供状态行「正在加载 {a}/{b} 天…」（AC-S1/S4）。
// ============================================================

import { useCallback, useEffect, useRef, useState } from 'react'

import { getSyncStatus, triggerSync } from '../api/dashboard'

const POLL_MS = 1000

export default function useSyncStatus({ onDone } = {}) {
  const [status, setStatus] = useState(null)
  const [rejected, setRejected] = useState(false) // 上次 POST accepted=false（syncRejected 注记）
  const timerRef = useRef(null)
  const pollingRef = useRef(false)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    pollingRef.current = false
  }, [])

  const tick = useCallback(async () => {
    let next
    try {
      next = await getSyncStatus()
    } catch (e) {
      // 状态接口瞬断：停止轮询，交回 summary 的状态行（不无限重试）
      stop()
      return
    }
    setStatus(next)
    if (next && next.state !== 'running') {
      stop()
      if (onDoneRef.current) onDoneRef.current()
    }
  }, [stop])

  const startPolling = useCallback(() => {
    if (pollingRef.current) return
    pollingRef.current = true
    tick()
    timerRef.current = setInterval(tick, POLL_MS)
  }, [tick])

  /** ↻ 手动刷新：对当前区间触发即时同步（D4；accepted=false 仍展示进度） */
  const start = useCallback(
    async (from, to) => {
      setRejected(false)
      try {
        const res = await triggerSync({ from, to })
        if (res && res.accepted === false) setRejected(true)
        if (res && res.status) setStatus(res.status)
      } catch (e) {
        setRejected(false)
        setStatus(null)
        throw e // 由调用方呈现错误（错误横幅，AC-S5）
      }
      startPolling()
    },
    [startPolling],
  )

  /** summary.meta.sync_status==='running' 时自动接入进度（DESIGN §6.3） */
  const ensurePolling = useCallback(() => {
    startPolling()
  }, [startPolling])

  useEffect(() => stop, [stop])

  const running = !!(status && status.state === 'running')
  return { status, current: running ? status.current : null, running, rejected, start, ensurePolling }
}
