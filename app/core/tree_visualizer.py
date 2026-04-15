"""
Tree visualization module for BioLab Workbench.
Uses ETE3 for tree visualization.
"""
import os
import re
import sys
from datetime import datetime
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params

logger = get_tools_logger()
SUPPORT_LABEL_RE = re.compile(r'^\s*\d*\.?\d+(?:\s*/\s*\d*\.?\d+)*\s*$')

# Set QT_QPA_PLATFORM for headless rendering and suppress Qt warnings
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.*=false'
os.environ['QT_DEBUG_PLUGINS'] = '0'


def detect_tree_format(filepath):
    """
    Heuristically detect tree format by extension/content.
    Returns one of: 'newick', 'nexus', 'phyloxml'.
    Defaults to newick.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.nexus', '.nex']:
        return 'nexus'
    if ext in ['.xml', '.phyloxml']:
        return 'phyloxml'

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            head = f.read(2048)
            if '#NEXUS' in head.upper():
                return 'nexus'
            if '<phyloxml' in head.lower():
                return 'phyloxml'
    except Exception:
        pass

    return 'newick'


def normalize_tree_file(filepath):
    """
    Normalize various tree formats to a Newick file for downstream rendering.
    Tries to auto-detect format using Biopython.
    Returns (path_to_newick, error_message).
    """
    try:
        from Bio import Phylo
    except ImportError:
        msg = "Biopython not installed; cannot convert non-Newick tree"
        logger.warning(msg)
        return None, msg

    # First, try to read as Newick as it's the most common format
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(2048).strip()
            # Simple check for Newick format
            if content.startswith('(') and content.endswith(';'):
                # It looks like a Newick tree, check if ete3 can read it directly
                from ete3 import Tree
                Tree(filepath)
                return filepath, None
    except Exception:
        pass # Not a simple Newick, try conversion

    # Try converting with Bio.Phylo using common formats
    for fmt in ['nexus', 'phyloxml', 'nexml', 'newick']:
        try:
            tree = Phylo.read(filepath, fmt)
            normalized = filepath + '.normalized.nwk'
            Phylo.write(tree, normalized, 'newick')
            logger.info(f"Successfully converted tree from '{fmt}' format.")
            return normalized, None
        except Exception:
            continue  # Try next format

    # If all conversions fail
    msg = "Could not parse tree file. Supported formats are Newick, Nexus, PhyloXML, and NeXML."
    logger.error(msg)
    return None, msg


def read_newick(filepath):
    """
    Read a tree file (any supported format) as text.
    Returns tree string.
    """
    normalized, err = normalize_tree_file(filepath)
    if err:
        raise ValueError(err)
    with open(normalized, 'r') as f:
        return f.read().strip()


def extract_species_prefix(node_name):
    """
    Extract species prefix from node name.
    Pattern: ^([a-zA-Z_]+)
    """
    match = re.match(r'^([a-zA-Z_]+)', node_name)
    return match.group(1) if match else None


def _support_to_percent(raw_value):
    """
    Normalize support value to 0-100 scale.
    Accepts:
    - float/int in 0-1 (converted to 0-100)
    - float/int in 1-100 (kept as-is)
    - string-like values (first token parsed)
    """
    if raw_value in (None, ''):
        return None
    try:
        if isinstance(raw_value, str):
            raw_value = raw_value.split('/')[0].strip()
        value = float(raw_value)
    except (TypeError, ValueError):
        return None

    if 0 <= value <= 1:
        value *= 100.0
    if value < 0:
        return None
    return value


def _extract_support_values(raw_value):
    """
    Extract one or more support values from a label like ``95`` or ``80/95``.
    """
    if raw_value in (None, ''):
        return []

    if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
        parsed = _support_to_percent(raw_value)
        return [float(parsed)] if parsed is not None else []

    text = str(raw_value).strip()
    if not text or not SUPPORT_LABEL_RE.fullmatch(text):
        return []

    values = []
    for token in text.split('/'):
        parsed = _support_to_percent(token.strip())
        if parsed is None:
            return []
        values.append(float(parsed))
    return values


def _get_node_support_values(node):
    """
    Return support values for an internal node.

    With ETE ``format=1``, internal labels are commonly stored in ``node.name``
    while ``node.support`` stays at the placeholder value ``1.0``. Prefer the
    explicit label so real support values are not silently turned into 100.
    """
    name_values = _extract_support_values(getattr(node, 'name', None))
    if name_values:
        return name_values

    raw_support = getattr(node, 'support', None)
    if raw_support in (None, ''):
        return []

    if isinstance(raw_support, (int, float)) and not isinstance(raw_support, bool) and float(raw_support) == 1.0:
        return []

    return _extract_support_values(raw_support)


def _format_support_value(value):
    if value is None:
        return None
    rounded = round(float(value), 2)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.2f}".rstrip('0').rstrip('.')


def _format_support_label(values):
    if not values:
        return None
    return '/'.join(_format_support_value(value) for value in values if value is not None)


def _select_support_value(values, support_metric='trailing'):
    if not values:
        return None
    if support_metric == 'leading' and len(values) > 1:
        return float(values[0])
    return float(values[-1])


def _other_support_values(values, support_metric='trailing'):
    if len(values) <= 1:
        return []
    if support_metric == 'leading':
        return [float(v) for v in values[1:]]
    return [float(v) for v in values[:-1]]


def _summarize_bootstrap_support(tree_obj, low_threshold=None, support_metric='trailing'):
    """
    Summarize internal-node bootstrap support in a tree.
    """
    supports = []
    other_supports = []
    composite_label_count = 0
    for node in tree_obj.traverse():
        if node.is_leaf():
            continue
        values = _get_node_support_values(node)
        if not values:
            continue
        selected = _select_support_value(values, support_metric=support_metric)
        if selected is not None:
            supports.append(selected)
        if len(values) > 1:
            composite_label_count += 1
            other_supports.extend(_other_support_values(values, support_metric=support_metric))

    metric_label = 'leading value' if support_metric == 'leading' else 'trailing value'
    other_metric_label = 'trailing value' if support_metric == 'leading' else 'leading value'

    summary = {
        'internal_nodes_total': sum(1 for n in tree_obj.traverse() if not n.is_leaf()),
        'internal_nodes_with_support': len(supports),
        'support_min': round(min(supports), 2) if supports else None,
        'support_max': round(max(supports), 2) if supports else None,
        'support_mean': round(sum(supports) / len(supports), 2) if supports else None,
        'support_other_min': round(min(other_supports), 2) if other_supports else None,
        'support_other_max': round(max(other_supports), 2) if other_supports else None,
        'support_other_mean': round(sum(other_supports) / len(other_supports), 2) if other_supports else None,
        'support_label_mode': 'composite' if composite_label_count else 'single',
        'composite_support_labels': composite_label_count > 0,
        'composite_label_count': composite_label_count,
        'support_metric_used': support_metric if composite_label_count else 'single',
        'support_metric_label': metric_label if composite_label_count else 'single value',
        'support_other_metric_label': other_metric_label if composite_label_count else None,
        'low_support_threshold': float(low_threshold) if low_threshold is not None else None,
        'low_support_count': None
    }
    if low_threshold is not None and supports:
        summary['low_support_count'] = sum(1 for s in supports if s < float(low_threshold))
    elif low_threshold is not None:
        summary['low_support_count'] = 0
    return summary


def get_species_from_tree(tree_string):
    """
    Get list of unique species prefixes from tree.
    """
    # Extract leaf names from Newick format
    # Simple regex to find names before :
    names = re.findall(r'([a-zA-Z_]+[a-zA-Z0-9_]*)[:\),]', tree_string)

    species = set()
    for name in names:
        prefix = extract_species_prefix(name)
        if prefix:
            species.add(prefix)

    return sorted(species)


def visualize_tree(tree_file, output_file=None, layout='rectangular',
                   colored_species=None, highlighted_genes=None,
                   show_bootstrap=True, font_size=10, v_scale=1.0,
                   center_gene=None, radius_edges=3, highlight_species=None,
                   fixed_branch_length=False, low_bootstrap_threshold=None,
                   support_metric='trailing',
                   low_bootstrap_color='#d62828'):
    """
    Visualize a phylogenetic tree.

    Args:
        tree_file: Path to Newick tree file
        output_file: Path for output SVG (optional, will create if not specified)
        layout: 'circular' or 'rectangular'
        colored_species: Dict of {species_prefix: color}
        highlighted_genes: List of gene names to highlight (yellow background)
        show_bootstrap: Whether to show bootstrap values
        font_size: Font size for labels
        v_scale: Vertical scale factor
        center_gene: Gene to center view on
        radius_edges: Radius around center gene
        highlight_species: List of species prefixes to highlight with background

    Returns:
        (success, result_dir, output_file, message, support_stats)
    """
    try:
        from ete3 import Tree, TreeStyle, NodeStyle, TextFace, AttrFace
    except ImportError:
        logger.error("ETE3 not installed")
        return False, None, None, "ETE3 library not installed", None

    if colored_species is None:
        colored_species = {}
    if highlighted_genes is None:
        highlighted_genes = []
    if highlight_species is None:
        highlight_species = []

    result_dir = create_result_dir('tree', 'visualization')

    # Save parameters
    params = {
        'tree_file': tree_file,
        'layout': layout,
        'colored_species': colored_species,
        'highlighted_genes': highlighted_genes,
        'highlight_species': highlight_species,
        'show_bootstrap': show_bootstrap,
        'font_size': font_size,
        'v_scale': v_scale,
        'low_bootstrap_threshold': low_bootstrap_threshold,
        'support_metric': support_metric,
        'low_bootstrap_color': low_bootstrap_color,
        'timestamp': datetime.now().isoformat()
    }
    params['fixed_branch_length'] = fixed_branch_length
    save_params(result_dir, params)

    if output_file is None:
        output_file = os.path.join(result_dir, 'tree.svg')

    # Normalize tree file (handles nexus/phyloxml -> newick)
    normalized_tree, error_message = normalize_tree_file(tree_file)
    if error_message:
        return False, result_dir, None, error_message, None

    try:
        # Load tree
        tree = Tree(normalized_tree, format=1)

        # If a center gene is provided, prune to a neighborhood around it
        if center_gene:
            # Search for the center node in both leaves and internal nodes
            target_nodes = tree.search_nodes(name=center_gene)
            if not target_nodes:
                return False, result_dir, None, f"Center gene not found: {center_gene}", None
            target = target_nodes[0]

            # Collect leaves within radius_edges
            # Use branch distance for better results
            leaves_to_keep = []
            try:
                for leaf in tree.get_leaves():
                    # Get distance in number of branches (count_leaves gives leaf count in subtree, not distance)
                    # Use get_distance which returns branch length by default
                    dist = target.get_distance(leaf, topology_only=True)  # topology_only counts branches
                    if dist <= max(1, int(radius_edges)):
                        leaves_to_keep.append(leaf.name)
            except Exception as e:
                logger.warning(f"Distance calculation error: {e}, trying leaf-based approach")
                # Fallback: keep all leaves descended from target
                for leaf in tree.get_leaves():
                    if leaf in target:
                        leaves_to_keep.append(leaf.name)

            if not leaves_to_keep:
                return False, result_dir, None, f"No leaves within radius {radius_edges} of {center_gene}. Try increasing radius or ensure gene name is exact.", None

            # Prune and set outgroup
            tree.prune(leaves_to_keep, preserve_branch_length=True)
            try:
                tree.set_outgroup(center_gene)
            except Exception:
                pass

        # Apply fixed branch length if requested
        if fixed_branch_length:
            for n in tree.traverse():
                n.dist = 1.0

        # Calculate adaptive width based on number of leaves
        num_leaves = len(tree.get_leaves())
        # Base width calculation: ensure readable spacing
        adaptive_width = max(800, min(2400, num_leaves * 15))
        
        # Create tree style
        ts = TreeStyle()
        ts.mode = 'c' if layout == 'circular' else 'r'
        ts.show_leaf_name = False
        ts.show_branch_length = False
        ts.show_branch_support = False
        ts.scale = 100  # pixels per branch unit
        ts.branch_vertical_margin = 10 * v_scale

        support_stats = _summarize_bootstrap_support(tree, low_bootstrap_threshold, support_metric)

        # Apply styles to nodes
        for node in tree.traverse():
            if node.is_leaf():
                # Get species prefix
                prefix = extract_species_prefix(node.name)

                # Create node style
                nstyle = NodeStyle()
                nstyle['size'] = 0  # Hide node circles

                # Set background color only if species is selected for highlight
                if prefix in highlight_species and prefix in colored_species:
                    nstyle['bgcolor'] = colored_species[prefix]

                # Highlight specific genes (stronger highlight, overrides species color)
                if node.name in highlighted_genes:
                    nstyle['bgcolor'] = '#ffff00'  # Yellow background

                node.set_style(nstyle)

                # Add name face - text is always black
                name_face = TextFace(node.name, fsize=font_size)
                name_face.fgcolor = '#000000'  # Black for all species text
                node.add_face(name_face, column=0, position='branch-right')

            else:
                support_values = _get_node_support_values(node)
                support_percent = _select_support_value(support_values, support_metric=support_metric)
                support_label = _format_support_label(support_values)
                if (
                    low_bootstrap_threshold is not None
                    and support_percent is not None
                    and support_percent < float(low_bootstrap_threshold)
                ):
                    nstyle = NodeStyle()
                    nstyle['size'] = 0
                    nstyle['hz_line_color'] = low_bootstrap_color
                    nstyle['vt_line_color'] = low_bootstrap_color
                    nstyle['hz_line_width'] = 2
                    nstyle['vt_line_width'] = 2
                    node.set_style(nstyle)

                # Internal node - show bootstrap if available
                if show_bootstrap and support_label is not None:
                    support_face = TextFace(support_label, fsize=font_size-2)
                    support_face.fgcolor = '#666666'
                    node.add_face(support_face, column=0, position='branch-top')

        # Render tree with adaptive width
        tree.render(output_file, tree_style=ts, w=adaptive_width, units='px')

        logger.info(f"Tree visualization saved to {output_file}")
        # Return relative path from results directory for proper web serving
        rel_path = os.path.relpath(output_file, config.RESULTS_DIR)
        return True, result_dir, rel_path, "Tree visualization completed", support_stats

    except Exception as e:
        logger.error(f"Tree visualization failed: {str(e)}")
        return False, result_dir, None, str(e), None


def get_tree_info(tree_file):
    """
    Get basic information about a tree.
    Returns (info_dict, error_message).
    """
    try:
        from ete3 import Tree
    except ImportError:
        return None, "ETE3 library not installed"

    normalized_tree, error_message = normalize_tree_file(tree_file)
    if error_message:
        return None, error_message

    try:
        tree = Tree(normalized_tree, format=1)

        leaves = [leaf.name for leaf in tree.get_leaves()]
        all_nodes = [node.name for node in tree.traverse()]
        species = set()
        for name in leaves:
            prefix = extract_species_prefix(name)
            if prefix:
                species.add(prefix)

        # Check if tree has support values
        has_support = any(_get_node_support_values(node) for node in tree.traverse() if not node.is_leaf())
        support_stats = _summarize_bootstrap_support(tree)

        info = {
            'species': sorted(species),
            'leaf_count': len(leaves),
            'has_support': has_support,
            'support_stats': support_stats,
            'leaves': leaves,
            'all_nodes': [n for n in all_nodes if n]  # Filter empty names
        }
        return info, None

    except Exception as e:
        msg = f"Failed to parse tree file: {e}"
        logger.error(msg)
        return None, msg


# Default color palette for species
DEFAULT_COLORS = [
    '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
    '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe',
    '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000',
    '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080'
]


def get_default_colors(species_list):
    """
    Assign default colors to species.
    """
    colors = {}
    for i, species in enumerate(species_list):
        colors[species] = DEFAULT_COLORS[i % len(DEFAULT_COLORS)]
    return colors


def extract_clade(tree_file, target_gene, levels_up=2, output_file=None,
                  layout='rectangular', colored_species=None,
                  show_bootstrap=True, font_size=10, v_scale=1.0, fixed_branch_length=False,
                  highlight_species=None, low_bootstrap_threshold=None,
                  support_metric='trailing',
                  low_bootstrap_color='#d62828'):
    """
    Extract and visualize a clade around a target gene.
    Goes 'levels_up' ancestors from the target gene.
    
    Args:
        tree_file: Path to tree file
        target_gene: Gene name to center on
        levels_up: Number of ancestor levels to go up (default 2)
        layout: 'circular' or 'rectangular'
        colored_species: Dict of {species_prefix: color}
        show_bootstrap: Show bootstrap values
        font_size: Font size for labels
        v_scale: Vertical spacing scale factor
        fixed_branch_length: If True, use uniform branch lengths
        highlight_species: List of species prefixes to highlight with background
    
    Returns:
        (success, result_dir, output_file, message, clade_info)
    """
    try:
        from ete3 import Tree, TreeStyle, NodeStyle, TextFace
    except ImportError:
        return False, None, None, "ETE3 not installed", None

    result_dir = create_result_dir('tree', 'clade')
    
    if colored_species is None:
        colored_species = {}
    if highlight_species is None:
        highlight_species = []

    try:
        normalized_tree, error_message = normalize_tree_file(tree_file)
        if error_message:
            return False, result_dir, None, error_message, None

        tree = Tree(normalized_tree, format=1)
        
        # Find target node
        target_nodes = tree.search_nodes(name=target_gene)
        if not target_nodes:
            return False, result_dir, None, f"Gene not found: {target_gene}", None
        target = target_nodes[0]
        
        # Go up 'levels_up' ancestors
        ancestor = target
        actual_levels = 0
        for i in range(levels_up):
            if ancestor.up:
                ancestor = ancestor.up
                actual_levels += 1
            else:
                break
        
        # Get clade info
        clade_leaves = [leaf.name for leaf in ancestor.get_leaves()]
        clade_info = {
            'target_gene': target_gene,
            'levels_up': actual_levels,
            'leaf_count': len(clade_leaves),
            'leaves': clade_leaves
        }
        
        # Create subtree copy
        display_tree = ancestor.copy()
        
        # Apply fixed branch length if requested
        if fixed_branch_length:
            for n in display_tree.traverse():
                n.dist = 1.0

        clade_info['support_stats'] = _summarize_bootstrap_support(
            display_tree,
            low_bootstrap_threshold,
            support_metric
        )
        
        # Style nodes
        for node in display_tree.traverse():
            if node.is_leaf():
                nstyle = NodeStyle()
                nstyle['size'] = 0
                
                prefix = extract_species_prefix(node.name)

                # Set background color only if species is selected for highlight
                if prefix in highlight_species and prefix in colored_species:
                    nstyle['bgcolor'] = colored_species[prefix]
                
                # Highlight target gene (strongest highlight, overrides species color)
                if node.name == target_gene:
                    nstyle['bgcolor'] = '#ffff00'
                
                node.set_style(nstyle)
                
                # Add name face - text is always black
                face_text = f"→ {node.name}" if node.name == target_gene else node.name
                face = TextFace(face_text, fsize=font_size, bold=(node.name == target_gene))
                face.fgcolor = '#000000'  # Black for all species text
                    
                node.add_face(face, column=0, position='branch-right')
            
            else:
                support_values = _get_node_support_values(node)
                support_percent = _select_support_value(support_values, support_metric=support_metric)
                support_label = _format_support_label(support_values)
                if (
                    low_bootstrap_threshold is not None
                    and support_percent is not None
                    and support_percent < float(low_bootstrap_threshold)
                ):
                    nstyle = NodeStyle()
                    nstyle['size'] = 0
                    nstyle['hz_line_color'] = low_bootstrap_color
                    nstyle['vt_line_color'] = low_bootstrap_color
                    nstyle['hz_line_width'] = 2
                    nstyle['vt_line_width'] = 2
                    node.set_style(nstyle)

                if show_bootstrap and support_label is not None:
                    face = TextFace(support_label, fsize=font_size-2, fgcolor='#666')
                    node.add_face(face, column=0, position='branch-top')
        
        # Tree style
        ts = TreeStyle()
        ts.mode = 'c' if layout == 'circular' else 'r'
        ts.show_leaf_name = False
        ts.show_branch_support = False
        ts.branch_vertical_margin = max(2.0, 15.0 * float(v_scale or 1.0))
        
        # Add legend
        if colored_species:
            ts.legend.add_face(TextFace("Species Legend", bold=True, fsize=12), column=0)
            for sp, color in colored_species.items():
                ts.legend.add_face(TextFace(f"  {sp}", fgcolor=color, fsize=10), column=0)
        
        # Output file
        if output_file is None:
            output_file = os.path.join(result_dir, f'{target_gene}_L{actual_levels}_{layout}.svg')
        
        # Render with adaptive width
        width = max(800, min(2400, len(clade_leaves) * 15))
        display_tree.render(output_file, tree_style=ts, w=width, units='px')
        
        rel_path = os.path.relpath(output_file, config.RESULTS_DIR)
        return True, result_dir, rel_path, f"Clade extracted: {len(clade_leaves)} leaves", clade_info
        
    except Exception as e:
        logger.error(f"Clade extraction failed: {e}")
        return False, result_dir, None, str(e), None
