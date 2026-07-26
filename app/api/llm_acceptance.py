from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import require_permission
from app.harness.llm.preflight import run_llm_provider_preflight

router = APIRouter(prefix="/llm", tags=["llm_acceptance"])


@router.get("/preflight")
async def llm_preflight(
    network_check: bool = Query(default=False, description="是否执行网络连通性检查（默认关闭）"),
    _current_user=Depends(require_permission("metrics:read")),
):
    result = run_llm_provider_preflight(perform_network_check=network_check)
    return result.to_dict()
