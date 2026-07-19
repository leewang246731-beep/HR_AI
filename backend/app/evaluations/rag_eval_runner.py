from __future__ import annotations

import asyncio
import inspect
import json
import math
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.evaluations.rag_eval_models import (
    RAGCaseEvaluationResult,
    RAGEvalCase,
    RAGEvalReport,
    RAGRegressionComparison,
    RAGRagasResult,
    RAGRunResult,
)
from app.evaluations.rag_rule_evaluator import RAGRuleEvaluator

"""固定问答集的 RAG 知识库评估运行器。"""

class RAGEvalRunner:
    """执行 RAG 固定问答评估样例并生成评估报告。"""

    def __init__(self, rule_evaluator: Optional[RAGRuleEvaluator] = None):
        self.rule_evaluator = rule_evaluator or RAGRuleEvaluator()

    async def run(
        self,
        cases: List[RAGEvalCase],
        repeat_runs: int = 3,
        concurrency: int = 1,
        use_ragas: bool = False,
        baseline_path: Optional[Path] = None,
    ) -> RAGEvalReport:
        enabled_cases = [case for case in cases if case.enabled]
        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def run_case(case: RAGEvalCase) -> RAGCaseEvaluationResult:
            async with semaphore:
                return await self._run_case(case, repeat_runs)

        case_results = await asyncio.gather(*(run_case(case) for case in enabled_cases))
        ragas_result = self._run_ragas_if_enabled(case_results, use_ragas)
        report = self._build_report(case_results, repeat_runs, ragas_result)
        if baseline_path:
            report.regression = self._compare_with_baseline(report, baseline_path)
        return report

    async def _run_case(self, case: RAGEvalCase, repeat_runs: int) -> RAGCaseEvaluationResult:
        runs: List[RAGRunResult] = []
        for repeat_index in range(1, repeat_runs + 1):
            runs.append(await self._run_once(case, repeat_index))

        successful_runs = [run for run in runs if run.success]
        failure_reasons = self._collect_failure_reasons(runs)
        passed = bool(runs) and all(
            run.success and all(check.passed for check in run.rule_checks)
            for run in runs
        )
        answer_lengths = [run.answer_metrics.answer_length for run in successful_runs]
        return RAGCaseEvaluationResult(
            case=case,
            runs=runs,
            passed=passed,
            average_rule_score=self._mean_number([run.rule_score for run in runs], default=0.0),
            average_recall_at_k=self._mean_optional([
                run.retrieval_metrics.recall_at_k for run in successful_runs
            ]),
            average_precision_at_k=self._mean_optional([
                run.retrieval_metrics.precision_at_k for run in successful_runs
            ]),
            average_hit_rate_at_k=self._mean_optional([
                run.retrieval_metrics.hit_rate_at_k for run in successful_runs
            ]),
            average_mrr=self._mean_optional([
                run.retrieval_metrics.mrr for run in successful_runs
            ]),
            average_ndcg_at_k=self._mean_optional([
                run.retrieval_metrics.ndcg_at_k for run in successful_runs
            ]),
            average_citation_accuracy=self._mean_optional([
                run.retrieval_metrics.citation_accuracy for run in successful_runs
            ]),
            average_context_keyword_recall=self._mean_optional([
                run.retrieval_metrics.context_keyword_recall for run in successful_runs
            ]),
            average_answer_hit_rate=self._mean_number([
                run.answer_metrics.answer_hit_rate for run in successful_runs
            ], default=0.0),
            average_refusal_accuracy=self._mean_optional([
                run.answer_metrics.refusal_accuracy for run in successful_runs
            ]),
            latency_average_ms=self._mean_number([run.latency_ms for run in runs], default=0.0),
            answer_length_stddev=(
                round(pstdev(answer_lengths), 2) if len(answer_lengths) > 1 else 0.0
            ),
            failure_reasons=failure_reasons,
        )

    async def _run_once(self, case: RAGEvalCase, repeat_index: int) -> RAGRunResult:
        started = time.perf_counter()
        try:
            answer_parts: List[str] = []
            sources: List[Dict[str, Any]] = []
            query_rewrite: Dict[str, Any] = {}
            events: List[Dict[str, Any]] = []
            context_used = False

            from app.core.database import AsyncSessionLocal
            from app.services.rag_service import RAGService

            async with AsyncSessionLocal() as db:
                service = RAGService(db)
                kb_id = UUID(case.knowledge_base_id) if case.knowledge_base_id else None
                async for event in service.ask_question_stream(
                    question=case.question,
                    user_id=UUID(case.user_id),
                    knowledge_base_id=kb_id,
                    conversation_history=case.conversation_history,
                    context_limit=case.context_limit,
                ):
                    event = dict(event)
                    events.append(event)
                    event_type = event.get("type")
                    if event_type == "start":
                        sources = list(event.get("sources") or sources)
                        query_rewrite = dict(event.get("query_rewrite") or query_rewrite)
                        context_used = bool(event.get("context_used"))
                    elif event_type == "chunk":
                        answer_parts.append(str(event.get("content") or ""))
                    elif event_type == "end":
                        sources = list(event.get("sources") or sources)
                    elif event_type == "error":
                        raise RuntimeError(str(event.get("error") or "RAG 流式响应错误"))

            answer = "".join(answer_parts).strip()
            latency_ms = int((time.perf_counter() - started) * 1000)
            rule_checks, retrieval_metrics, answer_metrics = self.rule_evaluator.evaluate(
                case=case,
                answer=answer,
                sources=sources,
                context_used=context_used,
                query_rewrite=query_rewrite,
            )
            return RAGRunResult(
                repeat_index=repeat_index,
                success=True,
                answer=answer,
                latency_ms=latency_ms,
                context_used=context_used,
                sources=sources,
                query_rewrite=query_rewrite,
                events=events,
                rule_checks=rule_checks,
                rule_score=self.rule_evaluator.aggregate_score(rule_checks),
                retrieval_metrics=retrieval_metrics,
                answer_metrics=answer_metrics,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            rule_checks, retrieval_metrics, answer_metrics = self.rule_evaluator.evaluate(
                case=case,
                answer="",
                sources=[],
                context_used=False,
                query_rewrite={},
            )
            return RAGRunResult(
                repeat_index=repeat_index,
                success=False,
                answer="",
                latency_ms=latency_ms,
                error=str(exc),
                rule_checks=rule_checks,
                rule_score=0.0,
                retrieval_metrics=retrieval_metrics,
                answer_metrics=answer_metrics,
            )

    def _run_ragas_if_enabled(
        self,
        case_results: List[RAGCaseEvaluationResult],
        use_ragas: bool,
    ) -> RAGRagasResult:
        if not use_ragas:
            return RAGRagasResult(enabled=False)
        try:
            rows = self._build_ragas_rows(case_results)
            if not rows:
                return RAGRagasResult(enabled=True, error="没有可用于 RAGAS 的成功运行结果。")

            from langchain_openai import ChatOpenAI, OpenAIEmbeddings
            from ragas import EvaluationDataset, evaluate
            from ragas.embeddings import LangchainEmbeddingsWrapper
            from ragas.llms import LangchainLLMWrapper

            from app.core.config import settings

            metrics = self._load_ragas_metrics()
            if not settings.LLM_API_KEY:
                raise ValueError("LLM_API_KEY 未配置，无法执行 RAGAS 评估。")

            evaluator_llm = LangchainLLMWrapper(
                ChatOpenAI(
                    model=settings.LLM_MODEL,
                    api_key=settings.LLM_API_KEY,
                    base_url=settings.LLM_BASE_URL,
                    temperature=0,
                )
            )
            embedding_api_key = settings.EMBEDDING_API_KEY or settings.LLM_API_KEY
            evaluator_embeddings = LangchainEmbeddingsWrapper(
                OpenAIEmbeddings(
                    model=settings.EMBEDDING_MODEL,
                    api_key=embedding_api_key,
                    base_url=settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL,
                    check_embedding_ctx_length=False,
                )
            )
            metrics = [
                self._instantiate_ragas_metric(metric, evaluator_llm, evaluator_embeddings)
                for metric in metrics
            ]
            dataset = EvaluationDataset.from_list(rows)
            result = evaluate(
                dataset=dataset,
                metrics=metrics,
                llm=evaluator_llm,
                embeddings=evaluator_embeddings,
            )
            return RAGRagasResult(
                enabled=True,
                scores=self._normalize_ragas_scores(result),
                failed_metrics=self._find_failed_ragas_metrics(result),
            )
        except Exception as exc:
            return RAGRagasResult(enabled=True, error=str(exc))

    def _load_ragas_metrics(self) -> List[Any]:
        try:
            from ragas.metrics import (
                AnswerCorrectness,
                AnswerRelevancy,
                ContextPrecision,
                ContextRecall,
                Faithfulness,
            )

            return [Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall, AnswerCorrectness]
        except Exception:
            from ragas.metrics import Faithfulness, FactualCorrectness, LLMContextPrecisionWithReference, LLMContextRecall

            return [Faithfulness, LLMContextPrecisionWithReference, LLMContextRecall, FactualCorrectness]

    def _instantiate_ragas_metric(
        self,
        metric: Any,
        evaluator_llm: Any,
        evaluator_embeddings: Any,
    ) -> Any:
        if not isinstance(metric, type):
            return metric

        parameters = inspect.signature(metric).parameters
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        kwargs: Dict[str, Any] = {}
        if accepts_kwargs or "llm" in parameters:
            kwargs["llm"] = evaluator_llm
        if accepts_kwargs or "embeddings" in parameters:
            kwargs["embeddings"] = evaluator_embeddings
        if metric.__name__ == "AnswerRelevancy" and (
            accepts_kwargs or "strictness" in parameters
        ):
            kwargs["strictness"] = 1
        return metric(**kwargs)

    def _build_ragas_rows(self, case_results: List[RAGCaseEvaluationResult]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for case_result in case_results:
            case = case_result.case
            if not case.reference_answer:
                continue
            for run in case_result.runs:
                if not run.success:
                    continue
                contexts = [
                    str(source.get("content") or "")
                    for source in run.sources
                    if str(source.get("content") or "").strip()
                ]
                if not contexts:
                    continue
                rows.append({
                    "user_input": case.question,
                    "retrieved_contexts": contexts,
                    "response": run.answer,
                    "reference": case.reference_answer,
                })
        return rows

    def _normalize_ragas_scores(self, result: Any) -> Dict[str, float]:
        raw = self._extract_ragas_scores(result)

        scores: Dict[str, float] = {}
        for key, value in raw.items():
            try:
                numeric_value = float(value)
                if math.isfinite(numeric_value):
                    scores[str(key)] = round(numeric_value, 4)
            except (TypeError, ValueError):
                continue
        return scores

    def _find_failed_ragas_metrics(self, result: Any) -> List[str]:
        failed_metrics: List[str] = []
        for key, value in self._extract_ragas_scores(result).items():
            try:
                if not math.isfinite(float(value)):
                    failed_metrics.append(str(key))
            except (TypeError, ValueError):
                failed_metrics.append(str(key))
        return failed_metrics

    def _extract_ragas_scores(self, result: Any) -> Dict[str, Any]:
        if hasattr(result, "to_pandas"):
            frame = result.to_pandas()
            return {
                column: float(frame[column].mean())
                for column in frame.columns
                if column not in {"user_input", "retrieved_contexts", "response", "reference"}
            }
        if isinstance(result, dict):
            return result
        return dict(result)

    def _build_report(
        self,
        case_results: List[RAGCaseEvaluationResult],
        repeat_runs: int,
        ragas_result: RAGRagasResult,
    ) -> RAGEvalReport:
        total_cases = len(case_results)
        passed_cases = len([item for item in case_results if item.passed])
        failed_cases = total_cases - passed_cases
        return RAGEvalReport(
            run_id=str(uuid.uuid4()),
            generated_at=datetime.now(timezone.utc).isoformat(),
            repeat_runs=repeat_runs,
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            pass_rate=round(passed_cases / total_cases, 4) if total_cases else 0.0,
            average_rule_score=self._mean_number([item.average_rule_score for item in case_results], default=0.0),
            average_recall_at_k=self._mean_optional([item.average_recall_at_k for item in case_results]),
            average_precision_at_k=self._mean_optional([item.average_precision_at_k for item in case_results]),
            average_hit_rate_at_k=self._mean_optional([item.average_hit_rate_at_k for item in case_results]),
            average_mrr=self._mean_optional([item.average_mrr for item in case_results]),
            average_ndcg_at_k=self._mean_optional([item.average_ndcg_at_k for item in case_results]),
            average_citation_accuracy=self._mean_optional([item.average_citation_accuracy for item in case_results]),
            average_context_keyword_recall=self._mean_optional([item.average_context_keyword_recall for item in case_results]),
            average_answer_hit_rate=self._mean_number([item.average_answer_hit_rate for item in case_results], default=0.0),
            average_refusal_accuracy=self._mean_optional([item.average_refusal_accuracy for item in case_results]),
            average_latency_ms=self._mean_number([item.latency_average_ms for item in case_results], default=0.0),
            ragas=ragas_result,
            case_results=case_results,
        )

    def _compare_with_baseline(
        self,
        report: RAGEvalReport,
        baseline_path: Path,
    ) -> RAGRegressionComparison:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_pass_rate = baseline.get("pass_rate")
        baseline_recall = baseline.get("average_recall_at_k")
        baseline_mrr = baseline.get("average_mrr")
        baseline_citation = baseline.get("average_citation_accuracy")
        baseline_answer_hit = baseline.get("average_answer_hit_rate")
        return RAGRegressionComparison(
            baseline_path=str(baseline_path),
            current_pass_rate=report.pass_rate,
            baseline_pass_rate=baseline_pass_rate,
            pass_rate_delta=self._delta(report.pass_rate, baseline_pass_rate),
            current_average_recall_at_k=report.average_recall_at_k,
            baseline_average_recall_at_k=baseline_recall,
            recall_at_k_delta=self._delta(report.average_recall_at_k, baseline_recall),
            current_average_mrr=report.average_mrr,
            baseline_average_mrr=baseline_mrr,
            mrr_delta=self._delta(report.average_mrr, baseline_mrr),
            current_average_citation_accuracy=report.average_citation_accuracy,
            baseline_average_citation_accuracy=baseline_citation,
            citation_accuracy_delta=self._delta(report.average_citation_accuracy, baseline_citation),
            current_average_answer_hit_rate=report.average_answer_hit_rate,
            baseline_average_answer_hit_rate=baseline_answer_hit,
            answer_hit_rate_delta=self._delta(report.average_answer_hit_rate, baseline_answer_hit),
        )

    def _collect_failure_reasons(self, runs: List[RAGRunResult]) -> List[str]:
        reasons: List[str] = []
        for run in runs:
            if run.error:
                reasons.append(f"第 {run.repeat_index} 次运行：{run.error}")
            for check in run.rule_checks:
                if not check.passed:
                    reasons.append(f"第 {run.repeat_index} 次运行：{check.name} - {check.reason}")
        return reasons

    def _mean_optional(self, values: List[Optional[float]]) -> Optional[float]:
        clean_values = [float(value) for value in values if value is not None]
        if not clean_values:
            return None
        return round(mean(clean_values), 4)

    def _mean_number(self, values: List[Optional[float]], default: float) -> float:
        clean_values = [float(value) for value in values if value is not None]
        if not clean_values:
            return default
        return round(mean(clean_values), 4)

    def _delta(self, current: Optional[float], baseline: Optional[float]) -> Optional[float]:
        if current is None or baseline is None:
            return None
        return round(float(current) - float(baseline), 4)


def load_rag_eval_cases(path: Path) -> List[RAGEvalCase]:
    """从单个 JSON 文件或目录下所有 JSON 文件读取 RAG 评估样例。"""
    files = [path] if path.is_file() else sorted(path.glob("*.json"))
    cases: List[RAGEvalCase] = []
    for file_path in files:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        raw_cases = data.get("cases") if isinstance(data, dict) else data
        if not isinstance(raw_cases, list):
            raise ValueError(f"RAG 评估文件格式错误: {file_path}")
        cases.extend(RAGEvalCase.from_dict(item) for item in raw_cases)
    return cases


def rag_report_to_dict(report: RAGEvalReport) -> Dict[str, Any]:
    """将 RAG 评估报告数据结构转换为可写入 JSON 的字典。"""
    return asdict(report)


def write_rag_json_report(report: RAGEvalReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(rag_report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_rag_markdown_report(report: RAGEvalReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# RAG 知识库评估报告",
        "",
        f"- 运行 ID：`{report.run_id}`",
        f"- 生成时间：`{report.generated_at}`",
        f"- 每条样例重复运行次数：`{report.repeat_runs}`",
        f"- 样例总数：`{report.total_cases}`",
        f"- 通过样例数：`{report.passed_cases}`",
        f"- 失败样例数：`{report.failed_cases}`",
        f"- 通过率：`{report.pass_rate:.2%}`",
        f"- 规则平均分：`{report.average_rule_score:.4f}`",
        f"- Recall@K：`{_format_optional_score(report.average_recall_at_k)}`",
        f"- Precision@K：`{_format_optional_score(report.average_precision_at_k)}`",
        f"- HitRate@K：`{_format_optional_score(report.average_hit_rate_at_k)}`",
        f"- MRR：`{_format_optional_score(report.average_mrr)}`",
        f"- NDCG@K：`{_format_optional_score(report.average_ndcg_at_k)}`",
        f"- 引用来源正确率：`{_format_optional_score(report.average_citation_accuracy)}`",
        f"- 上下文关键词召回率：`{_format_optional_score(report.average_context_keyword_recall)}`",
        f"- 答案命中率：`{report.average_answer_hit_rate:.4f}`",
        f"- 拒答正确率：`{_format_optional_score(report.average_refusal_accuracy)}`",
        f"- 平均延迟：`{report.average_latency_ms:.2f} ms`",
        "",
    ]
    if report.ragas.enabled:
        lines.extend(["## RAGAS 评估", ""])
        if report.ragas.error:
            lines.append(f"- RAGAS 执行失败：`{report.ragas.error}`")
        elif report.ragas.scores:
            for key, value in report.ragas.scores.items():
                lines.append(f"- {key}：`{value:.4f}`")
        else:
            lines.append("- RAGAS 未返回可解析分数。")
        for key in report.ragas.failed_metrics:
            lines.append(f"- {key}：`计算失败（请查看评估过程中的 Job 异常）`")
        lines.append("")

    if report.regression:
        lines.extend([
            "## 回归对比",
            "",
            f"- 基线报告：`{report.regression.baseline_path}`",
            f"- 通过率变化：`{_format_delta(report.regression.pass_rate_delta)}`",
            f"- Recall@K 变化：`{_format_delta(report.regression.recall_at_k_delta)}`",
            f"- MRR 变化：`{_format_delta(report.regression.mrr_delta)}`",
            f"- 引用来源正确率变化：`{_format_delta(report.regression.citation_accuracy_delta)}`",
            f"- 答案命中率变化：`{_format_delta(report.regression.answer_hit_rate_delta)}`",
            "",
        ])

    lines.extend(["## 样例结果", ""])
    for case_result in report.case_results:
        status = "通过" if case_result.passed else "失败"
        lines.extend([
            f"### {status} - {case_result.case.id}: {case_result.case.name}",
            "",
            f"- 问题：{case_result.case.question}",
            f"- 是否应回答：`{case_result.case.should_answer}`",
            f"- 规则平均分：`{case_result.average_rule_score:.4f}`",
            f"- Recall@K：`{_format_optional_score(case_result.average_recall_at_k)}`",
            f"- Precision@K：`{_format_optional_score(case_result.average_precision_at_k)}`",
            f"- HitRate@K：`{_format_optional_score(case_result.average_hit_rate_at_k)}`",
            f"- MRR：`{_format_optional_score(case_result.average_mrr)}`",
            f"- NDCG@K：`{_format_optional_score(case_result.average_ndcg_at_k)}`",
            f"- 引用来源正确率：`{_format_optional_score(case_result.average_citation_accuracy)}`",
            f"- 上下文关键词召回率：`{_format_optional_score(case_result.average_context_keyword_recall)}`",
            f"- 答案命中率：`{case_result.average_answer_hit_rate:.4f}`",
            f"- 拒答正确率：`{_format_optional_score(case_result.average_refusal_accuracy)}`",
            f"- 答案长度标准差：`{case_result.answer_length_stddev}`",
            f"- 平均延迟：`{case_result.latency_average_ms:.2f} ms`",
        ])
        if case_result.failure_reasons:
            lines.append("- 失败原因：")
            for reason in case_result.failure_reasons[:12]:
                lines.append(f"  - {reason}")
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _format_optional_score(value: Optional[float]) -> str:
    return "未配置" if value is None else f"{value:.4f}"


def _format_delta(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "无"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.4f}"
