# HR Agent 项目迁移设计文档

**日期**: 2026-07-19  
**目标**: 将 HR Agent 智能人力资源管理系统从学习资料完整迁移到 `d:\hr_ai`，推送到 GitHub

---

## 1. 项目概述

HR Agent 是一个智能人力资源管理系统，覆盖招聘全流程：JD 生成、简历筛选与评分、智能面试方案、知识库 RAG 问答、考试生成与阅卷、邮件自动化、HR Agent 对话。

**技术栈**: FastAPI + PostgreSQL/pgvector + SQLAlchemy + Vue 3 + Element Plus + 阿里云百炼 LLM + Dify 工作流

---

## 2. 源码来源策略

- **主源**: `D:\学习资料\HRAgent项目设计与实现\代码\hr-agent-study\`
- **补充源**: `D:\学习资料\hr-agent-study-2.zip`（仅补充主源缺失文件）
- **流程图**: `D:\学习资料\images\`
- **排除**: `__pycache__/`, `*.pyc`, `.DS_Store`, `.idea/`, `node_modules/`

---

## 3. 目标目录结构

```
d:\hr_ai/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/    # 16 个 API 端点
│   │   ├── core/                 # config, database, security, exceptions, middleware, logging
│   │   ├── models/               # 11 个数据模型
│   │   ├── schemas/              # Pydantic 请求/响应 schema
│   │   ├── services/             # 20+ 业务服务
│   │   └── utils/                # 工具函数
│   ├── skills/hr-agent-email/    # 邮件技能
│   ├── scripts/                  # DB 初始化脚本
│   ├── main.py                   # FastAPI 入口
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
├── frontend/
│   ├── src/
│   │   ├── api/                  # Axios API 调用层
│   │   ├── views/                # Vue 页面组件
│   │   ├── router/               # Vue Router
│   │   ├── stores/               # Pinia 状态管理
│   │   ├── layouts/              # 布局组件
│   │   └── utils/                # 请求封装
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docs/                         # 设计文档 + Dify 部署指南
├── images/                       # 工作流程图 (PNG/SVG)
├── knowledge_base/               # 知识库文档
├── sample_resumes/               # 简历样本
├── .env                          # 环境变量
├── .gitignore
└── README.md
```

---

## 4. 关键配置

| 配置项 | 值 |
|--------|-----|
| LLM API Key (千问/阿里云) | `sk-b67a88b0601941338abadced5c03474c` |
| LLM Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| LLM Model | `qwen-max` |
| Embedding API Key | 同 LLM Key |
| Embedding Model | `text-embedding-v1` |
| DeepSeek API Key | `sk-503ce9d2f0fc4af381473862c3f00781` |
| DB Password | `121300` |
| DB User/Name | `hr_agent_user` / `hr_agent` |
| Dify | 并行部署，配置后续填入 |

---

## 5. 部署架构

```
Docker Compose:
  └── postgres (pgvector/pgvector:pg16)  :5432
  └── backend  (Dockerfile)              :8000

本地:
  └── frontend (Vite dev server)         :3000

外部:
  └── Dify (独立 docker compose)          :80
  └── 阿里云 DashScope API
```

---

## 6. 实施步骤（概要）

1. 初始化 git 仓库 + `.gitignore`
2. 迁移 backend 源码（排除缓存）
3. 迁移 frontend 源码（排除 node_modules/.idea）
4. 复制 docs / images / knowledge_base / sample_resumes
5. 创建 `.env` 填入配置
6. 修改 docker-compose.yml 适配本地
7. 编写 README.md
8. Docker 启动 PostgreSQL
9. 安装 Python 依赖 + 启动后端验证
10. 安装前端依赖 + 启动前端验证
11. 推送到 GitHub

---

## 7. 不包含范围

- Dify 工作流部署（另一台智能体并行执行）
- 生产环境优化（nginx、HTTPS、域名等）
- CI/CD 流水线
