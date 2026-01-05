"""
统一的API响应格式和工具函数
"""
from typing import Any, Optional, Dict
from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIResponse:
    """统一的API响应类"""
    
    @staticmethod
    def success(data: Any = None, message: str = "操作成功", status_code: int = 200):
        """成功响应
        
        Args:
            data: 返回的数据
            message: 成功消息
            status_code: HTTP状态码
            
        Returns:
            Flask Response对象
        """
        response = {
            "success": True,
            "data": data,
            "message": message
        }
        return jsonify(response), status_code
    
    @staticmethod
    def error(
        message: str,
        code: str = "ERROR",
        details: Optional[Dict] = None,
        status_code: int = 400
    ):
        """错误响应
        
        Args:
            message: 错误消息
            code: 错误代码
            details: 错误详情
            status_code: HTTP状态码
            
        Returns:
            Flask Response对象
        """
        response = {
            "success": False,
            "error": {
                "code": code,
                "message": message
            }
        }
        if details:
            response["error"]["details"] = details
            
        return jsonify(response), status_code
    
    @staticmethod
    def validation_error(message: str, details: Optional[Dict] = None):
        """验证错误响应"""
        return APIResponse.error(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            status_code=400
        )
    
    @staticmethod
    def not_found(resource: str = "资源"):
        """404响应"""
        return APIResponse.error(
            message=f"{resource}不存在",
            code="NOT_FOUND",
            status_code=404
        )
    
    @staticmethod
    def forbidden(message: str = "访问被拒绝"):
        """403响应"""
        return APIResponse.error(
            message=message,
            code="FORBIDDEN",
            status_code=403
        )
    
    @staticmethod
    def internal_error(message: str = "服务器内部错误"):
        """500响应"""
        return APIResponse.error(
            message=message,
            code="INTERNAL_ERROR",
            status_code=500
        )


def handle_exception(e: Exception):
    """统一异常处理
    
    Args:
        e: 异常对象
        
    Returns:
        Flask Response对象
    """
    # HTTP异常
    if isinstance(e, HTTPException):
        return APIResponse.error(
            message=e.description,
            code=e.name.upper().replace(" ", "_"),
            status_code=e.code
        )
    
    # 自定义异常
    if hasattr(e, 'to_dict'):
        error_dict = e.to_dict()
        return APIResponse.error(
            message=error_dict.get('message', str(e)),
            code=error_dict.get('code', 'ERROR'),
            details=error_dict.get('details'),
            status_code=error_dict.get('status_code', 400)
        )
    
    # 未知异常
    return APIResponse.internal_error(str(e))