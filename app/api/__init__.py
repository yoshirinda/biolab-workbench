"""
API模块 - 提供RESTful API接口
"""
from flask import Blueprint

# 创建API蓝图
api_bp = Blueprint('api', __name__, url_prefix='/api')

# 导入路由
from . import projects, sequences

# 注册子蓝图
api_bp.register_blueprint(projects.projects_bp)
api_bp.register_blueprint(sequences.sequences_bp)
