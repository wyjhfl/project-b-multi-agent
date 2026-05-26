from __future__ import annotations

from fastapi import APIRouter

from app.auth.oidc_config import build_oidc_status
from app.core.config import settings

router = APIRouter(prefix="/auth/oidc", tags=["auth", "oidc"])


@router.get("/status")
async def get_oidc_status():
    """返回 OIDC/SSO 最小接入骨架的配置状态（不包含密钥原文）。"""
    return build_oidc_status(settings)
