from __future__ import annotations

import re
from statistics import mean
from typing import Any, Dict, List

from app.evaluations.agent_eval_models import AgentEvalCase, AgentRuleCheckResult

"""HR Agent 响应的确定性规则检查。"""

class AgentRuleEvaluator:
    """使用可审计的规则评估 Agent 响应契约。"""

    def evaluate(self, case: AgentEvalCase, response: Dict[str, Any]) -> List[AgentRuleCheckResult]:
        checks = [
            self._check_response_non_empty(response),
            self._check_intent(case, response),
            self._check_route(case, response),
            self._check_requires_confirmation(case, response),
            self._check_artifact_types(case, response),
            self._check_forbidden_artifact_types(case, response),
            self._check_step_ids(case, response),
            self._check_step_statuses(case, response),
            self._check_tools(case, response),
            self._check_missing_fields(case, response),
            self._check_message_keywords(case, response),
            self._check_forbidden_message_keywords(case, response),
            self._check_content_paths(case, response),
        ]
        return [check for check in checks if check is not None]

    def aggregate_score(self, checks: List[AgentRuleCheckResult]) -> float:
        if not checks:
            return 0.0
        return round(mean(check.score for check in checks), 4)

    def _check_response_non_empty(self, response: Dict[str, Any]) -> AgentRuleCheckResult:
        passed = bool(response)
        return AgentRuleCheckResult(
            name="响应非空检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="Agent 返回了响应。" if passed else "Agent 响应为空。",
        )

    def _check_intent(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        if case.expected_intent is None:
            return None
        actual = str(response.get("intent") or "")
        passed = actual == case.expected_intent
        return AgentRuleCheckResult(
            name="意图检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=(
                f"意图正确：{actual}。"
                if passed
                else f"意图错误，期望 {case.expected_intent}，实际 {actual or '空'}。"
            ),
            details={"expected": case.expected_intent, "actual": actual},
        )

    def _check_route(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        if case.expected_route is None:
            return None
        actual = response.get("route")
        passed = actual == case.expected_route
        return AgentRuleCheckResult(
            name="前端路由检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=(
                f"路由正确：{actual}。"
                if passed
                else f"路由错误，期望 {case.expected_route}，实际 {actual}。"
            ),
            details={"expected": case.expected_route, "actual": actual},
        )

    def _check_requires_confirmation(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        if case.expected_requires_confirmation is None:
            return None
        actual = bool(response.get("requires_confirmation"))
        passed = actual == case.expected_requires_confirmation
        return AgentRuleCheckResult(
            name="人工确认检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=(
                f"确认状态正确：{actual}。"
                if passed
                else f"确认状态错误，期望 {case.expected_requires_confirmation}，实际 {actual}。"
            ),
            details={"expected": case.expected_requires_confirmation, "actual": actual},
        )

    def _check_artifact_types(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        expected = case.expected_artifact_types
        if not expected:
            return None
        actual = self._artifact_types(response)
        missing = [item for item in expected if item not in actual]
        passed = not missing
        score = (len(expected) - len(missing)) / len(expected)
        return AgentRuleCheckResult(
            name="产物类型检查",
            passed=passed,
            score=round(score, 4),
            reason="必要 artifacts 全部存在。" if passed else f"缺少 artifacts：{', '.join(missing)}。",
            details={"expected": expected, "actual": actual, "missing": missing},
        )

    def _check_forbidden_artifact_types(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        forbidden = case.forbidden_artifact_types
        if not forbidden:
            return None
        actual = self._artifact_types(response)
        hits = [item for item in forbidden if item in actual]
        passed = not hits
        return AgentRuleCheckResult(
            name="禁用产物检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="未返回禁用 artifacts。" if passed else f"返回了禁用 artifacts：{', '.join(hits)}。",
            details={"forbidden": forbidden, "hits": hits},
        )

    def _check_step_ids(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        expected = case.expected_step_ids
        if not expected:
            return None
        actual = [str(step.get("id") or "") for step in self._steps(response)]
        missing = [item for item in expected if item not in actual]
        passed = not missing
        score = (len(expected) - len(missing)) / len(expected)
        return AgentRuleCheckResult(
            name="步骤 ID 检查",
            passed=passed,
            score=round(score, 4),
            reason="必要步骤全部存在。" if passed else f"缺少步骤：{', '.join(missing)}。",
            details={"expected": expected, "actual": actual, "missing": missing},
        )

    def _check_step_statuses(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        expected = case.expected_step_statuses
        if not expected:
            return None
        actual_by_id = {
            str(step.get("id") or ""): str(step.get("status") or "")
            for step in self._steps(response)
        }
        mismatches = {
            step_id: {"expected": status, "actual": actual_by_id.get(step_id)}
            for step_id, status in expected.items()
            if actual_by_id.get(step_id) != status
        }
        passed = not mismatches
        score = (len(expected) - len(mismatches)) / len(expected)
        return AgentRuleCheckResult(
            name="步骤状态检查",
            passed=passed,
            score=round(score, 4),
            reason="步骤状态全部符合预期。" if passed else f"步骤状态不符：{list(mismatches.keys())}。",
            details={"mismatches": mismatches},
        )

    def _check_tools(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        expected = case.expected_tools
        if not expected:
            return None
        actual = [
            str(step.get("tool") or "")
            for step in self._steps(response)
            if step.get("tool")
        ]
        missing = [item for item in expected if item not in actual]
        passed = not missing
        score = (len(expected) - len(missing)) / len(expected)
        return AgentRuleCheckResult(
            name="工具调用标记检查",
            passed=passed,
            score=round(score, 4),
            reason="必要工具标记全部存在。" if passed else f"缺少工具标记：{', '.join(missing)}。",
            details={"expected": expected, "actual": actual, "missing": missing},
        )

    def _check_missing_fields(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        expected = case.expected_missing_fields
        if not expected and not case.missing_fields_exact:
            return None
        actual = [str(item) for item in response.get("missing_fields") or []]
        if case.missing_fields_exact:
            missing = [item for item in expected if item not in actual]
            extra = [item for item in actual if item not in expected]
            passed = not missing and not extra
            score = 1.0 if passed else 0.0
            reason = "缺失字段完全符合预期。" if passed else f"缺失字段不符，缺少 {missing}，多出 {extra}。"
            details = {"expected": expected, "actual": actual, "missing": missing, "extra": extra}
        else:
            missing = [item for item in expected if item not in actual]
            passed = not missing
            score = (len(expected) - len(missing)) / len(expected) if expected else 1.0
            reason = "必要缺失字段已标记。" if passed else f"未标记缺失字段：{', '.join(missing)}。"
            details = {"expected": expected, "actual": actual, "missing": missing}
        return AgentRuleCheckResult(
            name="缺失字段检查",
            passed=passed,
            score=round(score, 4),
            reason=reason,
            details=details,
        )

    def _check_message_keywords(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        keywords = case.expected_message_keywords
        if not keywords:
            return None
        message = self._normalize_text(response.get("message") or "")
        missing = [item for item in keywords if self._normalize_text(item) not in message]
        passed = not missing
        score = (len(keywords) - len(missing)) / len(keywords)
        return AgentRuleCheckResult(
            name="回复关键词检查",
            passed=passed,
            score=round(score, 4),
            reason="回复关键词全部命中。" if passed else f"缺少回复关键词：{', '.join(missing)}。",
            details={"expected": keywords, "missing": missing},
        )

    def _check_forbidden_message_keywords(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        forbidden = case.forbidden_message_keywords
        if not forbidden:
            return None
        message = self._normalize_text(response.get("message") or "")
        hits = [item for item in forbidden if self._normalize_text(item) in message]
        passed = not hits
        return AgentRuleCheckResult(
            name="回复禁用词检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="未命中回复禁用词。" if passed else f"命中禁用词：{', '.join(hits)}。",
            details={"forbidden": forbidden, "hits": hits},
        )

    def _check_content_paths(
        self, case: AgentEvalCase, response: Dict[str, Any]
    ) -> AgentRuleCheckResult | None:
        checks = case.content_checks
        if not checks:
            return None
        failures: Dict[str, str] = {}
        scores: List[float] = []
        for path, expectation in checks.items():
            values = self._extract_values(response, path)
            passed, score, reason = self._match_expectation(values, expectation)
            scores.append(score)
            if not passed:
                failures[path] = reason
        passed = not failures
        return AgentRuleCheckResult(
            name="结构化内容检查",
            passed=passed,
            score=round(mean(scores), 4) if scores else 0.0,
            reason="结构化内容全部符合预期。" if passed else "部分结构化内容不符合预期。",
            details={"failures": failures},
        )

    def _match_expectation(self, values: List[Any], expectation: Any) -> tuple[bool, float, str]:
        if isinstance(expectation, dict):
            if expectation.get("exists") is not None:
                expected_exists = bool(expectation["exists"])
                passed = bool(values) == expected_exists
                return passed, 1.0 if passed else 0.0, f"存在性期望为 {expected_exists}，实际值数量 {len(values)}。"
            if not values:
                return False, 0.0, "路径没有取到值。"
            text_values = [str(item) for item in values]
            if "equals" in expectation:
                target = str(expectation["equals"])
                passed = any(str(item) == target for item in values)
                return passed, 1.0 if passed else 0.0, f"没有值等于 {target}。"
            if "contains" in expectation:
                target = self._normalize_text(expectation["contains"])
                passed = any(target in self._normalize_text(item) for item in text_values)
                return passed, 1.0 if passed else 0.0, f"没有值包含 {expectation['contains']}。"
            if "regex" in expectation:
                pattern = str(expectation["regex"])
                passed = any(re.search(pattern, text) for text in text_values)
                return passed, 1.0 if passed else 0.0, f"没有值匹配正则 {pattern}。"
            if "min_length" in expectation:
                min_length = int(expectation["min_length"])
                best_length = max((len(text) for text in text_values), default=0)
                passed = best_length >= min_length
                score = min(best_length / max(min_length, 1), 1.0)
                return passed, score, f"最大长度 {best_length}，最低要求 {min_length}。"
        if not values:
            return False, 0.0, "路径没有取到值。"
        target = str(expectation)
        passed = any(str(item) == target for item in values)
        return passed, 1.0 if passed else 0.0, f"没有值等于 {target}。"

    def _extract_values(self, response: Dict[str, Any], path: str) -> List[Any]:
        parts = [part for part in path.split(".") if part]
        values: List[Any] = [response]
        for part in parts:
            next_values: List[Any] = []
            for value in values:
                next_values.extend(self._extract_part(value, part))
            values = next_values
            if not values:
                break
        return values

    def _extract_part(self, value: Any, part: str) -> List[Any]:
        if isinstance(value, list):
            result: List[Any] = []
            for item in value:
                result.extend(self._extract_part(item, part))
            return result
        if not isinstance(value, dict):
            return []
        if part in value:
            return [value[part]]
        if part.startswith("artifact:"):
            artifact_type = part.split(":", 1)[1]
            return [
                item
                for item in value.get("artifacts") or []
                if isinstance(item, dict) and item.get("type") == artifact_type
            ]
        if part.startswith("step:"):
            step_id = part.split(":", 1)[1]
            return [
                item
                for item in value.get("steps") or []
                if isinstance(item, dict) and item.get("id") == step_id
            ]
        return []

    def _artifact_types(self, response: Dict[str, Any]) -> List[str]:
        return [
            str(item.get("type") or "")
            for item in response.get("artifacts") or []
            if isinstance(item, dict)
        ]

    def _steps(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [item for item in response.get("steps") or [] if isinstance(item, dict)]

    def _normalize_text(self, text: Any) -> str:
        return re.sub(r"\s+", "", str(text or "")).lower()
