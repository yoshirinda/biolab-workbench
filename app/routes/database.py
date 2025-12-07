"""
Database related routes for BioLab Workbench.
"""
from flask import Blueprint, jsonify
from app.core.blast_wrapper import list_blast_databases
from app.utils.logger import get_app_logger

database_bp = Blueprint('database', __name__)
logger = get_app_logger()

@database_bp.route('/blast-databases')
def get_blast_databases():
    """
    Get a list of available BLAST databases.
    """
    try:
        databases = list_blast_databases()
        return jsonify({'success': True, 'databases': databases})
    except Exception as e:
        logger.error(f"Failed to get BLAST databases: {e}")
        return jsonify({'success': False, 'error': str(e)})
