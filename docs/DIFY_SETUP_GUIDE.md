# Dify 工作流引擎 —— 完整部署与适配清单

> 给另一台智能体执行。本清单可独立运行，不需要依赖主项目其他部分。

---

## 前置条件

- Docker Desktop 已安装并运行
- 配置了阿里云百炼 (DashScope) API Key: `sk-b67a88b0601941338abadced5c03474c`
- DeepSeek API Key: `sk-503ce9d2f0fc4af381473862c3f00781`

---

## 第一阶段：部署 Dify 平台

### 步骤 1：克隆 Dify

```bash
cd d:\hr_ai
git clone https://github.com/langgenius/dify.git
cd dify\docker
```

### 步骤 2：配置环境变量

复制并编辑 `.env`：

```bash
cp .env.example .env
```

编辑 `.env` 文件，关键配置如下（其余保持默认）：

```env
# 核心数据库（Dify 自己的 postgres，不与 HR Agent 共用）
DB_USERNAME=postgres
DB_PASSWORD=dify_postgres_2024

# Redis 密码
REDIS_PASSWORD=dify_redis_2024

# Dify 管理后台登录（首次启动后在此设置）
# 这些是启动后在浏览器中设置的，不需要在 .env 中写
```

### 步骤 3：启动 Dify

```bash
docker compose up -d
```

> 预计 6-8 个容器启动。等待 2-3 分钟。可通过 `docker ps` 确认所有容器状态为 healthy。

### 步骤 4：访问 Dify 管理后台

浏览器打开 `http://localhost`，首次访问会让你：
1. 设置管理员邮箱和密码（例如 admin@hr-agent.com / 你的密码）
2. 登录后进入 Dify 主界面

---

## 第二阶段：配置 LLM 模型供应商

### 步骤 5：添加通义千问（阿里云百炼）模型供应商

1. 点击右上角头像 → **设置** → **模型供应商**
2. 找到 **Tongyi (通义千问)** → 点击 **设置**
3. 填入 API Key: `sk-b67a88b0601941338abadced5c03474c`
4. 点击保存

### 步骤 6：添加 DeepSeek 模型供应商（如列表中没有）

1. 在模型供应商页面，点击 **添加供应商**
2. 选择 **OpenAI-API-compatible** 类型
3. 配置如下：

| 字段 | 值 |
|------|-----|
| 供应商名称 | `DeepSeek` |
| API Base URL | `https://api.deepseek.com/v1` |
| API Key | `sk-503ce9d2f0fc4af381473862c3f00781` |

4. 保存后，模型列表应出现 `deepseek-chat`, `deepseek-v4-flash` 等

---

## 第三阶段：导入 HR Agent 工作流应用

### 步骤 7：导入工作流 YAML

HR Agent 工作流配置文件位于主项目的：
`D:\学习资料\HRAgent项目设计与实现\资料\dify资料\hr_agent.yml`

1. 在 Dify 主页，点击 **创建应用** → **导入应用**
2. 选择上述 `hr_agent.yml` 文件
3. 导入后，应用名称为 `hr_agent`

### 步骤 8：修复导入后的模型引用

导入后，工作流中的 LLM 节点可能显示模型不可用（原配置引用 `langgenius/tongyi/tongyi` 供应商下的 `deepseek-v4-flash`）。

逐一检查每个 LLM 节点，将模型重新选择为你已配置的供应商下的模型：

- 如果用的是通义千问的 deepseek 模型 → 选 Tongyi 供应商
- 如果用的是 DeepSeek 原生 API → 选你配置的 DeepSeek 供应商

工作流中有 **6 个 LLM 节点**，按 type 区分：

| type | 功能 | LLM节点标题 | 需要选择的模型 |
|------|------|-------------|--------------|
| 1 | 生成 JD | `LLM` | deepseek-v4-flash (或 qwen-max) |
| 2 | 生成简历评价标准 | `LLM 2` | deepseek-v4-flash (或 qwen-max) |
| 3 | 简历评分 | `LLM 3` | deepseek-v4-flash (或 qwen-max) |
| 4 | 生成面试方案 | `LLM 4` | deepseek-v4-flash (或 qwen-max) |
| 5 | 根据文档生成试卷 | `LLM 5` | deepseek-v4-flash (或 qwen-max) |
| 6 | 试卷阅卷打分 | `LLM 6` | deepseek-v4-flash (或 qwen-max) |

### 步骤 9：测试工作流

1. 在 Dify 应用中点击 **运行** 或 **预览**
2. 在对话中输入测试内容，选择 type=1（生成JD）
3. 输入：`我需要招聘一名高级Python开发工程师，要求5年以上经验，熟悉FastAPI和PostgreSQL`
4. 确认能正常返回 JD 内容

依次测试 type 2-6。

---

## 第四阶段：获取 API Key 给主项目

### 步骤 10：发布应用并获取 API Key

1. 在 `hr_agent` 应用页面，点击 **发布**
2. 点击左侧菜单 **API 访问**
3. 复制 **API Key**（格式类似 `app-xxxxxxxxxxxxx`）
4. 获取 **API Base URL**（通常是 `http://localhost/v1`）

### 步骤 11：将 Dify 配置填入主项目

将以下配置告诉主项目执行者（或自行填入 `d:\hr_ai\.env`）：

```env
DIFY_BASE_URL=http://localhost/v1
DIFY_API_KEY=app-xxxxxxxxxxxxx    # 替换为步骤10获取的实际值
DIFY_USER_ID=hr-agent-user
```

---

## 验证清单

全部完成后，确认以下检查项：

- [ ] `docker ps` 显示 Dify 所有容器运行正常
- [ ] 浏览器 `http://localhost` 可访问 Dify 管理后台
- [ ] 模型供应商页面：Tongyi 显示为已配置状态（绿色勾）
- [ ] `hr_agent` 应用内 6 个 LLM 节点无红色报错
- [ ] 测试 type=1（生成JD）能正常返回结果
- [ ] API Key 已获取并记录

---

## 常见问题

**Q: 容器启动失败，端口冲突？**
A: 修改 `.env` 中的 `EXPOSE_NGINX_PORT` 为其他端口（如 8088）。

**Q: 导入 YAML 后工作流图形不显示？**
A: 检查 Dify 版本兼容性。原 YAML 版本为 `0.6.0`。如果新版 Dify 不兼容，尝试手动重建工作流（参考下方手动重建说明）。

**Q: Tongyi 供应商找不到 deepseek-v4-flash？**
A: Tongyi 供应商下的模型列表由阿里云控制。如果找不到，改用 DeepSeek 原生 API 供应商（步骤 6 配置的）。
