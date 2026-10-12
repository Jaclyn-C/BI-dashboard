#!/usr/bin/env python3
"""export_diff.py — 对比两份「全部订单」CSV 导出（看板导出的 orders_all_*.csv）

用途：
  1. 新旧系统切换验收：同一日期段分别导出，逐单比对。
  2. 稳定性复测：同系统不同时间导出，检查分类是否翻转。

用法：
  python3 export_diff.py <旧导出.csv> <新导出.csv>

比对项：订单集合差异、类别翻转（已计入<->被剔除）、退款状态变化、美元金额变化。
"""
import csv
import sys


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return {r["订单编号"]: r for r in csv.DictReader(f)}


def main():
    if len(sys.argv) != 3:
        sys.exit(f"用法: {sys.argv[0]} <旧.csv> <新.csv>")

    a, b = load(sys.argv[1]), load(sys.argv[2])

    def brief(d):
        inc = sum(1 for r in d.values() if r["类别"] == "已计入")
        return f"{len(d)} 笔 (已计入 {inc}, 被剔除 {len(d) - inc})"

    print(f"旧文件: {sys.argv[1]}  {brief(a)}")
    print(f"新文件: {sys.argv[2]}  {brief(b)}")

    only_a = set(a) - set(b)
    only_b = set(b) - set(a)
    print(f"\n只在旧文件: {len(only_a)} 笔")
    print(f"只在新文件: {len(only_b)} 笔")
    for oid in sorted(only_b)[:10]:
        r = b[oid]
        print(f"  + {oid} {r['创建时间']} {r['币种']} {r['金额']} {r['状态']} {r['类别']}")

    both = set(a) & set(b)
    flips = [oid for oid in both if a[oid]["类别"] != b[oid]["类别"]]
    print(f"\n两份共有: {len(both)} 笔")
    print(f"类别翻转: {len(flips)} 笔")
    for oid in sorted(flips)[:20]:
        print(f"  {oid} {a[oid]['创建时间']}: {a[oid]['类别']} -> {b[oid]['类别']}")

    status = [oid for oid in both if a[oid]["状态"] != b[oid]["状态"]]
    print(f"退款状态变化: {len(status)} 笔")
    for oid in sorted(status)[:10]:
        print(f"  {oid}: {a[oid]['状态']} -> {b[oid]['状态']}")

    amounts = [oid for oid in both if a[oid]["预估美元"] != b[oid]["预估美元"]]
    print(f"美元金额变化: {len(amounts)} 笔")

    print("\n结论:", "完全一致/稳定" if not (flips or only_a or status or amounts)
          else "存在差异，见上方明细")


if __name__ == "__main__":
    main()
