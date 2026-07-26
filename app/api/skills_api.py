from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import require_permission

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillMatchRequest(BaseModel):
    query: str


def _get_skill_registry():
    from app.main import get_skill_registry
    return get_skill_registry()


@router.get("")
async def list_skills(_current_user=Depends(require_permission("skills:read"))):
    registry = _get_skill_registry()
    return [s.model_dump() for s in registry.list_skills()]


@router.post("/match")
async def match_skills(request: SkillMatchRequest, _current_user=Depends(require_permission("skills:read"))):
    registry = _get_skill_registry()
    matched = registry.match(request.query)
    return {"query": request.query, "matched_skills": [s.model_dump() for s in matched]}
