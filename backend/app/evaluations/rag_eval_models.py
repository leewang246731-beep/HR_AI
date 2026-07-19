from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
"""RAG 知识库评估使用的数据结构。"""


@dataclass
class RAGEvalCase:
    """单条 RAG 固定问答评估样例。"""

    id: str
    name: str
    question: str
    user_id: str
    knowledge_base_id: Optional[str] = None
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    context_limit: int = 5
    should_answer: bool = True
    expected_context_used: Optional[bool] = None
    reference_answer: str = ""
    expected_answer_keywords: List[str] = field(default_factory=list)
    expected_document_ids: List[str] = field(default_factory=list)
    expected_chunk_refs: List[str] = field(default_factory=list)
    expected_context_keywords: List[str] = field(default_factory=list)
    expected_query_keywords: List[str] = field(default_factory=list)
    forbidden_answer_keywords: List[str] = field(default_factory=list)
    refusal_keywords: List[str] = field(default_factory=lambda: ["没有找到", "无法", "不足", "知识库"])
    min_recall_at_k: Optional[float] = None
    min_mrr: Optional[float] = None
    min_precision_at_k: Optional[float] = None
    min_ndcg_at_k: Optional[float] = None
    min_citation_accuracy: Optional[float] = None
    min_answer_hit_rate: Optional[float] = None
    min_context_keyword_recall: Optional[float] = None
    min_answer_length: int = 1
    max_answer_length: Optional[int] = None
    rubric: str = ""
    tags: List[str] = field(default_factory=list)
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGEvalCase":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or data["id"]),
            question=str(data["question"]),
            user_id=str(data["user_id"]),
            knowledge_base_id=(
                str(data["knowledge_base_id"])
                if data.get("knowledge_base_id") is not None
                else None
            ),
            conversation_history=[
                {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
                for item in data.get("conversation_history") or []
                if isinstance(item, dict)
            ],
            context_limit=int(data.get("context_limit") or 5),
            should_answer=bool(data.get("should_answer", True)),
            expected_context_used=(
                bool(data["expected_context_used"])
                if data.get("expected_context_used") is not None
                else None
            ),
            reference_answer=str(data.get("reference_answer") or ""),
            expected_answer_keywords=[
                str(item) for item in data.get("expected_answer_keywords") or []
            ],
            expected_document_ids=[
                str(item) for item in data.get("expected_document_ids") or data.get("expected_source_ids") or []
            ],
            expected_chunk_refs=[
                _normalize_chunk_ref(item) for item in data.get("expected_chunk_refs") or []
            ],
            expected_context_keywords=[
                str(item) for item in data.get("expected_context_keywords") or []
            ],
            expected_query_keywords=[
                str(item) for item in data.get("expected_query_keywords") or []
            ],
            forbidden_answer_keywords=[
                str(item) for item in data.get("forbidden_answer_keywords") or data.get("forbidden_keywords") or []
            ],
            refusal_keywords=[
                str(item) for item in data.get("refusal_keywords") or ["没有找到", "无法", "不足", "知识库"]
            ],
            min_recall_at_k=_optional_float(data.get("min_recall_at_k")),
            min_mrr=_optional_float(data.get("min_mrr")),
            min_precision_at_k=_optional_float(data.get("min_precision_at_k")),
            min_ndcg_at_k=_optional_float(data.get("min_ndcg_at_k")),
            min_citation_accuracy=_optional_float(data.get("min_citation_accuracy")),
            min_answer_hit_rate=_optional_float(data.get("min_answer_hit_rate")),
            min_context_keyword_recall=_optional_float(data.get("min_context_keyword_recall")),
            min_answer_length=int(data.get("min_answer_length") or 1),
            max_answer_length=(
                int(data["max_answer_length"]) if data.get("max_answer_length") is not None else None
            ),
            rubric=str(data.get("rubric") or ""),
            tags=[str(item) for item in data.get("tags") or []],
            enabled=bool(data.get("enabled", True)),
        )


@dataclass
class RAGRuleCheckResult:
    """单个 RAG 确定性规则检查结果。"""

    name: str
    passed: bool
    score: float
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGRetrievalMetrics:
    """RAG 检索阶段指标。"""

    k: int
    context_used: bool
    num_sources: int
    retrieved_document_ids: List[str] = field(default_factory=list)
    retrieved_chunk_refs: List[str] = field(default_factory=list)
    relevant_ranks: List[int] = field(default_factory=list)
    recall_at_k: Optional[float] = None
    precision_at_k: Optional[float] = None
    hit_rate_at_k: Optional[float] = None
    mrr: Optional[float] = None
    ndcg_at_k: Optional[float] = None
    citation_accuracy: Optional[float] = None
    context_keyword_recall: Optional[float] = None


@dataclass
class RAGAnswerMetrics:
    """RAG 生成答案阶段指标。"""

    answer_hit_rate: float
    forbidden_keyword_hits: List[str] = field(default_factory=list)
    refusal_accuracy: Optional[float] = None
    answer_length: int = 0


@dataclass
class RAGRagasResult:
    """RAGAS 对一次或多次 RAG 输出的聚合评分。"""

    enabled: bool
    scores: Dict[str, float] = field(default_factory=dict)
    failed_metrics: List[str] = field(default_factory=list)
    error: str = ""


@dataclass
class RAGRunResult:
    """某个 RAG 评估样例的一次重复运行结果。"""

    repeat_index: int
    success: bool
    answer: str
    latency_ms: int
    context_used: bool = False
    sources: List[Dict[str, Any]] = field(default_factory=list)
    query_rewrite: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    rule_checks: List[RAGRuleCheckResult] = field(default_factory=list)
    rule_score: float = 0.0
    retrieval_metrics: RAGRetrievalMetrics = field(
        default_factory=lambda: RAGRetrievalMetrics(k=5, context_used=False, num_sources=0)
    )
    answer_metrics: RAGAnswerMetrics = field(
        default_factory=lambda: RAGAnswerMetrics(answer_hit_rate=0.0)
    )


@dataclass
class RAGCaseEvaluationResult:
    """单条 RAG 样例的聚合评估结果。"""

    case: RAGEvalCase
    runs: List[RAGRunResult]
    passed: bool
    average_rule_score: float
    average_recall_at_k: Optional[float]
    average_precision_at_k: Optional[float]
    average_hit_rate_at_k: Optional[float]
    average_mrr: Optional[float]
    average_ndcg_at_k: Optional[float]
    average_citation_accuracy: Optional[float]
    average_context_keyword_recall: Optional[float]
    average_answer_hit_rate: float
    average_refusal_accuracy: Optional[float]
    latency_average_ms: float
    answer_length_stddev: float
    failure_reasons: List[str]


@dataclass
class RAGRegressionComparison:
    """当前 RAG 评估结果与历史基线报告的回归对比。"""

    baseline_path: str
    current_pass_rate: float
    baseline_pass_rate: Optional[float]
    pass_rate_delta: Optional[float]
    current_average_recall_at_k: Optional[float]
    baseline_average_recall_at_k: Optional[float]
    recall_at_k_delta: Optional[float]
    current_average_mrr: Optional[float]
    baseline_average_mrr: Optional[float]
    mrr_delta: Optional[float]
    current_average_citation_accuracy: Optional[float]
    baseline_average_citation_accuracy: Optional[float]
    citation_accuracy_delta: Optional[float]
    current_average_answer_hit_rate: float
    baseline_average_answer_hit_rate: Optional[float]
    answer_hit_rate_delta: Optional[float]


@dataclass
class RAGEvalReport:
    """完整的 RAG 知识库评估报告。"""

    run_id: str
    generated_at: str
    repeat_runs: int
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    average_rule_score: float
    average_recall_at_k: Optional[float]
    average_precision_at_k: Optional[float]
    average_hit_rate_at_k: Optional[float]
    average_mrr: Optional[float]
    average_ndcg_at_k: Optional[float]
    average_citation_accuracy: Optional[float]
    average_context_keyword_recall: Optional[float]
    average_answer_hit_rate: float
    average_refusal_accuracy: Optional[float]
    average_latency_ms: float
    ragas: RAGRagasResult
    case_results: List[RAGCaseEvaluationResult]
    regression: Optional[RAGRegressionComparison] = None


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_chunk_ref(value: Any) -> str:
    if isinstance(value, dict):
        document_id = str(value.get("document_id") or "").strip()
        chunk_index = value.get("chunk_index")
        chunk_id = str(value.get("chunk_id") or "").strip()
        if chunk_id:
            return f"chunk_id:{chunk_id}"
        if document_id and chunk_index is not None:
            return f"{document_id}#{chunk_index}"
        if document_id:
            return document_id
    return str(value).strip()
