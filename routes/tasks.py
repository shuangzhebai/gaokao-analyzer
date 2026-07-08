"""任务状态轮询路由（P1-02）。"""

from typing import Any

from fastapi import APIRouter

from celery_app import _HAS_CELERY, app as celery_app

router = APIRouter()


@router.get("/api/tasks/{task_id}", include_in_schema=False)
@router.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str) -> dict[str, Any]:
    """查询异步任务状态。Celery 不可用时返回降级信息。"""
    if not _HAS_CELERY or celery_app is None:
        return {
            "task_id": task_id,
            "status": "UNAVAILABLE",
            "info": "Celery 未启用，任务以同步模式运行。",
        }
    try:
        async_result = celery_app.AsyncResult(task_id)
        state = async_result.state
        result_data: dict[str, Any] = {"task_id": task_id, "status": state}

        if state == "PENDING":
            result_data["info"] = "任务等待执行"
        elif state == "STARTED":
            result_data["info"] = "任务正在执行"
        elif state == "SUCCESS":
            result_data["result"] = async_result.result
        elif state == "FAILURE":
            result_data["error"] = str(async_result.result)
        elif state == "RETRY":
            result_data["info"] = "任务等待重试"

        return result_data
    except Exception as e:
        return {"task_id": task_id, "status": "ERROR", "error": str(e)}
