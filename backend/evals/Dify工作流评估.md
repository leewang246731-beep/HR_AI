## Dify 工作流评估

评估 Dify 中 **JD 生成**和**评分标准生成**工作流的稳定性。

>  这里以 **JD 生成**和**评分标准生成**为例，其他模块评估方式类似

### 当前覆盖：

- JD 生成（`workflow_type=1`）：`backend/evals/dify_cases/jd_cases.json`
- 评分标准生成（`workflow_type=2`）：`backend/evals/dify_cases/scoring_cases.json`
- 多次重复运行：脚本参数 `--repeat-runs`
- 通用规则检查：非空、长度、必要关键词、必要章节、禁用词
- 大模型裁判评分：脚本参数 `--llm-judge`
- 回归对比：脚本参数 `--baseline`

### 评估流程

1. 从 `dify_cases` 读取固定评估样例，只接受 `workflow_type=1` 和 `workflow_type=2`。
2. 按样例调用对应 Dify 工作流；默认阻塞调用，可通过 `--stream` 验证流式输出。
3. 对输出执行确定性规则检查；任一必检规则失败，本次运行即失败。
4. 可选启用 `--llm-judge`，根据样例中的 `rubric` 评估语义质量和业务可用性。
5. 按 `--repeat-runs` 聚合稳定性、输出长度波动、延迟和失败原因。
6. 生成 JSON/Markdown 报告，并可通过 `--baseline` 做回归对比。



### 运行

运行示例：

```bash
cd backend

# 指定评估集：--cases evals/dify_cases
# 重复次数：--repeat-runs 3
python scripts/run_dify_evals.py --cases evals/dify_cases --repeat-runs 3
```

启用大模型裁判评分：

```bash
cd backend

# 使用大模型裁判评分 --llm-judge
python scripts/run_dify_evals.py --cases evals/dify_cases --repeat-runs 3 --llm-judge
```

和历史报告做回归对比：

```bash
cd backend

# 回归对比：--baseline evals/reports/dify_eval_latest.json
python scripts/run_dify_evals.py  --cases evals/dify_cases  --repeat-runs 3  --baseline evals/reports/dify_eval_latest.json
```

输出文件：

- `backend/evals/reports/dify_eval_<timestamp>.json`
- `backend/evals/reports/dify_eval_<timestamp>.md`
- `backend/evals/reports/dify_eval_latest.json`
- `backend/evals/reports/dify_eval_latest.md`
