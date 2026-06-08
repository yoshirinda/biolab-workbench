"""
Main page routes for BioLab Workbench.
"""
from flask import Blueprint, jsonify, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Render the home page."""
    modules = [
        {
            'name': 'Reference Miner',
            'description': 'Curate UniProt reference FASTA sets with reviewed status, taxonomy scope, metadata, and saved query provenance.',
            'icon': 'bi-cloud-download',
            'endpoint': 'uniprot.uniprot_page',
            'color': 'danger'
        },
        {
            'name': 'BLAST Workbench',
            'description': 'Build local BLAST databases, run parameterized searches, inspect TSV/alignment outputs, and extract hit sequences.',
            'icon': 'bi-search',
            'endpoint': 'blast.blast_page',
            'color': 'success'
        },
        {
            'name': 'Alignment Workbench',
            'description': 'Align selected FASTA sequences with MAFFT, ClustalW, or MUSCLE and export reproducible visualizations.',
            'icon': 'bi-text-left',
            'endpoint': 'alignment.alignment_page',
            'color': 'warning'
        },
        {
            'name': 'Tree / Clade Viewer',
            'description': 'Render target-centered clades with species highlighting, support labels, layout controls, and exportable SVGs.',
            'icon': 'bi-tree',
            'endpoint': 'tree.tree_page',
            'color': 'secondary'
        },
        {
            'name': 'Phylogenetic Pipeline',
            'description': 'Run the original HMMER → BLAST filter → length filter → MAFFT → ClipKIT → IQ-TREE workflow with saved intermediates.',
            'icon': 'bi-diagram-3',
            'endpoint': 'phylo.phylo_page',
            'color': 'info'
        }
    ]
    return render_template('index.html', modules=modules)


@main_bp.route('/health')
def health():
    return jsonify({'status': 'ok'})
