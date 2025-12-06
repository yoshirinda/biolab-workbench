"""
Alternative tree renderer using Biopython Phylo + Matplotlib
Avoids Qt dependencies and ETE3 segmentation faults
"""
import os
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch
from matplotlib.lines import Line2D
from Bio import Phylo
from Bio.Phylo import draw
from io import StringIO
import math

from app.utils.logger import get_tools_logger

logger = get_tools_logger()


class PhyloRenderer:
    """Render phylogenetic trees using Bio.Phylo + Matplotlib"""
    
    def __init__(self, tree_file, format='newick'):
        """
        Initialize renderer with tree file
        
        Args:
            tree_file: Path to tree file
            format: Tree format (newick, nexus, phyloxml)
        """
        self.tree_file = tree_file
        self.format = format
        self.tree = None
        self._filtered_terminals = None
        self.load_tree()
        
    def load_tree(self):
        """Load tree from file"""
        try:
            self.tree = Phylo.read(self.tree_file, self.format)
            logger.info(f"Loaded tree with {self.tree.count_terminals()} leaves")
        except Exception as e:
            logger.error(f"Failed to load tree: {e}")
            raise
            
    def _prune_tree_to_clade(self, terminal_names):
        """
        Create a pruned tree containing only specified terminals
        
        Args:
            terminal_names: List of terminal names to keep
            
        Returns:
            New Phylo tree object
        """
        # Get terminals to remove
        all_terminals = [t.name for t in self.tree.get_terminals()]
        to_remove = [t for t in all_terminals if t not in terminal_names]
        
        # Make a copy of the tree
        from copy import deepcopy
        pruned_tree = deepcopy(self.tree)
        
        # Remove unwanted terminals
        for term_name in to_remove:
            try:
                terminal = next(t for t in pruned_tree.get_terminals() if t.name == term_name)
                pruned_tree.prune(terminal)
            except (StopIteration, ValueError):
                pass
                
        return pruned_tree
            
    def extract_subtree(self, target_gene, levels_up=5):
        """
        Extract subtree around target gene
        
        Args:
            target_gene: Gene name to center on
            levels_up: Number of parent levels to include
            
        Returns:
            Bio.Phylo.BaseTree object or None
        """
        if not self.tree:
            return None
            
        # Find target terminal
        target_terminal = None
        for terminal in self.tree.get_terminals():
            if target_gene in terminal.name:
                target_terminal = terminal
                break
                
        if not target_terminal:
            logger.warning(f"Target gene {target_gene} not found in tree")
            return None
            
        # Find ancestor at specified level
        path = self.tree.get_path(target_terminal)
        
        if len(path) <= levels_up + 1:
            # Return whole tree if levels exceed depth
            logger.info(f"Levels ({levels_up}) exceed tree depth ({len(path)-1}), returning full tree")
            return self.tree
            
        # Get ancestor node (levels_up steps from target)
        ancestor_node = path[-(levels_up + 1)]
        
        # Get all terminals under this ancestor
        ancestor_terminals = [term for term in self.tree.get_terminals() 
                             if ancestor_node in self.tree.get_path(term)]
        
        # Create a new tree with just these terminals
        # (Bio.Phylo doesn't have direct subtree extraction like ETE3)
        # So we return the full tree but will filter in rendering
        logger.info(f"Extracted clade with {len(ancestor_terminals)} leaves")
        
        # For Bio.Phylo, we need to work with the full tree
        # We'll mark which terminals to display
        self._filtered_terminals = set(t.name for t in ancestor_terminals)
        
        return self.tree
        
    def render_tree(self, output_file, highlighted_species=None, layout='rectangular', 
                   show_labels=True, label_colors=None):
        """
        Render tree to SVG file
        
        Args:
            output_file: Output SVG path
            highlighted_species: List of species prefixes to highlight
            layout: 'rectangular' or 'circular'
            show_labels: Whether to show leaf labels
            label_colors: Dict mapping species prefix to color hex
        """
        if not self.tree:
            logger.error("No tree loaded")
            return False
            
        try:
            # Calculate figure size based on number of leaves
            num_leaves = self.tree.count_terminals()
            
            if layout == 'circular':
                # Square figure for circular layout
                size = max(8, min(20, num_leaves * 0.3))
                fig = plt.figure(figsize=(size, size), dpi=150)
                ax = fig.add_subplot(1, 1, 1)
                
                # Use Bio.Phylo's draw function for circular
                Phylo.draw(self.tree, do_show=False, axes=ax)
                
            else:
                # Rectangular layout
                height = max(6, min(50, num_leaves * 0.15))
                width = max(8, min(24, height * 0.8))
                fig = plt.figure(figsize=(width, height), dpi=150)
                ax = fig.add_subplot(1, 1, 1)
                
                # Draw tree
                Phylo.draw(self.tree, do_show=False, axes=ax, 
                          show_confidence=False, 
                          label_func=lambda x: x.name if x.is_terminal() else '')
                
            # Apply custom colors to labels if specified
            if highlighted_species and label_colors:
                self._apply_label_colors(ax, highlighted_species, label_colors)
                
            # Set title
            ax.set_title(f"Phylogenetic Tree ({num_leaves} taxa)", 
                        fontsize=12, pad=10)
            
            # Remove axis
            ax.axis('off')
            
            # Tight layout
            plt.tight_layout()
            
            # Save as SVG
            plt.savefig(output_file, format='svg', 
                       bbox_inches='tight', 
                       facecolor='white',
                       edgecolor='none')
            plt.close(fig)
            
            logger.info(f"Rendered tree to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to render tree: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def _apply_label_colors(self, ax, highlighted_species, label_colors):
        """
        Apply custom colors to leaf labels
        
        Args:
            ax: Matplotlib axes
            highlighted_species: List of species prefixes to highlight
            label_colors: Dict mapping species prefix to color hex
        """
        for text in ax.texts:
            label = text.get_text()
            if not label:
                continue
                
            # Check if label matches any highlighted species
            matched_prefix = None
            for prefix in highlighted_species:
                if label.startswith(prefix):
                    matched_prefix = prefix
                    break
                    
            if matched_prefix and matched_prefix in label_colors:
                # Apply color to highlighted species
                text.set_color(label_colors[matched_prefix])
                text.set_fontweight('bold')
            else:
                # Black for non-highlighted
                text.set_color('#000000')
                
    def render_subtree(self, output_file, target_gene, levels_up=5, 
                      highlighted_species=None, layout='rectangular',
                      label_colors=None):
        """
        Extract and render subtree around target gene
        
        Args:
            output_file: Output SVG path
            target_gene: Gene name to center on  
            levels_up: Number of parent levels to include
            highlighted_species: List of species prefixes to highlight
            layout: 'rectangular' or 'circular'
            label_colors: Dict mapping species prefix to color hex
        """
        # Extract subtree
        _ = self.extract_subtree(target_gene, levels_up)
        
        if not self._filtered_terminals:
            logger.error(f"Failed to extract subtree for {target_gene}")
            return False
            
        # Create pruned tree with only clade terminals
        pruned_tree = self._prune_tree_to_clade(list(self._filtered_terminals))
        
        # Temporarily replace tree
        original_tree = self.tree
        self.tree = pruned_tree
        
        # Render
        success = self.render_tree(output_file, highlighted_species, 
                                   layout, True, label_colors)
        
        # Restore original tree
        self.tree = original_tree
        self._filtered_terminals = None
        
        return success
