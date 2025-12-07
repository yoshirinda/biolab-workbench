"""
BioLab Workbench Flask Application Factory
"""
from flask import Flask, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
import config
import logging


def create_app():
    """Create and configure the Flask application."""
    # Disable werkzeug request logging
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    app = Flask(__name__)

    # Handle reverse proxy headers for DevTunnel/port forwarding
    # This fixes URL generation issues when running behind a reverse proxy
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
        x_prefix=1
    )

    # Load configuration
    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    app.config['UPLOADS_DIR'] = config.UPLOADS_DIR
    app.config['RESULTS_DIR'] = config.RESULTS_DIR

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.sequence import sequence_bp
    from app.routes.blast import blast_bp
    from app.routes.phylo import phylo_bp
    from app.routes.alignment import alignment_bp
    from app.routes.uniprot import uniprot_bp
    from app.routes.tree import tree_bp
    from app.routes.docs import docs_bp
    from app.routes.pipeline import pipeline_bp
    from app.routes.database import database_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(sequence_bp, url_prefix='/sequence')
    app.register_blueprint(blast_bp, url_prefix='/blast')
    app.register_blueprint(phylo_bp, url_prefix='/phylo')
    app.register_blueprint(alignment_bp, url_prefix='/alignment')
    app.register_blueprint(uniprot_bp, url_prefix='/uniprot')
    app.register_blueprint(tree_bp, url_prefix='/tree')
    app.register_blueprint(docs_bp, url_prefix='/docs')
    app.register_blueprint(pipeline_bp, url_prefix='/pipeline')
    app.register_blueprint(database_bp, url_prefix='/database')

    # Return JSON for API-style requests to avoid HTML breaking fetch()
    @app.errorhandler(Exception)
    def json_error_handler(err):
        status = 500
        if isinstance(err, HTTPException):
            status = err.code or 500

        wants_json = (
            request.accept_mimetypes.best == 'application/json' or
            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
            request.path.startswith(('/phylo', '/blast', '/pipeline', '/alignment', '/tree'))
        )

        if wants_json:
            return jsonify({'success': False, 'error': str(err)}), status

        return err

    # Setup logging
    from app.utils.logger import setup_logging
    setup_logging(app)

    # Internationalization: inject translation helper and current translations
    try:
        from app.utils.i18n import get_translations_for, t

        @app.context_processor
        def inject_i18n():
            lang = config.DEFAULT_LANG if hasattr(config, 'DEFAULT_LANG') else None
            if not lang:
                lang = None
            translations = get_translations_for(lang or 'en')
            return {
                'i18n': translations,
                't': lambda k: t(k, lang)
            }
    except Exception:
        # If i18n helper or translations are not available, add safe fallbacks
        @app.context_processor
        def inject_i18n():
            return {'i18n': {}, 't': lambda k: k}

    return app
