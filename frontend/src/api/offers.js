// ============================================================
// offers.js — Offer 管理契约函数（REQ-20261022-02，唯一真源）
// ============================================================

import { request } from './client'

/**
 * Offer 列表 → 200 {offers:[{id,code,name,description,supplier_share,
 * supplier_share_pct,in_use,sort_order}]}；仅 admin+（客户 403）
 */
export function listOffers() {
  return request('/offers')
}

/**
 * 供应商收益（在用 offer）→ 200 {total_supplier_earnings_usd,total_order_usd,
 * total_order_count,earnings:[{code,name,supplier_share,supplier_share_pct,
 * order_count,order_total_usd,supplier_earnings_usd}]}；仅 admin+
 */
export function getOfferEarnings() {
  return request('/offers/earnings')
}
