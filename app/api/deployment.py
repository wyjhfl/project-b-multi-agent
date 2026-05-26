from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.dependencies import require_permission
from app.core.deployment_guard import run_deployment_checks

router = APIRouter(prefix="/deployment", tags=["deployment"])


@router.get("/check")
async def deployment_check(_current_user=Depends(require_permission("metrics:read"))):
    return run_deployment_checks().model_dump()
