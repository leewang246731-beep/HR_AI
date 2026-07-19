## HR项目代码文件说明

#### 一、 HR项目整体是前后端分离架构：

- `backend`：FastAPI 后端，负责认证、用户/角色、知识库、RAG 问答、简历评估、JD 生成、评分标准、面试方案、考试管理、邮箱抓取等业务。
- `frontend`：Vue 3 + Vite + Element Plus 前端，提供登录注册、工作台、招聘、培训、知识助理、系统管理等页面。
- 数据层：后端使用 SQLAlchemy async + PostgreSQL，文档向量检索依赖 `pgvector`。
- AI 能力：包含 OpenAI 兼容 LLM 调用、Qwen rerank、LangChain RAG、Dify 工作流、远程 HR 服务调用。
- 启动入口是 [backend/main.py](/Users/ijeff/Desktop/HRAgent/hr-agent-study-master/backend/main.py)，API 聚合入口是 [backend/app/api/v1/api.py](/Users/ijeff/Desktop/HRAgent/hr-agent-study-master/backend/app/api/v1/api.py)。

**后端入口**

- `backend/main.py`：创建 FastAPI 应用，配置 CORS、中间件、异常处理、API 路由；生命周期里初始化数据库并启动邮件抓取调度器，关闭时释放数据库连接和调度任务。

**app/core**
- `config.py`：集中定义项目配置，包括 API 前缀、数据库、JWT、LLM、Embedding、Dify、RAG、上传文件、日志等环境变量。
- `database.py`：创建异步数据库引擎、`AsyncSessionLocal`、`get_db` 依赖，并提供初始化、关闭、连通性检查。
- `security.py`：密码哈希校验、JWT access token 创建和 token 解析。
- `middleware.py`：请求日志中间件、安全响应头中间件。
- `logging.py`：日志目录、控制台/文件日志、错误日志配置。
- `exceptions.py`：定义统一业务异常，如认证、权限、文档、知识库、LLM、数据库、外部服务异常。
- `exception_handlers.py`：把 FastAPI、Pydantic、SQLAlchemy、自定义异常统一转换成 JSON 错误响应。
- `__init__.py`：core 包标识文件。

**app/models**

- `base.py`：所有 ORM 模型的基类，内置 `id`、`created_at`、`updated_at`、`is_active`、`to_dict()` 等通用字段和方法。
- `user.py`：用户、角色、用户角色关联表；支持传统枚举角色和 RBAC 多角色体系。
- `conversation.py`：对话与消息模型，保存用户聊天历史、消息角色、状态和元数据。
- `document.py`：文档模型，保存文件路径、哈希、提取文本、摘要、标签、知识库归属和向量 embedding。
- `knowledge_base.py`：知识库和 FAQ 模型，组织文档、常见问题、访问配置和统计信息。
- `resume_evaluation.py`：简历评估模型，保存简历内容、岗位、AI 评分、状态、评估结果。
- `exam.py`：试卷和题目模型，保存考试结构、题型、答案、分值、分享状态等。
- `exam_result.py`：考试提交结果模型，保存考生答案、得分、评分详情。
- `email_config.py`：招聘邮箱配置和邮件抓取日志模型。
- `jd_status.py`：JD 状态枚举。
- `scoring_status.py`：评分标准状态枚举。
- `__init__.py`：集中导出 ORM 模型，方便数据库初始化和服务层导入。

**app/schemas**
- `auth.py`：登录、注册、Token、重置密码、修改密码请求/响应模型，并做密码强度校验。
- `user.py`：用户、角色、分配角色相关 Pydantic schema。
- `conversation.py`：对话、消息、消息反馈的创建、更新、响应模型。
- `chat.py`：聊天请求、聊天响应、流式消息、建议问题、反馈、上下文模型。
- `document.py`：文档上传、文档响应、搜索请求、搜索结果、chunk 响应模型，并处理 embedding 序列化。
- `knowledge_base.py`：知识库、FAQ、知识库搜索和反馈相关 schema。
- `resume_evaluation.py`：简历上传、评估指标、AI 评估结果、历史列表、导出请求模型。
- `job_description.py`：JD 保存、更新、列表、生成请求和响应模型。
- `scoring_criteria.py`：评分标准保存、更新、列表、生成请求和响应模型。
- `interview_plan.py`：面试方案保存、生成、列表和详情响应模型。
- `exam.py`：试卷生成、提交、创建请求模型。
- `email_config.py`：邮箱配置、连接测试、抓取日志、自动评估请求模型。
- `intent.py`：意图路由、需求解析、考试意图解析及知识文件信息模型。
- `__init__.py`：schema 包导出入口。

**app/api**
- `deps.py`：认证依赖，解析 OAuth2 Bearer token，获取当前用户，检查 HR、超管、管理员角色权限。
- `__init__.py`：API 包标识文件。

**app/api/v1**
- `api.py`：把所有 endpoint 注册到 `/api/v1` 下，并提供 `/health` 健康检查。
- `__init__.py`：v1 包标识文件。

**app/api/v1/endpoints**
- `auth.py`：注册、登录、刷新 token、获取当前用户信息。
- `users.py`：用户 CRUD、管理员创建用户、角色列表、角色创建/删除、用户角色分配。
- `conversations.py`：创建、查询、更新、删除对话，以及查询对话消息。
- `chat.py`：普通聊天、流式聊天、建议问题、聊天反馈。
- `documents.py`：文档列表、上传、详情、chunk 查询、删除；上传走增强文档处理服务。
- `knowledge_base.py`：知识库列表、创建、更新、删除，并做管理员权限校验。
- `knowledge_assistant.py`：知识助手配置、流式问答、知识文档列表、自动选择知识库。
- `hr_workflows.py`：封装 Dify HR 工作流，覆盖需求解析、JD 生成、评分标准、简历评估、面试方案、批量简历、试卷生成和提交。
- `job_description.py`：JD 保存、更新、详情、列表、删除。
- `scoring_criteria.py`：评分标准保存、更新、详情、列表、删除。
- `resume_evaluation.py`：自动简历评估、历史记录、详情、状态更新、删除、ZIP 导出、触发文件创建。
- `interview_plan.py`：面试方案创建、更新、详情、列表、删除。
- `exam_management.py`：试卷列表、保存、详情、更新、删除、分享试卷、考试结果、结果导出。
- `email_configs.py`：邮箱配置 CRUD、连接测试、手动抓取、抓取日志、最新邮件。
- `stats.py`：工作台统计、招聘趋势、培训完成率、近期活动。
- `intent_router.py`：根据用户输入做意图分类，返回前端路由建议。
- `__init__.py`：endpoint 包标识文件。

**app/services**
- `user_service.py`：用户注册登录、token 刷新、用户 CRUD、角色管理和 RBAC 分配。
- `conversation_service.py`：对话权限检查、对话 CRUD、消息写入和消息列表。
- `chat_service.py`：组合 LLM、对话服务和文档服务，处理聊天、流式输出、建议问题、反馈。
- `llm_service.py`：OpenAI 兼容接口封装，支持生成回复、流式回复、embedding、摘要、建议问题。
- `embedding_service.py`：Embedding 单例服务，避免重复初始化，并提供文本切分器。
- `compatible_embeddings.py`：LangChain Embeddings 适配器，调用 OpenAI 兼容 embedding API。
- `document_service.py`：基础文档上传、查询、更新、删除、搜索和哈希去重。
- `enhanced_document_service.py`：增强文档处理，负责语义切分、长文本拆分、短块合并、向量化入库。
- `lightweight_document_service.py`：轻量文档查询/删除服务，不触发 LLM 或 embedding 初始化。
- `knowledge_base_service.py`：知识库/FAQ 管理、访问控制、后台 endpoint 专用权限逻辑。
- `knowledge_assistant_service.py`：知识助手业务封装，调 RAG 服务做流式问答。
- `rag_service.py`：RAG 核心，包含查询增强、全文检索、向量/文本分数融合、重排、上下文构造和流式回答。
- `rerank_service.py`：Qwen/DashScope 重排服务，对召回文档重新排序。
- `kb_selection_service.py`：根据问题和用户文档列表，调用 LLM 自动选择最相关知识库。
- `intent_service.py`：规则优先、LLM 兜底的意图分类，并映射到前端路由。
- `dify_service.py`：Dify 工作流同步/流式调用封装。
- `remote_service_client.py`：统一远程 HR 服务 HTTP 客户端，封装 header、参数、响应处理。
- `job_description_service.py`：JD 业务层，主要通过远程服务保存、更新、查询、删除。
- `scoring_criteria_service.py`：评分标准业务层，调用远程服务完成 CRUD。
- `interview_plan_service.py`：面试方案业务层，调用远程服务并关联简历评估数据。
- `resume_parser_service.py`：简历文件校验和 TXT/PDF/DOC/DOCX 文本提取。
- `resume_evaluation_service.py`：简历自动评分主逻辑，保存上传文件、匹配 JD、调用 AI 评估、写入评估记录。
- `exam_service.py`：考试管理核心逻辑，处理试卷 CRUD、题目同步、分享考试、提交结果和导出。
- `email_service.py`：邮箱配置服务和邮件抓取服务，读取附件并可生成简历评估记录。
- `email_scheduler.py`：基于 asyncio 的邮箱自动抓取调度器，为启用配置启动/刷新/停止任务。
- `stats_service.py`：聚合简历、考试、面试、对话等数据，为仪表板提供统计。
- `__init__.py`：services 包标识文件。

**app/utils**

- `file_utils.py`：文件哈希、MIME、目录创建、安全删除/复制、上传保存、文件名清洗和唯一命名。
- `text_utils.py`：文本清洗、HTML 去除、关键词提取、文本切块、相似度、Markdown 转义、敏感信息脱敏。
- `validation_utils.py`：邮箱、密码、用户名、文件类型/大小、手机号、URL、UUID、JSON、IP、颜色、SQL 输入校验。
- `date_utils.py`：UTC 时间、格式化/解析、时区转换、日期差、工作日判断、相对时间、常用时区。
- `email_utils.py`：IMAP/POP/SMTP 邮箱读取工具，支持连接、列目录、搜邮件、解析邮件内容和附件。
- `__init__.py`：导出常用工具函数。

**backend/scripts**
- `db_manager.py`：数据库运维脚本，支持创建/删除数据库、生成迁移、应用迁移、回滚、查看迁移历史。

- `seed_roles.py`：初始化内置角色和默认超级管理员。

  