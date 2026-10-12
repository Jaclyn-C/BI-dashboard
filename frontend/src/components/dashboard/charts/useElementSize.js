// ============================================================
// useElementSize.js — ResizeObserver + 150ms 防抖（DESIGN §6.2，AC-R3）
// 返回 [ref, width]；宽度变化整树重渲染（React 无残留旧图）。
// ============================================================

import { useEffect, useRef, useState } from 'react'

export default function useElementSize() {
  const ref = useRef(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const el = ref.current
    if (!el) return undefined
    setWidth(el.clientWidth) // 初次直接量测（不防抖，避免首帧用回退宽度闪动）
    let timer = null
    const observer = new ResizeObserver(() => {
      clearTimeout(timer)
      timer = setTimeout(() => setWidth(el.clientWidth), 150)
    })
    observer.observe(el)
    return () => {
      clearTimeout(timer)
      observer.disconnect()
    }
  }, [])

  return [ref, width]
}
