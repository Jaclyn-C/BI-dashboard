// ============================================================
// CustomerViewPage.jsx — 客户视图页（REQ-20261015-02）
// 展示下游客户调用供应商接口能看到的全部数据：仅已计入订单、纯订单信息
// （后端 /dashboard/customer-orders 已做 included-only + 字段裁剪，页面
// 不引入任何分类信息）。复用 TimeFilters + OrdersCard(hideClass) + Banners。
// ============================================================

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import useAuth from '../auth/useAuth'
import usePageTitle from '../utils/usePageTitle'
import { customRange, presetRange, todayKey } from '../dashboard/range'
import { buildFormatters, intNum } from '../dashboard/format'
import useCustomerOrders from '../dashboard/useCustomerOrders'
import AppBar from '../components/dashboard/AppBar'
import TimeFilters from '../components/dashboard/TimeFilters'
import Banners from '../components/dashboard/Banners'
import OrdersCard from '../components/dashboard/OrdersCard'

export default function CustomerViewPage() {
  const { t, i18n } = useTranslation()
  const { logout } = useAuth()
  const navigate = useNavigate()
  usePageTitle('common.pageTitle.customer')

  const [range, setRange] = useState(() => presetRange('7d'))
  const [filters, setFilters] = useState({ currency: 'all', status: 'all' })
  const [sort, setSort] = useState({ key: 'date', dir: 'desc' })
  const [page, setPage] = useState(1)

  const locale = i18n.language === 'zh' ? 'zh-CN' : 'en-US'
  const fmt = useMemo(() => buildFormatters(locale), [locale])

  const orders = useCustomerOrders({
    from: range.from,
    to: range.to,
    currency: filters.currency,
    status: filters.status,
    sortKey: sort.key,
    sortDir: sort.dir,
    page,
  })

  // 币种筛选失效回落 all（选项由当前区间动态生成，同看板 AC-O2）
  const orderCurrencies = orders.data ? orders.data.currencies : null
  useEffect(() => {
    if (!orderCurrencies) return
    if (filters.currency !== 'all' && !orderCurrencies.includes(filters.currency)) {
      setFilters((f) => ({ ...f, currency: 'all' }))
      setPage(1)
    }
  }, [orderCurrencies, filters.currency])

  const handlePreset = useCallback((preset) => {
    setRange(presetRange(preset))
    setPage(1)
  }, [])

  const handleCustom = useCallback((from, to) => {
    setRange(customRange(from, to))
    setPage(1)
  }, [])

  const handleFilterChange = useCallback((patch) => {
    setFilters((f) => ({ ...f, ...patch }))
    setPage(1)
  }, [])

  const handleSort = useCallback((key) => {
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }))
    setPage(1)
  }, [])

  const handleLogout = useCallback(() => {
    logout()
    navigate('/login', { replace: true })
  }, [logout, navigate])

  const total = orders.data ? orders.data.total : 0
  const totalInRange = orders.data ? orders.data.total_in_range : 0

  return (
    <div className="wrap">
      <AppBar
        sub={t('customer.subBar')}
        nav={{ label: t('customer.navBack'), onClick: () => navigate('/') }}
        onRefresh={orders.reload}
        onLogout={handleLogout}
      />
      <TimeFilters range={range} today={todayKey()} onPreset={handlePreset} onCustom={handleCustom} />
      <Banners error={orders.error} onRetryError={orders.reload} />
      <main className={orders.loading ? 'loadingdim' : undefined}>
        <div className="custnote">{t('customer.note')}</div>
        <div className="stack">
          <OrdersCard
            data={orders.data}
            fmt={fmt}
            filters={filters}
            classValue="all"
            classLocked
            hideClass
            title={t('customer.title')}
            sub={t('customer.ordersSub', { n: intNum(fmt, total), m: intNum(fmt, totalInRange) })}
            sort={sort}
            page={page}
            onFilterChange={handleFilterChange}
            onSort={handleSort}
            onPageChange={setPage}
          />
        </div>
      </main>
    </div>
  )
}
