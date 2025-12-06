"""
Documentation routes for BioLab Workbench.
"""
from flask import Blueprint, render_template

docs_bp = Blueprint('docs', __name__)


@docs_bp.route('/')
def docs_index():
    """Render the documentation index page."""
    return render_template('docs/index.html')


@docs_bp.route('/blast')
def blast_docs():
    """Render BLAST documentation."""
    return render_template('docs/blast.html')


@docs_bp.route('/phylo')
def phylo_docs():
    """Render phylogenetic pipeline documentation."""
    return render_template('docs/phylo.html')


@docs_bp.route('/alignment')
def alignment_docs():
    """Render alignment documentation."""
    return render_template('docs/alignment.html')


@docs_bp.route('/tree')
def tree_docs():
    """Render tree visualization documentation."""
    return render_template('docs/tree.html')


@docs_bp.route('/uniprot')
def uniprot_docs():
    """Render UniProt documentation."""
    return render_template('docs/uniprot.html')
