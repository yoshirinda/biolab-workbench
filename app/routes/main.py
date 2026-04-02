"""
Main page routes for BioLab Workbench.
"""
from flask import Blueprint, render_template, current_app, request, redirect, url_for, jsonify
import config
try:
    from app.utils.tool_health import get_system_tool_health
except Exception:
    def get_system_tool_health(*_args, **_kwargs):
        return []

main_bp = Blueprint('main', __name__)


def _is_ara_blast_enabled() -> bool:
    return 'ara_blast.ara_blast_page' in current_app.view_functions


def _build_home_context():
    modules = [
        {
            'name': 'Sequence Management',
            'description': 'Import, view, edit and analyze sequences. Supports FASTA and GenBank formats.',
            'icon': 'bi-file-earmark-text',
            'endpoint': 'sequence.sequence_page',
            'color': 'primary'
        },
        {
            'name': 'BLAST Search',
            'description': 'Run BLAST searches against local databases. Supports blastn, blastp, blastx, and tblastn.',
            'icon': 'bi-search',
            'endpoint': 'blast.blast_page',
            'color': 'success'
        },
        {
            'name': 'Phylogenetic Pipeline',
            'description': 'Complete phylogenetic analysis pipeline: HMMer, MAFFT, ClipKIT, and IQ-Tree.',
            'icon': 'bi-diagram-3',
            'endpoint': 'phylo.phylo_page',
            'color': 'info'
        },
        {
            'name': 'Sequence Alignment',
            'description': 'Multiple sequence alignment with MAFFT, ClustalW, or MUSCLE. Visualize conservation.',
            'icon': 'bi-text-left',
            'endpoint': 'alignment.alignment_page',
            'color': 'warning'
        },
        {
            'name': 'UniProt Search',
            'description': 'Search and download sequences from UniProt. Filter by taxonomy and database type.',
            'icon': 'bi-cloud-download',
            'endpoint': 'uniprot.uniprot_page',
            'color': 'danger'
        },
        {
            'name': 'Tree Visualization',
            'description': 'Visualize phylogenetic trees with species coloring and gene highlighting.',
            'icon': 'bi-tree',
            'endpoint': 'tree.tree_page',
            'color': 'secondary'
        }
    ]
    if _is_ara_blast_enabled():
        modules.insert(2, {
            'name': 'Arabidopsis BLAST',
            'description': 'Specialized 2-OGD family hunter for Arabidopsis thaliana genome. Optimized one-click pipeline.',
            'icon': 'bi-flower1',
            'endpoint': 'ara_blast.ara_blast_page',
            'color': 'success'
        })
    quick_start_tracks = [
        {
            'title': 'Find Homologs Quickly',
            'summary': 'Upload or paste a query sequence, run BLAST, then extract matching FASTA.',
            'steps': [
                'Open Sequence to clean headers and verify sequence type.',
                'Run BLAST with Balanced preset as baseline.',
                'Apply identity + coverage filters, then export report/FASTA.'
            ],
            'target': 'blast.blast_page',
            'badge': 'Similarity'
        },
        {
            'title': 'Build a Publication Tree',
            'summary': 'Go from candidate sequences to a robust phylogeny with reproducible parameters.',
            'steps': [
                'Pipeline: clean FASTA -> HMM/BLAST filtering -> MSA -> ClipKIT -> IQ-TREE.',
                'Start with IQ-TREE Publication preset; raise bootstrap for final runs.',
                'Export snapshot JSON so collaborators can rerun with identical settings.'
            ],
            'target': 'phylo.phylo_page',
            'badge': 'Phylogeny'
        },
        {
            'title': 'Fetch and Curate Reference Sets',
            'summary': 'Collect reference proteins from UniProt and align before downstream analysis.',
            'steps': [
                'Use UniProt filters (taxonomy/review status) to avoid noisy hits.',
                'Align with MAFFT first, then inspect conservation/length outliers.',
                'Keep a minimal, high-confidence reference panel for iterative updates.'
            ],
            'target': 'uniprot.uniprot_page',
            'badge': 'Reference'
        }
    ]

    scientific_defaults = [
        {
            'tool': 'BLAST',
            'hint': 'For broad discovery: identity >= 30%, qcovs >= 50%, E-value <= 1e-5.'
        },
        {
            'tool': 'HMMER',
            'hint': 'Use GA threshold when available; otherwise start near E-value 1e-5 and tighten gradually.'
        },
        {
            'tool': 'IQ-TREE',
            'hint': 'Use >=1000 UFBoot for final inference and enable SH-aLRT when branch support is critical.'
        }
    ]

    system_info = {
        'base_dir': config.BASE_DIR,
        'databases_dir': config.DATABASES_DIR,
        'results_dir': config.RESULTS_DIR,
        'uploads_dir': config.UPLOADS_DIR,
        'conda_env': config.CONDA_ENV
    }

    return {
        'modules': modules,
        'quick_start_tracks': quick_start_tracks,
        'scientific_defaults': scientific_defaults,
        'system_info': system_info,
    }


@main_bp.route('/')
def index():
    """Render the home page."""
    host = request.host.lower()
    if host.startswith('ara.') and _is_ara_blast_enabled():
        return redirect(url_for('ara_blast.ara_blast_page'))

    context = _build_home_context()
    return render_template('index.html', **context)


@main_bp.route('/api/system-readiness')
def system_readiness():
    """Return runtime tool readiness without blocking initial page render."""
    tool_health = get_system_tool_health(testing_mode=current_app.config.get('TESTING', False))
    return jsonify({'success': True, 'tool_health': tool_health})
