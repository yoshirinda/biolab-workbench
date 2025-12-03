"""
BioLab Workbench Configuration
All paths and settings are centralized here.
"""
import os

# 基础目录
BASE_DIR = "/mnt/e/Kun/wsl/biolab"

# 子目录
DATABASES_DIR = os.path.join(BASE_DIR, "databases")
REFERENCES_DIR = os.path.join(BASE_DIR, "references")
GOLD_LISTS_DIR = os.path.join(REFERENCES_DIR, "gold_lists")
HMM_PROFILES_DIR = os.path.join(REFERENCES_DIR, "hmm_profiles")
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Conda 环境名
CONDA_ENV = "bio"

# 默认参数
DEFAULT_THREADS = 4

# Flask 配置
SECRET_KEY = "biolab-workbench-secret-key"
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB

# 确保目录存在 (skip in test environments or when path doesn't exist)
try:
    for dir_path in [DATABASES_DIR, REFERENCES_DIR, GOLD_LISTS_DIR,
                     HMM_PROFILES_DIR, PROJECTS_DIR, UPLOADS_DIR,
                     RESULTS_DIR, LOGS_DIR]:
        os.makedirs(dir_path, exist_ok=True)
except (PermissionError, OSError):
    # Running in test environment or directory not accessible
    pass

# 物种分类 (用于UniProt检索)
TAXONOMY_OPTIONS = {
    "Viridiplantae": 33090,
    "Embryophyta": 3193,
    "Tracheophyta": 58023,
    "Spermatophyta": 58024,
    "Angiospermae": 3398,
    "Gymnospermae": 3312,
    "Arabidopsis thaliana": 3702,
    "Oryza sativa": 4530,
}
