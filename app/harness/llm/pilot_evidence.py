from __future__ import annotations

from typing import Any

from app.core.structured_logging import redact_mapping


def collect_llm_runtime_evidence_snapshot(metrics_payload: dict[str, Any]) -> dict[str, Any]:
    runtime = dict(metrics_payload or {})
    llm_budget = dict(runtime.get("llm_budget") or {})
    llm_cache = dict(runtime.get("llm_cache") or {})

    safe_summary = {
        "llm_budget": {
            "enabled": bool(llm_budget.get("enabled", False)),
            "scope": llm_budget.get("scope"),
            "window_start": llm_budget.get("window_start"),
            "window_end": llm_budget.get("window_end"),
            "total_cost": float(llm_budget.get("total_cost", 0.0) or 0.0),
            "soft_limit": float(llm_budget.get("soft_limit", 0.0) or 0.0),
            "hard_limit": float(llm_budget.get("hard_limit", 0.0) or 0.0),
        },
        "llm_cache": {
            "enabled": bool(llm_cache.get("enabled", False)),
            "size": int(llm_cache.get("size", 0) or 0),
            "ttl_seconds": int(llm_cache.get("ttl_seconds", 0) or 0),
            "hit_count": int(llm_cache.get("hit_count", 0) or 0),
            "miss_count": int(llm_cache.get("miss_count", 0) or 0),
        },
        "runtime_metric_keys": sorted(runtime.keys()),
    }
    return redact_mapping(safe_summary)
