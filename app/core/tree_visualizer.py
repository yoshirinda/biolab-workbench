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


def read_newick(filepath):
    """
    Read a Newick tree file.
    Returns tree string.
    """
    with open(filepath, 'r') as f:
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
                   show_bootstrap=True, font_size=10, v_scale=1.0):
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

    result_dir = create_result_dir('tree', 'visualization')

    # Save parameters
    params = {
        'tree_file': tree_file,
        'layout': layout,
        'colored_species': colored_species,
        'highlighted_genes': highlighted_genes,
        'show_bootstrap': show_bootstrap,
        'font_size': font_size,
        'v_scale': v_scale,
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)

    if output_file is None:
        output_file = os.path.join(result_dir, 'tree.svg')

    try:
        # Load tree
        tree = Tree(tree_file, format=1)

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

                # Highlight specific genes
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

        # Render tree
        tree.render(output_file, tree_style=ts, w=1200, units='px')

        logger.info(f"Tree visualization saved to {output_file}")
        return True, result_dir, output_file, "Tree visualization completed"

    except Exception as e:
        logger.error(f"Tree visualization failed: {str(e)}")
        return False, result_dir, None, str(e)


def get_tree_info(tree_file):
    """
    Get basic information about a tree.
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
            'has_support': None
        }

    try:
        tree = Tree(tree_file, format=1)

        leaves = [leaf.name for leaf in tree.get_leaves()]
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
            'leaves': leaves[:100]  # First 100 leaves
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
