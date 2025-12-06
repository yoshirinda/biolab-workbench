"""
Tree visualization module for BioLab Workbench.
Uses ETE3 for tree visualization.
"""
import os
import re
from datetime import datetime
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params

logger = get_tools_logger()

# Set QT_QPA_PLATFORM for headless rendering
os.environ['QT_QPA_PLATFORM'] = 'offscreen'


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
    Returns the path to a Newick file (original if already Newick).
    """
    fmt = detect_tree_format(filepath)
    if fmt == 'newick':
        return filepath

    try:
        from Bio import Phylo
    except ImportError:
        logger.warning("Biopython not installed; cannot convert non-Newick tree")
        return filepath

    try:
        tree = Phylo.read(filepath, fmt)
        # Write to a normalized Newick file alongside the original
        normalized = filepath + '.normalized.nwk'
        Phylo.write(tree, normalized, 'newick')
        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize tree ({fmt}): {e}")
        return filepath


def read_newick(filepath):
    """
    Read a tree file (any supported format) as text.
    Returns tree string.
    """
    normalized = normalize_tree_file(filepath)
    with open(normalized, 'r') as f:
        return f.read().strip()


def extract_species_prefix(node_name):
    """
    Extract species prefix from node name.
    Pattern: ^([a-zA-Z_]+)
    """
    match = re.match(r'^([a-zA-Z_]+)', node_name)
    return match.group(1) if match else None


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
                   center_gene=None, radius_edges=3, highlight_species=None):
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
        (success, result_dir, output_file, message)
    """
    try:
        from ete3 import Tree, TreeStyle, NodeStyle, TextFace, AttrFace
    except ImportError:
        logger.error("ETE3 not installed")
        return False, None, None, "ETE3 library not installed"

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
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)

    if output_file is None:
        output_file = os.path.join(result_dir, 'tree.svg')

    # Normalize tree file (handles nexus/phyloxml -> newick)
    normalized_tree = normalize_tree_file(tree_file)

    try:
        # Load tree
        tree = Tree(normalized_tree, format=1)

        # If a center gene is provided, prune to a neighborhood around it
        if center_gene:
            # Search for the center node in both leaves and internal nodes
            target_nodes = tree.search_nodes(name=center_gene)
            if not target_nodes:
                return False, result_dir, None, f"Center gene not found: {center_gene}"
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
                return False, result_dir, None, f"No leaves within radius {radius_edges} of {center_gene}. Try increasing radius or ensure gene name is exact."

            # Prune and set outgroup
            tree.prune(leaves_to_keep, preserve_branch_length=True)
            try:
                tree.set_outgroup(center_gene)
            except Exception:
                pass

        # Calculate adaptive width based on number of leaves
        num_leaves = len(tree.get_leaves())
        # Base width calculation: ensure readable spacing
        adaptive_width = max(800, min(2400, num_leaves * 15))
        
        # Create tree style
        ts = TreeStyle()
        ts.mode = 'c' if layout == 'circular' else 'r'
        ts.show_leaf_name = True
        ts.show_branch_length = False
        ts.show_branch_support = show_bootstrap
        ts.scale = 100  # pixels per branch unit
        ts.branch_vertical_margin = 10 * v_scale

        # Apply styles to nodes
        for node in tree.traverse():
            if node.is_leaf():
                # Get species prefix
                prefix = extract_species_prefix(node.name)

                # Create node style
                nstyle = NodeStyle()

                # Color by species
                if prefix in colored_species:
                    nstyle['fgcolor'] = colored_species[prefix]

                # Highlight by species (light background)
                if prefix in highlight_species:
                    nstyle['bgcolor'] = '#ffffcc'  # Light yellow background

                # Highlight specific genes (stronger highlight)
                if node.name in highlighted_genes:
                    nstyle['bgcolor'] = '#ffff00'  # Yellow background

                nstyle['size'] = 0  # Hide node circles

                node.set_style(nstyle)

                # Add name face
                name_face = TextFace(node.name, fsize=font_size)
                if prefix in colored_species:
                    name_face.fgcolor = colored_species[prefix]
                node.add_face(name_face, column=0, position='branch-right')

            else:
                # Internal node - show bootstrap if available
                if show_bootstrap and node.support:
                    support_face = TextFace(f"{node.support:.0f}", fsize=font_size-2)
                    support_face.fgcolor = '#666666'
                    node.add_face(support_face, column=0, position='branch-top')

        # Render tree with adaptive width
        tree.render(output_file, tree_style=ts, w=adaptive_width, units='px')

        logger.info(f"Tree visualization saved to {output_file}")
        # Return relative path from results directory for proper web serving
        rel_path = os.path.relpath(output_file, config.RESULTS_DIR)
        return True, result_dir, rel_path, "Tree visualization completed"

    except Exception as e:
        logger.error(f"Tree visualization failed: {str(e)}")
        return False, result_dir, None, str(e)


def get_tree_info(tree_file):
    """
    Get basic information about a tree.
    Returns species, leaves, and all nodes for center-gene search.
    """
    try:
        from ete3 import Tree
    except ImportError:
        # Fallback without ETE3
        tree_string = read_newick(tree_file)
        species = get_species_from_tree(tree_string)
        return {
            'species': species,
            'leaf_count': None,
            'has_support': None,
            'leaves': [],
            'all_nodes': []
        }

    try:
        normalized_tree = normalize_tree_file(tree_file)
        tree = Tree(normalized_tree, format=1)

        leaves = [leaf.name for leaf in tree.get_leaves()]
        all_nodes = [node.name for node in tree.traverse()]
        species = set()
        for name in leaves:
            prefix = extract_species_prefix(name)
            if prefix:
                species.add(prefix)

        # Check if tree has support values
        has_support = any(node.support for node in tree.traverse() if not node.is_leaf())

        return {
            'species': sorted(species),
            'leaf_count': len(leaves),
            'has_support': has_support,
            'leaves': leaves,
            'all_nodes': [n for n in all_nodes if n]  # Filter empty names
        }

    except Exception as e:
        logger.error(f"Failed to get tree info: {str(e)}")
        return None


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
                  show_bootstrap=True, font_size=10, fixed_branch_length=False,
                  highlight_species=None):
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
        normalized_tree = normalize_tree_file(tree_file)
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
        
        # Style nodes
        for node in display_tree.traverse():
            if node.is_leaf():
                nstyle = NodeStyle()
                nstyle['size'] = 0
                
                prefix = extract_species_prefix(node.name)
                
                # Highlight by species (light background)
                if prefix in highlight_species:
                    nstyle['bgcolor'] = '#ffffcc'
                
                # Color by species (as border/text color)
                if prefix in colored_species:
                    nstyle['fgcolor'] = colored_species[prefix]
                
                # Highlight target gene (strongest highlight)
                if node.name == target_gene:
                    nstyle['bgcolor'] = '#ffff00'
                
                node.set_style(nstyle)
                
                # Add name face
                face_text = f"→ {node.name}" if node.name == target_gene else node.name
                face = TextFace(face_text, fsize=font_size, bold=(node.name == target_gene))
                if prefix in colored_species:
                    face.fgcolor = colored_species[prefix]
                node.add_face(face, column=0, position='branch-right')
            
            elif show_bootstrap and node.name:
                # Show bootstrap values
                try:
                    val = float(node.name.split('/')[0])
                    if 0 <= val <= 1:
                        val = int(val * 100)
                    face = TextFace(str(int(val)), fsize=font_size-2, fgcolor='#666')
                    node.add_face(face, column=0, position='branch-top')
                except (ValueError, IndexError):
                    pass
        
        # Tree style
        ts = TreeStyle()
        ts.mode = 'c' if layout == 'circular' else 'r'
        ts.show_leaf_name = False
        ts.show_branch_support = False
        ts.branch_vertical_margin = 15
        
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
