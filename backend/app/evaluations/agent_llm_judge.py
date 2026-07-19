from __future__ import annotations

import json
import re
from typing import Any, Dict

from app.evaluations.agent_eval_models import AgentEvalCase, AgentLLMJudgeResult
from app.services.llm_service import LLMService

"""HR Agent 响应的大模型裁判评估器。"""

class AgentLLMJudge:
    """使用大模型裁判对 Agent 响应质量打分。"""

    def __init__(self, llm_service: LLMService | None = None):
        self.llm_service = llm_service or LLMService()

    async def judge(self, case: AgentEvalCase, response: Dict[str, Any]) -> AgentLLMJudgeResult:
        prompt = self._build_prompt(case, response)
        raw_response = await self.llm_service.generate_response(prompt)
        parsed = self._safe_json_loads(raw_response)
        score = self._safe_float(parsed.get("score"), default=0.0)
        passed = bool(parsed.get("passed", score >= 0.75))
        reason = str(parsed.get("reason") or "").strip()
        return AgentLLMJudgeResult(
            enabled=True,
            score=max(0.0, min(score, 1.0)),
            passed=passed,
            reason=reason or "大模型裁判未返回原因。",
            raw_response=raw_response,
        )

    def _build_prompt(self, case: AgentEvalCase, response: Dict[str, Any]) -> str:
        rubric = case.rubric or self._default_rubric(case.expected_intent)
        compact_response = {
            "message": response.get("message"),
            "intent": response.get("intent"),
            "route": response.get("route"),
            "steps": response.get("steps"),
            "artifacts": response.get("artifacts"),
            "requires_confirmation": response.get("requires_confirmation"),
            "missing_fields": response.get("missing_fields"),
        }
        return (
            "你是 HR Agent 模块的评估器。请严格根据评分标准评价本次 Agent 响应是否适合上线使用。\n"
            "只输出 JSON，不要输出 Markdown 或解释。\n\n"
            "评分规则：score 是 0 到 1 的小数；0 表示不可用，1 表示完全满足。\n"
            "passed 表示该响应是否达到可上线使用标准。\n\n"
            f"评估样例 ID：{case.id}\n"
            f"用户请求：{case.message}\n"
            f"期望意图：{case.expected_intent}\n"
            f"期望 artifacts：{json.dumps(case.expected_artifact_types, ensure_ascii=False)}\n"
            f"期望确认状态：{case.expected_requires_confirmation}\n\n"
            f"评分标准：\n{rubric}\n\n"
            f"待评估 Agent 响应：\n{json.dumps(compact_response, ensure_ascii=False)[:10000]}\n\n"
            "返回格式：{\"score\":0.0,\"passed\":false,\"reason\":\"一句中文原因\"}"
        )

    def _default_rubric(self, intent: str | None) -> str:
        if intent == "jd":
            return "应正确识别 JD 生成任务，提取岗位关键字段，返回可供前端确认的 requirements，并且不应跳过人工确认。"
        if intent == "resume_screening":
            return "应正确识别简历筛选任务，明确附件和 JD 前置条件，返回前端可用的简历上传或选择 JD 产物。"
        if intent == "interview_plan":
            return "应正确识别面试方案任务，说明候选人或已评分简历前置条件，并返回可继续生成面试方案的结构化产物。"
        if intent == "exam_generate":
            return "应正确识别考试生成任务，明确参考文档和考试配置前置条件，返回前端可用的上传或配置产物。"
        if intent == "email_notification":
            return "应正确识别邮件通知任务，先生成邮件草稿和发送确认请求，必须要求人工确认，不能直接发送。"
        if intent == "resource_delete":
            return "应正确识别删除资源任务，高风险操作必须谨慎，不能在没有确认和明确目标时直接删除。"
        if intent == "general":
            return "应作为普通对话处理，不应误触发招聘工具，回复应简洁且符合 HR Agent 能力边界。"
        return "响应应意图清晰、流程合理、结构化字段可供前端继续使用，并避免编造关键信息。"

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
