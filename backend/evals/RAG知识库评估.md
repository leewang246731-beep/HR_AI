## RAG 知识库评估

### 目前常用的 RAG 评估

#### RAG通常分成两部分：

```
检索评估 Retrieval Evaluation
  -> 看有没有找对文档、找全证据

生成评估 Generation Evaluation
  -> 看答案是否正确、是否忠实于证据、是否引用正确
```

因为 RAG 的核心链路是：

```
用户问题
  -> 查询改写
  -> 向量检索 / 关键词检索 / 混合检索
  -> Rerank
  -> 选取 Top-K 文档块
  -> LLM 基于文档块生成答案
  -> 返回答案和引用来源
```

所以评估不能只看最后答案，要分别看“检索阶段”和“回答阶段”。

#### **一、检索阶段评估**

检索阶段评估的是：系统有没有把正确文档块找出来。

常用指标：

| **指标**          | **专业术语**             | **作用**                           |
| ----------------- | ------------------------ | ---------------------------------- |
| Recall@K          | Top-K 召回率             | 正确文档块是否出现在 Top-K 结果里  |
| Precision@K       | Top-K 精确率             | Top-K 里有多少是真正相关的         |
| Hit Rate@K        | Top-K 命中率             | Top-K 中是否至少命中一个正确文档块 |
| MRR               | 平均倒数排名             | 第一个正确结果排得有多靠前         |
| NDCG@K            | Top-K 归一化折损累计增益 | 相关文档越靠前得分越高             |
| Context Relevance | 上下文相关性             | 检索上下文和问题是否相关           |
| Source Coverage   | 来源覆盖率               | 是否覆盖回答所需的关键来源         |

最常用的是这几个：

```
Recall@5  
MRR  
Hit Rate@5
```

例如固定问答集里有一个问题：

```
问题：公司的年假规则是什么？
标准证据块：document_id=doc_001, chunk_id=chunk_003
```

系统检索 Top-5 返回：

```
chunk_010
chunk_003
chunk_020
chunk_007
chunk_011
```

那么：

```
Recall@5 = 1，因为chunk_003在 Top-5里
Hit Rate@5 = 1，因为命中了至少一个正确证据块
MRR = 1 / 2，因为第一个正确结果排第2
```

#### **二、生成阶段评估**

生成阶段评估的是：LLM 基于检索内容生成的答案是否正确、完整、可信。

常用指标：

| **指标**            | **专业术语** | **作用**                 |
| ------------------- | ------------ | ------------------------ |
| Faithfulness        | 忠实度       | 答案是否忠实于检索文档   |
| Answer Relevance    | 答案相关性   | 答案是否回答了用户问题   |
| Context Utilization | 上下文利用率 | 是否有效使用了检索上下文 |
| Citation Accuracy   | 引用准确率   | 引用来源是否正确         |
| Hallucination Rate  | 幻觉率       | 是否出现文档中没有的信息 |

其中最重要的是：

```
Faithfulness
Answer Relevance
Citation Accuracy
```

因为 RAG 最大风险是：

```
看起来很专业，但事实不来自知识库
```



### **RAGAS 常用指标**

如果使用 RAGAS，一般会评估这些：

| **RAGAS 指标**    | **专业术语** | **含义**                             |
| ----------------- | ------------ | ------------------------------------ |
| Faithfulness      | 忠实度       | 答案是否忠实于上下文                 |
| Answer Relevancy  | 答案相关度   | 答案是否与问题相关                   |
| Context Precision | 上下文精确率 | 检索到的相关上下文是否集中且排序合理 |
| Context Recall    | 上下文召回率 | 标准答案所需的信息是否被上下文覆盖   |



### HR Agent 项目的知识库问答

当前项目的 RAG 实际链路是：

```text
  -> 用户问题
  -> 可选查询改写与关键词扩展
  -> PGVector 向量召回
  -> PostgreSQL tsvector / ILIKE 文本召回
  -> 合并打分
  -> 可选 Rerank 重排
  -> 返回 sources 给前端展示文档块
  -> LLM 基于 sources 生成流式答案
```

因此评估被拆成三层：

- 检索质量：是否找对文档块，以及正确文档块排得是否靠前。
- 引用质量：前端展示的 sources 是否是真正相关来源。
- 答案质量：答案是否命中标准答案要点，是否忠实于上下文，知识库外问题是否拒答。

#### 覆盖指标

确定性指标：

- `Recall@K`：Top-K sources 中命中了多少期望文档或 chunk。
- `Precision@K`：Top-K sources 中有多少是相关来源。
- `HitRate@K`：Top-K 中是否至少命中一个相关来源。
- `MRR`：第一个相关来源出现得越靠前分数越高。
- `NDCG@K`：相关来源越靠前分数越高。
- `引用来源正确率`：返回给前端展示的 sources 中相关来源占比。
- `上下文关键词召回率`：检索到的 sources 是否覆盖标准证据关键词。
- `答案命中率`：答案是否覆盖标准答案关键词。
- `延迟`：RAG 流式响应总耗时。

可选 RAGAS 指标 (*)：

- `Faithfulness`：答案是否忠实于检索上下文。
- `Answer Relevancy`：答案是否回答用户问题。
- `Context Precision`：检索上下文排序是否合理。
- `Context Recall`：检索上下文是否覆盖参考答案。

不同 RAGAS 版本的指标类名可能不同，脚本会优先使用新指标，失败时回退到兼容指标。

#### 运行方式

基础运行：

```bash
cd backend
python scripts/run_rag_evals.py --cases evals/rag_cases --repeat-runs 1
```

> --cases  evals/rag_cases  使用的评估集
>
> --repeat-runs 1 重复运行次数

启用 RAGAS：

```bash
cd backend
# 安装RAGAS
pip install -r evals/rag_requirements.txt
# --ragas 启用RAGAS
python scripts/run_rag_evals.py --cases evals/rag_cases --repeat-runs 1 --ragas
```

回归对比：

```bash
cd backend

# --baseline 以 evals/reports/rag_eval_latest.json 的评估结果为基准
python scripts/run_rag_evals.py  --cases evals/rag_cases  --repeat-runs 1  --baseline  evals/reports/rag_eval_latest.json
```


#### 输出文件

- `backend/evals/reports/rag_eval_<timestamp>.json`
- `backend/evals/reports/rag_eval_<timestamp>.md`
- `backend/evals/reports/rag_eval_latest.json`
- `backend/evals/reports/rag_eval_latest.md`

#### 样例字段

```json
{
  "id": "rag_policy_single_turn_001",
  "name": "单轮制度问答：年假申请规则",
  "enabled": true,
  "user_id": "真实用户UUID",  
  "knowledge_base_id": "真实知识库UUID",
  "question": "员工年假申请需要提前多久提交？",
  "context_limit": 5,
  "should_answer": true,
  "expected_context_used": true,
  "reference_answer": "标准参考答案，用于 RAGAS 和人工对比。",
  "expected_answer_keywords": ["年假", "提前", "审批"],
  "expected_document_ids": ["应命中的文档UUID"],
  "expected_chunk_refs": ["文档UUID#chunk_index"],
  "expected_context_keywords": ["年假", "申请", "审批"],
  "expected_query_keywords": ["年假", "申请"],
  "forbidden_answer_keywords": ["我猜", "随便"],
  "min_recall_at_k": 0.5,
  "min_mrr": 0.2,
  "min_citation_accuracy": 0.2,
  "min_answer_hit_rate": 0.8,
  "min_context_keyword_recall": 0.8
}
```

#### 需要修改，才可以运行【重要】
```json
  "user_id": "真实用户UUID",  
  "knowledge_base_id": "真实知识库UUID",
  "expected_document_ids": ["应命中的文档UUID"],
  "expected_chunk_refs": ["文档UUID#chunk_index"],
```

#### 标注文档和 Chunk

文档级标注：

```json
"expected_document_ids": ["document_uuid"]
```

Chunk 级标注：

```json
"expected_chunk_refs": ["document_uuid#3"]
```

或者：

```json
"expected_chunk_refs": [
  {
    "document_id": "document_uuid",
    "chunk_index": 3
  }
]
```

如果你能拿到 `chunk_id`，也可以写：

```json
"expected_chunk_refs": [
  {
    "chunk_id": "chunk_uuid"
  }
]
```

#### 和项目代码的对应关系

评估脚本调用：

- `backend/app/services/rag_service.py`
- `RAGService.ask_question_stream()`

#### 评估集建议

评估集建议包含：

- 单轮制度问答。
- 多轮追问，用来评估查询改写。
- 精确 chunk 命中，用来评估切块、召回和 rerank。
- 容易混淆的问题，用来评估引用来源正确率。
