"""
自定义异常类
"""


class BaseAPIError(Exception):
    """API错误基类"""
    
    def __init__(self, message: str, code: str = "ERROR", details: dict = None, status_code: int = 400):
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "message": self.message,
            "code": self.code,
            "details": self.details,
            "status_code": self.status_code
        }


class ValidationError(BaseAPIError):
    """验证错误"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            status_code=400
        )


class NotFoundError(BaseAPIError):
    """资源不存在错误"""
    
    def __init__(self, resource: str = "资源"):
        super().__init__(
            message=f"{resource}不存在",
            code="NOT_FOUND",
            status_code=404
        )


class ConflictError(BaseAPIError):
    """冲突错误（如资源已存在）"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409
        )


class ForbiddenError(BaseAPIError):
    """禁止访问错误"""
    
    def __init__(self, message: str = "访问被拒绝"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403
        )


class InternalError(BaseAPIError):
    """内部错误"""
    
    def __init__(self, message: str = "服务器内部错误"):
        super().__init__(
            message=message,
            code="INTERNAL_ERROR",
            status_code=500
        )