"""
High-quality tree renderer using Biopython Phylo + Matplotlib
Beautiful visualization with custom styling and layout
"""
import os
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, FancyBboxPatch
from matplotlib.lines import Line2D
from Bio import Phylo
import numpy as np
import math
from io import StringIO

from app.utils.logger import get_tools_logger

logger = get_tools_logger()


class PhyloRenderer:
    """Render beautiful phylogenetic trees using Bio.Phylo + custom Matplotlib styling"""
    
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
        self.target_gene = None
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
        
    def _get_species_prefix(self, gene_name):
        """Extract species prefix from gene name (e.g., 'AT' from 'AT1G12345')"""
        if not gene_name:
            return None
        # Try common patterns: AT, Os, Sl, Mp, etc.
        import re
        match = re.match(r'^([A-Z][a-z]?)', gene_name)
        if match:
            return match.group(1)
        return None
            
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
        Render beautiful tree to SVG file with custom styling
        
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
            num_leaves = self.tree.count_terminals()
            
            if layout == 'circular':
                return self._render_circular(output_file, highlighted_species, label_colors, num_leaves)
            else:
                return self._render_rectangular(output_file, highlighted_species, label_colors, num_leaves)
                
        except Exception as e:
            logger.error(f"Failed to render tree: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def _render_rectangular(self, output_file, highlighted_species, label_colors, num_leaves):
        """Render rectangular layout with beautiful styling"""
        # Calculate adaptive figure size
        height = max(8, min(60, num_leaves * 0.2))
        width = max(10, min(28, height * 0.7))
        
        fig = plt.figure(figsize=(width, height), dpi=120)
        ax = fig.add_subplot(1, 1, 1)
        
        # Draw tree with custom styling
        def custom_label_func(clade):
            if clade.is_terminal():
                name = clade.name or ''
                prefix = self._get_species_prefix(name)
                
                # Add arrow for target gene
                if self.target_gene and name == self.target_gene:
                    return f'→ {name}'
                return name
            return ''
        
        # Use Phylo.draw with custom parameters
        Phylo.draw(self.tree, do_show=False, axes=ax,
                  show_confidence=False,
                  label_func=custom_label_func,
                  branch_labels=None)
        
        # Enhance the visualization
        self._style_tree_labels(ax, highlighted_species, label_colors)
        
        # Add target gene highlighting background
        if self.target_gene:
            self._highlight_target_gene(ax)
        
        # Style the plot
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        
        # Add title
        title_text = f'Phylogenetic Tree'
        if self.target_gene:
            title_text += f' centered on {self.target_gene}'
        title_text += f' ({num_leaves} taxa)'
        ax.set_title(title_text, fontsize=14, fontweight='bold', pad=20)
        
        # Add legend if colors specified
        if label_colors and highlighted_species:
            self._add_legend(ax, highlighted_species, label_colors)
        
        plt.tight_layout()
        plt.savefig(output_file, format='svg', bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close(fig)
        
        logger.info(f"Rendered rectangular tree to {output_file}")
        return True
        
    def _render_circular(self, output_file, highlighted_species, label_colors, num_leaves):
        """Render circular layout using custom polar coordinates"""
        try:
            # Calculate adaptive figure size
            size = max(10, min(24, num_leaves * 0.25))
            
            fig = plt.figure(figsize=(size, size), dpi=120)
            ax = fig.add_subplot(1, 1, 1, projection='polar')
            
            # Get terminal positions
            terminals = list(self.tree.get_terminals())
            n_terms = len(terminals)
            
            # Assign angles to terminals
            angles = np.linspace(0, 2 * np.pi, n_terms, endpoint=False)
            terminal_angles = {term.name: angle for term, angle in zip(terminals, angles)}
            
            # Calculate radial positions (depth from root)
            terminal_radii = {}
            for term in terminals:
                path = self.tree.get_path(term)
                depth = sum(getattr(node, 'branch_length', 1.0) or 1.0 for node in path)
                terminal_radii[term.name] = depth
            
            max_radius = max(terminal_radii.values()) if terminal_radii else 1.0
            
            # Draw branches
            for clade in self.tree.find_clades():
                if clade.is_terminal():
                    continue
                    
                # Get children
                children = list(clade)
                if len(children) < 2:
                    continue
                    
                # Calculate parent position
                child_angles = []
                for child in children:
                    if child.is_terminal():
                        child_angles.append(terminal_angles[child.name])
                    else:
                        # Average of descendant terminals
                        desc_terms = [t for t in child.get_terminals()]
                        child_angles.append(np.mean([terminal_angles[t.name] for t in desc_terms]))
                
                parent_angle = np.mean(child_angles)
                parent_path = self.tree.get_path(clade)
                parent_radius = sum(getattr(node, 'branch_length', 1.0) or 1.0 for node in parent_path[:-1])
                
                # Draw branches to children
                for child, child_angle in zip(children, child_angles):
                    if child.is_terminal():
                        child_radius = terminal_radii[child.name]
                    else:
                        child_path = self.tree.get_path(child)
                        child_radius = sum(getattr(node, 'branch_length', 1.0) or 1.0 for node in child_path[:-1])
                    
                    # Draw radial line
                    ax.plot([child_angle, child_angle], [parent_radius, child_radius],
                           color='#333333', linewidth=1.2, zorder=1)
                    
                    # Draw arc at parent level
                    if abs(child_angle - parent_angle) > 0.01:
                        arc_angles = np.linspace(min(child_angle, parent_angle),
                                                max(child_angle, parent_angle), 20)
                        arc_radii = [parent_radius] * len(arc_angles)
                        ax.plot(arc_angles, arc_radii, color='#333333', linewidth=1.2, zorder=1)
            
            # Draw terminal labels
            for term in terminals:
                angle = terminal_angles[term.name]
                radius = terminal_radii[term.name]
                name = term.name
                prefix = self._get_species_prefix(name)
                
                # Determine label properties
                is_target = (self.target_gene and name == self.target_gene)
                is_highlighted = (highlighted_species and prefix in highlighted_species)
                
                # Label styling
                if is_target:
                    label_text = f'→ {name}'
                    color = label_colors.get(prefix, '#FF0000') if label_colors else '#FF0000'
                    fontweight = 'bold'
                    fontsize = 10
                elif is_highlighted and label_colors and prefix in label_colors:
                    label_text = name
                    color = label_colors[prefix]
                    fontweight = 'bold'
                    fontsize = 9
                else:
                    label_text = name
                    color = '#000000'
                    fontweight = 'normal'
                    fontsize = 8
                
                # Adjust text rotation and alignment
                rotation = np.degrees(angle)
                if rotation > 90 and rotation < 270:
                    rotation = rotation + 180
                    ha = 'right'
                else:
                    ha = 'left'
                
                ax.text(angle, radius * 1.05, label_text,
                       rotation=rotation, rotation_mode='anchor',
                       ha=ha, va='center',
                       fontsize=fontsize, fontweight=fontweight, color=color, zorder=3)
            
            # Style polar plot
            ax.set_ylim(0, max_radius * 1.3)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.spines['polar'].set_visible(False)
            ax.grid(False)
            
            # Add title
            title_text = f'Circular Phylogenetic Tree'
            if self.target_gene:
                title_text += f'\ncentered on {self.target_gene}'
            title_text += f'\n({n_terms} taxa)'
            plt.title(title_text, fontsize=14, fontweight='bold', pad=30)
            
            plt.tight_layout()
            plt.savefig(output_file, format='svg', bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            plt.close(fig)
            
            logger.info(f"Rendered circular tree to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Circular rendering failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _style_tree_labels(self, ax, highlighted_species, label_colors):
        """Apply beautiful styling to tree labels"""
        for text in ax.texts:
            label = text.get_text()
            if not label or label.startswith('→'):
                # Target gene already styled
                if label.startswith('→'):
                    text.set_fontsize(11)
                    text.set_fontweight('bold')
                continue
            
            prefix = self._get_species_prefix(label)
            
            # Apply colors
            if highlighted_species and prefix in highlighted_species:
                if label_colors and prefix in label_colors:
                    text.set_color(label_colors[prefix])
                    text.set_fontweight('bold')
                    text.set_fontsize(10)
                else:
                    text.set_color('#000000')
                    text.set_fontsize(9)
            else:
                text.set_color('#000000')
                text.set_fontsize(9)
    
    def _highlight_target_gene(self, ax):
        """Add background highlight for target gene"""
        for text in ax.texts:
            if text.get_text().startswith('→'):
                # Get text position
                x, y = text.get_position()
                
                # Add yellow background
                bbox = text.get_window_extent(renderer=ax.figure.canvas.get_renderer())
                bbox_data = ax.transData.inverted().transform(bbox)
                
                rect = FancyBboxPatch(
                    (bbox_data[0][0] - 0.1, bbox_data[0][1] - 0.02),
                    bbox_data[1][0] - bbox_data[0][0] + 0.2,
                    bbox_data[1][1] - bbox_data[0][1] + 0.04,
                    boxstyle="round,pad=0.05",
                    facecolor='#FFFF99',
                    edgecolor='#FFCC00',
                    linewidth=1.5,
                    zorder=0,
                    transform=ax.transData
                )
                ax.add_patch(rect)
                break
    
    def _add_legend(self, ax, highlighted_species, label_colors):
        """Add beautiful legend for species colors"""
        legend_elements = []
        for species in highlighted_species:
            if species in label_colors:
                legend_elements.append(
                    Line2D([0], [0], marker='o', color='w',
                          markerfacecolor=label_colors[species],
                          markersize=10, label=species,
                          markeredgewidth=0)
                )
        
        if legend_elements:
            ax.legend(handles=legend_elements, loc='upper left',
                     bbox_to_anchor=(1.02, 1), frameon=True,
                     fontsize=10, title='Species', title_fontsize=11)
                
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
        # Store target gene for highlighting
        self.target_gene = target_gene
        
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
        self.target_gene = None
        
        return success
