// ============================================================
// dashboard.js — 看板契约函数（DESIGN §5，前后端并行的唯一真源）
// 五函数：summary / orders / orders.csv / sync(POST) / sync/status。
// 开发期 mock：VITE_DASHBOARD_MOCK=1 时切换到 mocks/dashboardFixtures
// （契约形状一致；真实联调点 = B-T7 合入后切回，DESIGN §7.3）。
// ============================================================

import { request, requestDownload } from './client'

const MOCK = import.meta.env.VITE_DASHBOARD_MOCK === '1'

function qs(params) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  return search.toString()
}

const sleep = (ms) => new Promise((resolve) => {
  setTimeout(resolve, ms)
})

async function callMock(name, args, latency = 220) {
  await sleep(latency)
  const fixtures = await import('../mocks/dashboardFixtures')
  return fixtures[name](args)
}

/** (1) GET /dashboard/summary?from&to&class — 一次装载全看板（除订单表），DESIGN §5.2；class=数据集切换（REQ-20261014-01） */
export function getSummary({ from, to, klass = 'all' }) {
  if (MOCK) return callMock('getSummaryMock', { from, to, klass })
  return request(`/dashboard/summary?${qs({ from, to, class: klass })}`)
}

/** (2) GET /dashboard/orders?from&to&class&currency&status&sort&dir&page — 订单分页表，DESIGN §5.3 */
export function getOrders({ from, to, klass = 'all', currency = 'all', status = 'all', sort = 'date', dir = 'desc', page = 1 }) {
  if (MOCK) return callMock('getOrdersMock', { from, to, klass, currency, status, sort, dir, page }, 150)
  return request(`/dashboard/orders?${qs({ from, to, class: klass, currency, status, sort, dir, page })}`)
}

/** (2b) GET /dashboard/customer-orders?from&to&currency&status&sort&dir&page — 客户视图订单表（REQ-20261015-02：included-only、无分类字段） */
export function getCustomerOrders({ from, to, currency = 'all', status = 'all', sort = 'date', dir = 'desc', page = 1 }) {
  return request(`/dashboard/customer-orders?${qs({ from, to, currency, status, sort, dir, page })}`)
}

/** (3) GET /dashboard/orders.csv?… — CSV 下载（scope=view|all；lang=en|zh），DESIGN §5.4 */
export async function downloadOrdersCsv({ from, to, scope, klass = 'all', currency = 'all', status = 'all', sort = 'date', dir = 'desc', lang = 'en' }) {
  const filename = `orders_all_${from}_to_${to}.csv` // 两档同名（AC-X2）
  if (MOCK) {
    // mock 档仅验下载契约形状（文件名/BOM/表头/列值），真值走查归 §7.3 联调点②（m11）
    const fixtures = await import('../mocks/dashboardFixtures')
    const built = fixtures.buildCsvMock({ from, to, scope, klass, currency, status, sort, dir, lang })
    await saveBlobFromText(built.text, filename)
    return
  }
  return requestDownload(`/dashboard/orders.csv?${qs({ from, to, scope, class: klass, currency, status, sort, dir, lang })}`, { filename })
}

/** (3b) GET /dashboard/customer-orders.csv?… — 客户视图 CSV（当前筛选全量行、跨页；REQ-20261015-02：7 列纯订单信息、included-only） */
export async function downloadCustomerOrdersCsv({ from, to, currency = 'all', status = 'all', sort = 'date', dir = 'desc', lang = 'en' }) {
  const filename = `customer_orders_${from}_to_${to}.csv`
  return requestDownload(`/dashboard/customer-orders.csv?${qs({ from, to, currency, status, sort, dir, lang })}`, { filename })
}

/** (4) POST /dashboard/sync {from,to} → 202 {accepted, status}，DESIGN §5.5 */
export function triggerSync({ from, to }) {
  if (MOCK) return callMock('triggerSyncMock', { from, to }, 120)
  return request('/dashboard/sync', { method: 'POST', body: { from, to } })
}

/** (5) GET /dashboard/sync/status → {state, current, last_run}，DESIGN §5.5 */
export function getSyncStatus() {
  if (MOCK) return callMock('getSyncStatusMock', null, 60)
  return request('/dashboard/sync/status')
}

// 与 client.saveBlob 相同的落盘方式，供 mock 文本使用（保持单一出口形状）
async function saveBlobFromText(text, filename) {
  const blob = new Blob(['\ufeff' + text], { type: 'text/csv;charset=utf-8;' }) // BOM：Excel 直开不乱码
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
