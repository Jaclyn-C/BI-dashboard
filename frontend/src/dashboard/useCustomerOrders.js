// ============================================================
// useCustomerOrders.js — 客户视图订单数据 hook（REQ-20261015-02）
// 镜像 useOrders（无 klass 维度：后端固定 included-only 且已裁剪字段）。
// ============================================================

import { useCallback, useEffect, useRef, useState } from 'react'

import { getCustomerOrders } from '../api/dashboard'

export default function useCustomerOrders({ from, to, currency, status, upstream, sortKey, sortDir, page }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [reloadSeq, setReloadSeq] = useState(0)
  const key = [from, to, currency, status, upstream, sortKey, sortDir, page].join('|')
  const keyRef = useRef(key)
  keyRef.current = key

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getCustomerOrders({ from, to, currency, status, upstream, sort: sortKey, dir: sortDir, page })
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
