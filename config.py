"""
BioLab Workbench Configuration
All paths and settings are centralized here.
"""
import os
import secrets


def get_base_dir():
    """
    Automatically detect and configure the base directory.
    
    Priority:
    1. BIOLAB_BASE_DIR environment variable
    2. User config file (~/.biolab/config)
    3. Project directory's biolab_data folder
    """
    # Priority 1: Environment variable
    if os.environ.get('BIOLAB_BASE_DIR'):
        return os.environ['BIOLAB_BASE_DIR']
    
    # Priority 2: User configuration file
    user_config = os.path.expanduser('~/.biolab/config')
    if os.path.exists(user_config):
        try:
            with open(user_config, 'r', encoding='utf-8') as f:
                base_dir = f.read().strip()
                if base_dir and os.path.isabs(base_dir):
                    return base_dir
        except (IOError, OSError):
            pass
    
    # Priority 3: Default to biolab_data in project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(project_dir, 'biolab_data')


def is_first_run():
    """Check if this is the first run of the application."""
    user_config = os.path.expanduser('~/.biolab/config')
    return not os.path.exists(user_config) and not os.environ.get('BIOLAB_BASE_DIR')


# Base directory - automatically detected
BASE_DIR = get_base_dir()

# 子目录
DATABASES_DIR = os.path.join(BASE_DIR, "databases")
REFERENCES_DIR = os.path.join(BASE_DIR, "references")
GOLD_LISTS_DIR = os.path.join(REFERENCES_DIR, "gold_lists")
HMM_PROFILES_DIR = os.path.join(REFERENCES_DIR, "hmm_profiles")
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Conda environment name
CONDA_ENV = os.environ.get('CONDA_DEFAULT_ENV') or os.environ.get('BIOLAB_CONDA_ENV') or 'bio'

# 默认参数
DEFAULT_THREADS = int(os.environ.get('BIOLAB_THREADS', 4))

# Flask 配置 - Secret key from environment or generated randomly
SECRET_KEY = os.environ.get('BIOLAB_SECRET_KEY', secrets.token_hex(32))

# 上传大小上限（默认 100MB）。若需更大可设置环境变量 BIOLAB_MAX_CONTENT_MB。
MAX_CONTENT_LENGTH = int(float(os.environ.get('BIOLAB_MAX_CONTENT_MB', 100)) * 1024 * 1024)

# 确保目录存在 (skip in test environments or when path doesn't exist)
try:
    for dir_path in [DATABASES_DIR, REFERENCES_DIR, GOLD_LISTS_DIR,
                     HMM_PROFILES_DIR, PROJECTS_DIR, UPLOADS_DIR,
                     RESULTS_DIR, LOGS_DIR]:
        os.makedirs(dir_path, exist_ok=True)
except (PermissionError, OSError):
    # Running in test environment or directory not accessible
    pass

# 物种分类 (用于UniProt检索) - 基于原脚本 uniprot_miner_v5.4.py
TAXONOMY_OPTIONS = {
    "All (不限制)": None,
    "Viridiplantae (绿色植物)": 33090,
    "Embryophyta (陆生植物)": 3193,
    "Tracheophyta (维管植物)": 58023,
    "Spermatophyta (种子植物)": 58024,
    "Angiospermae (被子植物)": 3398,
    "Gymnospermae (裸子植物)": 3312,
    "Polypodiopsida (真蕨)": 241806,
    "Lycopodiopsida (石松)": 3247,
    "Bryophyta (苔藓)": 3208,
    "Chlorophyta (绿藻)": 3041,
    "Arabidopsis thaliana": 3702,
    "Oryza sativa (水稻)": 4530,
    "Zea mays (玉米)": 4577,
    "Glycine max (大豆)": 3847,
    "Nicotiana tabacum (烟草)": 4097,
    "Solanum lycopersicum (番茄)": 4081,
    "Populus (杨属)": 3689,
}
