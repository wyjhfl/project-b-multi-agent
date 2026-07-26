from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import require_permission

router = APIRouter(prefix="/eval", tags=["eval"])

_last_multi_agent_accuracy: float | None = None
_last_nl2sql_accuracy: float | None = None


class EvalSummaryResponse(BaseModel):
    nl2sql_eval_available: bool = False
    multi_agent_eval_available: bool = False
    bad_case_eval_available: bool = False
    latest_multi_agent_accuracy: float | None = None
    latest_nl2sql_accuracy: float | None = None
    bad_case_count: int = 0
    case_counts: dict[str, int] = Field(default_factory=dict)


class SuiteResult(BaseModel):
    suite: str
    total: int
    passed: int
    accuracy: float
    failures: list[dict] = Field(default_factory=list)


class RunAllResponse(BaseModel):
    suites: list[SuiteResult] = Field(default_factory=list)
    total_cases: int = 0
    total_passed: int = 0
    overall_accuracy: float = 0.0
    failures: list[dict] = Field(default_factory=list)


@router.get("/summary", response_model=EvalSummaryResponse)
async def get_eval_summary(_current_user=Depends(require_permission("eval:read"))):
    global _last_multi_agent_accuracy, _last_nl2sql_accuracy

    nl2sql_eval_available = False
    multi_agent_eval_available = False
    bad_case_eval_available = False
    case_counts: dict[str, int] = {}
    bad_case_count = 0

    try:
        from app.harness.eval.cases import EvalCaseLoader
        loader = EvalCaseLoader()
        nl2sql_cases = loader.load()
        nl2sql_eval_available = True
        case_counts["nl2sql"] = len(nl2sql_cases)
    except Exception:
        case_counts["nl2sql"] = 0

    try:
        from app.harness.eval.multi_agent_runner import MultiAgentEvalRunner
        multi_agent_eval_available = True
        from app.main import get_multi_agent_orchestrator
        orchestrator = get_multi_agent_orchestrator()
        runner = MultiAgentEvalRunner(orchestrator)
        cases = runner.load_cases()
        case_counts["multi_agent"] = len(cases)
    except Exception:
        case_counts["multi_agent"] = 0

    try:
        from app.harness.eval.bad_case_runner import BadCaseRunner
        bc_runner = BadCaseRunner()
        bc_cases = bc_runner.load_cases()
        bad_case_eval_available = True
        bad_case_count = len(bc_cases)
        case_counts["bad_cases"] = bad_case_count
    except Exception:
        case_counts["bad_cases"] = 0

    return EvalSummaryResponse(
        nl2sql_eval_available=nl2sql_eval_available,
        multi_agent_eval_available=multi_agent_eval_available,
        bad_case_eval_available=bad_case_eval_available,
        latest_multi_agent_accuracy=_last_multi_agent_accuracy,
        latest_nl2sql_accuracy=_last_nl2sql_accuracy,
        bad_case_count=bad_case_count,
        case_counts=case_counts,
    )


@router.post("/run-all", response_model=RunAllResponse)
async def run_all_evals(_current_user=Depends(require_permission("eval:run"))):
    global _last_multi_agent_accuracy, _last_nl2sql_accuracy

    suites: list[SuiteResult] = []
    total_cases = 0
    total_passed = 0
    all_failures: list[dict] = []

    try:
        from app.harness.eval.nl2sql_runner import NL2SQLEvalRunner
        nl2sql_runner = NL2SQLEvalRunner()
        nl2sql_stats = nl2sql_runner.run()
        _last_nl2sql_accuracy = nl2sql_stats.accuracy
        suites.append(SuiteResult(
            suite="nl2sql",
            total=nl2sql_stats.total,
            passed=nl2sql_stats.passed,
            accuracy=nl2sql_stats.accuracy,
            failures=[f.model_dump() for f in nl2sql_stats.failures],
        ))
        total_cases += nl2sql_stats.total
        total_passed += nl2sql_stats.passed
        all_failures.extend([{"suite": "nl2sql", **f.model_dump()} for f in nl2sql_stats.failures])
    except Exception as exc:
        suites.append(SuiteResult(
            suite="nl2sql",
            total=0,
            passed=0,
            accuracy=0.0,
            failures=[{"case_id": "__error__", "reason": str(exc)}],
        ))

    try:
        from app.main import get_multi_agent_orchestrator
        from app.harness.eval.multi_agent_runner import MultiAgentEvalRunner
        orchestrator = get_multi_agent_orchestrator()
        ma_runner = MultiAgentEvalRunner(orchestrator)
        ma_result = ma_runner.run()
        _last_multi_agent_accuracy = ma_result.accuracy
        suites.append(SuiteResult(
            suite="multi_agent",
            total=ma_result.total,
            passed=ma_result.passed,
            accuracy=ma_result.accuracy,
            failures=[f.model_dump() for f in ma_result.failures],
        ))
        total_cases += ma_result.total
        total_passed += ma_result.passed
        all_failures.extend([{"suite": "multi_agent", **f.model_dump()} for f in ma_result.failures])
    except Exception as exc:
        suites.append(SuiteResult(
            suite="multi_agent",
            total=0,
            passed=0,
            accuracy=0.0,
            failures=[{"case_id": "__error__", "reason": str(exc)}],
        ))

    overall_accuracy = round(total_passed / total_cases, 4) if total_cases > 0 else 0.0

    return RunAllResponse(
        suites=suites,
        total_cases=total_cases,
        total_passed=total_passed,
        overall_accuracy=overall_accuracy,
        failures=all_failures,
    )
