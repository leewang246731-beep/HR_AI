from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

from app.evaluations.dify_eval_models import (
    CaseEvaluationResult,
    DifyEvalCase,
    DifyEvalReport,
    DifyRunResult,
    LLMJudgeResult,
    RegressionComparison,
    SUPPORTED_WORKFLOW_TYPES,
)
from app.evaluations.dify_llm_judge import DifyLLMJudge
from app.evaluations.dify_rule_evaluator import DifyRuleEvaluator
from app.services.dify_service import DifyService

"""固定评估集的 Dify 工作流评估运行器。"""

class DifyEvalRunner:
    """执行 Dify 工作流评估样例并生成评估报告。"""

    def __init__(
        self,
        dify_service: Optional[DifyService] = None,
        rule_evaluator: Optional[DifyRuleEvaluator] = None,
        llm_judge: Optional[DifyLLMJudge] = None,
    ):
        self.dify_service = dify_service or DifyService()
        self.rule_evaluator = rule_evaluator or DifyRuleEvaluator()
        self.llm_judge = llm_judge

    async def run(
        self,
        cases: List[DifyEvalCase],
        repeat_runs: int = 3,
        use_llm_judge: bool = False,
        use_stream: bool = False,
        concurrency: int = 1,
        baseline_path: Optional[Path] = None,
    ) -> DifyEvalReport:
        unsupported_types = sorted({
            case.workflow_type
            for case in cases
            if case.workflow_type not in SUPPORTED_WORKFLOW_TYPES
        })
        if unsupported_types:
            raise ValueError(
                f"评估集中包含暂不支持的 Dify 工作流类型: {unsupported_types}；"
                "当前仅评估 type=1（JD 生成）和 type=2（评分标准生成）。"
            )
        enabled_cases = [case for case in cases if case.enabled]
        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def run_case(case: DifyEvalCase) -> CaseEvaluationResult:
            async with semaphore:
                return await self._run_case(case, repeat_runs, use_llm_judge, use_stream)

        case_results = await asyncio.gather(*(run_case(case) for case in enabled_cases))
        report = self._build_report(case_results, repeat_runs)
        if baseline_path:
            report.regression = self._compare_with_baseline(report, baseline_path)
        return report

    async def _run_case(
        self,
        case: DifyEvalCase,
        repeat_runs: int,
        use_llm_judge: bool,
        use_stream: bool,
    ) -> CaseEvaluationResult:
        runs: List[DifyRunResult] = []
        for repeat_index in range(1, repeat_runs + 1):
            run = await self._run_once(case, repeat_index, use_llm_judge, use_stream)
            runs.append(run)

        successful_runs = [run for run in runs if run.success]
        average_rule_score = mean(run.rule_score for run in runs) if runs else 0.0
        judge_scores = [
            run.judge.score
            for run in runs
            if run.judge.enabled and run.judge.score is not None
        ]
        output_lengths = [len(run.output or "") for run in successful_runs]
        latency_values = [run.latency_ms for run in runs]
        failure_reasons = self._collect_failure_reasons(runs)
        passed = bool(runs) and all(
            run.success
            and all(check.passed for check in run.rule_checks)
            and (not run.judge.enabled or bool(run.judge.passed))
            for run in runs
        )
        return CaseEvaluationResult(
            case=case,
            runs=runs,
            passed=passed,
            average_rule_score=round(average_rule_score, 4),
            average_judge_score=round(mean(judge_scores), 4) if judge_scores else None,
            output_length_stddev=round(pstdev(output_lengths), 2) if len(output_lengths) > 1 else 0.0,
            latency_average_ms=round(mean(latency_values), 2) if latency_values else 0.0,
            failure_reasons=failure_reasons,
        )

    async def _run_once(
        self,
        case: DifyEvalCase,
        repeat_index: int,
        use_llm_judge: bool,
        use_stream: bool,
    ) -> DifyRunResult:
        started = time.perf_counter()
        try:
            if use_stream:
                output, raw_response = await self._call_workflow_stream(case)
            else:
                raw_response = await self.dify_service.call_workflow_sync(
                    workflow_type=case.workflow_type,
                    query=case.query,
                    conversation_id=None,
                    additional_inputs=case.inputs,
                )
                output = self._extract_answer(raw_response)
            latency_ms = int((time.perf_counter() - started) * 1000)
            rule_checks = self.rule_evaluator.evaluate(case, output)
            rule_score = self.rule_evaluator.aggregate_score(rule_checks)
            judge = LLMJudgeResult(enabled=False)
            if use_llm_judge:
                judge = await self._judge(case, output)
            return DifyRunResult(
                repeat_index=repeat_index,
                success=True,
                output=output,
                latency_ms=latency_ms,
                raw_response=raw_response,
                rule_checks=rule_checks,
                rule_score=rule_score,
                judge=judge,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return DifyRunResult(
                repeat_index=repeat_index,
                success=False,
                output="",
                latency_ms=latency_ms,
                error=str(exc),
                rule_checks=self.rule_evaluator.evaluate(case, ""),
                rule_score=0.0,
                judge=LLMJudgeResult(enabled=use_llm_judge, passed=False, score=0.0, reason=str(exc)),
            )

    async def _call_workflow_stream(self, case: DifyEvalCase) -> tuple[str, List[Any]]:
        chunks: List[Any] = []
        output_parts: List[str] = []
        async for chunk in self.dify_service.call_workflow_stream(
            workflow_type=case.workflow_type,
            query=case.query,
            conversation_id=None,
            additional_inputs=case.inputs,
        ):
            chunks.append(chunk)
            output_parts.append(self._extract_stream_delta(chunk))
        return "".join(output_parts).strip(), chunks

    async def _judge(self, case: DifyEvalCase, output: str) -> LLMJudgeResult:
        judge = self.llm_judge or DifyLLMJudge()
        return await judge.judge(case, output)

    def _build_report(self, case_results: List[CaseEvaluationResult], repeat_runs: int) -> DifyEvalReport:
        total_cases = len(case_results)
        passed_cases = len([item for item in case_results if item.passed])
        failed_cases = total_cases - passed_cases
        rule_scores = [item.average_rule_score for item in case_results]
        judge_scores = [
            item.average_judge_score
            for item in case_results
            if item.average_judge_score is not None
        ]
        latencies = [item.latency_average_ms for item in case_results]
        return DifyEvalReport(
            run_id=str(uuid.uuid4()),
            generated_at=datetime.now(timezone.utc).isoformat(),
            repeat_runs=repeat_runs,
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            pass_rate=round(passed_cases / total_cases, 4) if total_cases else 0.0,
            average_rule_score=round(mean(rule_scores), 4) if rule_scores else 0.0,
            average_judge_score=round(mean(judge_scores), 4) if judge_scores else None,
            average_latency_ms=round(mean(latencies), 2) if latencies else 0.0,
            case_results=case_results,
        )

    def _compare_with_baseline(self, report: DifyEvalReport, baseline_path: Path) -> RegressionComparison:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_pass_rate = baseline.get("pass_rate")
        baseline_average_score = baseline.get("average_rule_score")
        return RegressionComparison(
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

    def _collect_failure_reasons(self, runs: List[DifyRunResult]) -> List[str]:
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

    def _extract_answer(self, response: Any) -> str:
        if isinstance(response, dict):
            if response.get("answer"):
                return str(response["answer"])
            data = response.get("data")
            if isinstance(data, dict) and data.get("answer"):
                return str(data["answer"])
            if response.get("text"):
                return str(response["text"])
            return json.dumps(response, ensure_ascii=False)
        return str(response)

    def _extract_stream_delta(self, chunk: Any) -> str:
        if isinstance(chunk, str):
            try:
                chunk = json.loads(chunk)
            except json.JSONDecodeError:
                return chunk
        if not isinstance(chunk, dict):
            return str(chunk)
        event = chunk.get("event")
        if event and event not in {"message", "agent_message", "text_chunk"}:
            return ""
        for key in ("answer", "delta", "text"):
            value = chunk.get(key)
            if isinstance(value, str):
                return value
        data = chunk.get("data")
        if isinstance(data, dict):
            for key in ("answer", "delta", "text"):
                value = data.get(key)
                if isinstance(value, str):
                    return value
        return ""


def load_eval_cases(path: Path) -> List[DifyEvalCase]:
    """从单个 JSON 文件或目录下所有 JSON 文件读取评估样例。"""
    files = [path] if path.is_file() else sorted(path.glob("*.json"))
    cases: List[DifyEvalCase] = []
    for file_path in files:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        raw_cases = data.get("cases") if isinstance(data, dict) else data
        if not isinstance(raw_cases, list):
            raise ValueError(f"评估文件格式错误: {file_path}")
        cases.extend(DifyEvalCase.from_dict(item) for item in raw_cases)
    return cases


def report_to_dict(report: DifyEvalReport) -> Dict[str, Any]:
    """将评估报告数据结构转换为可写入 JSON 的字典。"""
    return asdict(report)


def write_json_report(report: DifyEvalReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_markdown_report(report: DifyEvalReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Dify 工作流评估报告",
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
        f"- 平均延迟：`{report.average_latency_ms:.2f} ms`",
        "",
    ]
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
            f"- 工作流类型：`{case_result.case.workflow_type}`",
            f"- 规则平均分：`{case_result.average_rule_score:.4f}`",
            f"- 大模型裁判平均分：`{_format_optional_score(case_result.average_judge_score)}`",
            f"- 输出长度标准差：`{case_result.output_length_stddev}`",
            f"- 平均延迟：`{case_result.latency_average_ms:.2f} ms`",
        ])
        if case_result.failure_reasons:
            lines.append("- 失败原因：")
            for reason in case_result.failure_reasons[:10]:
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
