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
