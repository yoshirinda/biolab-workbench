# BioLab Workbench

Unified Bioinformatics Web Platform

## Overview

BioLab Workbench is a comprehensive bioinformatics web platform that integrates multiple analysis tools into a unified interface. It can run on any Linux environment or WSL (Windows Subsystem for Linux) and is accessible via a web browser.

## Features

### 1. Sequence Management
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

### 3. Phylogenetic Pipeline
- Step 1: FASTA header cleaning
- Step 2: HMMer search (hmmsearch)
- Step 2.5: BLAST filtering with gold standard
- Step 2.7: Sequence length statistics
- Step 2.8: Length filtering
- Step 3: MAFFT alignment
- Step 4: ClipKIT trimming
- Step 5: IQ-Tree phylogenetic tree building

### 4. Sequence Alignment
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

### Prerequisites 前置条件

1. **Linux or WSL**: BioLab Workbench runs on Linux. Windows users should use WSL.
2. **Conda**: Miniconda or Anaconda is required for managing bioinformatics tools.

### One-Click Installation 一键安装

The easiest way to install BioLab Workbench:

```bash
# Clone the repository
git clone https://github.com/your-username/biolab-workbench.git
cd biolab-workbench

# Run the installation script
chmod +x setup.sh
./setup.sh
```

The setup script will:
1. Create a conda environment with all required tools
2. Install Python dependencies
3. Run the setup wizard to configure your data directory

### Manual Installation 手动安装

If you prefer to install manually:

```bash
# 1. Clone the repository
git clone https://github.com/your-username/biolab-workbench.git
cd biolab-workbench

# 2. Create conda environment
conda env create -f environment.yml

# 3. Activate environment
conda activate biolab

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Run the application
python run.py
```

On first run, the setup wizard will help you configure the data directory.

### Alternative: Environment Variable

You can also set the data directory using an environment variable:

```bash
export BIOLAB_BASE_DIR=/path/to/your/data
python run.py
```

## Usage 使用方法

### Starting the Application 启动应用

```bash
# Activate the conda environment
conda activate biolab

# Run the application
python run.py
```

### Accessing the Web Interface 访问 Web 界面

Open your browser and navigate to:
- **Local access**: http://localhost:5000
- **Network access**: http://your-ip-address:5000

## Configuration 配置

BioLab Workbench automatically detects its data directory using the following priority:

1. **Environment variable** `BIOLAB_BASE_DIR`
2. **User config file** `~/.biolab/config`
3. **Default directory** `./biolab_data` (in the project folder)

### Configuration Options

You can configure the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `BIOLAB_BASE_DIR` | Base data directory | `./biolab_data` |
| `BIOLAB_CONDA_ENV` | Conda environment name | `biolab` |
| `BIOLAB_THREADS` | Number of threads for tools | `4` |
| `BIOLAB_DEBUG` | Enable debug mode | `false` |
| `BIOLAB_SECRET_KEY` | Flask secret key | Random |

## Directory Structure 目录结构

### Project Structure 项目结构

```
biolab-workbench/
├── app/                      # Application code
│   ├── __init__.py          # Flask app factory
│   ├── core/                # Core functionality
│   │   ├── sequence_utils.py
│   │   ├── blast_wrapper.py
│   │   ├── phylo_pipeline.py
│   │   ├── alignment_tools.py
│   │   ├── uniprot_client.py
│   │   └── tree_visualizer.py
│   ├── routes/              # Route handlers
│   ├── templates/           # HTML templates
│   ├── static/              # CSS, JS
│   └── utils/               # Utilities
├── data/                    # Example data
│   ├── examples/            # Sample sequences
│   └── references/          # Reference files
├── tests/                   # Test files
├── config.py                # Configuration
├── run.py                   # Entry point
├── setup.sh                 # Installation script
├── setup_wizard.py          # Setup wizard
├── environment.yml          # Conda environment
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

### Data Directory Structure 数据目录结构

```
biolab_data/                 # Your data directory
├── databases/              # BLAST databases
├── references/             # Reference files
│   ├── gold_lists/        # Gold standard gene lists
│   └── hmm_profiles/      # HMM profiles
├── projects/              # Saved projects
├── uploads/               # Uploaded files
├── results/               # Analysis results
└── logs/                  # Application logs
```

## Example Data 示例数据

The repository includes example data files:

- `data/examples/sample_proteins.fasta` - Example protein sequences
- `data/examples/sample_nucleotides.fasta` - Example nucleotide sequences
- `data/references/gold_lists/2-OGD-AT.txt` - Arabidopsis 2-OGD gene family gold standard

## External Tools 外部工具

The following tools are installed via the conda environment:

| Tool | Version | Purpose |
|------|---------|---------|
| BLAST+ | 2.17+ | Sequence similarity search |
| HMMER | 3.4+ | HMM-based sequence search |
| MAFFT | 7.5+ | Multiple sequence alignment |
| ClipKIT | 2.3+ | Alignment trimming |
| IQ-Tree | 2.3+ | Phylogenetic tree building |
| ETE3 | 3.1+ | Tree visualization |

## Troubleshooting 故障排除

### Common Issues 常见问题

**Q: conda command not found**
```bash
# Install Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

**Q: Permission denied when creating directories**
```bash
# Use a directory in your home folder
export BIOLAB_BASE_DIR=~/biolab_data
python run.py
```

**Q: Port 5000 already in use**
```bash
# Check what's using port 5000
lsof -i :5000
# Kill the process or use a different port
export FLASK_RUN_PORT=5001
python run.py
```

**Q: ETE3 visualization errors**
```bash
# Set the QT platform for headless mode
export QT_QPA_PLATFORM=offscreen
python run.py
```

### Getting Help 获取帮助

1. Check the logs in `biolab_data/logs/`
2. Run with debug mode: `BIOLAB_DEBUG=true python run.py`
3. Create an issue on GitHub

## Contributing 贡献

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a pull request

## License 许可证

MIT License

## Acknowledgements 致谢

This project uses the following open-source tools:
- BLAST+ (NCBI)
- HMMER (Sean Eddy Lab)
- MAFFT (Kazutaka Katoh)
- ClipKIT (Jacob Steenwyk)
- IQ-Tree (BQ Minh et al.)
- ETE3 (Jaime Huerta-Cepas)

## Support 支持

For issues and questions, please create an issue in the repository.
