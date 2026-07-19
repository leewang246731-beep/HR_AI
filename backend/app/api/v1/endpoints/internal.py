"""
内部服务端点 - 供 RemoteServiceClient 调用
这些端点使用 X-API-Key 认证而非 JWT，避免自调用死循环
"""
import logging
from typing import Any, Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from uuid import UUID

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


async def verify_api_key(x_api_key: str = Header(None)) -> None:
    """验证 X-API-Key 内部服务认证"""
    if x_api_key != settings.HR_SERVICE_APIKEY:
        raise HTTPException(status_code=403, detail="无效的API密钥")


# ===== JD 管理 =====

@router.get("/job-descriptions/")
async def list_jd_internal(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：获取JD列表"""
    try:
        from app.models.base import BaseModel
        from sqlalchemy import Table, MetaData, Column, String, Text, DateTime, Boolean
        # 使用原始SQL进行CRUD，因为没有独立的JD model
        offset = (page - 1) * size
        where_clause = ""
        params = {}
        if current_user_id:
            where_clause = "WHERE created_by = :user_id"
            params["user_id"] = str(current_user_id)
        if status_filter:
            where_clause += " AND status = :status" if where_clause else "WHERE status = :status"
            params["status"] = status_filter

        count_sql = f"SELECT COUNT(*) FROM jd_records {where_clause}"
        count_result = await db.execute(
            __import__('sqlalchemy').text(count_sql), params
        )
        total = count_result.scalar()

        data_sql = f"SELECT * FROM jd_records {where_clause} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = size
        params["offset"] = offset
        result = await db.execute(__import__('sqlalchemy').text(data_sql), params)
        rows = result.fetchall()
        columns = result.keys()
        items = [dict(zip(columns, row)) for row in rows]

        for item in items:
            for key, value in item.items():
                if isinstance(value, UUID):
                    item[key] = str(value)

        return {"items": items, "total": total, "page": page, "size": size, "pages": max(1, (total + size - 1) // size)}
    except Exception as e:
        return {"items": [], "total": 0, "page": page, "size": size, "pages": 0}


@router.post("/job-descriptions/save")
async def save_jd_internal(
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：保存JD"""
    import uuid as _uuid
    from datetime import datetime, timezone
    jd_id = data.get("id") or str(_uuid.uuid4())
    now = datetime.now(timezone.utc)
    user_id = data.get("created_by") or "system"

    sql = """
    INSERT INTO jd_records (id, title, department, position_title, requirements, content,
        status, created_by, created_at, updated_at, is_active)
    VALUES (:id, :title, :department, :position_title, :requirements, :content,
        :status, :created_by, :created_at, :updated_at, :is_active)
    ON CONFLICT (id) DO UPDATE SET
        title = EXCLUDED.title, department = EXCLUDED.department,
        position_title = EXCLUDED.position_title, requirements = EXCLUDED.requirements,
        content = EXCLUDED.content, status = EXCLUDED.status, updated_at = EXCLUDED.updated_at
    """
    await db.execute(__import__('sqlalchemy').text(sql), {
        "id": jd_id,
        "title": data.get("title") or data.get("position_title", ""),
        "department": data.get("department", ""),
        "position_title": data.get("position_title", ""),
        "requirements": data.get("requirements", ""),
        "content": data.get("content", ""),
        "status": data.get("status", "draft"),
        "created_by": str(user_id),
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    })
    await db.commit()

    return {"data": {**data, "id": jd_id}}


@router.get("/job-descriptions/{jd_id}")
async def get_jd_internal(
    jd_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：获取单个JD"""
    result = await db.execute(
        __import__('sqlalchemy').text("SELECT * FROM jd_records WHERE id = :id"),
        {"id": jd_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="JD未找到")
    columns = result.keys()
    item = dict(zip(columns, row))
    for key, value in item.items():
        if isinstance(value, UUID):
            item[key] = str(value)
    return item


@router.put("/job-descriptions/{jd_id}")
async def update_jd_internal(
    jd_id: str,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：更新JD"""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    await db.execute(__import__('sqlalchemy').text("""
        UPDATE jd_records SET title=:title, requirements=:requirements,
        content=:content, status=:status, department=:department,
        position_title=:position_title, updated_at=:updated_at
        WHERE id=:id
    """), {
        "id": jd_id,
        "title": data.get("title", ""),
        "requirements": data.get("requirements", ""),
        "content": data.get("content", ""),
        "status": data.get("status", "draft"),
        "department": data.get("department", ""),
        "position_title": data.get("position_title", ""),
        "updated_at": now,
    })
    await db.commit()
    return {"data": {**data, "id": jd_id}}


@router.delete("/job-descriptions/{jd_id}")
async def delete_jd_internal(
    jd_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：删除JD"""
    await db.execute(
        __import__('sqlalchemy').text("DELETE FROM jd_records WHERE id = :id"),
        {"id": jd_id}
    )
    await db.commit()
    return {"message": "删除成功"}


# ===== 评分标准管理 =====

@router.get("/scoring-criteria/")
async def list_scoring_internal(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    job_description_id: Optional[str] = Query(None),
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：获取评分标准列表"""
    try:
        offset = (page - 1) * size
        conditions = []
        params = {}
        if current_user_id:
            conditions.append("created_by = :user_id")
            params["user_id"] = str(current_user_id)
        if job_description_id:
            conditions.append("job_description_id = :jd_id")
            params["jd_id"] = job_description_id

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        params["limit"] = size
        params["offset"] = offset

        count_result = await db.execute(
            __import__('sqlalchemy').text(f"SELECT COUNT(*) FROM scoring_criteria {where_clause}"),
            {k: v for k, v in params.items() if k != "limit" and k != "offset"}
        )
        total = count_result.scalar()

        result = await db.execute(
            __import__('sqlalchemy').text(f"SELECT * FROM scoring_criteria {where_clause} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            params
        )
        rows = result.fetchall()
        columns = result.keys()
        items = [dict(zip(columns, row)) for row in rows]
        for item in items:
            for key, value in item.items():
                if isinstance(value, UUID):
                    item[key] = str(value)
        return {"items": items, "total": total, "page": page, "size": size, "pages": max(1, (total + size - 1) // size)}
    except Exception:
        return {"items": [], "total": 0, "page": page, "size": size, "pages": 0}


@router.post("/scoring-criteria/save")
async def save_scoring_internal(
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：保存评分标准"""
    import uuid as _uuid
    from datetime import datetime, timezone
    sc_id = data.get("id") or str(_uuid.uuid4())
    now = datetime.now(timezone.utc)

    await db.execute(__import__('sqlalchemy').text("""
        INSERT INTO scoring_criteria (id, title, job_description_id, criteria_content,
            status, created_by, created_at, updated_at, is_active)
        VALUES (:id, :title, :jd_id, :content, :status, :created_by, :created_at, :updated_at, :is_active)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title, criteria_content = EXCLUDED.criteria_content,
            status = EXCLUDED.status, updated_at = EXCLUDED.updated_at
    """), {
        "id": sc_id,
        "title": data.get("title", ""),
        "jd_id": data.get("job_description_id", ""),
        "content": data.get("criteria_content", data.get("content", "")),
        "status": data.get("status", "active"),
        "created_by": str(data.get("created_by", "system")),
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    })
    await db.commit()
    return {"data": {**data, "id": sc_id}}


@router.get("/scoring-criteria/{sc_id}")
async def get_scoring_internal(
    sc_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：获取单个评分标准"""
    result = await db.execute(
        __import__('sqlalchemy').text("SELECT * FROM scoring_criteria WHERE id = :id"),
        {"id": sc_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404)
    columns = result.keys()
    item = dict(zip(columns, row))
    for key, value in item.items():
        if isinstance(value, UUID):
            item[key] = str(value)
    return item


@router.put("/scoring-criteria/{sc_id}")
async def update_scoring_internal(
    sc_id: str,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：更新评分标准"""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    await db.execute(__import__('sqlalchemy').text("""
        UPDATE scoring_criteria SET title=:title, criteria_content=:content,
        status=:status, updated_at=:updated_at
        WHERE id=:id
    """), {
        "id": sc_id,
        "title": data.get("title", ""),
        "content": data.get("criteria_content", data.get("content", "")),
        "status": data.get("status", "active"),
        "updated_at": now,
    })
    await db.commit()
    return {"data": {**data, "id": sc_id}}


@router.delete("/scoring-criteria/{sc_id}")
async def delete_scoring_internal(
    sc_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：删除评分标准"""
    await db.execute(
        __import__('sqlalchemy').text("DELETE FROM scoring_criteria WHERE id = :id"),
        {"id": sc_id}
    )
    await db.commit()
    return {"message": "删除成功"}


# ===== 统计端点 =====

@router.get("/stats/dashboard")
async def dashboard_stats_internal(
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：仪表板统计"""
    return {
        "recruitment": {"total": 0, "change": 0},
        "training": {"total": 0, "change": 0},
        "interview": {"total": 0, "change": 0},
        "assistant": {"total": 0, "change": 0}
    }


@router.get("/stats/recruitment-trend")
async def recruitment_trend_internal(
    days: int = Query(30),
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：招聘趋势"""
    return {"data": []}


@router.get("/stats/training-completion")
async def training_completion_internal(
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：培训完成统计"""
    return {"data": []}


@router.get("/stats/recent-activities")
async def recent_activities_internal(
    limit: int = Query(10),
    offset: int = Query(0),
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：最近活动（跨5张业务表UNION查询）"""
    try:
        sql = """
        SELECT * FROM (
            SELECT id::text, COALESCE(title, position_title, '未命名JD') as title, 'jd' as type, created_at FROM jd_records WHERE is_active = true
            UNION ALL
            SELECT id::text, COALESCE(candidate_name, '简历评价') as title, 'resume' as type, created_at FROM resume_evaluations WHERE is_active = true
            UNION ALL
            SELECT id::text, COALESCE(title, '评分标准') as title, 'scoring' as type, created_at FROM scoring_criteria WHERE is_active = true
            UNION ALL
            SELECT id::text, COALESCE(title, '面试方案') as title, 'interview' as type, created_at FROM interview_plans WHERE is_active = true
            UNION ALL
            SELECT id::text, COALESCE(exam_name, '考试结果') as title, 'exam' as type, created_at FROM exam_results WHERE is_active = true
        ) AS activities
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """
        result = await db.execute(__import__('sqlalchemy').text(sql), {"limit": limit, "offset": offset})
        rows = result.fetchall()
        items = []
        for row in rows:
            item = {"id": str(row[0]), "title": row[1], "type": row[2], "created_at": str(row[3]) if row[3] else None}
            items.append(item)
        return {"items": items, "total": len(items) + offset, "page": offset // limit + 1 if limit else 1, "size": limit}
    except Exception as e:
        logger.error(f"获取活动列表失败: {e}")
        return {"items": [], "total": 0, "page": 1, "size": limit}


@router.get("/jd-stats/jd-recent-activities")
async def jd_recent_activities_internal(
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：活动记录（兼容StatsService，跨5张业务表UNION）"""
    try:
        sql = """
        SELECT * FROM (
            SELECT id::text as id, COALESCE(title, position_title, '未命名JD') as title, 'jd' as type, created_at FROM jd_records WHERE is_active = true
            UNION ALL
            SELECT id::text, COALESCE(title, '评分标准') as title, 'scoring' as type, created_at FROM scoring_criteria WHERE is_active = true
            UNION ALL
            SELECT id::text, COALESCE(title, '面试方案') as title, 'interview' as type, created_at FROM interview_plans WHERE is_active = true
            UNION ALL
            SELECT id::text, COALESCE(candidate_name, '简历评价') as title, 'resume' as type, created_at FROM resume_evaluations WHERE is_active = true
            UNION ALL
            SELECT id::text, COALESCE(exam_name, '考试结果') as title, 'exam' as type, created_at FROM exam_results WHERE is_active = true
        ) AS activities
        ORDER BY created_at DESC LIMIT 20
        """
        result = await db.execute(__import__('sqlalchemy').text(sql))
        rows = result.fetchall()
        return [{"id": str(r[0]), "title": r[1], "type": r[2], "created_at": str(r[3]) if r[3] else None} for r in rows]
    except Exception as e:
        logger.error(f"获取活动列表失败: {e}")
        return []


@router.get("/jd-stats/jd_dashboard")
async def jd_dashboard_internal(
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：JD仪表板统计"""
    try:
        result = await db.execute(__import__('sqlalchemy').text("SELECT COUNT(*) FROM jd_records WHERE is_active = true"))
        total = result.scalar()
        return {"total": total, "change": 0}
    except Exception:
        return {"total": 0, "change": 0}


@router.get("/jd-stats/jd-recruitment-trend")
async def jd_recruitment_trend_internal(
    days: int = Query(30),
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：招聘趋势"""
    return {"data": []}


# ===== 面试方案管理 =====

@router.get("/interview-plans/")
async def list_interview_internal(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    current_user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：获取面试方案列表"""
    return {"items": [], "total": 0, "page": page, "size": size, "pages": 0}


@router.post("/interview-plans/save-generated")
async def save_interview_internal(
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """内部：保存面试方案"""
    import uuid
    from datetime import datetime, timezone
    plan_id = data.get("id") or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db.execute(__import__('sqlalchemy').text("""
        INSERT INTO interview_plans (id, title, plan_content, status, created_by, created_at, updated_at, is_active)
        VALUES (:id, :title, :content, :status, :created_by, :created_at, :updated_at, :is_active)
    """), {
        "id": plan_id, "title": data.get("title", ""),
        "content": str(data.get("plan_content", data.get("content", ""))),
        "status": data.get("status", "draft"),
        "created_by": str(data.get("created_by", "system")),
        "created_at": now, "updated_at": now, "is_active": True,
    })
    await db.commit()
    return {"data": {**data, "id": plan_id}}


@router.get("/interview-plans/{plan_id}")
async def get_interview_internal(plan_id: str, db: AsyncSession = Depends(get_db), _: None = Depends(verify_api_key)):
    result = await db.execute(__import__('sqlalchemy').text("SELECT * FROM interview_plans WHERE id = :id"), {"id": plan_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404)
    item = dict(zip(result.keys(), row))
    return {k: str(v) if isinstance(v, UUID) else v for k, v in item.items()}


@router.put("/interview-plans/{plan_id}")
async def update_interview_internal(plan_id: str, data: Dict[str, Any], db: AsyncSession = Depends(get_db), _: None = Depends(verify_api_key)):
    from datetime import datetime, timezone
    await db.execute(__import__('sqlalchemy').text("UPDATE interview_plans SET title=:title, plan_content=:content, status=:status, updated_at=:updated_at WHERE id=:id"), {
        "id": plan_id, "title": data.get("title", ""), "content": str(data.get("plan_content", "")),
        "status": data.get("status", "draft"), "updated_at": datetime.now(timezone.utc),
    })
    await db.commit()
    return {"data": {**data, "id": plan_id}}


@router.delete("/interview-plans/{plan_id}")
async def delete_interview_internal(plan_id: str, db: AsyncSession = Depends(get_db), _: None = Depends(verify_api_key)):
    await db.execute(__import__('sqlalchemy').text("DELETE FROM interview_plans WHERE id = :id"), {"id": plan_id})
    await db.commit()
    return {"message": "删除成功"}
