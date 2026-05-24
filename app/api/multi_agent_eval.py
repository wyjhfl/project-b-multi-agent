from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.harness.eval.multi_agent_runner import MultiAgentEvalResult

router = APIRouter(prefix="/tasks/eval", tags=["eval"])


class MultiAgentEvalResponse(BaseModel):
    total: int
    passed: int
    accuracy: float
    failures: list[dict] = Field(default_factory=list)
    mode_confusion_count: int = 0


@router.post("/multi-agent", response_model=MultiAgentEvalResponse)
async def run_multi_agent_eval():
    from app.main import get_multi_agent_orchestrator

    orchestrator = get_multi_agent_orchestrator()

    from app.harness.eval.multi_agent_runner import MultiAgentEvalRunner
    runner = MultiAgentEvalRunner(orchestrator)
    result: MultiAgentEvalResult = runner.run()

    return MultiAgentEvalResponse(
        total=result.total,
        passed=result.passed,
        accuracy=result.accuracy,
        failures=[f.model_dump() for f in result.failures],
        mode_confusion_count=result.mode_confusion_count,
    )
