from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import closing
from datetime import date, datetime
from typing import Any

from app.core.config import settings


def _get_conn() -> sqlite3.Connection:
    db_path = settings.ops_db_path
    if not db_path:
        raise ValueError("OPS_DB_PATH 未配置")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()


def _fetch_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()


def _db_error_result(tool_name: str, error_msg: str) -> dict[str, Any]:
    return {
        "tool": tool_name,
        "error": error_msg,
        "data": None,
    }


def get_today_gmv() -> dict[str, Any]:
    """获取今日 GMV

    Returns:
        包含今日 GMV 的字典
    """
    try:
        today = date.today().isoformat()
        row = _fetch_one("SELECT gmv, order_count FROM daily_metrics WHERE metric_date = ?", (today,))

        if row:
            return {"date": today, "gmv": row["gmv"], "currency": "CNY", "order_count": row["order_count"]}

        latest = _fetch_one("SELECT gmv FROM daily_metrics ORDER BY metric_date DESC LIMIT 1")

        if latest:
            return {"date": today, "gmv": latest["gmv"], "currency": "CNY", "note": "使用最近一天数据"}
        return _db_error_result("get_today_gmv", "daily_metrics 表无数据")
    except Exception as exc:
        return _db_error_result("get_today_gmv", str(exc))


def get_month_new_users() -> dict[str, Any]:
    """获取本月新增用户数

    Returns:
        包含本月新增用户数的字典
    """
    try:
        year = date.today().year
        month = date.today().month
        month_prefix = f"{year}-{month:02d}"
        row = _fetch_one("SELECT COUNT(*) as cnt FROM users WHERE registered_date LIKE ?", (f"{month_prefix}%",))

        if row:
            return {"year": year, "month": month, "new_users": row["cnt"]}
        return _db_error_result("get_month_new_users", "users 表无数据")
    except Exception as exc:
        return _db_error_result("get_month_new_users", str(exc))


def get_order_count() -> dict[str, Any]:
    """获取今日订单数量

    Returns:
        包含今日订单数量的字典
    """
    try:
        today = date.today().isoformat()
        row = _fetch_one("SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount), 0) as total FROM orders WHERE order_date = ?", (today,))

        if row and row["cnt"] > 0:
            return {"date": today, "order_count": row["cnt"], "total_amount": row["total"]}

        latest = _fetch_one("SELECT COUNT(*) as cnt FROM orders WHERE order_date = (SELECT MAX(order_date) FROM orders)")

        if latest and latest["cnt"] > 0:
            return {"date": today, "order_count": latest["cnt"], "note": "使用最近一天数据"}
        return _db_error_result("get_order_count", "orders 表无今日数据")
    except Exception as exc:
        return _db_error_result("get_order_count", str(exc))


def get_top_products(limit: int = 5) -> dict[str, Any]:
    """获取 Top 商品

    Args:
        limit: 返回数量，默认 5

    Returns:
        包含 Top 商品列表的字典
    """
    try:
        rows = _fetch_all(
            """
            SELECT p.name, p.category, SUM(o.quantity) as total_qty, SUM(o.total_amount) as total_revenue
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.status = 'completed'
            GROUP BY o.product_id
            ORDER BY total_revenue DESC
            LIMIT ?
            """,
            (limit,),
        )

        products = [
            {
                "name": row["name"],
                "category": row["category"],
                "total_qty": row["total_qty"],
                "total_revenue": round(row["total_revenue"], 2),
            }
            for row in rows
        ]
        return {"top_products": products, "count": len(products)}
    except Exception as exc:
        return _db_error_result("get_top_products", str(exc))


def get_refund_rate() -> dict[str, Any]:
    """获取退款率

    Returns:
        包含退款率的字典
    """
    try:
        total_row = _fetch_one("SELECT COUNT(*) as total FROM orders")
        refund_row = _fetch_one("SELECT COUNT(*) as refund_count, COALESCE(SUM(refund_amount), 0) as refund_total FROM refund_orders")

        total_orders = total_row["total"] if total_row else 0
        refund_count = refund_row["refund_count"] if refund_row else 0
        refund_total = refund_row["refund_total"] if refund_row else 0

        rate = round(refund_count / total_orders * 100, 2) if total_orders > 0 else 0.0
        return {
            "total_orders": total_orders,
            "refund_count": refund_count,
            "refund_rate_percent": rate,
            "refund_total_amount": round(refund_total, 2),
        }
    except Exception as exc:
        return _db_error_result("get_refund_rate", str(exc))


def simulate_refund_order(order_id: str = "ORD-DEMO-0001", amount: float = 99.0) -> dict[str, Any]:
    """模拟创建退款单（纯内存仿真）

    高风险写操作演示工具：不读写数据库，不调用任何外部系统，
    仅在内存中构造一条仿真退款单，用于现场演示
    PolicyEngine 拦截 → 审批单创建 → waiting_approval → 审批通过 resume 的完整 HITL 链路。

    Args:
        order_id: 订单号，默认演示订单
        amount: 退款金额，默认演示金额

    Returns:
        仿真退款单字典（simulated=True 标记非真实数据）
    """
    return {
        "simulated": True,
        "refund_id": f"SIM-RF-{uuid.uuid4().hex[:8]}",
        "order_id": order_id,
        "amount": amount,
        "status": "refund_created",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "note": "仿真数据，未修改任何真实订单",
    }
