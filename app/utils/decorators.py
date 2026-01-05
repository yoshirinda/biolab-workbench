"""
API装饰器 - 统一错误处理和响应格式
"""
from functools import wraps
from flask import request
from typing import Callable, Any
from .responses import APIResponse, handle_exception
from .errors import ValidationError
from .logger import get_app_logger

logger = get_app_logger()


def api_route(f: Callable) -> Callable:
    """API路由装饰器 - 统一错误处理和响应格式
    
    用法:
        @api_route
        def get_projects():
            return list_of_projects
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            
            # 如果返回的已经是Response对象，直接返回
            if hasattr(result, 'status_code'):
                return result
            
            # 否则包装成success响应
            return APIResponse.success(data=result)
            
        except Exception as e:
            logger.error(f"API error in {f.__name__}: {str(e)}", exc_info=True)
            return handle_exception(e)
    
    return wrapper


def validate_json(*required_fields):
    """验证JSON请求体装饰器
    
    Args:
        *required_fields: 必需的字段名称
    
    用法:
        @validate_json('name', 'description')
        def create_project():
            data = request.get_json()
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                raise ValidationError("请求必须是JSON格式")
            
            data = request.get_json()
            
            # 检查必需字段
            missing_fields = []
            for field in required_fields:
                if field not in data or data[field] is None:
                    missing_fields.append(field)
            
            if missing_fields:
                raise ValidationError(
                    f"缺少必需字段: {', '.join(missing_fields)}",
                    details={"missing_fields": missing_fields}
                )
            
            return f(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_query_params(**param_validators):
    """验证查询参数装饰器
    
    Args:
        **param_validators: 参数名和验证函数的字典
    
    用法:
        @validate_query_params(
            page=lambda x: int(x) > 0,
            limit=lambda x: 0 < int(x) <= 100
        )
        def get_projects():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            for param_name, validator in param_validators.items():
                param_value = request.args.get(param_name)
                
                if param_value is not None:
                    try:
                        if not validator(param_value):
                            raise ValidationError(
                                f"参数'{param_name}'验证失败"
                            )
                    except (ValueError, TypeError) as e:
                        raise ValidationError(
                            f"参数'{param_name}'格式错误",
                            details={"param": param_name, "error": str(e)}
                        )
            
            return f(*args, **kwargs)
        
        return wrapper
    return decorator


def log_request(f: Callable) -> Callable:
    """记录请求日志装饰器"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        logger.info(
            f"API Request: {request.method} {request.path}",
            extra={
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
                "user_agent": request.user_agent.string
            }
        )
        result = f(*args, **kwargs)
        return result
    
    return wrapper