from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
"""Dify 工作流评估使用的数据结构。"""

SUPPORTED_WORKFLOW_TYPES = {1, 2}


@dataclass
class DifyEvalCase:
    """单条 Dify 工作流固定评估样例。"""

    id: str
    name: str
    workflow_type: int
    query: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    expected_keywords: List[str] = field(default_factory=list)
    required_sections: List[str] = field(default_factory=list)
    forbidden_keywords: List[str] = field(default_factory=list)
    min_length: int = 80
    max_length: Optional[int] = None
    rubric: str = ""
    tags: List[str] = field(default_factory=list)
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DifyEvalCase":
        workflow_type = int(data["workflow_type"])
        if workflow_type not in SUPPORTED_WORKFLOW_TYPES:
            raise ValueError(
                f"不支持的 Dify 评估工作流类型: {workflow_type}；当前仅评估 "
                "type=1（JD 生成）和 type=2（评分标准生成）。"
            )
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or data["id"]),
            workflow_type=workflow_type,
            query=str(data["query"]),
            inputs=dict(data.get("inputs") or {}),
            expected_keywords=[str(item) for item in data.get("expected_keywords") or []],
            required_sections=[str(item) for item in data.get("required_sections") or []],
            forbidden_keywords=[str(item) for item in data.get("forbidden_keywords") or []],
            min_length=int(data.get("min_length") or 80),
            max_length=int(data["max_length"]) if data.get("max_length") is not None else None,
            rubric=str(data.get("rubric") or ""),
            tags=[str(item) for item in data.get("tags") or []],
            enabled=bool(data.get("enabled", True)),
        )


@dataclass
class RuleCheckResult:
    """单个确定性规则检查结果。"""

    name: str
    passed: bool
    score: float
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMJudgeResult:
    """大模型裁判评分结果。"""

    enabled: bool
    score: Optional[float] = None
    passed: Optional[bool] = None
    reason: str = ""
    raw_response: str = ""


@dataclass
class DifyRunResult:
    """某个评估样例的一次重复运行结果。"""

    repeat_index: int
    success: bool
    output: str
    latency_ms: int
    error: Optional[str] = None
    raw_response: Any = None
    rule_checks: List[RuleCheckResult] = field(default_factory=list)
    rule_score: float = 0.0
    judge: LLMJudgeResult = field(default_factory=lambda: LLMJudgeResult(enabled=False))


@dataclass
class CaseEvaluationResult:
    """单条评估样例的聚合评估结果。"""

    case: DifyEvalCase
    runs: List[DifyRunResult]
    passed: bool
    average_rule_score: float
    average_judge_score: Optional[float]
    output_length_stddev: float
    latency_average_ms: float
    failure_reasons: List[str]


@dataclass
class RegressionComparison:
    """当前评估结果与历史基线报告的回归对比。"""

    baseline_path: str
    current_pass_rate: float
    baseline_pass_rate: Optional[float]
    pass_rate_delta: Optional[float]
    current_average_score: float
    baseline_average_score: Optional[float]
    average_score_delta: Optional[float]


@dataclass
class DifyEvalReport:
    """完整的 Dify 工作流评估报告。"""

    run_id: str
    generated_at: str
    repeat_runs: int
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    average_rule_score: float
    average_judge_score: Optional[float]
    average_latency_ms: float
    case_results: List[CaseEvaluationResult]
    regression: Optional[RegressionComparison] = None
