from __future__ import annotations

import re
from statistics import mean
from typing import List

from app.evaluations.dify_eval_models import DifyEvalCase, RuleCheckResult

"""Dify 工作流输出的确定性规则检查。"""

class DifyRuleEvaluator:
    """使用可审计的确定性规则评估输出。"""

    def evaluate(self, case: DifyEvalCase, output: str) -> List[RuleCheckResult]:
        checks = [
            self._check_non_empty(output),
            self._check_min_length(case, output),
            self._check_max_length(case, output),
            self._check_expected_keywords(case, output),
            self._check_required_sections(case, output),
            self._check_forbidden_keywords(case, output),
            self._check_scoring_quantification(case, output),
        ]
        return [check for check in checks if check is not None]

    def aggregate_score(self, checks: List[RuleCheckResult]) -> float:
        if not checks:
            return 0.0
        return round(mean(check.score for check in checks), 4)

    def _check_non_empty(self, output: str) -> RuleCheckResult:
        text = output.strip()
        passed = bool(text)
        return RuleCheckResult(
            name="非空检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="输出非空。" if passed else "Dify 输出为空。",
        )

    def _check_min_length(self, case: DifyEvalCase, output: str) -> RuleCheckResult:
        length = len(output.strip())
        passed = length >= case.min_length
        return RuleCheckResult(
            name="最小长度检查",
            passed=passed,
            score=1.0 if passed else max(0.0, length / max(case.min_length, 1)),
            reason=f"输出长度 {length}，最低要求 {case.min_length}。",
            details={"length": length, "min_length": case.min_length},
        )

    def _check_max_length(self, case: DifyEvalCase, output: str) -> RuleCheckResult | None:
        if case.max_length is None:
            return None
        length = len(output.strip())
        passed = length <= case.max_length
        return RuleCheckResult(
            name="最大长度检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=f"输出长度 {length}，最高限制 {case.max_length}。",
            details={"length": length, "max_length": case.max_length},
        )

    def _check_expected_keywords(self, case: DifyEvalCase, output: str) -> RuleCheckResult:
        keywords = case.expected_keywords
        if not keywords:
            return RuleCheckResult(
                name="必要关键词检查",
                passed=True,
                score=1.0,
                reason="未配置必要关键词，跳过。",
            )
        normalized_output = self._normalize_text(output)
        missing = [item for item in keywords if self._normalize_text(item) not in normalized_output]
        passed = not missing
        score = (len(keywords) - len(missing)) / len(keywords)
        return RuleCheckResult(
            name="必要关键词检查",
            passed=passed,
            score=round(score, 4),
            reason="必要关键词全部命中。" if passed else f"缺少关键词：{', '.join(missing)}。",
            details={"missing": missing, "expected": keywords},
        )

    def _check_required_sections(self, case: DifyEvalCase, output: str) -> RuleCheckResult:
        sections = case.required_sections
        if not sections:
            return RuleCheckResult(
                name="必要章节检查",
                passed=True,
                score=1.0,
                reason="未配置必要章节，跳过。",
            )
        normalized_output = self._normalize_text(output)
        missing = [section for section in sections if self._normalize_text(section) not in normalized_output]
        passed = not missing
        score = (len(sections) - len(missing)) / len(sections)
        return RuleCheckResult(
            name="必要章节检查",
            passed=passed,
            score=round(score, 4),
            reason="必要章节全部命中。" if passed else f"缺少章节：{', '.join(missing)}。",
            details={"missing": missing, "required": sections},
        )

    def _check_forbidden_keywords(self, case: DifyEvalCase, output: str) -> RuleCheckResult:
        forbidden = case.forbidden_keywords
        if not forbidden:
            return RuleCheckResult(
                name="禁用词检查",
                passed=True,
                score=1.0,
                reason="未配置禁用词，跳过。",
            )
        normalized_output = self._normalize_text(output)
        hits = [item for item in forbidden if self._normalize_text(item) in normalized_output]
        passed = not hits
        return RuleCheckResult(
            name="禁用词检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="未命中禁用词。" if passed else f"命中禁用词：{', '.join(hits)}。",
            details={"hits": hits, "forbidden": forbidden},
        )

    def _check_scoring_quantification(
        self,
        case: DifyEvalCase,
        output: str,
    ) -> RuleCheckResult | None:
        if case.workflow_type != 2:
            return None

        normalized_output = self._normalize_text(output)
        total_score_patterns = (
            r"(?:总分|满分|合计|总计)[：:]?100(?:分)?",
            r"100分制",
        )
        has_total_score = any(
            re.search(pattern, normalized_output)
            for pattern in total_score_patterns
        )
        score_items = re.findall(r"(?<!\d)\d{1,3}(?:\.\d+)?(?:分|%|％)", normalized_output)
        has_dimension_scores = len(score_items) >= 4
        passed = has_total_score and has_dimension_scores
        if passed:
            reason = "评分标准明确总分 100 分，且至少包含 4 个量化分值。"
        else:
            missing = []
            if not has_total_score:
                missing.append("总分 100 分声明")
            if not has_dimension_scores:
                missing.append("至少 4 个维度分值")
            reason = f"评分标准缺少：{'、'.join(missing)}。"
        return RuleCheckResult(
            name="评分标准量化检查",
            passed=passed,
            score=(float(has_total_score) + float(has_dimension_scores)) / 2,
            reason=reason,
            details={
                "has_total_score": has_total_score,
                "score_item_count": len(score_items),
                "score_items": score_items[:20],
            },
        )

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", "", str(text or "")).lower()
