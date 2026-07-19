# API 接口协议

## 1. 文档目的

本文档定义 HR Agent 后端 API 的联调协议，包括通用请求约定、认证方式、分页规则、错误结构、核心接口参数、请求示例、响应示例、文件上传格式和 SSE 流式响应格式。

本文档面向前端开发、后端开发、测试、联调和上线验收人员。接口基础路径为：

```text
/api/v1
```

## 2. 通用约定

### 2.1 请求协议

| 项 | 约定 |
| --- | --- |
| 协议 | HTTP/HTTPS |
| 数据格式 | JSON，文件上传使用 `multipart/form-data` |
| 字符编码 | UTF-8 |
| 时间格式 | ISO 8601 字符串 |
| ID 格式 | UUID，少量考试分享场景可使用字符串 ID |
| 鉴权方式 | Bearer Token |

### 2.2 通用 Header

普通 JSON 请求：

```http
Content-Type: application/json
Authorization: Bearer <access_token>
```

文件上传请求：

```http
Content-Type: multipart/form-data
Authorization: Bearer <access_token>
```

流式请求：

```http
Accept: text/event-stream
Content-Type: application/json
Authorization: Bearer <access_token>
```

### 2.3 分页约定

列表接口统一建议支持以下查询参数，具体以接口实现为准：

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| page | int | 否 | 1 | 页码，从 1 开始 |
| size | int | 否 | 10 | 每页数量 |
| keyword | string | 否 | 空 | 搜索关键词 |
| status | string | 否 | 空 | 状态过滤 |

分页响应建议结构：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "size": 10,
  "pages": 0
}
```

### 2.4 通用错误结构

后端错误响应统一为：

```json
{
  "error": {
    "message": "验证失败",
    "type": "ValidationError",
    "details": {
      "errors": [
        {
          "field": "body -> title",
          "message": "Field required",
          "type": "missing"
        }
      ]
    }
  }
}
```

常见状态码：

| 状态码 | 含义 | 场景 |
| --- | --- | --- |
| 400 | 请求错误 | 外键无效、业务参数冲突 |
| 401 | 未认证 | Token 缺失、无效或过期 |
| 403 | 权限不足 | 普通用户访问管理接口 |
| 404 | 资源不存在 | 查询不存在的 JD、文档、试卷 |
| 409 | 资源冲突 | 用户名、邮箱、角色名重复 |
| 422 | 参数校验失败 | 必填字段缺失、字段格式错误 |
| 500 | 服务端错误 | 数据库、外部服务或程序异常 |

## 3. 认证接口

### 3.1 用户注册

```http
POST /api/v1/auth/register
```

权限：无需登录。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| username | string | 是 | 用户名，3-50 字符，唯一 |
| email | string | 是 | 邮箱，唯一 |
| password | string | 是 | 密码，至少 6 位 |
| full_name | string | 否 | 姓名 |
| phone | string | 否 | 手机号 |
| department | string | 否 | 部门 |
| position | string | 否 | 职位 |
| employee_id | string | 否 | 员工编号 |
| bio | string | 否 | 简介 |

请求示例：

```json
{
  "username": "hr_zhang",
  "email": "hr_zhang@example.com",
  "password": "test123",
  "full_name": "张三",
  "department": "人力资源部",
  "position": "HR 专员"
}
```

响应示例：

```json
{
  "id": "6fbbf4ff-6c2a-4db2-8c8a-7a7d6b0f2a01",
  "username": "hr_zhang",
  "email": "hr_zhang@example.com",
  "full_name": "张三",
  "phone": null,
  "department": "人力资源部",
  "position": "HR 专员",
  "employee_id": null,
  "role": "employee",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false,
  "avatar_url": null,
  "last_login": null,
  "created_at": "2026-06-09T10:00:00",
  "updated_at": "2026-06-09T10:00:00"
}
```

### 3.2 用户登录

```http
POST /api/v1/auth/login
```

权限：无需登录。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| email | string | 是 | 登录邮箱 |
| password | string | 是 | 密码 |

请求示例：

```json
{
  "email": "hr_zhang@example.com",
  "password": "test123"
}
```

响应示例：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 691200
}
```

### 3.3 获取当前用户

```http
GET /api/v1/auth/me
```

权限：已登录。

响应示例：

```json
{
  "id": "6fbbf4ff-6c2a-4db2-8c8a-7a7d6b0f2a01",
  "username": "hr_zhang",
  "email": "hr_zhang@example.com",
  "full_name": "张三",
  "role": "hr_specialist",
  "is_active": true,
  "is_superuser": false,
  "is_verified": true
}
```

## 4. 用户与角色接口

### 4.1 用户列表

```http
GET /api/v1/users/?page=1&size=10&keyword=hr
```

权限：超级管理员。

响应示例：

```json
[
  {
    "id": "6fbbf4ff-6c2a-4db2-8c8a-7a7d6b0f2a01",
    "username": "hr_zhang",
    "email": "hr_zhang@example.com",
    "full_name": "张三",
    "department": "人力资源部",
    "position": "HR 专员",
    "role": "hr_specialist",
    "is_superuser": false,
    "is_verified": true,
    "is_active": true,
    "roles": [
      {
        "id": "4c930674-c5f5-4ff0-a915-6c7f4f004f5b",
        "name": "HR 专员",
        "description": "招聘业务操作角色",
        "is_builtin": true,
        "created_at": "2026-06-09T10:00:00",
        "updated_at": "2026-06-09T10:00:00"
      }
    ]
  }
]
```

### 4.2 管理员创建用户

```http
POST /api/v1/users/admin/users
```

权限：超级管理员。

请求示例：

```json
{
  "username": "training_admin",
  "email": "training_admin@example.com",
  "password": "test123",
  "full_name": "李四",
  "department": "培训部",
  "position": "培训管理员",
  "role": "employee"
}
```

### 4.3 分配用户角色

```http
PUT /api/v1/users/admin/users/{user_id}/roles
```

权限：超级管理员。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| role_ids | UUID[] | 是 | 角色 ID 列表 |

请求示例：

```json
{
  "role_ids": [
    "4c930674-c5f5-4ff0-a915-6c7f4f004f5b"
  ]
}
```

### 4.4 角色管理接口

| 方法 | 路径 | 用途 | 权限 |
| --- | --- | --- | --- |
| GET | `/users/admin/roles` | 查询角色列表 | 超级管理员 |
| POST | `/users/admin/roles` | 创建角色 | 超级管理员 |
| DELETE | `/users/admin/roles/{role_id}` | 删除角色 | 超级管理员 |
| GET | `/users/me/roles` | 查询当前用户角色 | 已登录 |

创建角色请求：

```json
{
  "name": "HR 负责人",
  "description": "查看招聘数据和候选人评估结果",
  "is_builtin": false
}
```

## 5. HR Agent 接口

### 5.1 Agent 普通对话

```http
POST /api/v1/agent/chat
```

权限：已登录。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| message | string | 是 | 用户自然语言需求 |
| conversation_id | string | 否 | 对话 ID |
| auto_execute | boolean | 否 | 是否自动执行低风险生成类工具，默认 true |
| confirmed_requirements | object | 否 | 用户确认后的结构化招聘需求 |
| attachments | object[] | 否 | 附件元信息 |

请求示例：

```json
{
  "message": "帮我生成一个上海前端工程师 JD，要求 3 年经验，熟悉 Vue 3 和 Element Plus",
  "auto_execute": true,
  "attachments": []
}
```

响应示例：

```json
{
  "message": "我已识别为 JD 生成任务，并为你准备了生成结果。",
  "intent": "jd",
  "route": "/recruitment/jd-generator",
  "steps": [
    {
      "id": "plan",
      "title": "选择执行工具",
      "status": "completed",
      "detail": "选择工具：生成岗位 JD，并自动生成简历评分标准。",
      "tool": "generate_jd"
    }
  ],
  "artifacts": [
    {
      "type": "job_description",
      "title": "前端工程师 JD",
      "content": "岗位职责：...",
      "metadata": {
        "route": "/recruitment/jd-generator"
      }
    }
  ],
  "suggestions": [
    "保存 JD",
    "继续生成评分标准",
    "进入简历筛选"
  ],
  "requires_confirmation": false,
  "missing_fields": []
}
```

### 5.2 Agent 流式对话

```http
POST /api/v1/agent/chat/stream
```

权限：已登录。

请求体与 `/agent/chat` 相同。

响应类型：

```http
Content-Type: text/event-stream
```

SSE 事件格式建议：

```text
event: step
data: {"id":"plan","title":"选择执行工具","status":"completed"}

event: delta
data: {"content":"正在生成 JD..."}

event: artifact
data: {"type":"job_description","title":"前端工程师 JD","content":"..."}

event: done
data: {"message":"生成完成"}
```

前端处理要求：

- 支持连接中断提示。
- 支持增量内容拼接。
- `done` 后结束加载状态。
- `error` 事件或连接异常时允许用户重试。

### 5.3 Agent 专用流式接口

| 方法 | 路径 | 用途 | 权限 |
| --- | --- | --- | --- |
| POST | `/agent/stream` | 兼容流式接口 | 已登录 |
| POST | `/agent/resume-screen/stream` | 简历筛选流式接口 | 已登录 |
| POST | `/agent/interview-plan/stream` | 面试方案流式接口 | 已登录 |
| POST | `/agent/exam/stream` | 试卷生成流式接口 | 已登录 |
| POST | `/agent/exam/document-stream` | 基于文档试卷流式接口 | 已登录 |

## 6. HR 工作流接口

### 6.1 解析招聘需求

```http
POST /api/v1/hr-workflows/parse-requirements
```

权限：已登录。

请求示例：

```json
{
  "requirements": "招聘一个上海前端工程师，3 年经验，本科，熟悉 Vue 3，薪资 20-30K"
}
```

响应示例：

```json
{
  "position_title": "前端工程师",
  "location": "上海",
  "experience_level": "3 年",
  "education": "本科",
  "salary_range": "20-30K",
  "skills": ["Vue 3"],
  "missing_fields": []
}
```

### 6.2 生成 JD

```http
POST /api/v1/hr-workflows/generate-jd
```

权限：已登录。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| requirements | string | 是 | 岗位需求描述 |
| position_title | string | 否 | 岗位名称 |
| department | string | 否 | 部门 |
| experience_level | string | 否 | 经验要求 |
| conversation_id | string | 否 | 对话 ID |
| stream | boolean | 否 | 是否流式输出 |

请求示例：

```json
{
  "requirements": "负责企业后台前端开发，熟悉 Vue 3、Element Plus、接口联调",
  "position_title": "前端工程师",
  "department": "技术部",
  "experience_level": "3 年",
  "stream": true
}
```

响应示例：

```json
{
  "title": "前端工程师",
  "content": "岗位职责：\n1. 负责企业后台前端开发...\n任职要求：\n1. 熟悉 Vue 3...",
  "requirements": "负责企业后台前端开发，熟悉 Vue 3、Element Plus、接口联调",
  "meta_data": {
    "source": "dify",
    "workflow_type": "jd_generation"
  }
}
```

### 6.3 生成评分标准

```http
POST /api/v1/hr-workflows/generate-scoring-criteria
```

权限：已登录。

请求示例：

```json
{
  "jd_content": "岗位职责：负责 Vue 3 企业后台开发...",
  "job_title": "前端工程师",
  "requirements": {
    "skills": ["Vue 3", "Element Plus", "Axios"],
    "experience": "3 年"
  },
  "stream": true
}
```

响应示例：

```json
{
  "title": "前端工程师简历评分标准",
  "total_score": "100",
  "content": "评分维度包括技术能力、项目经验、岗位匹配度...",
  "scoring_dimensions": [
    {
      "name": "前端技术能力",
      "max_score": 40,
      "description": "Vue 3、组件化、工程化、接口联调能力"
    },
    {
      "name": "项目经验",
      "max_score": 30,
      "description": "企业后台、复杂表单、权限系统等项目经验"
    }
  ]
}
```

### 6.4 HR 工作流接口汇总

| 方法 | 路径 | 用途 | 权限 |
| --- | --- | --- | --- |
| POST | `/hr-workflows/parse-requirements` | 解析招聘需求 | 已登录 |
| POST | `/hr-workflows/generate-jd` | 生成 JD | 已登录 |
| POST | `/hr-workflows/generate-scoring-criteria` | 生成评分标准 | 已登录 |
| POST | `/hr-workflows/evaluate` | 简历评估 | 已登录 |
| POST | `/hr-workflows/generate-interview-plan-by-resume` | 基于简历生成面试方案 | 已登录 |
| POST | `/hr-workflows/papers/parse-intent` | 解析试卷需求 | 已登录 |
| POST | `/hr-workflows/papers/generate` | 生成试卷 | 已登录 |
| POST | `/hr-workflows/papers/submit` | 提交考试答案 | 可按业务免登录 |

## 7. JD 接口

### 7.1 保存 JD

```http
POST /api/v1/job-descriptions/save
```

权限：已登录。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| title | string | 是 | 岗位标题 |
| content | string | 是 | JD 正文 |
| department | string | 否 | 部门 |
| location | string | 否 | 工作地点 |
| salary_range | string | 否 | 薪资范围 |
| experience_level | string | 否 | 经验要求 |
| education | string | 否 | 学历要求 |
| job_type | string | 否 | 岗位类型 |
| skills | string[] | 否 | 技能列表 |
| requirements | string | 否 | 原始需求 |
| status | string | 否 | 状态，默认 draft |
| meta_data | object | 否 | 元数据 |
| conversation_id | string | 否 | 对话 ID |

请求示例：

```json
{
  "title": "前端工程师",
  "department": "技术部",
  "location": "上海",
  "salary_range": "20-30K",
  "experience_level": "3 年",
  "education": "本科",
  "job_type": "全职",
  "skills": ["Vue 3", "Element Plus", "Axios"],
  "content": "岗位职责：负责企业后台前端开发...",
  "requirements": "需要熟悉 Vue 3 和后台系统开发",
  "status": "draft"
}
```

响应示例：

```json
{
  "id": "9d8a3f90-2cd9-4e56-83d7-c8c3f98d2b71",
  "title": "前端工程师",
  "department": "技术部",
  "location": "上海",
  "salary_range": "20-30K",
  "experience_level": "3 年",
  "education": "本科",
  "job_type": "全职",
  "skills": ["Vue 3", "Element Plus", "Axios"],
  "content": "岗位职责：负责企业后台前端开发...",
  "requirements": "需要熟悉 Vue 3 和后台系统开发",
  "status": "draft",
  "meta_data": null,
  "conversation_id": null,
  "workflow_type": "jd_generation",
  "user_id": "6fbbf4ff-6c2a-4db2-8c8a-7a7d6b0f2a01",
  "created_at": "2026-06-09T10:00:00",
  "updated_at": "2026-06-09T10:00:00",
  "is_active": true
}
```

### 7.2 JD 列表

```http
GET /api/v1/job-descriptions/?page=1&size=10&keyword=前端
```

权限：已登录。

响应示例：

```json
{
  "items": [
    {
      "id": "9d8a3f90-2cd9-4e56-83d7-c8c3f98d2b71",
      "title": "前端工程师",
      "location": "上海",
      "status": "draft",
      "content": "岗位职责：...",
      "user_id": "6fbbf4ff-6c2a-4db2-8c8a-7a7d6b0f2a01",
      "created_at": "2026-06-09T10:00:00",
      "updated_at": "2026-06-09T10:00:00",
      "is_active": true
    }
  ],
  "total": 1,
  "page": 1,
  "size": 10,
  "pages": 1
}
```

### 7.3 JD 详情、更新与删除

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/job-descriptions/{jd_id}` | 获取 JD 详情 |
| PUT | `/job-descriptions/{jd_id}` | 更新 JD，字段均可选 |
| DELETE | `/job-descriptions/{jd_id}` | 删除 JD |

更新请求示例：

```json
{
  "salary_range": "25-35K",
  "status": "active"
}
```

## 8. 评分标准接口

### 8.1 保存评分标准

```http
POST /api/v1/scoring-criteria/save
```

权限：已登录。

请求示例：

```json
{
  "title": "前端工程师简历评分标准",
  "job_title": "前端工程师",
  "content": "总分 100 分，按技术能力、项目经验、沟通协作等维度评分。",
  "total_score": "100",
  "scoring_dimensions": [
    {
      "name": "前端技术能力",
      "max_score": 40,
      "description": "Vue 3、组件化、工程化能力"
    },
    {
      "name": "项目经验",
      "max_score": 30,
      "description": "企业后台、权限、复杂表单经验"
    }
  ],
  "job_description_id": "9d8a3f90-2cd9-4e56-83d7-c8c3f98d2b71",
  "status": "draft"
}
```

响应示例：

```json
{
  "id": "cebc6e60-e28c-41fa-9f08-40dc2f88f744",
  "title": "前端工程师简历评分标准",
  "job_title": "前端工程师",
  "content": "总分 100 分...",
  "criteria_data": null,
  "total_score": "100",
  "scoring_dimensions": [
    {
      "name": "前端技术能力",
      "max_score": 40,
      "description": "Vue 3、组件化、工程化能力"
    }
  ],
  "status": "draft",
  "job_description_id": "9d8a3f90-2cd9-4e56-83d7-c8c3f98d2b71",
  "workflow_type": "scoring_criteria_generation",
  "user_id": "6fbbf4ff-6c2a-4db2-8c8a-7a7d6b0f2a01",
  "created_at": "2026-06-09T10:00:00",
  "updated_at": "2026-06-09T10:00:00",
  "is_active": true
}
```

### 8.2 评分标准管理接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/scoring-criteria/` | 分页查询评分标准 |
| GET | `/scoring-criteria/{criteria_id}` | 获取评分标准详情 |
| PUT | `/scoring-criteria/{criteria_id}` | 更新评分标准 |
| DELETE | `/scoring-criteria/{criteria_id}` | 删除评分标准 |

## 9. 简历评估接口

### 9.1 自动评估简历

```http
POST /api/v1/resume-evaluation/evaluate-auto
```

权限：已登录。

请求类型：`multipart/form-data`。

表单字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | file | 是 | 简历文件，支持 PDF/DOC/DOCX |
| job_description_id | UUID | 是 | 关联 JD |
| scoring_criteria_id | UUID | 否 | 关联评分标准 |
| conversation_id | string | 否 | 对话 ID |

请求示例：

```bash
curl -X POST "http://localhost:8000/api/v1/resume-evaluation/evaluate-auto" \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@/path/to/resume.pdf" \
  -F "job_description_id=9d8a3f90-2cd9-4e56-83d7-c8c3f98d2b71" \
  -F "scoring_criteria_id=cebc6e60-e28c-41fa-9f08-40dc2f88f744"
```

响应示例：

```json
{
  "id": "8f8fa2c8-442c-4f6e-a2a4-e67a7ef3a110",
  "evaluation_metrics": [
    {
      "name": "前端技术能力",
      "score": 34,
      "max": 40,
      "reason": "候选人具备 Vue 3 和企业后台项目经验。"
    }
  ],
  "total_score": 86,
  "name": "王五",
  "position": "前端工程师",
  "workYears": 4,
  "education": "本科",
  "age": 28,
  "sex": "男",
  "school": "某某大学",
  "resume_content": "王五，4 年前端开发经验...",
  "original_filename": "王五-前端工程师.pdf",
  "created_at": "2026-06-09T10:00:00",
  "updated_at": "2026-06-09T10:00:00"
}
```

### 9.2 简历评估历史

```http
GET /api/v1/resume-evaluation/history?page=1&size=10
```

权限：已登录。

响应结构：

```json
{
  "items": [
    {
      "id": "8f8fa2c8-442c-4f6e-a2a4-e67a7ef3a110",
      "original_filename": "王五-前端工程师.pdf",
      "candidate_name": "王五",
      "candidate_position": "前端工程师",
      "total_score": 86,
      "job_description_id": "9d8a3f90-2cd9-4e56-83d7-c8c3f98d2b71",
      "created_at": "2026-06-09T10:00:00",
      "updated_at": "2026-06-09T10:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 10,
  "pages": 1
}
```

### 9.3 简历评估管理接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/resume-evaluation/supported-formats` | 查询支持格式 |
| GET | `/resume-evaluation/{evaluation_id}` | 获取评估详情 |
| PUT | `/resume-evaluation/{evaluation_id}/status` | 更新候选人状态 |
| DELETE | `/resume-evaluation/{evaluation_id}` | 删除评估 |
| POST | `/resume-evaluation/export-zip` | 批量导出 |

批量导出请求示例：

```json
{
  "resume_ids": [
    "8f8fa2c8-442c-4f6e-a2a4-e67a7ef3a110"
  ]
}
```

## 10. 面试方案接口

### 10.1 保存生成的面试方案

```http
POST /api/v1/interview-plans/save-generated
```

权限：已登录。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| content | string | 是 | 面试方案内容 |
| candidate_name | string | 否 | 候选人姓名 |
| candidate_position | string | 否 | 应聘岗位 |

请求示例：

```json
{
  "candidate_name": "王五",
  "candidate_position": "前端工程师",
  "content": "一、面试目标...\n二、核心问题...\n三、评分建议..."
}
```

响应示例：

```json
{
  "id": "60d41d78-1f33-4bda-b09d-344f983cad7b",
  "candidate_name": "王五",
  "candidate_position": "前端工程师",
  "content": "一、面试目标...",
  "resume_evaluation_id": "8f8fa2c8-442c-4f6e-a2a4-e67a7ef3a110",
  "user_id": "6fbbf4ff-6c2a-4db2-8c8a-7a7d6b0f2a01",
  "created_at": "2026-06-09T10:00:00",
  "updated_at": "2026-06-09T10:00:00"
}
```

### 10.2 面试方案管理接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/interview-plans/` | 分页查询面试方案 |
| GET | `/interview-plans/{plan_id}` | 获取方案详情 |
| PUT | `/interview-plans/{plan_id}` | 更新方案 |
| DELETE | `/interview-plans/{plan_id}` | 删除方案 |

## 11. 文档与知识库接口

### 11.1 上传文档

```http
POST /api/v1/documents/upload
```

权限：已登录。

请求类型：`multipart/form-data`。

表单字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | file | 是 | 文档文件 |
| knowledge_base_id | UUID | 否 | 归属知识库 |
| category | string | 否 | 分类 |
| tags | string[] | 否 | 标签 |

请求示例：

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@/path/to/hr-policy.pdf" \
  -F "category=HR制度"
```

响应示例：

```json
{
  "id": "34af92e7-2c97-464c-9b54-7e7b9cf34a15",
  "filename": "hr-policy.pdf",
  "category": "HR制度",
  "tags": null,
  "knowledge_base_id": null,
  "file_path": "uploads/hr-policy.pdf",
  "file_size": 204800,
  "file_hash": "ab12cd34",
  "mime_type": "application/pdf",
  "extracted_content": null,
  "created_at": "2026-06-09T10:00:00",
  "updated_at": "2026-06-09T10:00:00"
}
```

### 11.2 处理文档

```http
POST /api/v1/documents/{document_id}/process
```

权限：已登录。

响应示例：

```json
{
  "id": "34af92e7-2c97-464c-9b54-7e7b9cf34a15",
  "filename": "hr-policy.pdf",
  "extracted_content": "第一章 总则...",
  "updated_at": "2026-06-09T10:05:00"
}
```

### 11.3 文档管理接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/documents/` | 查询文档列表 |
| GET | `/documents/{document_id}` | 查询文档详情 |
| GET | `/documents/{document_id}/chunks` | 查询文档切片 |
| DELETE | `/documents/{document_id}` | 删除文档 |

### 11.4 创建知识库

```http
POST /api/v1/knowledge-base/
```

权限：已登录。

请求示例：

```json
{
  "name": "HR 制度知识库",
  "description": "用于员工制度问答",
  "is_public": false,
  "is_searchable": true,
  "category": "HR",
  "tags": ["制度", "员工手册"]
}
```

响应示例：

```json
{
  "id": "d32af56c-5539-4970-9875-1edb2f34eada",
  "name": "HR 制度知识库",
  "description": "用于员工制度问答",
  "is_public": false,
  "is_searchable": true,
  "category": "HR",
  "tags": ["制度", "员工手册"],
  "document_count": 0,
  "created_at": "2026-06-09T10:00:00",
  "updated_at": "2026-06-09T10:00:00"
}
```

### 11.5 知识助手问答

```http
POST /api/v1/knowledge-assistant/ask
```

权限：已登录。

请求示例：

```json
{
  "question": "员工年假规则是什么？",
  "knowledge_base_id": "d32af56c-5539-4970-9875-1edb2f34eada",
  "conversation_id": null
}
```

响应示例：

```json
{
  "answer": "根据已上传制度文档，员工年假规则为...",
  "sources": [
    {
      "document_id": "34af92e7-2c97-464c-9b54-7e7b9cf34a15",
      "filename": "hr-policy.pdf",
      "content": "年假规则相关片段...",
      "score": 0.86
    }
  ],
  "confidence": 0.86
}
```

### 11.6 知识库管理接口

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/knowledge-base/` | 知识库列表 | 已登录 |
| PUT | `/knowledge-base/{kb_id}` | 更新知识库 | 超级管理员 |
| DELETE | `/knowledge-base/{kb_id}` | 删除知识库 | 超级管理员 |
| GET | `/knowledge-assistant/config` | 获取知识助手配置 | 已登录 |
| GET | `/knowledge-assistant/documents` | 知识助手文档列表 | 已登录 |
| POST | `/knowledge-assistant/auto-select-kb` | 自动选择知识库 | 已登录 |

## 12. 试卷与考试接口

### 12.1 创建/保存试卷

```http
POST /api/v1/exam-management/papers
```

权限：已登录。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| title | string | 是 | 试卷标题 |
| subject | string | 是 | 科目 |
| description | string | 否 | 描述 |
| difficulty | string | 否 | 难度 |
| duration | int | 否 | 时长，分钟 |
| total_score | int | 是 | 总分 |
| question_types | string[] | 否 | 题型 |
| question_counts | object | 否 | 各题型数量 |
| knowledge_files | object[] | 否 | 参考资料 |
| special_requirements | string | 否 | 特殊要求 |
| content | string | 否 | 试卷正文 |
| questions | object[] | 否 | 题目列表 |

请求示例：

```json
{
  "title": "HR 制度培训考试",
  "subject": "HR 制度",
  "difficulty": "中等",
  "duration": 60,
  "total_score": 100,
  "question_types": ["single_choice", "multiple_choice", "true_false"],
  "question_counts": {
    "single_choice": 5,
    "multiple_choice": 3,
    "true_false": 2
  },
  "content": "一、单选题..."
}
```

### 12.2 生成试卷

```http
POST /api/v1/hr-workflows/papers/generate
```

权限：已登录。

请求示例：

```json
{
  "title": "HR 制度培训考试",
  "subject": "HR 制度",
  "difficulty": "中等",
  "duration": 60,
  "total_score": 100,
  "question_types": ["single_choice", "multiple_choice", "true_false"],
  "question_counts": {
    "single_choice": 5,
    "multiple_choice": 3,
    "true_false": 2
  },
  "knowledge_files": [
    {
      "document_id": "34af92e7-2c97-464c-9b54-7e7b9cf34a15",
      "filename": "hr-policy.pdf"
    }
  ],
  "special_requirements": "题目应覆盖年假、考勤、请假流程",
  "stream": true
}
```

响应示例：

```json
{
  "title": "HR 制度培训考试",
  "content": "一、单选题\n1. 员工年假规则...",
  "questions": [
    {
      "id": "q1",
      "type": "single_choice",
      "question": "员工年假规则主要依据什么？",
      "options": ["A. 制度文档", "B. 个人习惯"],
      "answer": "A",
      "score": 10,
      "explanation": "依据 HR 制度文档。"
    }
  ]
}
```

### 12.3 考试提交

```http
POST /api/v1/hr-workflows/papers/submit
```

权限：试点默认允许分享页免登录提交，管理端查看结果需登录。

请求示例：

```json
{
  "exam_id": "exam-20260609-001",
  "student_name": "赵六",
  "department": "销售部",
  "answers": {
    "q1": "A",
    "q2": ["A", "C"]
  },
  "exam_content": "一、单选题..."
}
```

响应示例：

```json
{
  "result_id": "83d2d570-02e7-4fc1-9305-7f3613488139",
  "exam_id": "exam-20260609-001",
  "student_name": "赵六",
  "score": 85,
  "submitted_at": "2026-06-09T11:00:00"
}
```

### 12.4 考试管理接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/exam-management/papers` | 试卷列表 |
| GET | `/exam-management/papers/{paper_id}` | 试卷详情 |
| PUT | `/exam-management/papers/{paper_id}` | 更新试卷 |
| DELETE | `/exam-management/papers/{paper_id}` | 删除试卷 |
| GET | `/exam-management/papers/{paper_id}/share` | 获取分享链接 |
| GET | `/exam-management/exam-results` | 考试结果列表 |
| GET | `/exam-management/exam-results/{result_id}` | 考试结果详情 |
| GET | `/exam-management/exam-results/{result_id}/export` | 导出考试结果 |

## 13. 邮箱配置接口

### 13.1 创建邮箱配置

```http
POST /api/v1/email-configs/
```

权限：超级管理员。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| name | string | 是 | 配置名称 |
| email | string | 是 | 邮箱地址 |
| password | string | 是 | 邮箱密码或授权码 |
| imap_server | string | 是 | IMAP 服务器 |
| imap_port | int | 否 | 默认 993 |
| imap_ssl | boolean | 否 | 默认 true |
| smtp_server | string | 否 | SMTP 服务器 |
| smtp_port | int | 否 | 默认 587 |
| smtp_ssl | boolean | 否 | 默认 true |
| fetch_interval | int | 否 | 抓取间隔，分钟 |
| auto_fetch | boolean | 否 | 是否自动抓取 |
| subject_keywords | string | 否 | 主题过滤关键词 |

请求示例：

```json
{
  "name": "招聘邮箱",
  "email": "recruit@example.com",
  "password": "mail-auth-code",
  "imap_server": "imap.example.com",
  "imap_port": 993,
  "imap_ssl": true,
  "smtp_server": "smtp.example.com",
  "smtp_port": 587,
  "smtp_ssl": true,
  "fetch_interval": 30,
  "auto_fetch": false,
  "subject_keywords": "简历,投递"
}
```

响应示例：

```json
{
  "id": "f3d85f6a-af94-4825-a9cc-bc1e7cb12401",
  "name": "招聘邮箱",
  "email": "recruit@example.com",
  "imap_server": "imap.example.com",
  "imap_port": 993,
  "imap_ssl": true,
  "smtp_server": "smtp.example.com",
  "smtp_port": 587,
  "smtp_ssl": true,
  "fetch_interval": 30,
  "auto_fetch": false,
  "status": "active",
  "subject_keywords": "简历,投递",
  "connection_status": "unknown",
  "last_fetch_at": null,
  "created_at": "2026-06-09T10:00:00",
  "updated_at": "2026-06-09T10:00:00"
}
```

### 13.2 邮箱连接测试

```http
POST /api/v1/email-configs/{config_id}/test
```

权限：超级管理员。

请求示例：

```json
{
  "imap_server": "imap.example.com",
  "imap_port": 993,
  "imap_ssl": true,
  "email": "recruit@example.com",
  "password": "mail-auth-code"
}
```

响应示例：

```json
{
  "success": true,
  "message": "邮箱连接测试成功"
}
```

### 13.3 邮箱配置管理接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/email-configs/` | 邮箱配置列表 |
| GET | `/email-configs/{config_id}` | 邮箱配置详情 |
| PUT | `/email-configs/{config_id}` | 更新邮箱配置 |
| DELETE | `/email-configs/{config_id}` | 删除邮箱配置 |
| POST | `/email-configs/{config_id}/fetch` | 手动抓取邮件 |
| GET | `/email-configs/{config_id}/logs` | 抓取日志 |
| GET | `/email-configs/{config_id}/latest-email` | 最近邮件 |

## 14. 统计接口

| 方法 | 路径 | 用途 | 权限 |
| --- | --- | --- | --- |
| GET | `/stats/dashboard` | 工作台统计 | 已登录 |
| GET | `/stats/recruitment-trend` | 招聘趋势 | 已登录 |
| GET | `/stats/training-completion` | 培训完成情况 | 已登录 |
| GET | `/stats/recent-activities` | 近期活动 | 已登录 |

工作台统计响应示例：

```json
{
  "job_descriptions": 12,
  "resume_evaluations": 86,
  "interview_plans": 20,
  "exams": 4,
  "documents": 18
}
```

## 15. 联调检查清单

| 检查项 | 标准 |
| --- | --- |
| 鉴权 Header | 除注册、登录、考试分享提交外，接口应携带 Bearer Token |
| 401 处理 | 前端清理登录状态并跳转登录 |
| 403 处理 | 前端提示权限不足 |
| 422 处理 | 展示字段校验错误 |
| 分页接口 | 前端正确处理 `items/total/page/size/pages` |
| 文件上传 | 使用 `multipart/form-data`，字段名与接口一致 |
| SSE | 前端支持增量内容、done、error 和连接中断 |
| 高风险操作 | 删除、邮件发送必须二次确认 |
| 敏感字段 | 密码、邮箱授权码不应在前端明文回显 |
