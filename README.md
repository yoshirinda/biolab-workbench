# BioLab Workbench

统一的生物信息学 Web 工作平台 / Unified Bioinformatics Web Platform

## Overview 概述

BioLab Workbench is a comprehensive bioinformatics web platform that integrates multiple analysis tools into a unified interface. It runs in a WSL (Windows Subsystem for Linux) environment and is accessible via a web browser.

BioLab Workbench 是一个综合性的生物信息学 Web 平台，将多种分析工具整合到统一的界面中。它运行在 WSL 环境中，可通过浏览器访问。

## Features 功能模块

### 1. Sequence Management 序列管理
- Import sequences (FASTA, GenBank formats)
- View and edit sequences
- DNA translation (6 reading frames)
- Reverse complement
- ORF (Open Reading Frame) finder
- Sequence statistics (length, GC content, molecular weight)
- Export sequences

### 2. BLAST Search
- Database management (create with makeblastdb, scan existing databases)
- Run BLAST searches (blastn, blastp, blastx, tblastn)
- Auto-detect sequence type
- Multiple output formats (TSV, TXT, HTML)
- Extract sequences from hits

### 3. Phylogenetic Pipeline 系统发育流程
- Step 1: FASTA header cleaning
- Step 2: HMMer search (hmmsearch)
- Step 2.5: BLAST filtering with gold standard
- Step 2.7: Sequence length statistics
- Step 2.8: Length filtering
- Step 3: MAFFT alignment
- Step 4: ClipKIT trimming
- Step 5: IQ-Tree phylogenetic tree building

### 4. Sequence Alignment 序列比对
- Support for MAFFT, ClustalW, MUSCLE
- Conservation visualization with coloring
- HTML output with conservation scores

### 5. UniProt Search
- Keyword search via UniProt REST API
- Taxonomy filtering (Viridiplantae, Arabidopsis, Oryza sativa, etc.)
- Database type filtering (Swiss-Prot, TrEMBL)
- Batch sequence download
- Custom FASTA header formatting (Gene_Species_ID)

### 6. Tree Visualization 进化树可视化
- Load Newick format tree files
- Species prefix detection and coloring
- Gene highlighting
- Circular and rectangular layouts
- Bootstrap value display
- SVG output

## Installation 安装

### Requirements 环境要求
- Python 3.10+
- Conda environment with bioinformatics tools
- WSL environment (for Windows users)

### Setup 设置

```bash
# Clone the repository
cd /mnt/e/Kun/wsl/biolab
git clone <repository-url> biolab-workbench

# Activate conda environment
conda activate bio

# Install Python dependencies
cd biolab-workbench
pip install -r requirements.txt

# Run the application
python run.py
```

### Access 访问

Open in your browser: http://localhost:5000

## Configuration 配置

All configuration is centralized in `config.py`:

```python
# Base directory
BASE_DIR = "/mnt/e/Kun/wsl/biolab"

# Subdirectories
DATABASES_DIR = os.path.join(BASE_DIR, "databases")
REFERENCES_DIR = os.path.join(BASE_DIR, "references")
GOLD_LISTS_DIR = os.path.join(REFERENCES_DIR, "gold_lists")
HMM_PROFILES_DIR = os.path.join(REFERENCES_DIR, "hmm_profiles")
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Conda environment
CONDA_ENV = "bio"
```

## Directory Structure 目录结构

```
biolab-workbench/
├── config.py                 # Configuration file
├── run.py                    # Application entry point
├── requirements.txt          # Python dependencies
├── README.md                 # Documentation
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── routes/              # Route handlers
│   │   ├── main.py          # Home page
│   │   ├── sequence.py      # Sequence management
│   │   ├── blast.py         # BLAST operations
│   │   ├── phylo.py         # Phylogenetic pipeline
│   │   ├── alignment.py     # Sequence alignment
│   │   ├── uniprot.py       # UniProt search
│   │   └── tree.py          # Tree visualization
│   ├── core/                # Core functionality
│   │   ├── sequence_utils.py
│   │   ├── blast_wrapper.py
│   │   ├── phylo_pipeline.py
│   │   ├── alignment_tools.py
│   │   ├── uniprot_client.py
│   │   └── tree_visualizer.py
│   ├── utils/               # Utilities
│   │   ├── logger.py
│   │   ├── path_utils.py
│   │   └── file_utils.py
│   ├── templates/           # HTML templates
│   └── static/              # CSS, JS
└── tests/                   # Test files
```

## Logging 日志

Logs are stored in the logs directory:
- `logs/app.log` - Application logs
- `logs/tools.log` - External tool execution logs

## Results 结果管理

All analysis results are saved to the results directory with the naming format:
`{tool}_{task}_{YYYYMMDD_HHMMSS}/`

Each task creates a separate directory containing:
- Output files
- `params.json` - Run parameters

## External Tools 外部工具

The following tools should be available in the conda environment:
- BLAST+ (blastn, blastp, blastx, tblastn, makeblastdb, blastdbcmd)
- HMMER (hmmsearch)
- MAFFT
- ClipKIT
- IQ-Tree
- ClustalW (optional)
- MUSCLE (optional)
- ETE3 (for tree visualization)

## License 许可证

MIT License

## Support 支持

For issues and questions, please create an issue in the repository.

