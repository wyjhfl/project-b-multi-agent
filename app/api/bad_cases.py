from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/eval", tags=["eval"])


class BadCaseRunRequest(BaseModel):
    use_judge: bool = False
    limit: int | None = None
    suite: str | None = None


class BadCaseRunResponse(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    accuracy: float = 0.0
    judge_average_score: float | None = None
    failures: list[dict] = Field(default_factory=list)


@router.post("/bad-cases/run", response_model=BadCaseRunResponse)
async def run_bad_cases(request: BadCaseRunRequest):
    from app.harness.eval.bad_case_runner import BadCaseRunner
    from app.harness.eval.judge import FakeJudge
    from app.main import get_metrics_recorder

    metrics = get_metrics_recorder()
    judge = FakeJudge() if request.use_judge else None

    runner = BadCaseRunner(metrics_recorder=metrics, judge=judge)
    summary = runner.run(use_judge=request.use_judge, limit=request.limit, suite=request.suite)

    return BadCaseRunResponse(
        total=summary.total,
        passed=summary.passed,
        failed=summary.failed,
        accuracy=summary.accuracy,
        judge_average_score=summary.judge_average_score,
        failures=[r.model_dump() for r in summary.failures],
    )


@router.get("/bad-cases")
async def list_bad_cases(
    suite: str | None = Query(default=None),
    tag: str | None = Query(default=None),
):
    from app.harness.eval.bad_case_runner import BadCaseRunner

    runner = BadCaseRunner()
    cases = runner.load_cases()

    if suite is not None:
        cases = [c for c in cases if c.suite == suite]
    if tag is not None:
        cases = [c for c in cases if tag in c.tags]

    return [c.model_dump() for c in cases]
