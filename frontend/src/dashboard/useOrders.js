// ============================================================
// useOrders.js — 订单分页表数据 hook（DESIGN §6.3，S8）
// 区间/数据集/筛选/排序/页码任一变化即重拉；响应携带区间动态币种选项
// （AC-O2）。klass = 数据集与表格类别筛选的合成值（REQ-20261014-01）。
// ============================================================

import { useCallback, useEffect, useRef, useState } from 'react'

import { getOrders } from '../api/dashboard'

export default function useOrders({ from, to, klass, currency, status, upstream, sortKey, sortDir, page }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [reloadSeq, setReloadSeq] = useState(0)
  const key = [from, to, klass, currency, status, upstream, sortKey, sortDir, page].join('|')
  const keyRef = useRef(key)
  keyRef.current = key

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getOrders({ from, to, klass, currency, status, upstream, sort: sortKey, dir: sortDir, page })
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
