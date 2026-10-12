// ============================================================
// range.js — 时间范围逻辑（DESIGN §6.4，HTML:1918-1955 逐条移植）
// 预设：today/7d/14d/30d（今天=浏览器本地日 todayStart()）；
// 自定义：任一变更生效、起>止交换、止/起>今天均钳今天（m4）、
//        跨度>92 天起点收缩为「止 − 91 天」（MAX_RANGE_DAYS）。
// 区间即本地日历日串（D6：数据按 UTC 日存储，展示层不换算）。
// ============================================================

export const MAX_RANGE_DAYS = 92

export const PRESETS = ['today', '7d', '14d', '30d']

const DAY_MS = 86400000

const pad = (n) => String(n).padStart(2, '0')

export function dateKey(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function parseDateKey(key) {
  const [y, m, d] = key.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function addDaysKey(key, n) {
  const d = parseDateKey(key)
  d.setDate(d.getDate() + n)
  return dateKey(d)
}

/** 浏览器本地今天 00:00 的日期串（HTML todayStart） */
export function todayKey() {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return dateKey(d)
}

export function listDays(from, to) {
  const out = []
  for (let d = from; d <= to; d = addDaysKey(d, 1)) out.push(d)
  return out
}

function presetToRange(preset, today) {
  switch (preset) {
    case 'today':
      return { from: today, to: today }
    case '14d':
      return { from: addDaysKey(today, -13), to: today }
    case '30d':
      return { from: addDaysKey(today, -29), to: today }
    case '7d':
    default:
      return { from: addDaysKey(today, -6), to: today }
  }
}

/** 预设区间（HTML setPreset） */
export function presetRange(preset, today = todayKey()) {
  const { from, to } = presetToRange(preset, today)
  return { preset, from, to }
}

/**
 * 自定义区间（HTML setCustomRange）：交换 + 双端钳今天 + 92 天收缩。
 * @returns {{preset: 'custom', from: string, to: string}}
 */
export function customRange(from, to, today = todayKey()) {
  let start = from
  let end = to
  if (start > end) [start, end] = [end, start]
  if (end > today) end = today
  if (start > today) start = today
  const span = Math.round((parseDateKey(end) - parseDateKey(start)) / DAY_MS) + 1
  if (span > MAX_RANGE_DAYS) start = addDaysKey(end, -(MAX_RANGE_DAYS - 1))
  return { preset: 'custom', from: start, to: end }
}

/** range 是否与某预设一致（用于 chips 选中态：custom 不回选，HTML 同行为） */
export function matchesPreset(range, preset, today = todayKey()) {
  if (range.preset !== preset) return false
  const p = presetRange(preset, today)
  return p.from === range.from && p.to === range.to
}

export function rangeKey(range) {
  return `${range.from}|${range.to}`
}
