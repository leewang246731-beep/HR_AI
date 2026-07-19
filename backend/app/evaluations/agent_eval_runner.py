from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from app.evaluations.agent_eval_models import (
    AgentCaseEvaluationResult,
    AgentEvalCase,
    AgentEvalReport,
    AgentLLMJudgeResult,
    AgentQualityMetrics,
    AgentRegressionComparison,
    AgentRunResult,
)
from app.evaluations.agent_rule_evaluator import AgentRuleEvaluator
"""固定评估集的 HR Agent 评估运行器。"""

if TYPE_CHECKING:
    from app.evaluations.agent_llm_judge import AgentLLMJudge


class AgentEvalRunner:
    """执行 HR Agent 评估样例并生成评估报告。"""

    def __init__(
        self,
        rule_evaluator: Optional[AgentRuleEvaluator] = None,
        llm_judge: Optional["AgentLLMJudge"] = None,
    ):
        self.rule_evaluator = rule_evaluator or AgentRuleEvaluator()
        self.llm_judge = llm_judge

    async def run(
        self,
        cases: List[AgentEvalCase],
        repeat_runs: int = 3,
        use_llm_judge: bool = False,
        concurrency: int = 1,
        baseline_path: Optional[Path] = None,
    ) -> AgentEvalReport:
        enabled_cases = [case for case in cases if case.enabled]
        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def run_case(case: AgentEvalCase) -> AgentCaseEvaluationResult:
            async with semaphore:
                return await self._run_case(case, repeat_runs, use_llm_judge)

        case_results = await asyncio.gather(*(run_case(case) for case in enabled_cases))
        report = self._build_report(case_results, repeat_runs)
        if baseline_path:
            report.regression = self._compare_with_baseline(report, baseline_path)
        return report

    async def _run_case(
        self,
        case: AgentEvalCase,
        repeat_runs: int,
        use_llm_judge: bool,
    ) -> AgentCaseEvaluationResult:
        runs: List[AgentRunResult] = []
        for repeat_index in range(1, repeat_runs + 1):
            runs.append(await self._run_once(case, repeat_index, use_llm_judge))

        average_rule_score = mean(run.rule_score for run in runs) if runs else 0.0
        judge_scores = [
            run.judge.score
            for run in runs
            if run.judge.enabled and run.judge.score is not None
        ]
        latencies = [run.latency_ms for run in runs]
        failure_reasons = self._collect_failure_reasons(runs)
        passed = bool(runs) and all(
            run.success
            and all(check.passed for check in run.rule_checks)
            and (not run.judge.enabled or bool(run.judge.passed))
            for run in runs
        )
        return AgentCaseEvaluationResult(
            case=case,
            runs=runs,
            passed=passed,
            average_rule_score=round(average_rule_score, 4),
            average_judge_score=round(mean(judge_scores), 4) if judge_scores else None,
            response_signature_stability=self._signature_stability(runs),
            latency_average_ms=round(mean(latencies), 2) if latencies else 0.0,
            failure_reasons=failure_reasons,
        )

    async def _run_once(
        self,
        case: AgentEvalCase,
        repeat_index: int,
        use_llm_judge: bool,
    ) -> AgentRunResult:
        started = time.perf_counter()
        try:
            response = await self._call_agent(case)
            latency_ms = int((time.perf_counter() - started) * 1000)
            rule_checks = self.rule_evaluator.evaluate(case, response)
            rule_score = self.rule_evaluator.aggregate_score(rule_checks)
            judge = AgentLLMJudgeResult(enabled=False)
            if use_llm_judge:
                judge = await self._judge(case, response)
            return AgentRunResult(
                repeat_index=repeat_index,
                success=True,
                response=response,
                latency_ms=latency_ms,
                rule_checks=rule_checks,
                rule_score=rule_score,
                judge=judge,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            response: Dict[str, Any] = {}
            return AgentRunResult(
                repeat_index=repeat_index,
                success=False,
                response=response,
                latency_ms=latency_ms,
                error=str(exc),
                rule_checks=self.rule_evaluator.evaluate(case, response),
                rule_score=0.0,
                judge=AgentLLMJudgeResult(
                    enabled=use_llm_judge,
                    passed=False,
                    score=0.0,
                    reason=str(exc),
                ),
            )

    async def _call_agent(self, case: AgentEvalCase) -> Dict[str, Any]:
        from app.core.database import AsyncSessionLocal
        from app.services.agent_service import AgentService

        async with AsyncSessionLocal() as db:
            service = AgentService(db)
            response = await service.chat(
                message=case.message,
                user_id=UUID(case.user_id),
                conversation_id=case.conversation_id,
                auto_execute=case.auto_execute,
                confirmed_requirements=case.confirmed_requirements,
                attachments=case.attachments,
            )
            return response.model_dump()

    async def _judge(self, case: AgentEvalCase, response: Dict[str, Any]) -> AgentLLMJudgeResult:
        from app.evaluations.agent_llm_judge import AgentLLMJudge

        judge = self.llm_judge or AgentLLMJudge()
        return await judge.judge(case, response)

    def _build_report(
        self,
        case_results: List[AgentCaseEvaluationResult],
        repeat_runs: int,
    ) -> AgentEvalReport:
        total_cases = len(case_results)
        passed_cases = len([item for item in case_results if item.passed])
        failed_cases = total_cases - passed_cases
        rule_scores = [item.average_rule_score for item in case_results]
        judge_scores = [
            item.average_judge_score
            for item in case_results
            if item.average_judge_score is not None
        ]
        stabilities = [item.response_signature_stability for item in case_results]
        latencies = [item.latency_average_ms for item in case_results]
        return AgentEvalReport(
            run_id=str(uuid.uuid4()),
            generated_at=datetime.now(timezone.utc).isoformat(),
            repeat_runs=repeat_runs,
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            pass_rate=round(passed_cases / total_cases, 4) if total_cases else 0.0,
            average_rule_score=round(mean(rule_scores), 4) if rule_scores else 0.0,
            average_judge_score=round(mean(judge_scores), 4) if judge_scores else None,
            average_signature_stability=round(mean(stabilities), 4) if stabilities else 0.0,
            average_latency_ms=round(mean(latencies), 2) if latencies else 0.0,
            case_results=case_results,
            quality_metrics=self._build_quality_metrics(case_results),
        )

    def _build_quality_metrics(
        self,
        case_results: List[AgentCaseEvaluationResult],
    ) -> AgentQualityMetrics:
        """按规则检查聚合关键能力指标。"""
        check_groups = {
            "intent_accuracy": {"意图检查"},
            "route_accuracy": {"前端路由检查"},
            "confirmation_accuracy": {"人工确认检查"},
            "artifact_contract_pass_rate": {"产物类型检查", "禁用产物检查", "结构化内容检查"},
            "tool_contract_pass_rate": {"工具调用标记检查", "步骤 ID 检查", "步骤状态检查"},
            "missing_field_accuracy": {"缺失字段检查"},
        }
        scores: Dict[str, List[float]] = {name: [] for name in check_groups}

        for case_result in case_results:
            for run in case_result.runs:
                for check in run.rule_checks:
                    for metric_name, check_names in check_groups.items():
                        if check.name in check_names:
                            scores[metric_name].append(check.score)

        return AgentQualityMetrics(
            intent_accuracy=self._optional_average(scores["intent_accuracy"]),
            route_accuracy=self._optional_average(scores["route_accuracy"]),
            confirmation_accuracy=self._optional_average(scores["confirmation_accuracy"]),
            artifact_contract_pass_rate=self._optional_average(scores["artifact_contract_pass_rate"]),
            tool_contract_pass_rate=self._optional_average(scores["tool_contract_pass_rate"]),
            missing_field_accuracy=self._optional_average(scores["missing_field_accuracy"]),
        )

    def _optional_average(self, values: List[float]) -> Optional[float]:
        return round(mean(values), 4) if values else None

    def _compare_with_baseline(self, report: AgentEvalReport, baseline_path: Path) -> AgentRegressionComparison:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_pass_rate = baseline.get("pass_rate")
        baseline_average_score = baseline.get("average_rule_score")
        return AgentRegressionComparison(
            baseline_path=str(baseline_path),
            current_pass_rate=report.pass_rate,
            baseline_pass_rate=baseline_pass_rate,
            pass_rate_delta=(
                round(report.pass_rate - float(baseline_pass_rate), 4)
                if baseline_pass_rate is not None
                else None
            ),
            current_average_score=report.average_rule_score,
            baseline_average_score=baseline_average_score,
            average_score_delta=(
                round(report.average_rule_score - float(baseline_average_score), 4)
                if baseline_average_score is not None
                else None
            ),
        )

    def _collect_failure_reasons(self, runs: List[AgentRunResult]) -> List[str]:
        reasons: List[str] = []
        for run in runs:
            if run.error:
                reasons.append(f"第 {run.repeat_index} 次运行：{run.error}")
            for check in run.rule_checks:
                if not check.passed:
                    reasons.append(f"第 {run.repeat_index} 次运行：{check.name} - {check.reason}")
            if run.judge.enabled and run.judge.passed is False:
                reasons.append(f"第 {run.repeat_index} 次运行：大模型裁判 - {run.judge.reason}")
        return reasons

    def _signature_stability(self, runs: List[AgentRunResult]) -> float:
        signatures = [self._response_signature(run.response) for run in runs if run.success]
        if not signatures:
            return 0.0
        most_common = max(signatures.count(signature) for signature in set(signatures))
        return round(most_common / len(signatures), 4)

    def _response_signature(self, response: Dict[str, Any]) -> str:
        signature = {
            "intent": response.get("intent"),
            "route": response.get("route"),
            "requires_confirmation": response.get("requires_confirmation"),
            "missing_fields": response.get("missing_fields") or [],
            "step_ids": [step.get("id") for step in response.get("steps") or [] if isinstance(step, dict)],
            "artifact_types": [
                artifact.get("type")
                for artifact in response.get("artifacts") or []
                if isinstance(artifact, dict)
            ],
        }
        return json.dumps(signature, ensure_ascii=False, sort_keys=True)


def load_eval_cases(path: Path) -> List[AgentEvalCase]:
    """从单个 JSON 文件或目录下所有 JSON 文件读取评估样例。"""
    files = [path] if path.is_file() else sorted(path.glob("*.json"))
    cases: List[AgentEvalCase] = []
    for file_path in files:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        raw_cases = data.get("cases") if isinstance(data, dict) else data
        if not isinstance(raw_cases, list):
            raise ValueError(f"评估文件格式错误: {file_path}")
        cases.extend(AgentEvalCase.from_dict(item) for item in raw_cases)
    return cases


def report_to_dict(report: AgentEvalReport) -> Dict[str, Any]:
    """将评估报告数据结构转换为可写入 JSON 的字典。"""
    return asdict(report)


def write_json_report(report: AgentEvalReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_markdown_report(report: AgentEvalReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# HR Agent 评估报告",
        "",
        f"- 运行 ID：`{report.run_id}`",
        f"- 生成时间：`{report.generated_at}`",
        f"- 每条样例重复运行次数：`{report.repeat_runs}`",
        f"- 样例总数：`{report.total_cases}`",
        f"- 通过样例数：`{report.passed_cases}`",
        f"- 失败样例数：`{report.failed_cases}`",
        f"- 通过率：`{report.pass_rate:.2%}`",
        f"- 规则平均分：`{report.average_rule_score:.4f}`",
        f"- 大模型裁判平均分：`{_format_optional_score(report.average_judge_score)}`",
        f"- 响应签名稳定性：`{report.average_signature_stability:.4f}`",
        f"- 平均延迟：`{report.average_latency_ms:.2f} ms`",
        "",
    ]
    metrics = report.quality_metrics
    lines.extend([
        "## 分项指标",
        "",
        f"- 意图准确率：`{_format_optional_score(metrics.intent_accuracy)}`",
        f"- 路由正确率：`{_format_optional_score(metrics.route_accuracy)}`",
        f"- 人工确认正确率：`{_format_optional_score(metrics.confirmation_accuracy)}`",
        f"- Artifact 契约通过率：`{_format_optional_score(metrics.artifact_contract_pass_rate)}`",
        f"- 工具与步骤契约通过率：`{_format_optional_score(metrics.tool_contract_pass_rate)}`",
        f"- 缺失字段准确率：`{_format_optional_score(metrics.missing_field_accuracy)}`",
        "",
    ])
    if report.regression:
        lines.extend([
            "## 回归对比",
            "",
            f"- 基线报告：`{report.regression.baseline_path}`",
            f"- 通过率变化：`{_format_delta(report.regression.pass_rate_delta)}`",
            f"- 规则分变化：`{_format_delta(report.regression.average_score_delta)}`",
            "",
        ])
    lines.extend(["## 样例结果", ""])
    for case_result in report.case_results:
        status = "通过" if case_result.passed else "失败"
        lines.extend([
            f"### {status} - {case_result.case.id}: {case_result.case.name}",
            "",
            f"- 期望意图：`{case_result.case.expected_intent}`",
            f"- 规则平均分：`{case_result.average_rule_score:.4f}`",
            f"- 大模型裁判平均分：`{_format_optional_score(case_result.average_judge_score)}`",
            f"- 响应签名稳定性：`{case_result.response_signature_stability:.4f}`",
            f"- 平均延迟：`{case_result.latency_average_ms:.2f} ms`",
        ])
        if case_result.failure_reasons:
            lines.append("- 失败原因：")
            for reason in case_result.failure_reasons[:12]:
                lines.append(f"  - {reason}")
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _format_optional_score(value: Optional[float]) -> str:
    return "未启用" if value is None else f"{value:.4f}"


def _format_delta(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "无"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.4f}"
