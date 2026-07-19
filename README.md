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
