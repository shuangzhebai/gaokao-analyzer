"""
全局异常处理（T03/T04）
- 全局 Exception：仅返回通用错误信息，避免泄露内部路径/SQL（R-2）
- HTTPException：返回应用层可控的 detail（安全，不泄露内部细节）
"""
import logging
import traceback

from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger("gaokao")


async def global_exception_handler(request: Request, exc: Exception):
    """未捕获异常：记录详细日志到服务端，仅向客户端返回通用错误。"""
    logger.error(
        f"Unhandled error on {request.method} {request.url}: {exc}\n{traceback.format_exc()}"
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常：返回应用层 detail（不含内部堆栈/SQL）。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail)},
    )
