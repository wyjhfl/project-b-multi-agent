from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.dependencies import require_permission

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/{session_id}")
async def get_memory(session_id: str, limit: int = 10, _current_user=Depends(require_permission("memory:read"))):
    from app.main import get_memory
    memory = get_memory()
    messages = memory.get_messages(session_id, limit=limit)
    context = memory.get_context(session_id)
    return {"session_id": session_id, "messages": messages, "context": context}


@router.delete("/{session_id}")
async def clear_memory(session_id: str, _current_user=Depends(require_permission("memory:manage"))):
    from app.main import get_memory
    memory = get_memory()
    memory.clear(session_id)
    return {"session_id": session_id, "cleared": True}
