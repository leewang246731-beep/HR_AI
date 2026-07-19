from __future__ import annotations

import json
import re
from typing import Any, Dict

from app.evaluations.dify_eval_models import DifyEvalCase, LLMJudgeResult
from app.services.llm_service import LLMService

"""Dify 工作流输出的大模型裁判评估器。"""

class DifyLLMJudge:
    """使用大模型裁判对 Dify 输出质量打分。"""

    def __init__(self, llm_service: LLMService | None = None):
        self.llm_service = llm_service or LLMService()

    async def judge(self, case: DifyEvalCase, output: str) -> LLMJudgeResult:
        prompt = self._build_prompt(case, output)
        raw_response = await self.llm_service.generate_response(prompt)
        parsed = self._safe_json_loads(raw_response)
        score = self._safe_float(parsed.get("score"), default=0.0)
        passed = bool(parsed.get("passed", score >= 0.75))
        reason = str(parsed.get("reason") or "").strip()
        return LLMJudgeResult(
            enabled=True,
            score=max(0.0, min(score, 1.0)),
            passed=passed,
            reason=reason or "大模型裁判未返回原因。",
            raw_response=raw_response,
        )

    def _build_prompt(self, case: DifyEvalCase, output: str) -> str:
        rubric = case.rubric or self._default_rubric(case.workflow_type)
        return (
            "你是 HR Agent 的 Dify 工作流输出评估器。请严格根据评分标准评价输出质量。\n"
            "只输出 JSON，不要输出 Markdown 或解释。\n\n"
            "评分规则：score 是 0 到 1 的小数；0 表示不可用，1 表示完全满足。\n"
            "passed 表示该输出是否达到可上线使用标准。\n\n"
            f"评估样例 ID：{case.id}\n"
            f"工作流类型：{case.workflow_type}\n"
            f"用户请求：{case.query}\n"
            f"额外输入：{json.dumps(case.inputs, ensure_ascii=False)}\n"
            f"必要关键词：{json.dumps(case.expected_keywords, ensure_ascii=False)}\n"
            f"必要章节：{json.dumps(case.required_sections, ensure_ascii=False)}\n\n"
            f"评分标准：\n{rubric}\n\n"
            f"待评估输出：\n{output[:8000]}\n\n"
            "返回格式：{\"score\":0.0,\"passed\":false,\"reason\":\"一句中文原因\"}"
        )

    def _default_rubric(self, workflow_type: int) -> str:
        if workflow_type == 1:
            return "JD 应包含岗位职责、任职要求、技能要求，并准确保留岗位名称、地点、经验、学历等输入条件；不得编造关键硬性条件。"
        if workflow_type == 2:
            return "评分标准应总分 100 分，包含清晰评分维度、分值区间、加分项和淘汰项，且与 JD 内容匹配。"
        raise ValueError(f"当前不支持评估 Dify 工作流类型: {workflow_type}")

    def _safe_json_loads(self, text: str) -> Dict[str, Any]:
        json_text = str(text or "").strip()
        if "```" in json_text:
            json_text = re.sub(r"^```(?:json)?", "", json_text, flags=re.IGNORECASE).strip()
            json_text = re.sub(r"```$", "", json_text).strip()
        match = re.search(r"\{.*\}", json_text, re.S)
        if match:
            json_text = match.group(0)
        try:
            value = json.loads(json_text)
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return default
