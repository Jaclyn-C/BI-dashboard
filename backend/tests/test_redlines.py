"""仓库红线断言（B-T9 grep 验收的测试化形态，随 CI 常态生效）。

- B1：share_service 不得被聚合 / API / CSV 输出路径 import（AC-D3 零分成输出；
  按 AST import 语句判定——docstring 里的「禁止 import」说明不算违规）；
- 凭据/遗留依赖：backend 源码中不得出现 tfctechnology（CLAUDE.md 红线 11）；
- 上游出站白名单：app/ 内出现的 "/open/..." 路径字面量恰好等于 3 个常量
  （AC-U5；新增上游路径必须先登记 client.py 常量并修订需求）。
"""

import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

#: B1 红线覆盖的输出路径（聚合引擎 / 看板路由 / CSV / 订单查询）
B1_OUTPUT_PATHS = [
    "app/services/aggregation.py",
    "app/services/orders_query.py",
    "app/services/csv_export.py",
    "app/api/v1/dashboard.py",
    "app/schemas/dashboard.py",
]

WHITELIST = {
    "/open/oauth2/token",
    "/open/order/list",
    "/open/order/adSummary",
}


def _imports_share_service(path: Path) -> bool:
    """AST 判定文件是否 import share_service（任何形式）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "share_service" in node.module:
                return True
            if any(alias.name == "share_service" for alias in node.names):
                return True
        elif isinstance(node, ast.Import):
            if any("share_service" in alias.name for alias in node.names):
                return True
    return False


def test_b1_share_service_not_imported_by_output_paths():
    for rel in B1_OUTPUT_PATHS:
        path = BACKEND / rel
        assert not _imports_share_service(path), (
            f"B1 红线被违反：{rel} import 了 share_service"
        )


def test_no_legacy_backend_domain_in_source():
    for directory in ("app", "alembic"):
        for path in (BACKEND / directory).rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            assert "tfctechnology" not in content, f"发现遗留自建后端域名：{path}"


def test_upstream_path_literals_match_whitelist():
    pattern = re.compile(r"[\"'](/open/[^\"']+)[\"']")
    found: set[str] = set()
    for path in (BACKEND / "app").rglob("*.py"):
        found.update(pattern.findall(path.read_text(encoding="utf-8")))
    assert found == WHITELIST

