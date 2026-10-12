// ============================================================
// useSummary.js — 看板总览数据 hook（DESIGN §6.3，S8 纯 hooks）
// loading 期间保留上一次数据（loadingdim 半透明降载，AC-S1）；
// 401 由 client 统一跳转（AC-G2）。
// ============================================================

import { useCallback, useEffect, useRef, useState } from 'react'

import { getSummary } from '../api/dashboard'
import { rangeKey } from './range'

export default function useSummary(range) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [reloadSeq, setReloadSeq] = useState(0)
  const key = rangeKey(range)
  const keyRef = useRef(key)
  keyRef.current = key

  useEffect(() => {
    let cancelled = false
    const [from, to] = key.split('|')
    setLoading(true)
    setError(null)
    getSummary({ from, to })
      .then((payload) => {
        if (!cancelled) setData(payload)
      })
      .catch((err) => {
        if (!cancelled) setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [key, reloadSeq])

  const reload = useCallback(() => setReloadSeq((s) => s + 1), [])

  return { data, error, loading, reload }
}
