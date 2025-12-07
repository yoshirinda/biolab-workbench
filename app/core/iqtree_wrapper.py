"""
IQ-TREE wrapper for BioLab Workbench.
Maximum-likelihood phylogenetic inference.
"""
import os
import subprocess
import shlex
import re
from datetime import datetime
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params

logger = get_tools_logger()


def run_conda_command(command, timeout=7200):
    """
    Run a command in the conda environment.
    Returns (success, stdout, stderr).
    """
    if config.USE_CONDA and config.CONDA_ENV:
        full_command = f"conda run -n {shlex.quote(config.CONDA_ENV)} {command}"
    else:
        full_command = command
    logger.info(f"Running command: {full_command}")

    try:
        result = subprocess.run(
            full_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        logger.info(f"Command completed with return code: {result.returncode}")
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds")
        return False, '', 'Command timed out'
    except Exception as e:
        logger.error(f"Command failed: {str(e)}")
        return False, '', str(e)


def parse_iqtree_log(log_file):
    """
    Parse IQ-TREE log file to extract key information.
    
    Returns:
        Dict with analysis results
    """
    info = {
        'model': None,
        'log_likelihood': None,
        'aic': None,
        'bic': None,
        'total_tree_length': None,
        'cpu_time': None,
        'wall_time': None
    }
    
    try:
        with open(log_file, 'r') as f:
            content = f.read()
            
            # Extract model
            model_match = re.search(r'Best-fit model:\s+(\S+)', content)
            if model_match:
                info['model'] = model_match.group(1)
            
            # Extract log likelihood
            ll_match = re.search(r'Log-likelihood of the tree:\s+([-\d.]+)', content)
            if ll_match:
                info['log_likelihood'] = float(ll_match.group(1))
            
            # Extract AIC
            aic_match = re.search(r'Akaike information criterion \(AIC\) score:\s+([\d.]+)', content)
            if aic_match:
                info['aic'] = float(aic_match.group(1))
            
            # Extract BIC
            bic_match = re.search(r'Bayesian information criterion \(BIC\) score:\s+([\d.]+)', content)
            if bic_match:
                info['bic'] = float(bic_match.group(1))
            
            # Extract tree length
            length_match = re.search(r'Total tree length \(sum of branch lengths\):\s+([\d.]+)', content)
            if length_match:
                info['total_tree_length'] = float(length_match.group(1))
            
            # Extract time
            cpu_match = re.search(r'Total CPU time used:\s+([\d.]+)', content)
            if cpu_match:
                info['cpu_time'] = float(cpu_match.group(1))
            
            wall_match = re.search(r'Total wall-clock time used:\s+([\d.]+)', content)
            if wall_match:
                info['wall_time'] = float(wall_match.group(1))
    
    except Exception as e:
        logger.warning(f"Failed to parse IQ-TREE log: {e}")
    
    return info


def run_iqtree(alignment_file, output_prefix=None, model='MFP', 
               bootstrap=1000, bootstrap_type='ufboot', alrt=False,
               bnni=True, threads='AUTO', seed=None, redo=False):
    """
    Run IQ-TREE for phylogenetic inference.
    
    Args:
        alignment_file: Path to alignment file (FASTA, PHYLIP, etc.)
        output_prefix: Prefix for output files
        model: Substitution model
            - 'MFP': ModelFinder Plus (automatic selection)
            - 'TEST': Test all models
            - Or specify model name (e.g., 'LG+G4', 'WAG+I+G')
        bootstrap: Number of bootstrap replicates
            - 0: No bootstrap
            - >0: Number of replicates (typically 1000)
        bootstrap_type: Type of bootstrap
            - 'ufboot': Ultrafast bootstrap (default, fast)
            - 'boot': Standard bootstrap (slower)
            - 'both': Both UFBoot and standard bootstrap
        alrt: Perform SH-aLRT test (branch support)
        bnni: Optimize UFBoot trees by NNI
        threads: Number of CPU threads ('AUTO' or integer)
        seed: Random seed for reproducibility
        redo: Force redo analysis (ignore checkpoint)
        
    Returns:
        (success, result_dir, output_files, log_info)
    """
    if not os.path.exists(alignment_file):
        return False, None, None, f"Alignment file not found: {alignment_file}"
    
    # Create result directory
    result_dir = create_result_dir('iqtree', 'inference')
    
    if output_prefix is None:
        basename = os.path.basename(alignment_file).rsplit('.', 1)[0]
        output_prefix = os.path.join(result_dir, basename)
    
    # Build command
    command = f'iqtree -s {shlex.quote(alignment_file)}'
    command += f' -pre {shlex.quote(output_prefix)}'
    
    # Model selection
    if model:
        command += f' -m {shlex.quote(model)}'
    
    # Bootstrap
    if bootstrap > 0:
        if bootstrap_type == 'ufboot':
            command += f' -bb {bootstrap}'
            if bnni:
                command += ' -bnni'
        elif bootstrap_type == 'boot':
            command += f' -b {bootstrap}'
        elif bootstrap_type == 'both':
            command += f' -bb {bootstrap} -b {bootstrap}'
            if bnni:
                command += ' -bnni'
    
    # SH-aLRT test
    if alrt:
        if isinstance(alrt, bool):
            command += ' -alrt 1000'
        else:
            command += f' -alrt {alrt}'
    
    # Threads
    if threads == 'AUTO':
        command += ' -nt AUTO'
    else:
        command += f' -nt {threads}'
    
    # Seed
    if seed:
        command += f' -seed {seed}'
    
    # Redo
    if redo:
        command += ' -redo'
    
    # Save parameters
    params = {
        'alignment_file': alignment_file,
        'model': model,
        'bootstrap': bootstrap,
        'bootstrap_type': bootstrap_type,
        'alrt': alrt,
        'bnni': bnni,
        'threads': threads,
        'seed': seed,
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)
    
    # Execute
    logger.info(f"Starting IQ-TREE analysis (this may take a while)...")
    if config.USE_CONDA and config.CONDA_ENV:
        full_command = f"conda run -n {shlex.quote(config.CONDA_ENV)} {command} > {shlex.quote(output_prefix)}.log 2>&1"
    else:
        full_command = f"{command} > {shlex.quote(output_prefix)}.log 2>&1"
    logger.info(f"Running command: {full_command}")

    popen = subprocess.Popen(
        full_command,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Collect expected output files
    output_files = {
        'treefile': output_prefix + '.treefile',
        'log': output_prefix + '.log',
        'iqtree': output_prefix + '.iqtree'
    }
    
    return popen, result_dir, output_files, output_prefix


def run_iqtree_modelfinder(alignment_file, output_prefix=None, 
                           test_models='all', threads='AUTO'):
    """
    Run only ModelFinder without tree inference.
    Useful for determining best substitution model.
    
    Args:
        alignment_file: Path to alignment file
        output_prefix: Prefix for output files
        test_models: Models to test ('all', 'nuclear', 'mitochondrial', etc.)
        threads: CPU threads
        
    Returns:
        (success, result_dir, best_model, model_list)
    """
    if not os.path.exists(alignment_file):
        return False, None, None, f"Alignment file not found: {alignment_file}"
    
    result_dir = create_result_dir('iqtree', 'modelfinder')
    
    if output_prefix is None:
        basename = os.path.basename(alignment_file).rsplit('.', 1)[0]
        output_prefix = os.path.join(result_dir, f'{basename}_models')
    
    # Build command - ModelFinder only
    command = f'iqtree -s {shlex.quote(alignment_file)}'
    command += f' -pre {shlex.quote(output_prefix)}'
    command += ' -m MF'  # ModelFinder only, no tree inference
    
    if test_models != 'all':
        command += f' -mset {shlex.quote(test_models)}'
    
    if threads == 'AUTO':
        command += ' -nt AUTO'
    else:
        command += f' -nt {threads}'
    
    # Execute
    success, stdout, stderr = run_conda_command(command)
    
    if not success:
        logger.error(f"ModelFinder failed: {stderr}")
        return False, result_dir, None, stderr
    
    # Parse results
    log_file = output_prefix + '.log'
    log_info = parse_iqtree_log(log_file)
    
    best_model = log_info.get('model')
    
    logger.info(f"ModelFinder completed: best model = {best_model}")
    
    return True, result_dir, best_model, log_info


def run_iqtree_constrained(alignment_file, constraint_tree, output_prefix=None,
                           model='MFP', bootstrap=1000, threads='AUTO'):
    """
    Run IQ-TREE with topological constraint.
    
    Args:
        alignment_file: Path to alignment file
        constraint_tree: Path to constraint tree file (Newick format)
        output_prefix: Output prefix
        model: Substitution model
        bootstrap: Bootstrap replicates
        threads: CPU threads
        
    Returns:
        (success, result_dir, output_files, log_info)
    """
    if not os.path.exists(constraint_tree):
        return False, None, None, f"Constraint tree not found: {constraint_tree}"
    
    # Use main run_iqtree but add constraint
    success, result_dir, output_files, log_info = run_iqtree(
        alignment_file=alignment_file,
        output_prefix=output_prefix,
        model=model,
        bootstrap=bootstrap,
        threads=threads
    )
    
    # Note: This would need modification of run_iqtree to add -g flag
    # For now, this is a placeholder showing the intended functionality
    
    return success, result_dir, output_files, output_prefix


def extract_bootstrap_support(treefile):
    """
    Extract bootstrap support values from tree file.
    
    Returns:
        List of support values
    """
    support_values = []
    
    try:
        with open(treefile, 'r') as f:
            tree_string = f.read().strip()
            
            # Find all numbers that appear before colons or parentheses
            # These are typically bootstrap/support values
            pattern = r'\)(\d+(?:\.\d+)?)[:\),]'
            matches = re.findall(pattern, tree_string)
            
            support_values = [float(m) for m in matches]
    
    except Exception as e:
        logger.error(f"Failed to extract bootstrap values: {e}")
    
    return support_values


def summarize_bootstrap_support(treefile):
    """
    Summarize bootstrap support statistics.
    
    Returns:
        Dict with support statistics
    """
    values = extract_bootstrap_support(treefile)
    
    if not values:
        return {
            'count': 0,
            'mean': 0,
            'median': 0,
            'min': 0,
            'max': 0,
            'strong_support': 0,  # >=95
            'moderate_support': 0,  # 70-94
            'weak_support': 0  # <70
        }
    
    sorted_values = sorted(values)
    n = len(values)
    
    return {
        'count': n,
        'mean': sum(values) / n,
        'median': sorted_values[n // 2] if n % 2 == 1 else (sorted_values[n//2-1] + sorted_values[n//2]) / 2,
        'min': min(values),
        'max': max(values),
        'strong_support': sum(1 for v in values if v >= 95),
        'moderate_support': sum(1 for v in values if 70 <= v < 95),
        'weak_support': sum(1 for v in values if v < 70)
    }
