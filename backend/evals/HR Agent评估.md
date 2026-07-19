# HR Agent 评估

评估 HR Agent 模块的稳定性和业务流程正确性。

当前覆盖：

- 固定评估集：`backend/evals/agent_cases/*.json`
- 多次重复运行：脚本参数 `--repeat-runs`
- 规则检查：意图、路由、步骤、产物、确认流程、缺失字段、结构化内容
- 大模型裁判评分：脚本参数 `--llm-judge`
- 回归对比：脚本参数 `--baseline`
- 分项质量指标：意图、路由、确认、Artifact、工具步骤、缺失字段

> Artifact 可以理解为 Agent 返回给前端的“可继续执行的结构化业务数据”。
> 它不是普通回复文字，而是前端能识别、展示并据此继续调用后端接口的数据对象。
>
> 评估中的“Artifact 契约通过率”检查的是：
> - Agent 是否返回正确的 Artifact 类型。
> - Artifact 的 content 中是否包含前端需要的字段。
> - 这些字段值是否正确，


## 评估重点

Agent 模块不是单纯聊天回复，因此评估重点是：

- 是否识别正确 `intent`
- 是否返回正确前端 `route`
- 是否返回正确 `steps`
- 是否返回前端可用的 `artifacts`
- 是否遵守 `requires_confirmation` 人工确认流程
- 是否正确标记 `missing_fields`
- 是否正确抽取结构化字段
- 同一输入多次运行是否稳定

## 运行示例

```bash
cd backend
python scripts/run_agent_evals.py --cases evals/agent_cases --repeat-runs 3
```

启用大模型裁判评分：

```bash
cd backend
python scripts/run_agent_evals.py --cases evals/agent_cases --repeat-runs 3 --llm-judge
```

和历史报告做回归对比：

```bash
cd backend
python scripts/run_agent_evals.py  --cases evals/agent_cases  --repeat-runs 3  --baseline evals/reports/agent_eval_latest.json
```


## 输出文件

- `backend/evals/reports/agent_eval_<timestamp>.json`
- `backend/evals/reports/agent_eval_<timestamp>.md`
- `backend/evals/reports/agent_eval_latest.json`
- `backend/evals/reports/agent_eval_latest.md`

## 样例字段说明

常用字段：

- `message`：用户自然语言输入。
- `attachments`：附件元信息，只需要文件名即可识别扩展名。
- `expected_intent`：期望 Agent 返回的意图。
- `expected_route`：期望前端跳转或展示的路由。
- `expected_requires_confirmation`：是否需要人工确认。
- `expected_artifact_types`：必须出现的 artifact 类型。
- `forbidden_artifact_types`：不允许出现的 artifact 类型。
- `expected_step_ids`：必须出现的步骤 ID。
- `expected_step_statuses`：指定步骤的期望状态。
- `expected_tools`：步骤里必须出现的工具标记。
- `expected_missing_fields`：期望标记的缺失字段。
- `content_checks`：结构化内容路径检查。
- `rubric`：大模型裁判评分标准。

`content_checks` 支持两类路径：

- `artifact:<type>.content.xxx`：按 artifact 类型查找内容。
- `step:<id>.status`：按 step ID 查找步骤字段。

> content_checks 是 Agent 评估用例中的“结构化内容断言”。
>
> 用于检查 Agent 返回的 artifacts 或 steps 内部字段是否符合预期，而不只检查是否返回了某个 Artifact 类型。

示例：

```json
{
  "content_checks": {
      "artifact:resume_upload_request.content.file_count": 3,
      "artifact:resume_upload_request.content.requires_job_description": true
    }
}
```
含义是：
- Agent 必须返回 resume_upload_request 类型的 Artifact。
- 该 Artifact 的 content.file_count 必须等于 3。
- content.requires_job_description 必须为 true。

支持的检查方式：

- 直接值：要求至少一个取值完全相等。
- `{"equals": "..."}`：完全相等。
- `{"contains": "..."}`：包含指定文本。
- `{"regex": "..."}`：匹配正则。
- `{"min_length": 20}`：文本长度达到下限。
- `{"exists": true}`：路径存在。

## 注意事项

默认样例避免真实副作用：

- 邮件只评估草稿和确认请求，不默认触发 SMTP 发送。
- 如果启用 `--llm-judge`，需要项目中的 LLM 配置可用。

## 建议发布阈值

| 指标 | 建议阈值 |
|---|-----:|
| 意图准确率 |  90% |
| Artifact 契约通过率 |  95% |
| 人工确认正确率 |  95% |
| 核心响应签名稳定性 |  90% |

