from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
"""HR Agent 评估使用的数据结构。"""


@dataclass
class AgentEvalCase:
    """单条 HR Agent 固定评估样例。"""

    id: str
    name: str
    message: str
    user_id: str = "00000000-0000-0000-0000-000000000001"
    conversation_id: Optional[str] = None
    auto_execute: bool = True
    confirmed_requirements: Optional[Dict[str, Any]] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    expected_intent: Optional[str] = None
    expected_route: Optional[str] = None
    expected_requires_confirmation: Optional[bool] = None
    expected_artifact_types: List[str] = field(default_factory=list)
    forbidden_artifact_types: List[str] = field(default_factory=list)
    expected_step_ids: List[str] = field(default_factory=list)
    expected_step_statuses: Dict[str, str] = field(default_factory=dict)
    expected_tools: List[str] = field(default_factory=list)
    expected_missing_fields: List[str] = field(default_factory=list)
    missing_fields_exact: bool = False
    expected_message_keywords: List[str] = field(default_factory=list)
    forbidden_message_keywords: List[str] = field(default_factory=list)
    content_checks: Dict[str, Any] = field(default_factory=dict)
    rubric: str = ""
    tags: List[str] = field(default_factory=list)
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentEvalCase":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or data["id"]),
            message=str(data["message"]),
            user_id=str(data.get("user_id") or "00000000-0000-0000-0000-000000000001"),
            conversation_id=(
                str(data["conversation_id"]) if data.get("conversation_id") is not None else None
            ),
            auto_execute=bool(data.get("auto_execute", True)),
            confirmed_requirements=(
                dict(data["confirmed_requirements"])
                if isinstance(data.get("confirmed_requirements"), dict)
                else None
            ),
            attachments=[dict(item) for item in data.get("attachments") or []],
            expected_intent=(
                str(data["expected_intent"]) if data.get("expected_intent") is not None else None
            ),
            expected_route=(
                str(data["expected_route"]) if data.get("expected_route") is not None else None
            ),
            expected_requires_confirmation=(
                bool(data["expected_requires_confirmation"])
                if data.get("expected_requires_confirmation") is not None
                else None
            ),
            expected_artifact_types=[
                str(item) for item in data.get("expected_artifact_types") or []
            ],
            forbidden_artifact_types=[
                str(item) for item in data.get("forbidden_artifact_types") or []
            ],
            expected_step_ids=[str(item) for item in data.get("expected_step_ids") or []],
            expected_step_statuses={
                str(key): str(value)
                for key, value in (data.get("expected_step_statuses") or {}).items()
            },
            expected_tools=[str(item) for item in data.get("expected_tools") or []],
            expected_missing_fields=[
                str(item) for item in data.get("expected_missing_fields") or []
            ],
            missing_fields_exact=bool(data.get("missing_fields_exact", False)),
            expected_message_keywords=[
                str(item) for item in data.get("expected_message_keywords") or []
            ],
            forbidden_message_keywords=[
                str(item) for item in data.get("forbidden_message_keywords") or []
            ],
            content_checks=dict(data.get("content_checks") or {}),
            rubric=str(data.get("rubric") or ""),
            tags=[str(item) for item in data.get("tags") or []],
            enabled=bool(data.get("enabled", True)),
        )


@dataclass
class AgentRuleCheckResult:
    """单个确定性规则检查结果。"""

    name: str
    passed: bool
    score: float
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentLLMJudgeResult:
    """大模型裁判评分结果。"""

    enabled: bool
    score: Optional[float] = None
    passed: Optional[bool] = None
    reason: str = ""
    raw_response: str = ""


@dataclass
class AgentRunResult:
    """某个评估样例的一次重复运行结果。"""

    repeat_index: int
    success: bool
    response: Dict[str, Any]
    latency_ms: int
    error: Optional[str] = None
    rule_checks: List[AgentRuleCheckResult] = field(default_factory=list)
    rule_score: float = 0.0
    judge: AgentLLMJudgeResult = field(default_factory=lambda: AgentLLMJudgeResult(enabled=False))


@dataclass
class AgentCaseEvaluationResult:
    """单条评估样例的聚合评估结果。"""

    case: AgentEvalCase
    runs: List[AgentRunResult]
    passed: bool
    average_rule_score: float
    average_judge_score: Optional[float]
    response_signature_stability: float
    latency_average_ms: float
    failure_reasons: List[str]


@dataclass
class AgentRegressionComparison:
    """当前评估结果与历史基线报告的回归对比。"""

    baseline_path: str
    current_pass_rate: float
    baseline_pass_rate: Optional[float]
    pass_rate_delta: Optional[float]
    current_average_score: float
    baseline_average_score: Optional[float]
    average_score_delta: Optional[float]


@dataclass
class AgentQualityMetrics:
    """按 Agent 关键能力拆分的质量指标。"""

    intent_accuracy: Optional[float] = None
    route_accuracy: Optional[float] = None
    confirmation_accuracy: Optional[float] = None
    artifact_contract_pass_rate: Optional[float] = None
    tool_contract_pass_rate: Optional[float] = None
    missing_field_accuracy: Optional[float] = None


@dataclass
class AgentEvalReport:
    """完整的 HR Agent 评估报告。"""

    run_id: str
    generated_at: str
    repeat_runs: int
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    average_rule_score: float
    average_judge_score: Optional[float]
    average_signature_stability: float
    average_latency_ms: float
    case_results: List[AgentCaseEvaluationResult]
    quality_metrics: AgentQualityMetrics
    regression: Optional[AgentRegressionComparison] = None
