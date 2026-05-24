from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillMatchRequest(BaseModel):
    query: str


def _get_skill_registry():
    from app.main import get_skill_registry
    return get_skill_registry()


@router.get("")
async def list_skills():
    registry = _get_skill_registry()
    return [s.model_dump() for s in registry.list_skills()]


@router.post("/match")
async def match_skills(request: SkillMatchRequest):
    registry = _get_skill_registry()
    matched = registry.match(request.query)
    return {"query": request.query, "matched_skills": [s.model_dump() for s in matched]}
