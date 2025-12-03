"""
Main page routes for BioLab Workbench.
"""
from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Render the home page."""
    modules = [
        {
            'name': 'Sequence Management',
            'description': 'Import, view, edit and analyze sequences. Supports FASTA and GenBank formats.',
            'icon': 'bi-file-earmark-text',
            'url': '/sequence',
            'color': 'primary'
        },
        {
            'name': 'BLAST Search',
            'description': 'Run BLAST searches against local databases. Supports blastn, blastp, blastx, and tblastn.',
            'icon': 'bi-search',
            'url': '/blast',
            'color': 'success'
        },
        {
            'name': 'Phylogenetic Pipeline',
            'description': 'Complete phylogenetic analysis pipeline: HMMer, MAFFT, ClipKIT, and IQ-Tree.',
            'icon': 'bi-diagram-3',
            'url': '/phylo',
            'color': 'info'
        },
        {
            'name': 'Sequence Alignment',
            'description': 'Multiple sequence alignment with MAFFT, ClustalW, or MUSCLE. Visualize conservation.',
            'icon': 'bi-text-left',
            'url': '/alignment',
            'color': 'warning'
        },
        {
            'name': 'UniProt Search',
            'description': 'Search and download sequences from UniProt. Filter by taxonomy and database type.',
            'icon': 'bi-cloud-download',
            'url': '/uniprot',
            'color': 'danger'
        },
        {
            'name': 'Tree Visualization',
            'description': 'Visualize phylogenetic trees with species coloring and gene highlighting.',
            'icon': 'bi-tree',
            'url': '/tree',
            'color': 'secondary'
        }
    ]
    return render_template('index.html', modules=modules)
