"""
项目管理API - 使用新的装饰器和响应格式
"""
from typing import Optional
from flask import Blueprint, request
from app.utils.decorators import api_route, validate_json, log_request
from app.utils.errors import ValidationError, NotFoundError
from app.core.project_manager import (
    list_projects,
    create_project,
    get_project,
    update_project,
    delete_project,
    create_folder
)
from app.utils.logger import get_app_logger

logger = get_app_logger()
projects_bp = Blueprint('projects', __name__, url_prefix='/projects')


@projects_bp.route('', methods=['GET'])
@api_route
@log_request
def get_all_projects():
    """获取所有项目
    
    Returns:
        list: 项目列表
    """
    projects = list_projects()
    return projects


@projects_bp.route('', methods=['POST'])
@api_route
@validate_json('name')
@log_request
def create_new_project():
    """创建新项目
    
    Request Body:
        {
            "name": "项目名称",
            "parent_path": "父路径(可选)",
            "description": "描述(可选)"
        }
    
    Returns:
        dict: 创建的项目信息
    """
    data = request.get_json()
    
    # 获取并验证参数
    name = data.get('name', '').strip()
    if not name:
        raise ValidationError('项目名称不能为空')
    
    parent_path = data.get('parent_path', '').strip() or None
    description = data.get('description', '')
    
    # 调用服务层
    success, project_data, message = create_project(
        path=None,
        name=name,
        parent_path=parent_path,
        description=description
    )
    
    if not success:
        raise ValidationError(message)
    
    logger.info(f"Created project: {project_data.get('name')}")
    return project_data


@projects_bp.route('/folders', methods=['POST'])
@api_route
@validate_json('name')
@log_request
def create_new_folder():
    """创建新文件夹
    
    Request Body:
        {
            "name": "文件夹名称",
            "parent_path": "父路径(可选)"
        }
    
    Returns:
        dict: 成功消息
    """
    data = request.get_json()
    
    name = data.get('name', '').strip()
    if not name:
        raise ValidationError('文件夹名称不能为空')
    
    parent_path = data.get('parent_path', '').strip() or None
    
    success, message = create_folder(
        path=None,
        name=name,
        parent_path=parent_path
    )
    
    if not success:
        raise ValidationError(message)
    
    return {'message': message}


@projects_bp.route('/<path:project_path>', methods=['GET'])
@api_route
@log_request
def get_project_details(project_path: str):
    """获取项目详情
    
    Args:
        project_path: 项目路径
    
    Returns:
        dict: 项目详细信息
    """
    success, project_data, message = get_project(project_path)
    
    if not success:
        raise NotFoundError('项目')
    
    return project_data


@projects_bp.route('/<path:project_path>', methods=['PUT'])
@api_route
@log_request
def update_project_details(project_path: str):
    """更新项目信息
    
    Args:
        project_path: 项目路径
    
    Request Body:
        {
            "name": "新名称(可选)",
            "description": "新描述(可选)"
        }
    
    Returns:
        dict: 更新后的项目信息
    """
    data = request.get_json()
    
    name = data.get('name')
    description = data.get('description')
    
    success, project_data, message = update_project(
        project_path,
        name,
        description
    )
    
    if not success:
        raise ValidationError(message)
    
    logger.info(f"Updated project: {project_path}")
    return project_data


@projects_bp.route('/<path:project_path>', methods=['DELETE'])
@api_route
@log_request
def delete_project_by_path(project_path: str):
    """删除项目
    
    Args:
        project_path: 项目路径
    
    Returns:
        dict: 成功消息
    """
    success, message = delete_project(project_path)
    
    if not success:
        raise ValidationError(message)
    
    logger.info(f"Deleted project: {project_path}")
    return {'message': message}