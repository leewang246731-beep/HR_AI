# 通知功能实施计划

> **For agentic workers:** Use superpowers:executing-plans to implement.

**Goal:** 将硬编码的通知铃铛改为真实系统通知，显示各业务模块最近活动

**Architecture:** 后端 internal.py 跨表 UNION 查询 → stats API 返回活动列表 → 前端 popover 展示 + 未读计数

**Tech Stack:** FastAPI + PostgreSQL + Vue 3 + Element Plus

## Global Constraints
- 只做拓展，不改原有代码
- 后端只改 `internal.py` 的 `recent_activities_internal` 函数
- 前端只改 `MainLayout.vue` 的通知铃铛部分
- 数据源：jd_records, resume_evaluations, scoring_criteria, interview_plans, exam_results

---

### Task 1: 后端 - 真实活动数据查询

**Files:**
- Modify: `backend/app/api/v1/endpoints/internal.py` (recent_activities_internal 函数)

- [ ] **Step 1: 替换 recent_activities_internal 实现**

将原来的 `return {"activities": [], "total": 0}` 替换为跨 5 张表的 UNION 查询：

```python
@router.get("/stats/recent-activities")
async def recent_activities_internal(
    limit: int = Query(10),
    offset: int = Query(0),
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：最近活动（跨业务表查询）"""
    try:
        sql = """
        SELECT * FROM (
            SELECT id, title, 'jd' as type, created_at FROM jd_records WHERE is_active = true
            UNION ALL
            SELECT id, '简历评价' as title, 'resume' as type, created_at FROM resume_evaluations WHERE is_active = true
            UNION ALL
            SELECT id, title, 'scoring' as type, created_at FROM scoring_criteria WHERE is_active = true
            UNION ALL
            SELECT id, title, 'interview' as type, created_at FROM interview_plans WHERE is_active = true
            UNION ALL
            SELECT id, title, 'exam' as type, created_at FROM exam_results WHERE is_active = true
        ) AS activities
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """
        result = await db.execute(__import__('sqlalchemy').text(sql), {"limit": limit, "offset": offset})
        rows = result.fetchall()
        items = []
        for row in rows:
            item = dict(zip(["id", "title", "type", "created_at"], row))
            for k, v in item.items():
                if isinstance(v, UUID):
                    item[k] = str(v)
            items.append(item)

        count_sql = """
        SELECT COUNT(*) FROM (
            SELECT id FROM jd_records WHERE is_active = true
            UNION ALL SELECT id FROM resume_evaluations WHERE is_active = true
            UNION ALL SELECT id FROM scoring_criteria WHERE is_active = true
            UNION ALL SELECT id FROM interview_plans WHERE is_active = true
            UNION ALL SELECT id FROM exam_results WHERE is_active = true
        ) AS total_count
        """
        count_result = await db.execute(__import__('sqlalchemy').text(count_sql))
        total = count_result.scalar()

        return {"items": items, "total": total, "page": offset // limit + 1 if limit else 1, "size": limit}
    except Exception as e:
        logger.error(f"获取活动列表失败: {e}")
        return {"items": [], "total": 0, "page": 1, "size": limit}
```

- [ ] **Step 2: 重启后端并验证**

```bash
touch backend/app/api/v1/endpoints/internal.py
sleep 5
curl -s -H "X-API-Key: your-api-key" "http://localhost:8000/api/v1/internal/stats/recent-activities?limit=5"
```

预期：返回 items 数组，total 为实际记录数

- [ ] **Step 3: 验证前端 API 也正常**

```bash
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stats/recent-activities?limit=5"
```

预期：同上

---

### Task 2: 前端 - 通知下拉面板

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue` (第 82-88 行通知铃铛部分 + script)

- [ ] **Step 1: 替换通知铃铛模板**

将：
```html
<el-badge :value="12" class="notification-badge">
  <el-button type="text" class="header-btn">
    <el-icon><Bell /></el-icon>
  </el-button>
</el-badge>
```
替换为：
```html
<el-popover placement="bottom-end" :width="360" trigger="click" @show="fetchNotifications">
  <template #reference>
    <el-badge :value="unreadCount" :hidden="unreadCount === 0" class="notification-badge">
      <el-button type="text" class="header-btn">
        <el-icon><Bell /></el-icon>
      </el-button>
    </el-badge>
  </template>
  <div class="notification-panel">
    <div class="notification-header">
      <span>通知消息</span>
      <span class="notification-count">共 {{ notifications.length }} 条</span>
    </div>
    <div class="notification-list" v-if="notifications.length > 0">
      <div class="notification-item" v-for="item in notifications" :key="item.id" @click="goToActivity(item)">
        <el-icon :size="20" class="notif-icon"><component :is="getActivityIcon(item.type)" /></el-icon>
        <div class="notif-content">
          <p class="notif-title">{{ item.title || item.type }}</p>
          <p class="notif-time">{{ formatTime(item.created_at) }}</p>
        </div>
        <el-tag size="small" :type="getActivityTagType(item.type)">{{ getActivityLabel(item.type) }}</el-tag>
      </div>
    </div>
    <div class="notification-empty" v-else>
      <el-empty description="暂无消息" :image-size="80" />
    </div>
  </div>
</el-popover>
```

- [ ] **Step 2: 添加 script 逻辑**

在 `<script setup>` 中添加：
```js
import { Document, EditPen, Tickets, DataAnalysis, List } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

const notifications = ref([])
const unreadCount = ref(0)

const fetchNotifications = async () => {
  try {
    const res = await fetch('/api/v1/stats/recent-activities?limit=10', {
      headers: { Authorization: `Bearer ${authStore.token}` }
    })
    const data = await res.json()
    notifications.value = data.items || []
    unreadCount.value = data.total || 0
  } catch (e) {
    console.error('获取通知失败', e)
  }
}

const getActivityIcon = (type) => {
  const icons = { jd: Document, resume: EditPen, scoring: DataAnalysis, interview: Tickets, exam: List }
  return icons[type] || Document
}

const getActivityLabel = (type) => {
  const labels = { jd: 'JD生成', resume: '简历评价', scoring: '评分标准', interview: '面试方案', exam: '考试' }
  return labels[type] || type
}

const getActivityTagType = (type) => {
  const types = { jd: 'primary', resume: 'success', scoring: 'warning', interview: 'danger', exam: 'info' }
  return types[type] || ''
}

const formatTime = (time) => {
  if (!time) return ''
  return dayjs(time).format('MM-DD HH:mm')
}

const goToActivity = (item) => {
  // 按类型跳转到对应页面
  const routes = { jd: '/recruitment/jd-generator', resume: '/recruitment/resume-screening', scoring: '/recruitment/jd-generator', interview: '/recruitment/smart-interview', exam: '/training/exam-management' }
  const path = routes[item.type]
  if (path) router.push(path)
}

// 初始加载
onMounted(() => fetchNotifications())
```

- [ ] **Step 3: 添加样式**

在 `<style>` 末尾追加：
```scss
.notification-panel {
  .notification-header {
    display: flex; justify-content: space-between; align-items: center;
    padding-bottom: 12px; border-bottom: 1px solid #ebeef5; margin-bottom: 8px;
    font-weight: 600; font-size: 15px;
    
    .notification-count {
      font-size: 12px; color: #909399; font-weight: normal;
    }
  }
  
  .notification-list {
    max-height: 360px; overflow-y: auto;
    
    .notification-item {
      display: flex; align-items: center; gap: 12px; padding: 10px 8px;
      border-radius: 8px; cursor: pointer; transition: background 0.2s;
      
      &:hover { background: #f5f7fa; }
      
      .notif-icon { color: #409eff; flex-shrink: 0; }
      
      .notif-content {
        flex: 1; min-width: 0;
        .notif-title { margin: 0; font-size: 13px; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .notif-time { margin: 4px 0 0; font-size: 11px; color: #c0c4cc; }
      }
    }
  }
  
  .notification-empty { padding: 20px 0; }
}
```

- [ ] **Step 4: 验证前端**

打开 http://localhost:3000，点击铃铛图标，确认下拉面板展开

---
