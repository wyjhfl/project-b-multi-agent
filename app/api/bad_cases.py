from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import require_permission
from app.core.config import settings

router = APIRouter(prefix="/eval", tags=["eval"])


class BadCaseRunRequest(BaseModel):
    use_judge: bool = False
    limit: int | None = None
    suite: str | None = None
    judge_provider: str | None = None
    judge_fallback_to_fake: bool | None = None


class BadCaseRunResponse(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    accuracy: float = 0.0
    judge_average_score: float | None = None
    failures: list[dict] = Field(default_factory=list)


@router.post("/bad-cases/run", response_model=BadCaseRunResponse)
async def run_bad_cases(request: BadCaseRunRequest, _current_user=Depends(require_permission("eval:run"))):
    from app.harness.eval.bad_case_runner import BadCaseRunner
    from app.harness.eval.judge import FakeJudge, LLMJudgeProvider
    from app.main import get_metrics_recorder

    metrics = get_metrics_recorder()
    judge = None
    judge_provider = request.judge_provider or settings.judge_provider
    fallback_to_fake = (
        settings.judge_fallback_to_fake
        if request.judge_fallback_to_fake is None
        else request.judge_fallback_to_fake
    )
    if request.use_judge:
        if judge_provider == "litellm":
            judge = LLMJudgeProvider(
                provider="litellm",
                fallback_to_fake=fallback_to_fake,
                model=settings.judge_model or None,
                base_url=settings.judge_base_url or settings.llm_base_url or None,
                timeout_seconds=settings.judge_timeout_seconds,
                max_retries=settings.judge_max_retries,
                retry_backoff_seconds=settings.judge_retry_backoff_seconds,
            )
        elif judge_provider == "fake":
            judge = FakeJudge()
        else:
            judge = LLMJudgeProvider(
                provider=judge_provider,
                fallback_to_fake=fallback_to_fake,
                model=settings.judge_model or None,
                base_url=settings.judge_base_url or settings.llm_base_url or None,
                timeout_seconds=settings.judge_timeout_seconds,
                max_retries=settings.judge_max_retries,
                retry_backoff_seconds=settings.judge_retry_backoff_seconds,
            )

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
    _current_user=Depends(require_permission("eval:read")),
):
    from app.harness.eval.bad_case_runner import BadCaseRunner

    runner = BadCaseRunner()
    cases = runner.load_cases()

    if suite is not None:
        cases = [c for c in cases if c.suite == suite]
    if tag is not None:
        cases = [c for c in cases if tag in c.tags]

    return [c.model_dump() for c in cases]
