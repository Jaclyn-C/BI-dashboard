// ============================================================
// useOrders.js — 订单分页表数据 hook（DESIGN §6.3，S8）
// 区间/筛选/排序/页码任一变化即重拉；响应携带区间动态币种选项（AC-O2）。
// ============================================================

import { useCallback, useEffect, useRef, useState } from 'react'

import { getOrders } from '../api/dashboard'

export default function useOrders({ from, to, currency, status, sortKey, sortDir, page }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [reloadSeq, setReloadSeq] = useState(0)
  const key = [from, to, currency, status, sortKey, sortDir, page].join('|')
  const keyRef = useRef(key)
  keyRef.current = key

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getOrders({ from, to, currency, status, sort: sortKey, dir: sortDir, page })
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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 参数已折叠为 key（避免对象 identity 抖动）
  }, [key, reloadSeq])

  const reload = useCallback(() => setReloadSeq((s) => s + 1), [])

  return { data, error, loading, reload }
}
