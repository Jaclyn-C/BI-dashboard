// ============================================================
// dashboardFixtures.js — F-T1 mock 数据（DESIGN §5 契约的唯一前端镜像）
// 用途：VITE_DASHBOARD_MOCK=1 时被 src/api/dashboard.js 切换调用；
//       本地 mock server（临时目录，不入仓库）也直接 import 本文件。
//
// ⚠️ 本文件是「模拟后端」：这里的金额生成 / 聚合 / 求和全部属于
//    后端职责的模拟（对标 DESIGN §4.1 聚合规则与 HTML derive()），
//    不是前端业务运算。真实前端代码（组件/卡片）零金额运算。
//
// 数据特征（覆盖前端各分支）：
//   - 10 个币种 → 每日图前 6+__other 折叠、对比环前 7+__other 折叠
//   - BHD/KZT 无固定汇率（conv.no_rate_currencies）
//   - BHD/KZT 部分订单缺 usd（conv.no_usd_* / AC-C8 横幅）
//   - 18+ 国家 → 国家条前 9+__other 折叠
//   - 固定一天 truncated（AC-S7 横幅）、区间含今天 → incomplete_tail
//   - 生成窗口 = 最近 100 天；更早的自定义区间返回空数据（空态走查用）
// ============================================================

const DAY_MS = 86400000
const HORIZON_DAYS = 100
const MAX_RANGE_DAYS = 92

// HTML:764-768 的 27 键静态汇率表（冻结值，仅对比口径使用）
const LEGACY_USD_RATES = {
  AED: 0.272, AUD: 0.65, BRL: 0.185, CAD: 0.73, CHF: 1.24, CLP: 0.00105,
  CZK: 0.048, EUR: 1.17, GBP: 1.35, HKD: 0.128, IDR: 0.000061, INR: 0.0114,
  JPY: 0.0068, KRW: 0.00072, MXN: 0.054, MYR: 0.24, NGN: 0.00065, PHP: 0.0175,
  QAR: 0.275, SAR: 0.267, SGD: 0.78, THB: 0.031, TRY: 0.024, TWD: 0.033,
  USD: 1, VND: 0.000038, ZAR: 0.056,
}

// 币种分布：w=订单权重，base=原币金额基数，rate=「上游自报美元」隐含汇率
// （与 LEGACY 略有出入 → 对比卡出现 Δ）；missingUsd=缺美元金额比例
const CURRENCIES = [
  { code: 'USD', w: 0.3, base: 4.99, rate: 1 },
  { code: 'JPY', w: 0.16, base: 740, rate: 0.0066 },
  { code: 'EUR', w: 0.12, base: 4.5, rate: 1.155 },
  { code: 'BRL', w: 0.1, base: 18, rate: 0.192 },
  { code: 'IDR', w: 0.09, base: 58000, rate: 0.000064 },
  { code: 'PHP', w: 0.07, base: 168, rate: 0.0171 },
  { code: 'MXN', w: 0.06, base: 78, rate: 0.0515 },
  { code: 'INR', w: 0.05, base: 340, rate: 0.0111 },
  { code: 'BHD', w: 0.03, base: 1.9, rate: 2.65, missingUsd: 0.3 },
  { code: 'KZT', w: 0.02, base: 1050, rate: 0.00188, missingUsd: 0.55 },
]

// language 权重表（country_key 由地区子标签推断，DESIGN §5.3）
const LANGUAGES = [
  ['en_US', 0.25], ['ja_JP', 0.14], ['pt_BR', 0.11], ['id_ID', 0.09], ['es_MX', 0.08],
  ['hi_IN', 0.06], ['tl_PH', 0.06], ['ko_KR', 0.05], ['th_TH', 0.04], ['vi_VN', 0.035],
  ['ar_BH', 0.025], ['en_GB', 0.02], ['fr_FR', 0.02], ['de_DE', 0.015], ['zh_TW', 0.014],
  ['ms_MY', 0.01], ['ru_RU', 0.008], ['kk_KZ', 0.007], ['en', 0.006], ['', 0.01],
]

// ---------------- 基础工具 ----------------

const pad = (n) => String(n).padStart(2, '0')
const keyOf = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const round2 = (v) => (Math.round(v * 100) / 100).toFixed(2)
const iso = (d) => new Date(d).toISOString()

function addDaysKey(key, n) {
  const [y, m, d] = key.split('-').map(Number)
  const r = new Date(y, m - 1, d + n)
  return keyOf(r)
}

function todayKey() {
  return keyOf(new Date())
}

function horizonStart() {
  return addDaysKey(todayKey(), -(HORIZON_DAYS - 1))
}

function listDays(from, to) {
  const out = []
  for (let d = from; d <= to; d = addDaysKey(d, 1)) out.push(d)
  return out
}

// 确定性 hash → [0,1)（同入参同输出，mock 数据可复现）
function hash01(str) {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return ((h >>> 0) % 1000000) / 1000000
}

function pickWeighted(entries, r) {
  let acc = 0
  for (const [value, w] of entries) {
    acc += w
    if (r < acc) return value
  }
  return entries[entries.length - 1][0]
}

function currencyOf(date, i) {
  return pickWeighted(CURRENCIES.map((c) => [c, c.w]), hash01(`c|${date}|${i}`))
}

function languageOf(date, i) {
  return pickWeighted(LANGUAGES, hash01(`l|${date}|${i}`))
}

// DESIGn §5.3：_-XX$ → XX 大写；无子标签 → 原串；空 → __unknown
function countryKeyOf(language) {
  const lang = String(language || '').trim()
  if (!lang) return '__unknown'
  const m = lang.match(/[_-]([A-Za-z]{2})$/)
  return m ? m[1].toUpperCase() : lang
}

function roundNative(code, v) {
  if (code === 'JPY' || code === 'IDR' || code === 'KZT' || code === 'KRW' || code === 'VND') {
    return Math.round(v)
  }
  return Math.round(v * 100) / 100
}

// ---------------- 订单生成（按日缓存） ----------------

const orderCache = new Map()

function ordersForDay(date) {
  if (orderCache.has(date)) return orderCache.get(date)
  const rows = []
  const today = todayKey()
  if (date >= horizonStart() && date <= today) {
    const count = 340 + Math.floor(hash01(`n|${date}`) * 260) // 340–600 单/日
    for (let i = 0; i < count; i++) {
      const cur = currencyOf(date, i)
      const lang = languageOf(date, i)
      const native = roundNative(cur.code, cur.base * (0.5 + hash01(`a|${date}|${i}`) * 1.4))
      const missingUsd = (cur.missingUsd || 0) > 0 && hash01(`u|${date}|${i}`) < cur.missingUsd
      const usd = missingUsd
        ? null
        : Math.round(native * cur.rate * (0.98 + hash01(`r|${date}|${i}`) * 0.04) * 100) / 100
      const returned = hash01(`x|${date}|${i}`) < 0.012
      const hh = Math.floor(hash01(`h|${date}|${i}`) * 24)
      const mm = Math.floor(hash01(`m|${date}|${i}`) * 60)
      const ss = Math.floor(hash01(`s|${date}|${i}`) * 60)
      const orderId = `R${date.replaceAll('-', '')}${String(i).padStart(5, '0')}`
      rows.push({
        order_id: orderId,
        create_time: `${date} ${pad(hh)}:${pad(mm)}:${pad(ss)}`,
        create_date: date,
        country_key: countryKeyOf(lang),
        language: lang,
        currency: cur.code,
        amount: native.toFixed(2),
        usd: usd === null ? null : usd.toFixed(2),
        // 模拟后端哈希打标（REQ-20261014-01）：确定性 ~80/20
        order_class: hash01(`cls|${orderId}`) < 0.8 ? 'included' : 'excluded',
        status: returned ? 'returned' : 'completed',
        refund_time: returned ? `${date} ${pad(Math.min(23, hh + 1))}:${pad(mm)}:${pad(ss)}` : null,
        theater_id: `T${100 + Math.floor(hash01(`t|${date}|${i}`) * 900)}`,
        chapter_id: `C${1 + Math.floor(hash01(`ch|${date}|${i}`) * 400)}`,
        promotion_code: hash01(`p|${date}|${i}`) < 0.06 ? `NS-${cur.code}` : '',
      })
    }
    rows.sort((a, b) => (a.create_time < b.create_time ? 1 : -1))
  }
  orderCache.set(date, rows)
  return rows
}

function adForDay(date) {
  if (date < horizonStart() || date > todayKey()) return null
  return round2(110 + hash01(`ad|${date}`) * 170)
}

// 固定一个截断日（今天-9，落在区间内即出现 AC-S7 横幅）
function truncatedDates() {
  return [addDaysKey(todayKey(), -9)]
}

// ---------------- 同步状态模拟（S7：POST → running → 1s 轮询推进） ----------------

const syncMock = {
  state: 'idle',
  current: null,
  startedAt: 0,
  lastRun: null,
  lastSyncAt: Date.now() - 32 * 60000,
}

function syncSnapshot() {
  return {
    state: syncMock.state,
    current: syncMock.current ? { ...syncMock.current } : null,
    last_run: syncMock.lastRun,
  }
}

export function triggerSyncMock({ from, to }) {
  if (syncMock.state === 'running') {
    return { accepted: false, status: syncSnapshot() }
  }
  const clampedFrom = from > todayKey() ? todayKey() : from
  const clampedTo = to > todayKey() ? todayKey() : to // 日期串比较（Math.min 会 NaN）
  const days = listDays(clampedFrom, clampedTo)
  syncMock.state = 'running'
  syncMock.startedAt = Date.now()
  syncMock.current = {
    id: 1234,
    trigger: 'manual',
    window_start: clampedFrom,
    window_end: clampedTo,
    days_done: 0,
    days_total: days.length,
    phase: 'orders',
  }
  return { accepted: true, status: syncSnapshot() }
}

export function getSyncStatusMock() {
  if (syncMock.state === 'running') {
    const elapsed = Date.now() - syncMock.startedAt
    const done = Math.min(syncMock.current.days_total, Math.floor(elapsed / 250))
    syncMock.current.days_done = done
    if (done >= syncMock.current.days_total) {
      const startedAt = syncMock.startedAt
      const cur = syncMock.current
      syncMock.state = 'idle'
      syncMock.current = null
      syncMock.lastSyncAt = Date.now()
      syncMock.lastRun = {
        id: cur.id,
        trigger: cur.trigger,
        window_start: cur.window_start,
        window_end: cur.window_end,
        status: 'success',
        started_at: iso(startedAt),
        finished_at: iso(Date.now()),
        truncated_days: [],
        orders_upserted: 3000 + Math.floor(hash01(String(cur.id)) * 3000),
        orders_error: null,
        ad_error: null,
      }
    }
  }
  return syncSnapshot()
}

// ---------------- summary 聚合（DESIGN §4.1 的镜像实现） ----------------

function sumMapEntries(map) {
  return [...map.entries()].sort((a, b) => b[1] - a[1])
}

export function getSummaryMock({ from, to, klass = 'all' }) {
  const days = listDays(from, to)
  const scopeAll = days.flatMap((d) => ordersForDay(d))
  // 数据集切换（REQ-20261014-01）：行集先按 tag 过滤，全部下游口径随之收窄
  const all = klass === 'all' ? scopeAll : scopeAll.filter((o) => o.order_class === klass)
  const completed = all.filter((o) => o.status === 'completed')
  const returned = all.filter((o) => o.status === 'returned')

  // 每日双口径（est=静态汇率估算 / usd=上游自报）+ 币种拆分
  const estByDay = new Map()
  const usdByDay = new Map()
  const curUsdTotals = new Map()
  const countries = new Map()
  const convRows = new Map()
  let noUsdOrderCount = 0
  const noUsdCurrencies = new Set()

  const dayEntry = (map, date) => {
    let e = map.get(date)
    if (!e) {
      e = { orders: 0, total: 0, by: new Map() }
      map.set(date, e)
    }
    return e
  }

  for (const o of completed) {
    const native = Number(o.amount)
    const rate = LEGACY_USD_RATES[o.currency]
    if (rate !== undefined) {
      const e = dayEntry(estByDay, o.create_date)
      const v = native * rate
      e.orders += 1
      e.total += v
      e.by.set(o.currency, (e.by.get(o.currency) || 0) + v)
    }
    if (o.usd !== null) {
      const usd = Number(o.usd)
      const e = dayEntry(usdByDay, o.create_date)
      e.orders += 1
      e.total += usd
      e.by.set(o.currency, (e.by.get(o.currency) || 0) + usd)
      curUsdTotals.set(o.currency, (curUsdTotals.get(o.currency) || 0) + usd)
      // 国家聚合（对标 HTML：仅计有美元金额的已完成订单）
      let c = countries.get(o.country_key)
      if (!c) {
        c = { usd: 0, orders: 0, by: new Map() }
        countries.set(o.country_key, c)
      }
      c.usd += usd
      c.orders += 1
      c.by.set(o.currency, (c.by.get(o.currency) || 0) + native)
    } else {
      noUsdOrderCount += 1
      noUsdCurrencies.add(o.currency)
    }
    // 对比卡行（全部已完成订单，无论有无美元/汇率）
    let r = convRows.get(o.currency)
    if (!r) {
      r = {
        currency: o.currency,
        has_rate: rate !== undefined,
        rate: rate === undefined ? null : String(rate),
        orders: 0,
        native: 0,
        legacy: 0,
        server: 0,
      }
      convRows.set(o.currency, r)
    }
    r.orders += 1
    r.native += native
    if (rate !== undefined) r.legacy += native * rate
    if (o.usd !== null) r.server += Number(o.usd)
  }

  const currencyRank = [...curUsdTotals.entries()].sort((a, b) => b[1] - a[1]).map(([c]) => c)

  // 每日图表序列预折叠：前 6 + __other（DESIGN §5.2）
  const mainCurrencies = currencyRank.slice(0, 6)
  const foldedCurrencies = currencyRank.slice(6)
  const seriesKeys = foldedCurrencies.length
    ? [...mainCurrencies, '__other']
    : [...mainCurrencies]

  const dailySeries = (entry) =>
    seriesKeys.map((key) => {
      if (key === '__other') {
        let sum = 0
        for (const c of foldedCurrencies) sum += entry.by.get(c) || 0
        return { key, amount: round2(sum) }
      }
      return { key, amount: round2(entry.by.get(key) || 0) }
    })

  const buildDailyArray = (map) =>
    days.map((date) => {
      const e = map.get(date)
      if (!e) {
        return { date, orders: 0, total: '0.00', by_currency: [], series: seriesKeys.map((k) => ({ key: k, amount: '0.00' })) }
      }
      return {
        date,
        orders: e.orders,
        total: round2(e.total),
        by_currency: sumMapEntries(e.by).map(([currency, v]) => ({ currency, amount: round2(v) })),
        series: dailySeries(e),
      }
    })

  const ad = []
  let adTotal = 0
  let adDays = 0
  for (const d of days) {
    const v = adForDay(d)
    if (v !== null) {
      ad.push({ date: d, amount: v })
      adTotal += Number(v)
      adDays += 1
    }
  }

  // 对比卡：行排序 max(server,legacy) 降序；切片前 7 + __other（RQ-3）
  const convList = [...convRows.values()]
    .map((r) => {
      const base = r.server || r.legacy
      const delta = r.server - r.legacy
      const flagged = base > 0 && Math.abs(delta) >= 1 && Math.abs(delta / base) >= 0.01
      return {
        ...r,
        native: round2(r.native),
        legacy_usd: round2(r.legacy),
        server_usd: round2(r.server),
        delta: round2(delta),
        delta_pct: base ? ((delta / base) * 100).toFixed(1) : '0',
        flagged,
      }
    })
    .sort((a, b) => Math.max(Number(b.server_usd), Number(b.legacy_usd)) - Math.max(Number(a.server_usd), Number(a.legacy_usd)))

  const legacyTotal = convList.reduce((s, r) => s + Number(r.legacy_usd), 0)
  const serverTotal = convList.reduce((s, r) => s + Number(r.server_usd), 0)
  const deltaTotal = serverTotal - legacyTotal
  const convBase = serverTotal || legacyTotal

  const convSlices = convList.slice(0, 7).map((r) => ({
    key: r.currency,
    legacy_usd: r.legacy_usd,
    server_usd: r.server_usd,
  }))
  const convTail = convList.slice(7)
  if (convTail.length) {
    convSlices.push({
      key: '__other',
      legacy_usd: round2(convTail.reduce((s, r) => s + Number(r.legacy_usd), 0)),
      server_usd: round2(convTail.reduce((s, r) => s + Number(r.server_usd), 0)),
    })
  }

  // 国家：表全量降序；条形前 9 + __other（usd/orders/byCurrency 求和合并）
  const countryEntries = [...countries.entries()]
    .map(([key, v]) => ({
      key,
      usd: Number(round2(v.usd)),
      orders: v.orders,
      byCurrency: sumMapEntries(v.by).map(([currency, amount]) => ({ currency, amount: round2(amount) })),
    }))
    .sort((a, b) => b.usd - a.usd)
  const countryTotalUsd = countryEntries.reduce((s, r) => s + r.usd, 0)
  const withShare = (r) => ({
    key: r.key,
    usd: round2(r.usd),
    orders: r.orders,
    share: countryTotalUsd ? ((r.usd / countryTotalUsd) * 100).toFixed(1) : '0',
    by_currency: r.byCurrency,
  })
  const countryTable = countryEntries.map(withShare)
  const countryBars = []
  const head = countryEntries.slice(0, 9)
  const tail = countryEntries.slice(9)
  for (const r of head) countryBars.push(withShare(r))
  if (tail.length) {
    const merged = { usd: 0, orders: 0, by: new Map() }
    for (const r of tail) {
      merged.usd += r.usd
      merged.orders += r.orders
      for (const bc of r.byCurrency) {
        merged.by.set(bc.currency, (merged.by.get(bc.currency) || 0) + Number(bc.amount))
      }
    }
    countryBars.push({
      key: '__other',
      usd: round2(merged.usd),
      orders: merged.orders,
      by_currency: sumMapEntries(merged.by).map(([currency, amount]) => ({ currency, amount: round2(amount) })),
    })
  }

  const syncStatus = syncMock.state === 'running' ? 'running' : 'ok'
  const truncated = truncatedDates().filter((d) => d >= from && d <= to)

  // 新口径 KPI（REQ-20261014-01）：含退款单、缺 usd 不计金额只计数；
  // 数据集切换下公式输入不在范围内的卡片为 null（前端不渲染）
  let totalUsd = 0
  let includedUsd = 0
  let excludedUsd = 0
  let refundedUsd = 0
  let includedCount = 0
  let excludedCount = 0
  let noUsdAllCount = 0
  for (const o of all) {
    if (o.order_class === 'included') includedCount += 1
    else if (o.order_class === 'excluded') excludedCount += 1
    if (o.usd === null) {
      noUsdAllCount += 1
      continue
    }
    const v = Number(o.usd)
    totalUsd += v
    if (o.order_class === 'included') includedUsd += v
    else if (o.order_class === 'excluded') excludedUsd += v
    if (o.status === 'returned') refundedUsd += v
  }
  const myShare = totalUsd * 0.7
  const isAll = klass === 'all'
  const payable = totalUsd * 0.5
  const paidActual = isAll ? includedUsd * 0.5 : totalUsd * 0.5
  const mergedCard = isAll
    ? {
        included: { count: includedCount, usd: round2(includedUsd) },
        excluded: { count: excludedCount, usd: round2(excludedUsd) },
      }
    : { included: null, excluded: null }

  return {
    range: { from, to },
    meta: {
      orders_total: all.length,
      latest_orders_sync_at: iso(syncMock.lastSyncAt),
      sync_status: syncStatus,
      latest_covered_date: todayKey(),
      incomplete_tail: to >= todayKey(),
      truncated_days: truncated,
      ad_available: true,
      ad_error: null,
    },
    kpis: {
      orders_total: all.length,
      orders_completed: completed.length,
      orders_returned: returned.length,
      total_usd: round2(totalUsd),
      my_share_usd: round2(myShare),
      supplier_payable_usd: isAll ? round2(payable) : null,
      supplier_paid_usd: klass === 'excluded' ? null : round2(paidActual),
      hidden_saving_usd: isAll ? round2(payable - paidActual) : null,
      net_expected_usd: isAll ? round2(myShare - payable) : null,
      net_actual_usd: klass === 'excluded' ? null : round2(myShare - paidActual),
      total_net_actual_usd: klass === 'excluded' ? null : round2(myShare - paidActual + adTotal),
      refunded_usd: round2(refundedUsd),
      included: mergedCard.included,
      excluded: mergedCard.excluded,
      ad_total: round2(adTotal),
      ad_days_reported: adDays,
      countries: countries.size,
      top_country: countryTable.length ? countryTable[0].key : null,
      no_usd_order_count: noUsdAllCount,
    },
    daily: {
      days,
      currency_rank: currencyRank,
      est: buildDailyArray(estByDay),
      usd: buildDailyArray(usdByDay),
      ad,
    },
    conv: {
      empty: convList.length === 0 || (legacyTotal <= 0 && serverTotal <= 0),
      rows: convList,
      slices: convSlices,
      legacy_total: round2(legacyTotal),
      server_total: round2(serverTotal),
      delta_total: round2(deltaTotal),
      delta_pct: convBase ? ((deltaTotal / convBase) * 100).toFixed(1) : '0',
      agree: convBase > 0 && Math.abs(deltaTotal / convBase) < 0.005,
      no_rate_currencies: convList.filter((r) => !r.has_rate).map((r) => r.currency).sort(),
      no_usd_order_count: noUsdOrderCount,
      no_usd_currencies: [...noUsdCurrencies].sort(),
    },
    countries: { table: countryTable, bars: countryBars },
  }
}

// ---------------- 订单分页（DESIGN §5.3） ----------------

export function getOrdersMock({ from, to, klass = 'all', currency = 'all', status = 'all', sort = 'date', dir = 'desc', page = 1 }) {
  const all = listDays(from, to).flatMap((d) => ordersForDay(d))
  const currencies = [...new Set(all.map((o) => o.currency))].sort()
  let rows = all
  if (klass !== 'all') rows = rows.filter((o) => o.order_class === klass)
  if (currency !== 'all') rows = rows.filter((o) => o.currency === currency)
  if (status === 'completed') rows = rows.filter((o) => o.status === 'completed')
  else if (status === 'returned') rows = rows.filter((o) => o.status === 'returned')

  const mult = dir === 'asc' ? 1 : -1
  rows = [...rows].sort((a, b) => {
    let va, vb
    if (sort === 'date') {
      va = a.create_time
      vb = b.create_time
    } else if (sort === 'amount') {
      va = Number(a.amount)
      vb = Number(b.amount)
    } else if (sort === 'usd') {
      va = a.usd === null ? -1 : Number(a.usd)
      vb = b.usd === null ? -1 : Number(b.usd)
    } else {
      va = a.currency
      vb = b.currency
    }
    const cmp = va < vb ? -1 : va > vb ? 1 : a.order_id < b.order_id ? -1 : 1
    return cmp * mult
  })

  const pageSize = 25
  const pages = Math.max(1, Math.ceil(rows.length / pageSize))
  const safePage = Math.min(Math.max(1, page), pages)
  const slice = rows.slice((safePage - 1) * pageSize, safePage * pageSize)
  return {
    rows: slice,
    page: safePage,
    page_size: pageSize,
    pages,
    total: rows.length,
    total_in_range: all.length,
    currencies,
  }
}

// ---------------- CSV（mock 档仅验下载契约形状，DESIGN §7.2 F-T8/m11） ----------------

function csvCell(value) {
  const str = value === null || value === undefined ? '' : String(value)
  const safe = /^[=+\-@\t\r]/.test(str) ? "'" + str : str
  return /[",\n\r]/.test(safe) ? '"' + safe.replace(/"/g, '""') + '"' : safe
}

export function buildCsvMock({ from, to, scope = 'view', klass = 'all', currency = 'all', status = 'all', sort = 'date', dir = 'desc', lang = 'en' }) {
  const headers = CSV_HEADERS[lang] || CSV_HEADERS.en
  const classWords = { en: { included: 'Included', excluded: 'Excluded' }, zh: { included: '已计入', excluded: '被剔除' } }
  // scope=all：区间内当前数据集全部订单（忽略表格筛选，create_time 降序）；
  // view：套用当前筛选+排序。数据集 klass 两档都生效（REQ §3.4）
  const rowsAll = scope === 'all'
    ? paginatedAll({ from, to, klass, currency: 'all', status: 'all', sort: 'date', dir: 'desc' })
    : paginatedAll({ from, to, klass, currency, status, sort, dir })
  const lines = [headers.map(csvCell).join(',')]
  for (const o of rowsAll) {
    lines.push([
      o.order_id,
      o.create_time,
      o.theater_id,
      o.chapter_id,
      csvCountry(o.country_key, lang),
      o.language,
      o.currency,
      Number(o.amount).toFixed(2),
      o.usd === null ? '' : Number(o.usd).toFixed(2),
      o.order_class ? classWords[lang][o.order_class] : '',
      '', // revShare（旧口径死列，REQ-20261014-01）
      '', // earningsUsd（旧口径死列）
      o.status === 'returned' ? CSV_STATUS[lang].returned : CSV_STATUS[lang].completed,
      o.promotion_code,
    ].map(csvCell).join(','))
  }
  return { filename: `orders_all_${from}_to_${to}.csv`, text: lines.join('\r\n') }
}

function paginatedAll({ from, to, klass, currency, status, sort, dir }) {
  // 取全量筛选行（绕过分页）：直接复用 getOrdersMock 的筛选逻辑
  const all = listDays(from, to).flatMap((d) => ordersForDay(d))
  let rows = all
  if (klass !== 'all') rows = rows.filter((o) => o.order_class === klass)
  if (currency !== 'all') rows = rows.filter((o) => o.currency === currency)
  if (status === 'completed') rows = rows.filter((o) => o.status === 'completed')
  else if (status === 'returned') rows = rows.filter((o) => o.status === 'returned')
  const mult = dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    let va, vb
    if (sort === 'date') {
      va = a.create_time
      vb = b.create_time
    } else if (sort === 'amount') {
      va = Number(a.amount)
      vb = Number(b.amount)
    } else if (sort === 'usd') {
      va = a.usd === null ? -1 : Number(a.usd)
      vb = b.usd === null ? -1 : Number(b.usd)
    } else {
      va = a.currency
      vb = b.currency
    }
    return (va < vb ? -1 : va > vb ? 1 : a.order_id < b.order_id ? -1 : 1) * mult
  })
}

function csvCountry(key, lang) {
  if (key === '__unknown') return lang === 'zh' ? '未知' : 'Unknown'
  return key
}

// CSV 表头/状态词与 locale 文件保持同源（HTML csvHeaders 逐字照搬）
const CSV_HEADERS = {
  en: ['orderId', 'createTime', 'theaterId', 'chapterId', 'country', 'language',
    'currency', 'amount', 'estUsd', 'class', 'revShare', 'earningsUsd', 'status', 'promotionCode'],
  zh: ['订单编号', '创建时间', '短剧ID', '章节ID', '国家/地区', '语种',
    '币种', '金额', '预估美元', '类别', '分成比例', '分成收入(美元)', '状态', '推广码'],
}
const CSV_STATUS = {
  en: { completed: 'Completed', returned: 'Returned' },
  zh: { completed: '已完成', returned: '已退款' },
}

export const MOCK_LIMITS = { MAX_RANGE_DAYS, HORIZON_DAYS }
