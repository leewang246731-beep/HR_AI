# HR Agent 项目迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 HR Agent 项目从学习资料完整迁移到 `d:\hr_ai`，配置环境，Docker 部署数据库，推送到 GitHub

**Architecture:** 源码从 `D:\学习资料\HRAgent项目设计与实现\代码\hr-agent-study\` 和 `D:\学习资料\hr-agent-study-2.zip` 提取，结构化复制到 `d:\hr_ai` 的 backend/frontend/docs/images 目录，排除所有缓存和 IDE 文件

**Tech Stack:** FastAPI + PostgreSQL/pgvector + SQLAlchemy + Vue 3 + Element Plus + Vite

## Global Constraints

- 源路径: `D:\学习资料\HRAgent项目设计与实现\代码\hr-agent-study\`
- 补充源: `D:\学习资料\hr-agent-study-2.zip`（仅提取 evaluations + evals + 3 个 eval 脚本）
- 目标路径: `d:\hr_ai`
- 排除: `__pycache__/`, `*.pyc`, `.DS_Store`, `.idea/`, `node_modules/`, `*.log`, `.pytest_cache/`
- 数据库密码: `121300`
- LLM API Key: `sk-b67a88b0601941338abadced5c03474c`
- DeepSeek API Key: `sk-503ce9d2f0fc4af381473862c3f00781`
- GitHub 仓库名: `HR_AI`

---

### Task 1: Git 初始化 + .gitignore + README

**Files:**
- Create: `d:\hr_ai\.gitignore`
- Create: `d:\hr_ai\README.md`

- [ ] **Step 1: 初始化 git 仓库**

```bash
cd d:\hr_ai
git init
```

- [ ] **Step 2: 创建 .gitignore**

写入 `d:\hr_ai\.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
*.log

# Node
node_modules/
dist/

# IDE
.idea/
.vscode/
*.swp

# Environment
.env
.venv/
venv/

# Docker
postgres_data/

# OS
.DS_Store
Thumbs.db

# Uploads
uploads/
```

- [ ] **Step 3: 创建 README.md**

写入 `d:\hr_ai\README.md`:

```markdown
# HR Agent - 智能人力资源管理系统

基于大语言模型的智能人力资源管理平台，覆盖招聘全流程自动化。

## 功能模块

- **JD 生成**: AI 驱动的岗位描述生成
- **简历筛选**: 智能简历解析、评分与排名
- **智能面试**: 自动生成面试方案与题目
- **知识库管理**: RAG 增强的企业知识问答
- **考试系统**: 自动生成试卷、智能阅卷
- **邮件工作流**: 自动化邮件通知
- **HR Agent 对话**: 统一的 AI 助手入口

## 技术栈

- **后端**: FastAPI + PostgreSQL + pgvector + SQLAlchemy
- **前端**: Vue 3 + Element Plus + Vite
- **AI**: 阿里云百炼 (通义千问) + DeepSeek + Dify 工作流

## 快速开始

### 1. 启动数据库

```bash
cd backend
docker compose up -d
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
python main.py
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

## 项目结构

```
├── backend/          # FastAPI 后端
├── frontend/         # Vue 3 前端
├── docs/             # 设计文档
├── images/           # 流程图
├── knowledge_base/   # 知识库文件
└── sample_resumes/   # 简历样本
```
```

- [ ] **Step 4: 提交**

```bash
cd d:\hr_ai
git add .gitignore README.md
git commit -m "chore: init repo with .gitignore and README"
```

---

### Task 2: 迁移 Backend 核心源码

**Files:**
- Create: `d:\hr_ai\backend\` (递归复制)

- [ ] **Step 1: 复制 backend 主目录文件**

```bash
cd "D:\学习资料\HRAgent项目设计与实现\代码\hr-agent-study\backend"
cp main.py "d:\hr_ai\backend\"
cp requirements.txt "d:\hr_ai\backend\"
cp Dockerfile "d:\hr_ai\backend\"
cp docker-compose.yml "d:\hr_ai\backend\"
cp alembic.ini "d:\hr_ai\backend\"
cp .env.example "d:\hr_ai\backend\"
```

- [ ] **Step 2: 复制 app/ 目录（排除缓存）**

```bash
mkdir -p "d:\hr_ai\backend\app"
cd "D:\学习资料\HRAgent项目设计与实现\代码\hr-agent-study\backend\app"
find . -type f -not -path "*__pycache__*" -not -name "*.pyc" -not -name ".DS_Store" | while read f; do
  dest="d:\hr_ai\backend\app\$f"
  mkdir -p "$(dirname "$dest")"
  cp "$f" "$dest"
done
```

- [ ] **Step 3: 复制 skills/ 目录**

```bash
cp -r "D:\学习资料\HRAgent项目设计与实现\代码\hr-agent-study\backend\skills" "d:\hr_ai\backend\skills"
```

- [ ] **Step 4: 复制 scripts/ 目录**

```bash
cp -r "D:\学习资料\HRAgent项目设计与实现\代码\hr-agent-study\backend\scripts" "d:\hr_ai\backend\scripts"
```

- [ ] **Step 5: 从 zip 补充 evaluations/ 目录**

```bash
cd /tmp && rm -rf hr_agent_zip_extract && mkdir hr_agent_zip_extract && cd hr_agent_zip_extract
unzip -o "D:\学习资料\hr-agent-study-2.zip" \
  "hr-agent-study-2/backend/app/evaluations/*" \
  -x "*.pyc" "__pycache__/*"
cp -r hr-agent-study-2/backend/app/evaluations "d:\hr_ai\backend\app\evaluations"
```

- [ ] **Step 6: 从 zip 补充 evals/ 目录和 eval 脚本**

```bash
cd /tmp/hr_agent_zip_extract
unzip -o "D:\学习资料\hr-agent-study-2.zip" \
  "hr-agent-study-2/backend/evals/*" \
  "hr-agent-study-2/backend/scripts/run_agent_evals.py" \
  "hr-agent-study-2/backend/scripts/run_dify_evals.py" \
  "hr-agent-study-2/backend/scripts/run_rag_evals.py" \
  -x "*.pyc" "__pycache__/*"
cp -r hr-agent-study-2/backend/evals "d:\hr_ai\backend\evals"
cp hr-agent-study-2/backend/scripts/run_*.py "d:\hr_ai\backend\scripts/"
```

- [ ] **Step 7: 验证 backend 文件完整性**

```bash
echo "=== Backend 目录结构 ==="
find "d:\hr_ai\backend" -type f -not -path "*__pycache__*" | sort
echo ""
echo "=== 文件数量 ==="
find "d:\hr_ai\backend" -type f -not -path "*__pycache__*" | wc -l
```

预期: 100+ 文件，包含 api/endpoints/, core/, models/, schemas/, services/, utils/, evaluations/, skills/, scripts/

- [ ] **Step 8: 提交**

```bash
cd d:\hr_ai
git add backend/
git commit -m "feat: migrate backend source code"
```

---

### Task 3: 迁移 Frontend 源码

**Files:**
- Create: `d:\hr_ai\frontend\` (递归复制)

- [ ] **Step 1: 复制 frontend 配置文件**

```bash
cd "D:\学习资料\HRAgent项目设计与实现\代码\hr-agent-study\frontend"
cp package.json "d:\hr_ai\frontend\"
cp package-lock.json "d:\hr_ai\frontend\"
cp vite.config.js "d:\hr_ai\frontend\"
cp index.html "d:\hr_ai\frontend\"
```

- [ ] **Step 2: 复制 src/ 和 public/ 目录**

```bash
cp -r "D:\学习资料\HRAgent项目设计与实现\代码\hr-agent-study\frontend\src" "d:\hr_ai\frontend\src"
cp -r "D:\学习资料\HRAgent项目设计与实现\代码\hr-agent-study\frontend\public" "d:\hr_ai\frontend\public"
```

- [ ] **Step 3: 验证 frontend 文件完整性**

```bash
echo "=== Frontend 目录结构 ==="
find "d:\hr_ai\frontend" -type f -not -path "*node_modules*" | sort
echo ""
echo "=== 文件数量 ==="
find "d:\hr_ai\frontend" -type f -not -path "*node_modules*" | wc -l
```

预期: 40+ 文件，包含 src/api/, src/views/, src/router/, src/stores/

- [ ] **Step 4: 提交**

```bash
cd d:\hr_ai
git add frontend/
git commit -m "feat: migrate frontend source code"
```

---

### Task 4: 迁移文档、图片、知识库、简历样本

**Files:**
- Create: `d:\hr_ai\docs\`
- Create: `d:\hr_ai\images\`
- Create: `d:\hr_ai\knowledge_base\`
- Create: `d:\hr_ai\sample_resumes\`

- [ ] **Step 1: 复制设计文档**

```bash
cp -r "D:\学习资料\HRAgent项目设计与实现\文档\docs" "d:\hr_ai\docs\project-docs"
cp "D:\学习资料\HRAgent项目设计与实现\文档\HRAgent项目设计与实现.pptx" "d:\hr_ai\docs\"
cp "D:\学习资料\HRAgent项目设计与实现\文档\HR Agent项目 环境配置与部署.pdf" "d:\hr_ai\docs\"
cp "D:\学习资料\HRAgent项目设计与实现\文档\HR Agent知识库优化方案.pdf" "d:\hr_ai\docs\"
cp "D:\学习资料\HRAgent项目设计与实现\文档\HRAgent使用流程.pdf" "d:\hr_ai\docs\"
cp "D:\学习资料\HRAgent项目设计与实现\文档\HRAgent知识库优化.md" "d:\hr_ai\docs\"
cp -r "D:\学习资料\HRAgent项目设计与实现\文档\kb优化方案" "d:\hr_ai\docs\kb优化方案"
```

- [ ] **Step 2: 复制流程图**

```bash
cp -r "D:\学习资料\images"/* "d:\hr_ai\images\"
```

- [ ] **Step 3: 复制知识库文件**

```bash
cp -r "D:\学习资料\HRAgent项目设计与实现\知识库"/* "d:\hr_ai\knowledge_base\"
```

- [ ] **Step 4: 复制简历样本**

```bash
cp -r "D:\学习资料\HRAgent项目设计与实现\简历"/* "d:\hr_ai\sample_resumes\"
```

- [ ] **Step 5: 提交**

```bash
cd d:\hr_ai
git add docs/ images/ knowledge_base/ sample_resumes/
git commit -m "docs: add project documentation, images, knowledge base and sample resumes"
```

---

### Task 5: 配置环境变量和 Docker

**Files:**
- Create: `d:\hr_ai\.env`
- Modify: `d:\hr_ai\backend\docker-compose.yml`

- [ ] **Step 1: 创建 .env 配置文件**

写入 `d:\hr_ai\.env`:

```env
# HR Agent 后端环境配置

# 应用设置
PROJECT_NAME=HR Agent
VERSION=1.0.0
DEBUG=true
HOST=0.0.0.0
PORT=8000
API_V1_STR=/api/v1

# 安全配置
SECRET_KEY=hr-agent-secret-key-change-in-production-2024
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 数据库配置
DATABASE_URL=postgresql://hr_agent_user:121300@localhost:5432/hr_agent
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=hr_agent_user
DATABASE_PASSWORD=121300
DATABASE_NAME=hr_agent

# 远程服务配置
HR_SERVICE_HOST=127.0.0.1
HR_SERVICE_PORT=8000
HR_SERVICE_APIKEY=your-api-key

# CORS 设置
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:8080","http://localhost:5173"]

# LLM 设置 (阿里云百炼 - 通义千问)
LLM_API_KEY=sk-b67a88b0601941338abadced5c03474c
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-max

# Qwen 重排序设置
QWEN_API_KEY=sk-b67a88b0601941338abadced5c03474c
QWEN_MODEL=gte-rerank-v2

# 嵌入设置
EMBEDDING_API_KEY=sk-b67a88b0601941338abadced5c03474c
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v1

# 查询改写设置
KB_QUERY_ENHANCE_ENABLED=true
KB_QUERY_EXPANSION_MAX_TERMS=6

# 向量数据库 (pgvector)
VECTOR_DIMENSION=1536

# 文件上传设置
MAX_FILE_SIZE=10485760
ALLOWED_FILE_TYPES=["pdf","docx","txt","md"]
UPLOAD_DIR=uploads

# 日志配置
LOG_LEVEL=INFO
REMOTE_SERVICE_LOG_ENABLED=false

# 上下文配置
CONTEXT_LIMIT=5

# Dify 工作流配置 (待 Dify 部署完成后填入实际值)
DIFY_BASE_URL=http://localhost/v1
DIFY_API_KEY=app-PLACEHOLDER
DIFY_USER_ID=hr-agent-user

# 重排序设置
RERANK_ENABLED=true
RERANK_TOP_K=10
RERANK_FINAL_K=10

# RAG 分数组合权重设置
RAG_CONTENT_WEIGHT=0.7
RAG_TEXT_WEIGHT=0.3
```

- [ ] **Step 2: 复制 .env 到 backend 目录（config.py 期望的路径）**

```bash
cp "d:\hr_ai\.env" "d:\hr_ai\backend\.env"
```

- [ ] **Step 3: 更新 docker-compose.yml 使用新密码**

读取 `d:\hr_ai\backend\docker-compose.yml`，修改数据库密码:

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: hr_agent_postgres
    environment:
      POSTGRES_DB: hr_agent
      POSTGRES_USER: hr_agent_user
      POSTGRES_PASSWORD: 121300
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hr_agent_user -d hr_agent"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

- [ ] **Step 4: 提交**

```bash
cd d:\hr_ai
git add .env backend/.env backend/docker-compose.yml
git commit -m "config: add environment configuration and docker-compose"
```

---

### Task 6: Docker 拉取并启动 PostgreSQL

- [ ] **Step 1: 拉取 pgvector 镜像**

```bash
docker pull pgvector/pgvector:pg16
```

- [ ] **Step 2: 启动 PostgreSQL 容器**

```bash
cd d:\hr_ai\backend
docker compose up -d
```

- [ ] **Step 3: 等待数据库就绪**

```bash
echo "等待 PostgreSQL 启动..."
sleep 10
docker ps --filter "name=hr_agent_postgres" --format "table {{.Names}}\t{{.Status}}"
```

预期: `hr_agent_postgres` 状态为 `Up` 且 `healthy`

- [ ] **Step 4: 验证数据库连接**

```bash
docker exec hr_agent_postgres psql -U hr_agent_user -d hr_agent -c "SELECT 1 AS connected;"
```

预期输出: `connected: 1`

---

### Task 7: 安装 Python 依赖并验证后端启动

- [ ] **Step 1: 创建虚拟环境**

```bash
cd d:\hr_ai\backend
python -m venv venv
source venv/Scripts/activate
```

- [ ] **Step 2: 安装依赖**

```bash
pip install -r requirements.txt
```

- [ ] **Step 3: 启动后端验证**

```bash
cd d:\hr_ai\backend
python main.py &
sleep 5
curl http://localhost:8000/docs
```

预期: FastAPI Swagger 文档页面返回 HTML

- [ ] **Step 4: 停止测试服务器**

```bash
pkill -f "python main.py"
```

---

### Task 8: 安装前端依赖并验证前端启动

- [ ] **Step 1: 安装 npm 依赖**

```bash
cd d:\hr_ai\frontend
npm install
```

- [ ] **Step 2: 验证 Vite 构建**

```bash
npx vite build
```

预期: 构建成功，`dist/` 目录生成

- [ ] **Step 3: 提交 lock 文件**

```bash
cd d:\hr_ai
git add frontend/package-lock.json
git commit -m "chore: add frontend lock file"
```

---

### Task 9: 推送到 GitHub

- [ ] **Step 1: 在 GitHub 创建仓库**

```bash
gh repo create HR_AI --public --description "HR Agent - 智能人力资源管理系统" --source=. --remote=origin --push
```

或者手动:
```bash
git remote add origin https://github.com/<your-username>/HR_AI.git
git branch -M main
git push -u origin main
```

- [ ] **Step 2: 验证推送**

```bash
git remote -v
git log --oneline -10
```

预期: 所有 commit 已推送到 GitHub

---

### Task 10: 最终验证清单

- [ ] PostgreSQL 容器运行正常: `docker ps | grep hr_agent_postgres`
- [ ] `.env` 配置已填入实际 API Key
- [ ] `backend/venv/` 虚拟环境已创建，`requirements.txt` 全部安装成功
- [ ] 后端可以启动: `python main.py` 无报错
- [ ] 前端可以启动: `npm run dev` 无报错
- [ ] GitHub 仓库 `HR_AI` 包含所有文件
- [ ] `.gitignore` 排除了 `__pycache__/`, `node_modules/`, `.env`, `uploads/`
